"""日线解析器 TdxDayReader 的单元测试（TDD 红灯阶段：先于实现编写）。"""
import struct

import pytest

from tdx_service.errors import DataFileError
from tdx_service.parser import DayRecord, TdxDayReader

# 日线记录结构：date, open, high, low, close(单位分), amount(float32 元), volume(股), reserved
DAY_STRUCT = struct.Struct("<IIIIIfII")
RECORD_SIZE = DAY_STRUCT.size  # 32


def make_day_bytes(records):
    """把 (date, open, high, low, close, amount, volume, reserved) 元组列表打包为 .day 二进制。"""
    return b"".join(DAY_STRUCT.pack(*rec) for rec in records)


def make_record(date=20240102, open=1000, high=1100, low=900, close=1050,
                amount=1234.5, volume=10000, reserved=0):
    """构造单条日线记录元组，默认字段可覆盖。"""
    return (date, open, high, low, close, amount, volume, reserved)


class TestTdxDayReader:
    """TdxDayReader 读取与过滤逻辑测试。"""

    def test_read_normal_file(self, tmp_path):
        """正常解析：各字段值与输入一致，价格单位为分、金额为元。"""
        recs = [
            make_record(date=20240102, open=1000, high=1100, low=900, close=1050,
                        amount=1234.5, volume=10000, reserved=7),
        ]
        f = tmp_path / "sh600000.day"
        f.write_bytes(make_day_bytes(recs))

        result = TdxDayReader().read_file(f)

        assert len(result) == 1
        r = result[0]
        assert isinstance(r, DayRecord)
        assert r.date == 20240102
        assert r.open == 1000
        assert r.high == 1100
        assert r.low == 900
        assert r.close == 1050
        assert r.amount == pytest.approx(1234.5)
        assert r.volume == 10000

    def test_multiple_records_sorted_by_date(self, tmp_path):
        """多条记录乱序写入，解析后按日期升序返回。"""
        recs = [
            make_record(date=20240104, close=400),
            make_record(date=20240102, close=200),
            make_record(date=20240103, close=300),
        ]
        f = tmp_path / "sh600000.day"
        f.write_bytes(make_day_bytes(recs))

        result = TdxDayReader().read_file(f)

        assert [r.date for r in result] == [20240102, 20240103, 20240104]
        assert [r.close for r in result] == [200, 300, 400]

    def test_truncated_tail_discarded(self, tmp_path):
        """残缺尾部：总长度非 32 整数倍时丢弃尾部，返回前 2 条且不抛异常。"""
        data = make_day_bytes([
            make_record(date=20240102),
            make_record(date=20240103),
        ])
        f = tmp_path / "sh600000.day"
        f.write_bytes(data + b"\x01" * 10)  # 32*2+10 字节

        result = TdxDayReader().read_file(f)

        assert len(result) == 2
        assert [r.date for r in result] == [20240102, 20240103]

    def test_invalid_dates_filtered(self, tmp_path):
        """非法日期过滤：0 与超上限/非法月份跳过，边界合法值保留。"""
        recs = [
            make_record(date=0, close=1),            # date=0 应跳过
            make_record(date=19900101, close=2),     # 合法下限边界，保留
            make_record(date=20370101, close=3),     # 超上限，跳过
            make_record(date=20261301, close=4),     # 月份 13，跳过
            make_record(date=20361231, close=5),     # 合法上限边界，保留
        ]
        f = tmp_path / "sh600000.day"
        f.write_bytes(make_day_bytes(recs))

        result = TdxDayReader().read_file(f)

        assert [r.date for r in result] == [19900101, 20361231]

    def test_empty_file_returns_empty_list(self, tmp_path):
        """空文件返回空列表。"""
        f = tmp_path / "sh600000.day"
        f.write_bytes(b"")

        result = TdxDayReader().read_file(f)

        assert result == []

    def test_missing_file_raises_data_file_error(self, tmp_path):
        """文件不存在时抛 DataFileError。"""
        f = tmp_path / "not_exist.day"

        with pytest.raises(DataFileError):
            TdxDayReader().read_file(f)

    def test_record_count(self, tmp_path):
        """record_count 返回 size//32，文件不存在返回 0。"""
        f = tmp_path / "sh600000.day"
        f.write_bytes(make_day_bytes([
            make_record(date=20240102),
            make_record(date=20240103),
        ]) + b"\x00" * 10)

        assert TdxDayReader.record_count(f) == 2
        assert TdxDayReader.record_count(tmp_path / "not_exist.day") == 0
