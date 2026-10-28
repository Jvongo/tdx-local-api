"""日线数据 LRU 缓存：按文件 mtime/size 校验有效性，线程安全。"""
import threading
from collections import OrderedDict
from pathlib import Path


class BarCache:
    """按 (mtime, size) 校验的日线记录 LRU 缓存，读写由 threading.Lock 保护。"""

    def __init__(self, maxsize: int = 512):
        self._maxsize = maxsize
        self._data = OrderedDict()  # path -> (st_mtime, st_size, records)
        self._lock = threading.Lock()

    def get(self, path: Path) -> list | None:
        """路径存在且 st_mtime/st_size 与缓存一致才返回记录，否则 None 并清除旧项。"""
        path = Path(path)
        try:
            st = path.stat()
        except OSError:
            return None
        with self._lock:
            item = self._data.get(path)
            if item is None:
                return None
            mtime, size, records = item
            if mtime != st.st_mtime or size != st.st_size:
                del self._data[path]  # 文件已变化，失效并清除旧项
                return None
            self._data.move_to_end(path)  # LRU：命中后置为最近使用
            return records

    def put(self, path: Path, records: list):
        """以 (st_mtime, st_size, records) 存入缓存，超出 maxsize 淘汰最久未用项。"""
        path = Path(path)
        try:
            st = path.stat()
        except OSError:
            return
        with self._lock:
            self._data[path] = (st.st_mtime, st.st_size, records)
            self._data.move_to_end(path)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)  # 淘汰最久未用项

    def __len__(self) -> int:
        """返回当前缓存条目数。"""
        with self._lock:
            return len(self._data)

    def clear(self):
        """清空全部缓存项。"""
        with self._lock:
            self._data.clear()
