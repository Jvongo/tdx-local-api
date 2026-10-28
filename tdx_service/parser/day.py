"""日线（.day）行情文件解析器：按 32 字节定长记录解包并过滤非法日期。"""

import logging
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tdx_service.errors import DataFileError
from tdx_service.parser.base import MarketFileReader

logger = logging.getLogger(__name__)


@dataclass
class DayRecord:
    """日线记录：date(YYYYMMDD)、开高低收（单位：分）、amount（元）、volume（股）。"""

    date: int
    open: int
    high: int
    low: int
    close: int
    amount: float
    volume: int


class TdxDayReader(MarketFileReader):
    """通达信日线文件读取器：解析 .day 二进制为按日期升序的 DayRecord 列表。"""

    DAY_STRUCT = struct.Struct("<IIIIIfII")
    RECORD_SIZE = 32
    MIN_VALID_DATE = 19900101
    MAX_VALID_DATE = 20361231

    @classmethod
    def _is_valid_date(cls, date: int) -> bool:
        """校验日期是否为 1990-01-01 ~ 2036-12-31 内的真实日历日期。"""
        if not (cls.MIN_VALID_DATE <= date <= cls.MAX_VALID_DATE):
            return False
        try:
            datetime.strptime(str(date), "%Y%m%d")
        except ValueError:
            return False
        return True

    def read_file(self, path: Path) -> list:
        """读取日线文件，返回按日期升序的 DayRecord 列表；文件不存在或读失败抛 DataFileError。"""
        path = Path(path)
        if not path.is_file():
            raise DataFileError(f"日线文件不存在: {path}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise DataFileError(f"日线文件读取失败: {path}, {exc}") from exc

        # 尾部不足 32 字节的残缺部分直接丢弃
        tail = len(data) % self.RECORD_SIZE
        if tail:
            logger.warning("日线文件 %s 尾部残缺 %d 字节，已丢弃", path, tail)
            data = data[: len(data) - tail]

        records = []
        invalid_count = 0
        for values in self.DAY_STRUCT.iter_unpack(data):
            date = values[0]
            if not self._is_valid_date(date):
                invalid_count += 1
                continue
            records.append(DayRecord(
                date=date, open=values[1], high=values[2], low=values[3],
                close=values[4], amount=values[5], volume=values[6],
            ))
        if invalid_count:
            logger.warning("日线文件 %s 跳过非法日期记录 %d 条", path, invalid_count)

        records.sort(key=lambda r: r.date)
        return records

    @classmethod
    def record_count(cls, path: Path) -> int:
        """按文件字节数返回日线记录条数（size//32），文件不存在返回 0。"""
        path = Path(path)
        if not path.is_file():
            return 0
        return path.stat().st_size // cls.RECORD_SIZE
