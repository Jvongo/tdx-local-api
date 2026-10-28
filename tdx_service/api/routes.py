"""API 路由：健康检查、系统信息、证券列表/详情与日线行情接口（前缀 /api/v1）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from tdx_service.api.deps import get_repository
from tdx_service.errors import DataRootUnavailable
from tdx_service.models import (
    ApiEnvelope,
    ApiResponse,
    DailyBar,
    DailyKlinePage,
    HealthData,
    SecuritiesPage,
    SecurityInfo,
    SystemInfo,
)
from tdx_service.repository import SecurityRepository
from tdx_service.services import MarketService

router = APIRouter(prefix="/api/v1", tags=["TDX本地行情"])

# 可复用的错误响应文档（Swagger 展示用）
_RESP_400 = {"description": "参数校验失败（code=40001）：代码/日期/分页参数不合法"}
_RESP_404 = {"description": "证券不存在或无数据（code=40401）"}
_RESP_404_BOTH = {"description": "证券不存在（code=40401）或日期范围内无数据（code=40402）"}
_RESP_500 = {"description": "数据文件解析失败（code=50001）"}
_RESP_503 = {"description": "行情数据根目录不可用（code=50301）"}


def _service(repo: SecurityRepository = Depends(get_repository)) -> MarketService:
    """按请求构造业务服务：仓库经依赖注入获取（可被测试用 Settings 覆盖）。"""
    return MarketService(repo)


@router.get(
    "/health",
    tags=["系统"],
    summary="健康检查",
    description="探测服务与行情数据目录状态。`vipdoc` 目录不可用时返回 HTTP 503（code=50301）。",
    response_description="服务状态与数据目录信息",
    responses={503: _RESP_503},
    response_model=ApiEnvelope[HealthData],
)
def health(service: MarketService = Depends(_service)):
    """健康检查：行情数据目录不可用时返回 503。"""
    info = service.health()
    if not info["vipdoc_exists"]:
        raise DataRootUnavailable(f"行情数据目录不存在: {info['tdx_home']}")
    return ApiResponse.ok(info)


@router.get(
    "/system/info",
    tags=["系统"],
    summary="系统与数据概况",
    description=(
        "返回各市场证券数量、总数、全局数据起止日期与当前缓存文件数。"
        "首次调用需全量扫描约万级文件（约 5 秒），结果按 `TDX_LIST_TTL`（默认 30 秒）缓存，"
        "TTL 内重复查询为毫秒级。"
    ),
    response_description="数据目录、市场分布、日期范围与缓存状态",
    responses={500: _RESP_500},
    response_model=ApiEnvelope[SystemInfo],
)
def system_info(service: MarketService = Depends(_service)):
    """系统信息：各市场证券数、总数与全局数据日期范围。"""
    return ApiResponse.ok(service.system_info())


@router.get(
    "/securities",
    tags=["证券"],
    summary="证券列表",
    description=(
        "分页列出全部有日线数据的证券（market 过滤 sh/sz/bj），"
        "每条含 K 线条数与首末交易日期。"
    ),
    response_description="证券元信息分页结果（items + total）",
    responses={400: _RESP_400, 500: _RESP_500},
    response_model=ApiEnvelope[SecuritiesPage],
)
def list_securities(
    market: Annotated[
        str | None,
        Query(description="市场过滤：sh=沪市 / sz=深市 / bj=北交所，不传返回全部", examples=["sh"]),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="每页条数（1-1000）", examples=[100]),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0, description="分页偏移量，从 0 开始", examples=[0]),
    ] = 0,
    service: MarketService = Depends(_service),
):
    """证券列表：market 过滤（sh/sz/bj）+ limit/offset 分页。"""
    infos, total = service.list_securities(market=market, limit=limit, offset=offset)
    return ApiResponse.ok({
        "items": [info.model_dump() for info in infos],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get(
    "/securities/{code}",
    tags=["证券"],
    summary="证券详情",
    description=(
        "查询单只证券的元信息（市场、代码、K 线条数、首末交易日期）。"
        "`code` 支持 `600000` 或 `sh600000` 形式；无市场前缀时按 sh → sz → bj 顺序定位，"
        "均不存在返回 404（code=40401）。"
    ),
    response_description="证券元信息",
    responses={400: _RESP_400, 404: _RESP_404, 500: _RESP_500},
    response_model=ApiEnvelope[SecurityInfo],
)
def get_security(
    code: Annotated[
        str,
        Path(description="证券代码，6 位数字，可带 sh/sz/bj 前缀", examples=["600000", "sh600000"]),
    ],
    service: MarketService = Depends(_service),
):
    """证券详情：代码不存在返回 404。"""
    return ApiResponse.ok(service.get_security_info(code))


@router.get(
    "/kline/daily",
    tags=["日线行情"],
    summary="历史日线查询",
    description=(
        "按证券代码查询历史日线（不复权），支持起止日期闭区间过滤与分页。\n\n"
        "- `code` 必填，支持 `600000` 或 `sh600000` 形式\n"
        "- `start_date`/`end_date` 为闭区间，支持 `YYYY-MM-DD` 或 `YYYYMMDD`；缺省时不限\n"
        "- 价格单位为元，成交量单位为股，成交额为元（float32 精度）\n"
        "- 区间内无数据返回 404（code=40402）"
    ),
    response_description="日线行情分页结果（items + count）",
    responses={400: _RESP_400, 404: _RESP_404_BOTH, 500: _RESP_500},
    response_model=ApiEnvelope[DailyKlinePage],
)
def daily_kline(
    code: Annotated[
        str,
        Query(description="证券代码，6 位数字，可带 sh/sz/bj 前缀", examples=["600000"]),
    ],
    start_date: Annotated[
        str | None,
        Query(description="起始日期（含），YYYY-MM-DD 或 YYYYMMDD", examples=["2026-10-01"]),
    ] = None,
    end_date: Annotated[
        str | None,
        Query(description="结束日期（含），YYYY-MM-DD 或 YYYYMMDD", examples=["2026-10-27"]),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=5000, description="每页条数（1-5000）", examples=[500]),
    ] = 500,
    offset: Annotated[
        int,
        Query(ge=0, description="分页偏移量，从 0 开始", examples=[0]),
    ] = 0,
    service: MarketService = Depends(_service),
):
    """日线查询：code 必填，支持闭区间日期过滤与 limit/offset 分页。"""
    bars = service.get_daily_bars(
        code, start_date=start_date, end_date=end_date, limit=limit, offset=offset,
    )
    return ApiResponse.ok({"items": [bar.model_dump() for bar in bars], "count": len(bars)})


@router.get(
    "/kline/daily/latest",
    tags=["日线行情"],
    summary="最新一根日线",
    description="返回该证券最近一个交易日的日线记录（文件末条，O(1) 读取）。",
    response_description="最新一根日线行情",
    responses={400: _RESP_400, 404: _RESP_404, 500: _RESP_500},
    response_model=ApiEnvelope[DailyBar],
)
def latest_daily_kline(
    code: Annotated[
        str,
        Query(description="证券代码，6 位数字，可带 sh/sz/bj 前缀", examples=["sz000001"]),
    ],
    service: MarketService = Depends(_service),
):
    """最新一根日线（末条记录）。"""
    return ApiResponse.ok(service.get_latest_bar(code))
