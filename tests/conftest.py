"""tests 公共辅助：构造假 .day 数据与 API 测试客户端工厂。"""
import struct

import pytest
from fastapi.testclient import TestClient

from tdx_service.config import Settings
from tdx_service.main import create_app

# 日线记录结构：date, open, high, low, close(单位分), amount(float32 元), volume(股), reserved
DAY_STRUCT = struct.Struct("<IIIIIfII")


def make_record(date, open=1000, high=1100, low=900, close=1050,
                amount=1234.5, volume=10000, reserved=0):
    """构造单条日线记录元组，默认字段可覆盖。"""
    return (date, open, high, low, close, amount, volume, reserved)


def make_day_bytes(records):
    """把日线记录元组列表打包为 .day 二进制。"""
    return b"".join(DAY_STRUCT.pack(*rec) for rec in records)


def build_fake_tdx(tmp_path, spec):
    """按 spec 在 tmp_path/vipdoc 下写假 .day 文件：spec={"sh": {"600000": [records...]}}。"""
    for market, files in spec.items():
        lday = tmp_path / "vipdoc" / market / "lday"
        lday.mkdir(parents=True, exist_ok=True)
        for code, records in files.items():
            (lday / f"{market}{code}.day").write_bytes(make_day_bytes(records))
    return tmp_path


@pytest.fixture
def make_client(tmp_path):
    """按 spec 造假数据并返回 TestClient：create_app 显式接收 Settings，不读全局环境变量。"""
    def _make(spec):
        build_fake_tdx(tmp_path, spec)
        app = create_app(Settings(tdx_home=str(tmp_path)))
        return TestClient(app)
    return _make
