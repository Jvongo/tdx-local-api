"""OpenAPI/Swagger 文档测试：验证中文元数据、标签分组、接口注释与错误响应文档化。"""

from tdx_service.main import create_app

# 六个业务接口的路径（与方法）
API_PATHS = [
    "/api/v1/health",
    "/api/v1/system/info",
    "/api/v1/securities",
    "/api/v1/securities/{code}",
    "/api/v1/kline/daily",
    "/api/v1/kline/daily/latest",
]


def _spec():
    """直接取应用的 OpenAPI 规范（不依赖数据目录，纯文档断言）。"""
    return create_app().openapi()


def test_openapi_info_metadata():
    """info 区：中文标题、版本号与描述包含数据来源/单位/错误码等关键说明。"""
    info = _spec()["info"]
    assert info["title"] == "通达信本地行情数据服务"
    assert info["version"] == "1.2.0"
    desc = info["description"]
    assert "vipdoc" in desc and "不复权" in desc and "40001" in desc


def test_openapi_tags_defined():
    """标签分组：系统/证券/日线行情 三个分组均已定义且有描述。"""
    tags = {t["name"]: t.get("description", "") for t in _spec()["tags"]}
    assert {"系统", "证券", "日线行情"} <= set(tags)
    assert all(tags.values())


def test_endpoints_fully_documented():
    """六个接口均有中文 summary、描述、标签归属，且错误响应已文档化。"""
    paths = _spec()["paths"]
    for path in API_PATHS:
        op = paths[path]["get"]
        assert op["summary"], f"{path} 缺少 summary"
        assert op["description"], f"{path} 缺少 description"
        assert op["tags"], f"{path} 未归属标签"
        # 每个接口至少文档化一个 4xx/5xx 错误响应
        assert any(c.startswith(("4", "5")) for c in op["responses"]), f"{path} 未文档化错误响应"


def test_query_params_documented():
    """关键查询参数均有中文描述与示例值（OpenAPI 3.1 示例位于 schema.examples）。"""
    paths = _spec()["paths"]
    params = {p["name"]: p for p in paths["/api/v1/kline/daily"]["get"]["parameters"]}
    for name in ("code", "start_date", "end_date", "limit", "offset"):
        assert name in params, f"kline/daily 缺少参数 {name}"
        param = params[name]
        assert param.get("description"), f"参数 {name} 缺少描述"
        schema = param.get("schema", {})
        assert schema.get("examples") or schema.get("example") or param.get("example"), \
            f"参数 {name} 缺少示例"


def test_schema_examples_present():
    """响应模型带示例值：DailyBar/SecurityInfo/SystemInfo 均含 example。"""
    schemas = _spec()["components"]["schemas"]
    for name in ("DailyBar", "SecurityInfo", "SystemInfo"):
        assert schemas[name].get("example"), f"{name} 缺少 schema 示例"


def test_root_redirects_to_docs():
    """根路径重定向到 Swagger 文档页 /docs。"""
    from fastapi.testclient import TestClient

    from tdx_service.config import Settings

    client = TestClient(create_app(Settings(tdx_home="./__no_such_dir__")))
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/docs"
