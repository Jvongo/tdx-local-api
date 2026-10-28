"""API 路由：健康检查、系统信息、证券列表/详情与日线行情接口（前缀 /api/v1）。"""

from fastapi import APIRouter, Depends, Query

from tdx_service.api.deps import get_repository
from tdx_service.errors import DataRootUnavailable
from tdx_service.models import ApiResponse
from tdx_service.repository import SecurityRepository
from tdx_service.services import MarketService

router = APIRouter(prefix="/api/v1", tags=["TDX本地行情"])


def _service(repo: SecurityRepository = Depends(get_repository)) -> MarketService:
    """按请求构造业务服务：仓库经依赖注入获取（可被测试用 Settings 覆盖）。"""
    return MarketService(repo)


@router.get("/health")
def health(service: MarketService = Depends(_service)):
    """健康检查：行情数据目录不可用时返回 503。"""
    info = service.health()
    if not info["vipdoc_exists"]:
        raise DataRootUnavailable(f"行情数据目录不存在: {info['tdx_home']}")
    return ApiResponse.ok(info)


@router.get("/system/info")
def system_info(service: MarketService = Depends(_service)):
    """系统信息：各市场证券数、总数与全局数据日期范围。"""
    return ApiResponse.ok(service.system_info())


@router.get("/securities")
def list_securities(
    market: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
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


@router.get("/securities/{code}")
def get_security(code: str, service: MarketService = Depends(_service)):
    """证券详情：代码不存在返回 404。"""
    return ApiResponse.ok(service.get_security_info(code))


@router.get("/kline/daily")
def daily_kline(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    service: MarketService = Depends(_service),
):
    """日线查询：code 必填，支持闭区间日期过滤与 limit/offset 分页。"""
    bars = service.get_daily_bars(
        code, start_date=start_date, end_date=end_date, limit=limit, offset=offset,
    )
    return ApiResponse.ok({"items": [bar.model_dump() for bar in bars], "count": len(bars)})


@router.get("/kline/daily/latest")
def latest_daily_kline(code: str, service: MarketService = Depends(_service)):
    """最新一根日线（末条记录）。"""
    return ApiResponse.ok(service.get_latest_bar(code))
