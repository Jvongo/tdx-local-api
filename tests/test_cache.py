"""BarCache LRU 缓存单元测试（TDD 红灯阶段：先于实现编写）。"""
import os

from tdx_service.cache import BarCache


class TestBarCache:
    """BarCache 读写命中、文件变更失效与 LRU 淘汰语义测试。"""

    def test_put_then_get_hit(self, tmp_path):
        """put 后 get 命中，返回同一 records 列表。"""
        f = tmp_path / "sh600000.day"
        f.write_bytes(b"x" * 64)
        records = [{"date": 20240102}, {"date": 20240103}]

        cache = BarCache()
        cache.put(f, records)

        assert cache.get(f) is records
        assert len(cache) == 1

    def test_mtime_change_invalidates(self, tmp_path):
        """文件 mtime 变化（os.utime 改时间戳）→ get 返回 None 并清除旧项。"""
        f = tmp_path / "sh600000.day"
        f.write_bytes(b"x" * 64)

        cache = BarCache()
        cache.put(f, [1, 2])
        os.utime(f, (1000000, 1000000))  # 修改时间戳模拟文件被改动

        assert cache.get(f) is None
        assert len(cache) == 0

    def test_size_change_invalidates(self, tmp_path):
        """文件 size 变化 → get 返回 None。"""
        f = tmp_path / "sh600000.day"
        f.write_bytes(b"x" * 64)

        cache = BarCache()
        cache.put(f, [1, 2])
        f.write_bytes(b"x" * 96)  # 内容长度变化

        assert cache.get(f) is None

    def test_lru_evicts_oldest_entry(self, tmp_path):
        """maxsize=2 连续 put 3 个不同 path，最早条目被淘汰。"""
        files = []
        for i in range(3):
            f = tmp_path / f"sh60000{i}.day"
            f.write_bytes(b"x" * 32)
            files.append(f)

        cache = BarCache(maxsize=2)
        cache.put(files[0], ["a"])
        cache.put(files[1], ["b"])
        cache.put(files[2], ["c"])

        assert cache.get(files[0]) is None
        assert cache.get(files[1]) == ["b"]
        assert cache.get(files[2]) == ["c"]

    def test_get_hit_delays_eviction(self, tmp_path):
        """LRU 语义：get 命中过的条目延后淘汰。"""
        files = []
        for i in range(2):
            f = tmp_path / f"sz00000{i}.day"
            f.write_bytes(b"x" * 32)
            files.append(f)
        third = tmp_path / "sz000009.day"
        third.write_bytes(b"x" * 32)

        cache = BarCache(maxsize=2)
        cache.put(files[0], ["a"])
        cache.put(files[1], ["b"])
        assert cache.get(files[0]) == ["a"]  # 访问 a 使其变为最近使用
        cache.put(third, ["c"])              # 淘汰最久未用的 b

        assert cache.get(files[0]) == ["a"]
        assert cache.get(files[1]) is None

    def test_get_unknown_path_returns_none(self, tmp_path):
        """get 未 put 过的 path → None。"""
        f = tmp_path / "sh600000.day"
        f.write_bytes(b"x" * 32)

        assert BarCache().get(f) is None

    def test_clear(self, tmp_path):
        """clear 清空全部缓存项。"""
        f = tmp_path / "sh600000.day"
        f.write_bytes(b"x" * 32)

        cache = BarCache()
        cache.put(f, [1])
        cache.clear()

        assert len(cache) == 0
        assert cache.get(f) is None
