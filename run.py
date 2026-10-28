"""本地启动入口：从环境变量读取配置并以 uvicorn 运行应用。"""

import uvicorn

from tdx_service.config import Settings
from tdx_service.main import create_app


def main():
    """读取 TDX_HOME/TDX_HOST/TDX_PORT 等环境变量，启动 uvicorn 服务。"""
    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
