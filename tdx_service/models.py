"""API 响应模型：pydantic v2 数据模型定义。"""
from typing import Any

from pydantic import BaseModel

from tdx_service.parser import DayRecord


class DailyBar(BaseModel):
    """日线行情：date 为 YYYY-MM-DD，开高低收单位为元，amount 为元，volume 为股。"""

    date: str
    open: float
    high: float
    low: float
    close: float
    amount: float
    volume: int

    @classmethod
    def from_record(cls, rec: DayRecord) -> "DailyBar":
        """由 DayRecord 转换：日期格式化为 YYYY-MM-DD，价格由分转元（/100）。"""
        d = str(rec.date)
        return cls(
            date=f"{d[:4]}-{d[4:6]}-{d[6:8]}",
            open=rec.open / 100,
            high=rec.high / 100,
            low=rec.low / 100,
            close=rec.close / 100,
            amount=rec.amount,
            volume=rec.volume,
        )


class SecurityInfo(BaseModel):
    """证券元信息：所属市场、代码、K 线条数与首末交易日期。"""

    market: str
    code: str
    bars: int
    first_date: str | None = None
    last_date: str | None = None


class SystemInfo(BaseModel):
    """系统信息：数据目录、各市场文件数、证券总数与全局数据日期范围。"""

    tdx_home: str
    markets: dict[str, int]
    total_securities: int
    data_from: str | None = None
    data_to: str | None = None
    cached_files: int = 0


class ApiResponse(BaseModel):
    """统一 API 响应包装：code/message/data 三要素。"""

    code: int = 0
    message: str = "ok"
    data: Any = None

    @classmethod
    def ok(cls, data: Any = None) -> "ApiResponse":
        """构造成功响应。"""
        return cls(code=0, message="ok", data=data)

    @classmethod
    def err(cls, code: int, message: str) -> "ApiResponse":
        """构造错误响应。"""
        return cls(code=code, message=message, data=None)
