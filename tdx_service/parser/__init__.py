"""解析器包：导出日线解析器、日线记录与读取器抽象基类。"""

from tdx_service.parser.base import MarketFileReader
from tdx_service.parser.day import DayRecord, TdxDayReader

__all__ = ["TdxDayReader", "DayRecord", "MarketFileReader"]
