"""FastAPI 应用工厂：注册全局异常处理器、挂载路由，并提供模块级 app 实例。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from tdx_service.api.deps import get_repository, get_settings
from tdx_service.api.routes import router
from tdx_service.config import Settings
from tdx_service.errors import AppError
from tdx_service.models import ApiResponse
from tdx_service.repository import SecurityRepository

logger = logging.getLogger(__name__)


def _error_response(status_code: int, code: int, message: str) -> JSONResponse:
    """构造统一错误信封（code/message/data），绝不含堆栈等敏感信息。"""
    return JSONResponse(status_code=status_code, content=ApiResponse.err(code, message).model_dump())


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建 FastAPI 应用：显式接收 Settings（不读全局环境），注册处理器并挂载路由。

    数据根目录缺失时仅记录告警、/health 返回 503，不阻断应用启动。
    """
    settings = settings if settings is not None else get_settings()
    app = FastAPI(title="TDX本地行情服务", version="1.0.0")
    # 用显式配置覆盖依赖单例，保证测试与多实例场景数据根正确
    app.dependency_overrides[get_repository] = lambda: SecurityRepository(settings)

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

    app.include_router(router)
    return app


# 模块级实例：uvicorn tdx_service.main:app 直接可用（配置来自环境变量）
app = create_app()
