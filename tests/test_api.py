"""API 路由测试（TDD 红灯阶段：先于实现编写）。"""
import pytest
from fastapi.testclient import TestClient

from conftest import make_record

# 标准假数据：sh 2 只、sz 1 只、bj 1 只，日期均落在 2026-01
def _rec(date):
    return make_record(date=date, close=1050)


SPEC = {
    "sh": {
        "600000": [_rec(d) for d in (20260105, 20260106, 20260107, 20260108, 20260109)],
        "600001": [_rec(d) for d in (20260106, 20260107)],
    },
    "sz": {"000001": [_rec(d) for d in (20260106, 20260107, 20260108)]},
    "bj": {"430047": [_rec(d) for d in (20260109, 20260110)]},
}


@pytest.fixture
def client(make_client):
    """基于标准 SPEC 的测试客户端。"""
    return make_client(SPEC)


class TestHealth:
    """健康检查接口测试。"""

    def test_health_ok(self, client):
        """GET /api/v1/health → 200，code=0，data.status=="ok"。"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["status"] == "ok"
        assert body["data"]["vipdoc_exists"] is True

    def test_health_data_root_missing(self, make_client, tmp_path):
        """数据根不存在 → 503 code=50301。"""
        client = make_client({})
        resp = client.get("/api/v1/health")
        assert resp.status_code == 503
        assert resp.json()["code"] == 50301


class TestSystemInfo:
    """系统信息接口测试。"""

    def test_system_info(self, client):
        """markets/total_securities/data_from/data_to 正确。"""
        resp = client.get("/api/v1/system/info")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["markets"] == {"sh": 2, "sz": 1, "bj": 1}
        assert data["total_securities"] == 4
        assert data["data_from"] == "2026-01-05"
        assert data["data_to"] == "2026-01-10"


class TestSecurities:
    """证券列表与详情接口测试。"""

    def test_list_pagination(self, client):
        """market=sh&limit=2 → 分页与 total 正确。"""
        resp = client.get("/api/v1/securities", params={"market": "sh", "limit": 2})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert [i["code"] for i in data["items"]] == ["600000", "600001"]

    def test_list_offset(self, client):
        """offset 分页正确。"""
        resp = client.get("/api/v1/securities", params={"market": "sh", "limit": 1, "offset": 1})
        data = resp.json()["data"]
        assert data["total"] == 2
        assert [i["code"] for i in data["items"]] == ["600001"]

    def test_list_invalid_market(self, client):
        """market=xx → 400 code=40001。"""
        resp = client.get("/api/v1/securities", params={"market": "xx"})
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001

    def test_get_security_info(self, client):
        """GET /api/v1/securities/600000 → 200 meta 正确。"""
        resp = client.get("/api/v1/securities/600000")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["market"] == "sh"
        assert data["code"] == "600000"
        assert data["bars"] == 5
        assert data["first_date"] == "2026-01-05"
        assert data["last_date"] == "2026-01-09"

    def test_get_security_not_found(self, client):
        """999999 → 404 code=40401。"""
        resp = client.get("/api/v1/securities/999999")
        assert resp.status_code == 404
        assert resp.json()["code"] == 40401


class TestDailyKline:
    """日线查询接口测试。"""

    def test_full_range(self, client):
        """不带日期 → 全量 5 条，date 为 YYYY-MM-DD、价格为元。"""
        resp = client.get("/api/v1/kline/daily", params={"code": "600000"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert [b["date"] for b in items] == [
            "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
        ]
        assert items[0]["open"] == 10.0  # 1000 分 → 10 元
        assert items[0]["close"] == 10.5  # 1050 分 → 10.5 元
        assert items[0]["volume"] == 10000

    def test_date_subrange(self, client):
        """start_date/end_date 子区间（闭区间）。"""
        resp = client.get("/api/v1/kline/daily", params={
            "code": "600000", "start_date": "2026-01-06", "end_date": "2026-01-08",
        })
        items = resp.json()["data"]["items"]
        assert [b["date"] for b in items] == ["2026-01-06", "2026-01-07", "2026-01-08"]

    def test_limit_offset(self, client):
        """limit/offset 分页。"""
        resp = client.get("/api/v1/kline/daily", params={
            "code": "600000", "limit": 2, "offset": 1,
        })
        items = resp.json()["data"]["items"]
        assert [b["date"] for b in items] == ["2026-01-06", "2026-01-07"]

    def test_no_data_in_range(self, client):
        """区间无数据 → 404 code=40402。"""
        resp = client.get("/api/v1/kline/daily", params={
            "code": "600000", "start_date": "2026-01-01", "end_date": "2026-01-02",
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == 40402

    def test_invalid_code(self, client):
        """code=abc → 400 code=40001。"""
        resp = client.get("/api/v1/kline/daily", params={"code": "abc"})
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001

    def test_invalid_date(self, client):
        """start_date=2026-13-99 → 400 code=40001。"""
        resp = client.get("/api/v1/kline/daily", params={
            "code": "600000", "start_date": "2026-13-99",
        })
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001

    def test_limit_out_of_range(self, client):
        """limit=99999 超上限 → 400 code=40001。"""
        resp = client.get("/api/v1/kline/daily", params={"code": "600000", "limit": 99999})
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001

    def test_start_after_end(self, client):
        """start>end → 400。"""
        resp = client.get("/api/v1/kline/daily", params={
            "code": "600000", "start_date": "2026-01-08", "end_date": "2026-01-05",
        })
        assert resp.status_code == 400
        assert resp.json()["code"] == 40001

    def test_latest_bar(self, client):
        """latest → 最后一根（2026-01-09）。"""
        resp = client.get("/api/v1/kline/daily/latest", params={"code": "600000"})
        assert resp.status_code == 200
        assert resp.json()["data"]["date"] == "2026-01-09"


class TestCrossRequestCache:
    """跨请求缓存复用测试（QA-2 压测暴露：override 每次请求构造新仓库导致双层缓存失效）。"""

    def test_repository_reused_across_requests(self, make_client, monkeypatch):
        """同一 app 连续两请求只解析一次文件：BarCache 必须跨请求复用。"""
        from tdx_service.parser import TdxDayReader

        client = make_client(SPEC)
        calls = []
        original = TdxDayReader.read_file

        def counting_read_file(self, path):
            calls.append(path)
            return original(self, path)

        monkeypatch.setattr(TdxDayReader, "read_file", counting_read_file)

        r1 = client.get("/api/v1/kline/daily", params={"code": "600000"})
        r2 = client.get("/api/v1/kline/daily", params={"code": "600000"})

        assert r1.status_code == 200 and r2.status_code == 200
        assert len(calls) == 1, f"read_file 被调用 {len(calls)} 次，BarCache 未跨请求复用"

    def test_entries_scan_ttl_across_requests(self, make_client, monkeypatch):
        """TTL 内连续两请求不重复扫描目录：_entries 缓存必须跨请求复用。"""
        import tdx_service.repository as repo_mod

        client = make_client(SPEC)
        globs = []
        original_glob = repo_mod.Path.glob

        def counting_glob(self, pattern):
            globs.append(str(self))
            return original_glob(self, pattern)

        monkeypatch.setattr(repo_mod.Path, "glob", counting_glob)

        r1 = client.get("/api/v1/securities", params={"market": "sh"})
        globs_after_first = len(globs)
        r2 = client.get("/api/v1/securities", params={"market": "sh"})

        assert r1.status_code == 200 and r2.status_code == 200
        assert globs_after_first == 3  # 首请求扫描 sh/sz/bj 三市场
        assert len(globs) == globs_after_first, "第二次请求重复扫描目录，TTL 缓存未跨请求复用"


class TestEnvelope:
    """统一响应结构测试。"""

    def test_all_responses_have_envelope(self, client):
        """所有响应（含错误响应）均含 code/message/data 三键。"""
        requests = [
            ("get", "/api/v1/health", None),
            ("get", "/api/v1/system/info", None),
            ("get", "/api/v1/securities", None),
            ("get", "/api/v1/securities/600000", None),
            ("get", "/api/v1/kline/daily", {"code": "600000"}),
            ("get", "/api/v1/kline/daily/latest", {"code": "600000"}),
            ("get", "/api/v1/securities/999999", None),
            ("get", "/api/v1/securities", {"market": "xx"}),
            ("get", "/api/v1/kline/daily", {"code": "abc"}),
        ]
        for method, url, params in requests:
            resp = client.request(method, url, params=params)
            assert set(resp.json().keys()) >= {"code", "message", "data"}, url
            assert "Traceback" not in resp.text
