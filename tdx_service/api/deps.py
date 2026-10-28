"""FastAPI 依赖注入：模块级单例的配置与数据仓库（供 Depends 使用）。"""

from tdx_service.config import Settings
from tdx_service.repository import SecurityRepository

_settings: Settings | None = None
_repository: SecurityRepository | None = None


def get_settings() -> Settings:
    """获取配置单例：首次调用从环境变量加载并缓存（测试经 create_app 显例传配置时绕过）。"""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def get_repository() -> SecurityRepository:
    """获取数据仓库单例：基于配置单例惰性构造，进程内复用扫描与缓存。"""
    global _repository
    if _repository is None:
        _repository = SecurityRepository(get_settings())
    return _repository
