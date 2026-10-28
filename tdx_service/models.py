"""API 响应模型：pydantic v2 数据模型定义。"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from tdx_service.parser import DayRecord

T = TypeVar("T")


class DailyBar(BaseModel):
    """日线行情：date 为 YYYY-MM-DD，开高低收单位为元，amount 为元，volume 为股。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2026-10-27", "open": 9.56, "high": 9.87,
            "low": 9.53, "close": 9.82, "amount": 789322240.0, "volume": 80753040,
        }
    })

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

    model_config = ConfigDict(json_schema_extra={
        "example": {"market": "sh", "code": "600000", "bars": 6414,
                    "first_date": "1999-11-10", "last_date": "2026-10-27"}
    })

    market: str
    code: str
    bars: int
    first_date: str | None = None
    last_date: str | None = None


class SystemInfo(BaseModel):
    """系统信息：数据目录、各市场文件数、证券总数与全局数据日期范围。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {"tdx_home": "D:\\new_tdx", "markets": {"sh": 5009, "sz": 4579, "bj": 357},
                    "total_securities": 9945, "data_from": "1990-12-19",
                    "data_to": "2026-10-27", "cached_files": 0}
    })

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


class ApiEnvelope(BaseModel, Generic[T]):
    """统一响应信封（泛型文档模型）：data 类型由各接口的 response_model 指定，输出结构与 ApiResponse 一致。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


class HealthData(BaseModel):
    """健康检查数据：服务状态与行情目录可用性。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {"status": "ok", "tdx_home": "/data", "vipdoc_exists": True}
    })

    status: str
    tdx_home: str
    vipdoc_exists: bool


class SecuritiesPage(BaseModel):
    """证券列表分页数据：当页元信息 + 总数。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [{"market": "sh", "code": "600000", "bars": 6414,
                       "first_date": "1999-11-10", "last_date": "2026-10-27"}],
            "total": 5009, "limit": 100, "offset": 0,
        }
    })

    items: list[SecurityInfo]
    total: int
    limit: int
    offset: int


class DailyKlinePage(BaseModel):
    """日线查询分页数据：当页日线 + 本页条数。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [{"date": "2026-10-27", "open": 9.56, "high": 9.87,
                       "low": 9.53, "close": 9.82, "amount": 789322240.0,
                       "volume": 80753040}],
            "count": 1,
        }
    })

    items: list[DailyBar]
    count: int
