"""SecurityRepository 数据仓库测试（TDD 红灯阶段：先于实现编写）。"""
import struct

import pytest

from tdx_service.config import Settings
from tdx_service.errors import NoDataInRange, ParamError, SecurityNotFound
from tdx_service.parser import TdxDayReader
from tdx_service.repository import SecurityEntry, SecurityRepository

# 日线记录结构：date, open, high, low, close(单位分), amount(float32 元), volume(股), reserved
DAY_STRUCT = struct.Struct("<IIIIIfII")
RECORD_SIZE = DAY_STRUCT.size  # 32


def make_record(date=20240102, open=1000, high=1100, low=900, close=1050,
                amount=1234.5, volume=10000, reserved=0):
    """构造单条日线记录元组，默认字段可覆盖。"""
    return (date, open, high, low, close, amount, volume, reserved)


def make_day_bytes(records):
    """把日线记录元组列表打包为 .day 二进制。"""
    return b"".join(DAY_STRUCT.pack(*rec) for rec in records)


def build_vipdoc(root):
    """在 root/vipdoc 下构造 sh/sz/bj 三市场假数据树。"""
    (root / "vipdoc" / "sh" / "lday").mkdir(parents=True)
    (root / "vipdoc" / "sz" / "lday").mkdir(parents=True)
    (root / "vipdoc" / "bj" / "lday").mkdir(parents=True)
    # 沪市 5 条：20240102-20240108
    (root / "vipdoc" / "sh" / "lday" / "sh600000.day").write_bytes(make_day_bytes([
        make_record(date=d, close=d % 100)
        for d in (20240102, 20240103, 20240104, 20240105, 20240108)
    ]))
    # 深市 3 条：20240106-20240108
    (root / "vipdoc" / "sz" / "lday" / "sz000001.day").write_bytes(make_day_bytes([
        make_record(date=d, close=d % 100)
        for d in (20240106, 20240107, 20240108)
    ]))
    # 京市 2 条：20240109-20240110
    (root / "vipdoc" / "bj" / "lday" / "bj430047.day").write_bytes(make_day_bytes([
        make_record(date=d, close=d % 100)
        for d in (20240109, 20240110)
    ]))


@pytest.fixture
def repo(tmp_path):
    """基于假数据树构造 SecurityRepository。"""
    build_vipdoc(tmp_path)
    return SecurityRepository(Settings(tdx_home=str(tmp_path)))


class TestResolve:
    """resolve 证券代码定位测试。"""

    def test_resolve_variants(self, repo):
        """resolve("600000")/("sh600000")→(sh,600000)，("SZ000001")→(sz,000001) 大小写不敏感。"""
        assert (repo.resolve("600000").market, repo.resolve("600000").code) == ("sh", "600000")
        assert (repo.resolve("sh600000").market, repo.resolve("sh600000").code) == ("sh", "600000")
        entry = repo.resolve("SZ000001")
        assert (entry.market, entry.code) == ("sz", "000001")
        assert isinstance(entry, SecurityEntry)
        assert entry.path.name == "sz000001.day"

    def test_resolve_not_found(self, repo):
        """resolve("999999")→抛 SecurityNotFound。"""
        with pytest.raises(SecurityNotFound):
            repo.resolve("999999")

    def test_resolve_invalid_code(self, repo):
        """非法代码格式 → 抛 ParamError。"""
        with pytest.raises(ParamError):
            repo.resolve("abc123")


class TestGetDailyBars:
    """get_daily_bars 查询测试。"""

    def test_full_range(self, repo):
        """全量返回 5 条。"""
        bars = repo.get_daily_bars("600000")
        assert [b.date for b in bars] == [20240102, 20240103, 20240104, 20240105, 20240108]

    def test_date_subrange(self, repo):
        """日期子区间（start=20240104）只返回区间内。"""
        bars = repo.get_daily_bars("600000", start_date="2024-01-04")
        assert [b.date for b in bars] == [20240104, 20240105, 20240108]

    def test_date_subrange_mixed_formats(self, repo):
        """YYYYMMDD 与 YYYY-MM-DD 混用也支持，闭区间。"""
        bars = repo.get_daily_bars("600000", start_date="20240104", end_date="2024-01-05")
        assert [b.date for b in bars] == [20240104, 20240105]

    def test_limit_offset(self, repo):
        """limit/offset 分页。"""
        bars = repo.get_daily_bars("600000", limit=2, offset=1)
        assert [b.date for b in bars] == [20240103, 20240104]

    def test_no_data_in_range(self, repo):
        """区间无数据抛 NoDataInRange。"""
        with pytest.raises(NoDataInRange):
            repo.get_daily_bars("600000", start_date="2024-02-01")

    def test_invalid_date_param(self, repo):
        """非法日期与 start>end 抛 ParamError。"""
        with pytest.raises(ParamError):
            repo.get_daily_bars("600000", start_date="2024-13-01")
        with pytest.raises(ParamError):
            repo.get_daily_bars("600000", start_date="2024-01-08", end_date="2024-01-02")

    def test_get_latest_bar(self, repo):
        """get_latest_bar 取最后一条，无数据抛 SecurityNotFound。"""
        assert repo.get_latest_bar("600000").date == 20240108


class TestGetSecurityInfo:
    """get_security_info 元信息测试。"""

    def test_security_info(self, repo):
        """bars/first/last/market/code 正确。"""
        info = repo.get_security_info("600000")
        assert info.bars == 5
        assert info.first_date == "2024-01-02"
        assert info.last_date == "2024-01-08"
        assert info.market == "sh"
        assert info.code == "600000"


class TestListSecurities:
    """list_securities 列表测试。"""

    def test_market_filter(self, repo):
        """market="sz" 只返回 sz，total=1。"""
        infos, total = repo.list_securities(market="sz")
        assert total == 1
        assert [i.code for i in infos] == ["000001"]

    def test_pagination(self, repo):
        """limit/offset 分页正确，total=3。"""
        infos, total = repo.list_securities(limit=2, offset=1)
        assert total == 3
        assert [i.code for i in infos] == ["000001", "430047"]

    def test_invalid_market(self, repo):
        """market 非 sh/sz/bj → ParamError。"""
        with pytest.raises(ParamError):
            repo.list_securities(market="hk")


class TestSystemInfo:
    """system_info 测试。"""

    def test_system_info(self, repo):
        """markets 计数、总数与全局 data_from/to。"""
        info = repo.system_info()
        assert info.markets == {"sh": 1, "sz": 1, "bj": 1}
        assert info.total_securities == 3
        assert info.data_from == "2024-01-02"
        assert info.data_to == "2024-01-10"

    def test_system_info_ttl_cache(self, repo, monkeypatch):
        """TTL 内重复 system_info 不重复读文件边缘（全量读取约秒级，必须缓存）。"""
        calls = []
        original = SecurityRepository._read_edge_records

        def counting(path):
            calls.append(path)
            return original(path)

        monkeypatch.setattr(SecurityRepository, "_read_edge_records", staticmethod(counting))

        repo.system_info()
        calls_after_first = len(calls)
        repo.system_info()

        assert calls_after_first == 3  # 首次数 3 个文件
        assert len(calls) == calls_after_first, "system_info 未按 TTL 缓存，每次全量重读"

    def test_system_info_single_flight(self, repo, monkeypatch):
        """TTL 过期后多线程并发只触发一次全量重算（单飞，防缓存击穿雪崩）。"""
        import threading
        import time as _time

        calls = []
        original = SecurityRepository._read_edge_records

        def slow_read(path):
            calls.append(path)
            _time.sleep(0.05)
            return original(path)

        monkeypatch.setattr(SecurityRepository, "_read_edge_records", staticmethod(slow_read))

        repo.system_info()
        calls.clear()
        # 手工将缓存时间戳置为 31 秒前，模拟 TTL 过期
        ts, info = repo._system_info_cache
        repo._system_info_cache = (ts - 31, info)

        barrier = threading.Barrier(2)

        def worker():
            barrier.wait()
            repo.system_info()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(calls) == 3, f"全量重算被触发 {len(calls) // 3} 次，发生缓存击穿"


class TestEdgeRecordsRobustness:
    """_read_edge_records 边界文件健壮性测试。"""

    def test_tiny_file_returns_none_not_raise(self, tmp_path):
        """1-31 字节残缺文件：返回 (None, None) 而非抛 DataFileError（与解析器截断行为一致）。"""
        repo = SecurityRepository(Settings(tdx_home=str(tmp_path)))
        f = tmp_path / "vipdoc" / "sh" / "lday" / "sh600000.day"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"\x01" * 10)  # 不足一条完整记录的残缺文件

        first, last = repo._read_edge_records(f)

        assert first is None
        assert last is None

    def test_empty_file_returns_none(self, tmp_path):
        """空文件：返回 (None, None)。"""
        repo = SecurityRepository(Settings(tdx_home=str(tmp_path)))
        f = tmp_path / "sh600000.day"
        f.write_bytes(b"")

        assert repo._read_edge_records(f) == (None, None)


class TestCacheIntegration:
    """仓库与 BarCache 的集成测试。"""

    def test_second_query_uses_cache(self, repo, monkeypatch):
        """连续两次 get_daily_bars，第二次走缓存（read_file 只调用一次）。"""
        calls = []
        original = TdxDayReader.read_file

        def counting_read_file(self, path):
            calls.append(path)
            return original(self, path)

        monkeypatch.setattr(TdxDayReader, "read_file", counting_read_file)

        repo.get_daily_bars("600000")
        repo.get_daily_bars("600000")

        assert len(calls) == 1
