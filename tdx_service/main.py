"""FastAPI 应用工厂：注册全局异常处理器、挂载路由，并提供模块级 app 实例。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from tdx_service import __version__
from tdx_service.api.deps import get_repository, get_settings
from tdx_service.api.routes import router
from tdx_service.config import Settings
from tdx_service.errors import AppError
from tdx_service.models import ApiResponse
from tdx_service.repository import SecurityRepository

logger = logging.getLogger(__name__)

# Swagger 文档分组标签：名称 + 中文说明
OPENAPI_TAGS = [
    {"name": "系统", "description": "健康检查与数据概况"},
    {"name": "证券", "description": "证券列表与详情查询"},
    {"name": "日线行情", "description": "历史日线与最新一根日线查询"},
]

# OpenAPI 描述：展示在 Swagger 文档页顶部的数据来源、单位与错误码说明
API_DESCRIPTION = """纯本地解析通达信行情文件的 HTTP API 服务，**不访问任何在线行情服务**。

## 数据来源

- 通达信安装目录下 `vipdoc/{sh,sz,bj}/lday/*.day` 二进制日线文件（沪/深/京），只读解析
- 数据目录由环境变量 `TDX_HOME` 指定（容器内部署默认为 `/data`，见 docker-compose 挂载）

## 单位与口径

| 项目 | 口径 |
|---|---|
| 价格 | **元**（文件内为价格×100 的整数，接口已 /100 转换） |
| 成交量 | **股**（通达信界面显示为"手"，1 手 = 100 股） |
| 成交额 | **元**，源数据为 float32，大额有量化误差（数十亿约 ±256 元） |
| 复权 | **不复权**（本地文件不含除权信息） |
| 日期 | `YYYY-MM-DD`（入参同时接受 `YYYYMMDD`） |

## 统一响应信封

```json
{ "code": 0, "message": "ok", "data": {} }
```

## 错误码

| HTTP | code | 含义 |
|---|---|---|
| 200 | 0 | 成功 |
| 400 | 40001 | 参数校验失败（代码/日期/分页参数不合法） |
| 404 | 40401 | 证券不存在或无日线数据 |
| 404 | 40402 | 日期范围内无数据 |
| 500 | 50001 | 数据文件解析失败（文件损坏） |
| 503 | 50301 | 行情数据根目录不可用 |

## 已知限制

- 不返回证券名称（本地无名称库）；不支持分钟线/分时线（格式已预留）
- 指数文件含早期零成交交易日，服务忠实透传源数据
"""


def _error_response(status_code: int, code: int, message: str) -> JSONResponse:
    """构造统一错误信封（code/message/data），绝不含堆栈等敏感信息。"""
    return JSONResponse(status_code=status_code, content=ApiResponse.err(code, message).model_dump())


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建 FastAPI 应用：显式接收 Settings（不读全局环境），注册处理器并挂载路由。

    数据根目录缺失时仅记录告警、/health 返回 503，不阻断应用启动。
    """
    settings = settings if settings is not None else get_settings()
    app = FastAPI(
        title="通达信本地行情数据服务",
        version=__version__,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    # 仓库进程内单例：BarCache 与目录扫描 TTL 缓存跨请求复用；
    # 若每次请求新建仓库，两层缓存全部失效（QA-2 压测实测热查询无加速）
    repository = SecurityRepository(settings)
    app.dependency_overrides[get_repository] = lambda: repository

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        """业务异常：按错误自带的 http_status 返回统一信封。"""
        return _error_response(exc.http_status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError):
        """参数校验异常：转 400 + 40001 信封，仅保留前几条错误摘要。"""
        brief = "; ".join(
            f"{'.'.join(str(p) for p in e.get('loc', ())[1:])}: {e.get('msg')}"
            for e in exc.errors()[:3]
        )
        return _error_response(400, 40001, f"参数校验失败: {brief}")

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        """未处理异常：完整堆栈仅进日志，响应只返回 50001 信封。"""
        logger.exception("未处理异常: %s %s", request.method, request.url.path)
        return _error_response(500, 50001, "服务器内部错误")

    if not settings.vipdoc_dir().is_dir():
        logger.warning("行情数据目录不存在: %s，/health 将返回 503", settings.vipdoc_dir())

    @app.get("/", include_in_schema=False)
    def root():
        """根路径重定向到 Swagger 交互式文档页。"""
        return RedirectResponse("/docs")

    app.include_router(router)
    return app


# 模块级实例：uvicorn tdx_service.main:app 直接可用（配置来自环境变量）
app = create_app()
