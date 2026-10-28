"""tdx_service 配置：数据目录、服务监听与缓存参数，支持环境变量覆盖。"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    """服务配置项：数据根目录、监听地址端口、缓存大小与列表缓存 TTL。"""

    tdx_home: str = "D:\\new_tdx"
    host: str = "127.0.0.1"
    port: int = 8000
    cache_size: int = 512
    list_ttl: int = 30

    @classmethod
    def from_env(cls):
        """从环境变量 TDX_HOME/TDX_HOST/TDX_PORT/TDX_CACHE_SIZE/TDX_LIST_TTL 构造配置，缺省用默认值。"""
        return cls(
            tdx_home=os.environ.get("TDX_HOME", cls.tdx_home),
            host=os.environ.get("TDX_HOST", cls.host),
            port=int(os.environ.get("TDX_PORT", cls.port)),
            cache_size=int(os.environ.get("TDX_CACHE_SIZE", cls.cache_size)),
            list_ttl=int(os.environ.get("TDX_LIST_TTL", cls.list_ttl)),
        )

    def vipdoc_dir(self) -> Path:
        """返回行情数据 vipdoc 目录路径。"""
        return Path(self.tdx_home) / "vipdoc"

    def markets(self) -> list:
        """返回支持的市场目录名列表：沪、深、京。"""
        return ["sh", "sz", "bj"]
