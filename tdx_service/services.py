"""业务服务层：封装 SecurityRepository，向 API 层提供统一业务编排接口。"""

from tdx_service.models import DailyBar, SecurityInfo, SystemInfo
from tdx_service.repository import SecurityRepository


class MarketService:
    """行情业务服务：健康检查、系统信息、证券列表/详情与日线查询的编排入口。"""

    def __init__(self, repo: SecurityRepository):
        self._repo = repo

    def health(self) -> dict:
        """健康检查：返回数据根目录及其存在状态（读取仓库内嵌配置）。"""
        settings = self._repo._settings  # 仓库构造时注入的配置
        return {
            "status": "ok",
            "tdx_home": settings.tdx_home,
            "vipdoc_exists": settings.vipdoc_dir().is_dir(),
        }

    def system_info(self) -> SystemInfo:
        """系统信息：各市场证券数、总数与全局数据日期范围。"""
        return self._repo.system_info()

    def list_securities(self, market: str | None = None, limit: int = 100,
                        offset: int = 0) -> tuple[list[SecurityInfo], int]:
        """分页列出证券，返回 (当页元信息列表, 过滤后总数)。"""
        return self._repo.list_securities(market=market, limit=limit, offset=offset)

    def get_security_info(self, code: str) -> SecurityInfo:
        """证券元信息：K 线条数与首末交易日期。"""
        return self._repo.get_security_info(code)

    def get_daily_bars(self, code: str, start_date: str | None = None,
                       end_date: str | None = None, limit: int = 500,
                       offset: int = 0) -> list[DailyBar]:
        """查询日线：DayRecord 经 DailyBar.from_record 转换为 API 输出模型。"""
        records = self._repo.get_daily_bars(
            code, start_date=start_date, end_date=end_date, limit=limit, offset=offset,
        )
        return [DailyBar.from_record(rec) for rec in records]

    def get_latest_bar(self, code: str) -> DailyBar:
        """最新一根日线（末条记录）。"""
        return DailyBar.from_record(self._repo.get_latest_bar(code))
