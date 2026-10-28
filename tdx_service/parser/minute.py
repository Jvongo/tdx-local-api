"""分钟线解析器占位模块：本期预留未实现，仅定义格式常量供后续开发使用。"""

import struct

# 分钟线记录结构（与日线同为 32 字节）：time(HHMM), 开高低收(float), amount(float), volume, reserved
MIN_STRUCT = struct.Struct("<HHfffffII")
MIN_RECORD_SIZE = 32
