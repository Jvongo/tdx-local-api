"""数据仓库：扫描 vipdoc 目录，提供证券定位、日线查询、列表与系统信息。"""
import os
import re
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from pathlib import Path

from tdx_service.cache import BarCache
from tdx_service.config import Settings
from tdx_service.errors import DataFileError, NoDataInRange, ParamError, SecurityNotFound
from tdx_service.models import SecurityInfo, SystemInfo
from tdx_service.parser import DayRecord, TdxDayReader

# 合法证券代码：可选市场前缀（SH/SZ/BJ）+ 6 位数字
CODE_PATTERN = re.compile(r"^(SH|SZ|BJ)?\d{6}$")


@dataclass
class SecurityEntry:
    """证券定位结果：市场、代码与日线文件路径。"""

    market: str
    code: str
    path: Path


def _fmt_date(date: int) -> str:
    """YYYYMMDD int 格式化为 YYYY-MM-DD。"""
    s = str(date)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _parse_date(value: str) -> int:
    """解析 YYYY-MM-DD 或 YYYYMMDD 日期字符串为 YYYYMMDD int，非法抛 ParamError。"""
    s = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        s = s.replace("-", "")
    if not re.fullmatch(r"\d{8}", s):
        raise ParamError(f"日期格式非法: {value}，应为 YYYY-MM-DD 或 YYYYMMDD")
    try:
        time.strptime(s, "%Y%m%d")
    except ValueError:
        raise ParamError(f"日期不存在: {value}") from None
    return int(s)


class SecurityRepository:
    """行情数据仓库：证券定位、日线查询、列表与系统信息，内置文件扫描 TTL 缓存。"""

    def __init__(self, settings: Settings, cache: BarCache | None = None):
        self._settings = settings
        self._cache = cache if cache is not None else BarCache(maxsize=settings.cache_size)
        self._entries_cache = None  # (时间戳, entries)

    def _entries(self) -> list[SecurityEntry]:
        """扫描 vipdoc/{sh,sz,bj}/lday/*.day，结果按 settings.list_ttl 秒 TTL 缓存。"""
        now = time.monotonic()
        if self._entries_cache is not None:
            ts, entries = self._entries_cache
            if now - ts < self._settings.list_ttl:
                return entries
        entries = []
        for market in self._settings.markets():
            lday_dir = self._settings.vipdoc_dir() / market / "lday"
            if not lday_dir.is_dir():
                continue
            for path in sorted(lday_dir.glob("*.day")):
                name = path.stem  # 形如 sh600000
                # 去掉文件名中的市场前缀，得到 6 位代码
                code = name[len(market):] if name.upper().startswith(market.upper()) else name
                entries.append(SecurityEntry(market=market, code=code, path=path))
        self._entries_cache = (now, entries)
        return entries

    def resolve(self, code: str) -> SecurityEntry:
        """定位证券：strip+upper 后正则校验，带前缀按前缀定位，无前缀按 sh→sz→bj 探测文件。"""
        normalized = code.strip().upper()
        if not CODE_PATTERN.match(normalized):
            raise ParamError(f"证券代码格式非法: {code}")
        if len(normalized) == 8:  # 带市场前缀，如 SH600000
            market, digits = normalized[:2].lower(), normalized[2:]
            path = self._settings.vipdoc_dir() / market / "lday" / f"{market}{digits}.day"
            if not path.is_file():
                raise SecurityNotFound(f"证券不存在: {code}")
            return SecurityEntry(market=market, code=digits, path=path)
        # 无前缀：按 sh→sz→bj 顺序探测文件存在性
        for market in self._settings.markets():
            path = self._settings.vipdoc_dir() / market / "lday" / f"{market}{normalized}.day"
            if path.is_file():
                return SecurityEntry(market=market, code=normalized, path=path)
        raise SecurityNotFound(f"证券不存在: {code}")

    def _load_bars(self, entry: SecurityEntry) -> list:
        """加载日线记录：BarCache 命中直接用，否则 TdxDayReader 读取并写入缓存。"""
        cached = self._cache.get(entry.path)
        if cached is not None:
            return cached
        records = TdxDayReader().read_file(entry.path)
        self._cache.put(entry.path, records)
        return records

    def get_daily_bars(self, code: str, start_date: str | None = None,
                       end_date: str | None = None, limit: int = 500, offset: int = 0) -> list:
        """查询日线：日期解析为 YYYYMMDD int，bisect 定位闭区间 [start,end]，再 offset/limit 切片。"""
        start = _parse_date(start_date) if start_date else None
        end = _parse_date(end_date) if end_date else None
        if start is not None and end is not None and start > end:
            raise ParamError(f"起始日期晚于结束日期: {start_date} ~ {end_date}")
        records = self._load_bars(self.resolve(code))
        dates = [r.date for r in records]
        lo = bisect_left(dates, start) if start is not None else 0
        hi = bisect_right(dates, end) if end is not None else len(dates)
        bars = records[lo:hi][offset:offset + limit]
        if not bars:
            raise NoDataInRange(f"日期范围内无数据: {code}")
        return bars

    def get_latest_bar(self, code: str) -> DayRecord:
        """取最新一条日线记录，无数据抛 SecurityNotFound。"""
        records = self._load_bars(self.resolve(code))
        if not records:
            raise SecurityNotFound(f"证券无日线数据: {code}")
        return records[-1]

    @staticmethod
    def _read_edge_records(path: Path) -> tuple[DayRecord | None, DayRecord | None]:
        """仅读文件首末各 32 字节解析首末记录，日期非法或空文件对应返回 None。"""
        try:
            with open(path, "rb") as fh:
                head = fh.read(TdxDayReader.RECORD_SIZE)
                if not head:
                    return None, None
                fh.seek(-TdxDayReader.RECORD_SIZE, os.SEEK_END)
                tail = fh.read(TdxDayReader.RECORD_SIZE)
        except OSError as exc:
            raise DataFileError(f"日线文件读取失败: {path}, {exc}") from exc
        result = []
        for chunk in (head, tail):
            if len(chunk) < TdxDayReader.RECORD_SIZE:
                result.append(None)
                continue
            values = TdxDayReader.DAY_STRUCT.unpack(chunk)
            if TdxDayReader._is_valid_date(values[0]):
                result.append(DayRecord(
                    date=values[0], open=values[1], high=values[2], low=values[3],
                    close=values[4], amount=values[5], volume=values[6],
                ))
            else:
                result.append(None)
        return result[0], result[1]

    def _entry_info(self, entry: SecurityEntry) -> SecurityInfo:
        """由定位结果构造 SecurityInfo：bars 与首末日期仅读文件两端字节。"""
        first, last = self._read_edge_records(entry.path)
        return SecurityInfo(
            market=entry.market,
            code=entry.code,
            bars=TdxDayReader.record_count(entry.path),
            first_date=_fmt_date(first.date) if first else None,
            last_date=_fmt_date(last.date) if last else None,
        )

    def get_security_info(self, code: str) -> SecurityInfo:
        """证券元信息：resolve + 文件首末记录（空文件时 first/last 为 None、bars=0）。"""
        return self._entry_info(self.resolve(code))

    def list_securities(self, market: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[SecurityInfo], int]:
        """分页列出证券：market 须为 sh/sz/bj，仅对当页条目计算 meta，total 为过滤后总数。"""
        if market is not None:
            market = market.strip().lower()
            if market not in self._settings.markets():
                raise ParamError(f"市场代码非法: {market}，应为 sh/sz/bj 之一")
        entries = self._entries()
        if market is not None:
            entries = [e for e in entries if e.market == market]
        total = len(entries)
        infos = [self._entry_info(e) for e in entries[offset:offset + limit]]
        return infos, total

    def system_info(self) -> SystemInfo:
        """系统信息：各市场文件数、证券总数、全局 data_from/to 与缓存文件数。"""
        entries = self._entries()
        markets = {m: 0 for m in self._settings.markets()}
        data_from = None
        data_to = None
        for entry in entries:
            markets[entry.market] += 1
            first, last = self._read_edge_records(entry.path)
            if first is not None:
                data_from = first.date if data_from is None else min(data_from, first.date)
            if last is not None:
                data_to = last.date if data_to is None else max(data_to, last.date)
        return SystemInfo(
            tdx_home=self._settings.tdx_home,
            markets=markets,
            total_securities=len(entries),
            data_from=_fmt_date(data_from) if data_from is not None else None,
            data_to=_fmt_date(data_to) if data_to is not None else None,
            cached_files=len(self._cache),
        )
