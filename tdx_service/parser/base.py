"""解析器抽象层：定义市场行情文件读取器的统一接口。"""

from abc import ABC, abstractmethod
from pathlib import Path


class MarketFileReader(ABC):
    """市场行情文件读取器抽象基类，约束各行情文件解析器的接口。"""

    @abstractmethod
    def read_file(self, path: Path) -> list:
        """读取单个行情文件，返回按时间升序排列的记录列表。"""
        raise NotImplementedError
