# API 文档 — TDX 本地行情数据服务（v1.2.0）

> 本文档所有示例均基于真实数据源 `D:/new_tdx`（sh 5009 + sz 4579 + bj 357 = 9945 个日线文件，数据截至 2026-10-27）实际调用验证，返回数据与接口行为一致。

## 1. 概述

| 项 | 值 |
|---|---|
| Base URL | `http://127.0.0.1:8000`（Docker 部署为 `http://127.0.0.1:8010`，见 docker-compose） |
| 路由前缀 | `/api/v1` |
| 内容类型 | `application/json`（UTF-8） |
| 交互式文档 | `http://127.0.0.1:8010/docs`（Swagger UI）、`/redoc`；根路径 `/` 自动跳转 `/docs` |
| 数据来源 | 本地通达信 `vipdoc/{sh,sz,bj}/lday/*.day` 只读解析，无任何在线访问 |

### 1.1 Swagger 交互式文档

服务内置 Swagger UI（基于 OpenAPI 3.1 规范自动生成），推荐作为接口探索与调试入口：

- **访问地址**：`http://127.0.0.1:8010/docs`（或浏览器直接访问根路径 `/` 自动跳转）
- **文档内容**：中文标题与分组（系统 / 证券 / 日线行情）、每个接口的摘要与详细说明、参数说明与示例值、响应结构 Schema（含示例数据）、错误响应说明
- **在线调试**：Swagger UI 内点击 `Try it out` 即可直接发起真实请求并查看响应，无需写代码
- **规范文件**：`/openapi.json`（可导入 Postman / Apifox 等工具）
- **备用风格**：`/redoc`（ReDoc 三栏式文档）

## 2. 通用约定

### 2.1 统一响应信封

所有接口（含错误）返回统一信封：

```json
{
  "code": 0,
  "message": "ok",
  "data": null
}
```

- `code`：业务码，`0` 表示成功，非 0 见错误码表
- `message`：成功为 `"ok"`；失败为具体错误描述（不含堆栈等敏感信息）
- `data`：业务数据，失败时为 `null`

### 2.2 日期格式

- `start_date`/`end_date` 接受 `YYYY-MM-DD`（如 `2026-10-27`）或 `YYYYMMDD`（如 `20261027`）两种格式，可混用
- 日期区间为**闭区间**（含首尾日期）
- 格式非法（如 `2026/10/01`）返回 `40001`；格式合法但不存在的日期（如 `2026-02-30`）返回 `40001`
- `start_date` 晚于 `end_date` 返回 `40001`

### 2.3 单位与精度

| 字段 | 单位 | 说明 |
|---|---|---|
| `open`/`high`/`low`/`close` | 元 | 源文件存储为价格 ×100 的整数（分），接口已 `/100` 换算为元 |
| `volume` | **股** | 注意：通达信行情界面按"手"显示，本接口返回股数（×100 换算） |
| `amount` | 元 | 源文件为 **float32**，存在量化误差：大额成交（数十亿元级）误差约 ±256 元。对精度敏感场景建议用 `volume × 均价` 交叉验证 |

### 2.4 分页语义

- `/securities`：`offset` 相对**市场过滤后**的全量列表头部；`offset` 越界返回**空 items**（HTTP 200，`total` 仍为过滤后总数）
- `/kline/daily`：`offset` 相对**日期区间过滤后**的头部；`offset` 越界返回 `40402`
- 注意：`/kline/daily` 不带日期范围时，`limit=500`（默认）返回的是**最早** 500 条（分页从历史头部起翻）；取近期数据请使用 `offset` 翻页或 `/kline/daily/latest`

### 2.5 证券代码与跨市场同名代码规则

代码格式：可选市场前缀（`SH`/`SZ`/`BJ`，大小写不敏感）+ 6 位数字，如 `600000`、`sh600000`、`SH600000` 等价。

| 形式 | 定位规则 |
|---|---|
| 带前缀（如 `sh600000`） | 直接定位前缀对应市场，文件不存在返回 `40401` |
| 无前缀（如 `600000`） | 按 **`sh → sz → bj`** 顺序探测文件，命中即返回 |

典型同名示例：`000001` 在沪市为上证指数、在深市为平安银行；不带前缀查询 `000001` 时按规则命中**沪市**（上证指数）。如需深市平安银行，请显式传 `sz000001`。

### 2.6 错误码总表

| code | HTTP 状态 | 含义 | 触发场景 |
|---|---|---|---|
| `0` | 200 | 成功 | 所有正常响应 |
| `40001` | 400 | 参数校验失败 | `market` 非法；证券代码格式非法；`limit`/`offset` 超出约束；日期格式非法/日期不存在；`start_date` 晚于 `end_date`；缺少必填参数 |
| `40401` | 404 | 证券不存在或无数据 | 代码文件不存在；文件存在但无有效日线记录（`/latest`） |
| `40402` | 404 | 日期范围内无数据 | 日期区间过滤后无记录；`offset` 越界 |
| `50001` | 500 | 数据文件错误/服务器内部错误 | `.day` 文件读取失败（OSError）；未处理异常（堆栈仅记录到服务日志） |
| `50301` | 503 | 行情数据目录不可用 | `TDX_HOME/vipdoc` 目录不存在（仅 `/health` 返回） |

错误响应示例（真实）：

```json
{
  "code": 40401,
  "message": "证券不存在: bj600000",
  "data": null
}
```

---

## 3. 接口详述

### 3.1 健康检查 `GET /api/v1/health`

**功能**：返回服务状态与行情数据目录可用性。`vipdoc` 目录不存在时返回 HTTP 503 + `50301`。

**请求参数**：无

**返回字段（`data`）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 固定 `"ok"` |
| `tdx_home` | string | 当前配置的通达信数据根目录 |
| `vipdoc_exists` | boolean | `vipdoc` 目录是否存在 |

**返回示例**（真实，HTTP 200）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok",
    "tdx_home": "D:/new_tdx",
    "vipdoc_exists": true
  }
}
```

**curl**：

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

**Python requests**：

```python
import requests

resp = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=10)
resp.raise_for_status()
data = resp.json()["data"]
print(data["status"], data["vipdoc_exists"])
# 输出: ok True
```

**错误码**：`50301`（数据目录不可用）。

---

### 3.2 系统信息 `GET /api/v1/system/info`

**功能**：各市场证券数量、总数与全局数据日期范围。首次调用需全量读取约 9945 个文件边缘记录（约 5 秒），结果按 `TDX_LIST_TTL`（默认 30 秒）缓存，TTL 内约 2ms。

**请求参数**：无

**返回字段（`data`）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `tdx_home` | string | 通达信数据根目录 |
| `markets` | object | 各市场文件数：`{"sh":5009,"sz":4579,"bj":357}` |
| `total_securities` | integer | 证券（文件）总数 |
| `data_from` | string | 全局最早交易日期 `YYYY-MM-DD` |
| `data_to` | string | 全局最晚交易日期 `YYYY-MM-DD` |
| `cached_files` | integer | 当前日线缓存文件数 |

**返回示例**（真实，HTTP 200）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "tdx_home": "D:/new_tdx",
    "markets": {
      "sh": 5009,
      "sz": 4579,
      "bj": 357
    },
    "total_securities": 9945,
    "data_from": "1990-12-19",
    "data_to": "2026-10-27",
    "cached_files": 0
  }
}
```

**curl**：

```bash
curl -s http://127.0.0.1:8000/api/v1/system/info
```

**Python requests**：

```python
import requests

resp = requests.get("http://127.0.0.1:8000/api/v1/system/info", timeout=30)
info = resp.json()["data"]
print(info["total_securities"], info["data_from"], "~", info["data_to"])
# 输出: 9945 1990-12-19 ~ 2026-10-27
```

**错误码**：`50001`（文件读取失败等内部错误）。

---

### 3.3 证券列表 `GET /api/v1/securities`

**功能**：分页列出证券元信息（K 线条数与首末交易日期），支持市场过滤。列表按市场（sh→sz→bj）+ 文件名排序。

**请求参数**：

| 名称 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---|---|---|---|
| `market` | string | 否 | 无 | `sh`/`sz`/`bj` 之一 | 市场过滤；非法值返回 `40001` |
| `limit` | integer | 否 | `100` | 1 ≤ limit ≤ 1000 | 当页条数 |
| `offset` | integer | 否 | `0` | offset ≥ 0 | 分页偏移，相对市场过滤后列表头部 |

**返回字段（`data`）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `items` | array | 当页证券元信息列表 |
| `items[].market` | string | 市场：`sh`/`sz`/`bj` |
| `items[].code` | string | 6 位证券代码 |
| `items[].bars` | integer | 日线记录条数 |
| `items[].first_date` | string \| null | 首个交易日；空文件为 `null` |
| `items[].last_date` | string \| null | 末个交易日；空文件为 `null` |
| `total` | integer | 市场过滤后的总数 |
| `limit` | integer | 回显请求的 limit |
| `offset` | integer | 回显请求的 offset |

**返回示例 1**：`?market=sh&limit=2&offset=0`（真实，HTTP 200）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "market": "sh",
        "code": "000001",
        "bars": 8750,
        "first_date": "1990-12-19",
        "last_date": "2026-10-27"
      },
      {
        "market": "sh",
        "code": "000002",
        "bars": 8750,
        "first_date": "1990-12-19",
        "last_date": "2026-10-27"
      }
    ],
    "total": 5009,
    "limit": 2,
    "offset": 0
  }
}
```

**返回示例 2**：`?market=sz&limit=2`（真实，HTTP 200，注意 `total` 为深市总数 4579）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "market": "sz",
        "code": "000001",
        "bars": 8478,
        "first_date": "1991-04-03",
        "last_date": "2026-10-27"
      },
      {
        "market": "sz",
        "code": "000002",
        "bars": 8504,
        "first_date": "1991-01-29",
        "last_date": "2026-10-27"
      }
    ],
    "total": 4579,
    "limit": 2,
    "offset": 0
  }
}
```

**curl**：

```bash
# 沪市前 2 条
curl -s "http://127.0.0.1:8000/api/v1/securities?market=sh&limit=2&offset=0"

# 翻页：北交所最后一页
curl -s "http://127.0.0.1:8000/api/v1/securities?market=bj&limit=2&offset=355"
```

**Python requests**：

```python
import requests

BASE = "http://127.0.0.1:8000/api/v1"

resp = requests.get(
    f"{BASE}/securities",
    params={"market": "sh", "limit": 2, "offset": 0},
    timeout=10,
)
data = resp.json()["data"]
print(data["total"], [item["code"] for item in data["items"]])
# 输出: 5009 ['000001', '000002']
```

**错误码**：`40001`（`market` 非法 / `limit`、`offset` 越界）。

---

### 3.4 证券详情 `GET /api/v1/securities/{code}`

**功能**：单个证券的元信息。`code` 支持 `600000`、`sh600000`、`SH600000` 形式；无前缀按 `sh→sz→bj` 顺序定位（见 2.5）。

**请求参数**：

| 名称 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---|---|---|---|
| `code` | string | 是 | — | 路径参数；`^(SH\|SZ\|BJ)?\d{6}$`（大小写不敏感） | 证券代码 |

**返回字段（`data`）**：同 3.3 的 `items[]` 单对象结构（`market`/`code`/`bars`/`first_date`/`last_date`）。

**返回示例 1**：`GET /api/v1/securities/600000`（真实，HTTP 200）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "market": "sh",
    "code": "600000",
    "bars": 6414,
    "first_date": "1999-11-10",
    "last_date": "2026-10-27"
  }
}
```

**返回示例 2**：`GET /api/v1/securities/SH600000`（真实，HTTP 200，前缀大小写不敏感，与示例 1 等价）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "market": "sh",
    "code": "600000",
    "bars": 6414,
    "first_date": "1999-11-10",
    "last_date": "2026-10-27"
  }
}
```

**返回示例 3**：`GET /api/v1/securities/000001`（真实，HTTP 200——无前缀按 sh→sz→bj 命中沪市上证指数，非深市平安银行）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "market": "sh",
    "code": "000001",
    "bars": 8750,
    "first_date": "1990-12-19",
    "last_date": "2026-10-27"
  }
}
```

**curl**：

```bash
curl -s http://127.0.0.1:8000/api/v1/securities/600000
curl -s http://127.0.0.1:8000/api/v1/securities/sz000001   # 深市平安银行
```

**Python requests**：

```python
import requests

BASE = "http://127.0.0.1:8000/api/v1"

resp = requests.get(f"{BASE}/securities/600000", timeout=10)
data = resp.json()["data"]
print(data["market"], data["code"], data["bars"])
# 输出: sh 600000 6414
```

**错误码**：

| 场景 | curl | 响应 |
|---|---|---|
| `40001` 代码格式非法 | `curl -s http://127.0.0.1:8000/api/v1/securities/abc123` | `{"code":40001,"message":"证券代码格式非法: abc123","data":null}` |
| `40401` 证券不存在 | `curl -s http://127.0.0.1:8000/api/v1/securities/600001` | `{"code":40401,"message":"证券不存在: 600001","data":null}` |
| `40401` 跨市场前缀无文件 | `curl -s http://127.0.0.1:8000/api/v1/securities/bj600000` | `{"code":40401,"message":"证券不存在: bj600000","data":null}` |

---

### 3.5 日线查询 `GET /api/v1/kline/daily`

**功能**：查询日 K 线，支持日期闭区间过滤与分页。

**请求参数**：

| 名称 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---|---|---|---|
| `code` | string | 是 | — | `^(SH\|SZ\|BJ)?\d{6}$`（大小写不敏感） | 证券代码 |
| `start_date` | string | 否 | 无 | `YYYY-MM-DD` 或 `YYYYMMDD` | 起始日期（含） |
| `end_date` | string | 否 | 无 | `YYYY-MM-DD` 或 `YYYYMMDD` | 结束日期（含） |
| `limit` | integer | 否 | `500` | 1 ≤ limit ≤ 5000 | 当页条数 |
| `offset` | integer | 否 | `0` | offset ≥ 0 | 分页偏移，相对日期区间头部 |

**返回字段（`data`）**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `items` | array | 当页日线列表，按日期升序 |
| `items[].date` | string | 交易日期 `YYYY-MM-DD` |
| `items[].open`/`high`/`low`/`close` | number | 开/高/低/收，单位元 |
| `items[].amount` | number | 成交额，单位元（float32 源数据，见 2.3） |
| `items[].volume` | integer | 成交量，单位股 |
| `count` | integer | 当页实际条数 |

**返回示例 1**：`?code=600000&limit=5`（真实，HTTP 200——无日期范围时从历史最早交易日起返回，此处为浦发银行 1999 年上市首周）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "date": "1999-11-10",
        "open": 29.5,
        "high": 29.8,
        "low": 27.0,
        "close": 27.75,
        "amount": 4859102208.0,
        "volume": 174085000
      },
      {
        "date": "1999-11-11",
        "open": 27.58,
        "high": 28.38,
        "low": 27.53,
        "close": 27.71,
        "amount": 821582208.0,
        "volume": 29403400
      },
      {
        "date": "1999-11-12",
        "open": 27.86,
        "high": 28.3,
        "low": 27.77,
        "close": 28.05,
        "amount": 421591616.0,
        "volume": 15007900
      },
      {
        "date": "1999-11-15",
        "open": 28.2,
        "high": 28.25,
        "low": 27.7,
        "close": 27.75,
        "amount": 332952800.0,
        "volume": 11921000
      },
      {
        "date": "1999-11-16",
        "open": 27.88,
        "high": 27.97,
        "low": 26.48,
        "close": 26.55,
        "amount": 628908288.0,
        "volume": 23223100
      }
    ],
    "count": 5
  }
}
```

**返回示例 2**：`?code=600000&start_date=2026-10-26&end_date=2026-10-27`（真实，HTTP 200——闭区间，两种日期格式可混用，完整 2 条）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "date": "2026-10-26",
        "open": 9.48,
        "high": 9.68,
        "low": 9.45,
        "close": 9.62,
        "amount": 757999744.0,
        "volume": 79376048
      },
      {
        "date": "2026-10-27",
        "open": 9.56,
        "high": 9.87,
        "low": 9.53,
        "close": 9.82,
        "amount": 789322240.0,
        "volume": 80753040
      }
    ],
    "count": 2
  }
}
```

**返回示例 3**：`?code=sz000001&limit=2`（真实，HTTP 200——深市平安银行最早 2 条，注意早年价格单位同为元）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "date": "1991-04-03",
        "open": 49.0,
        "high": 49.0,
        "low": 49.0,
        "close": 49.0,
        "amount": 5000.0,
        "volume": 100
      },
      {
        "date": "1991-04-04",
        "open": 48.76,
        "high": 48.76,
        "low": 48.76,
        "close": 48.76,
        "amount": 15000.0,
        "volume": 300
      }
    ],
    "count": 2
  }
}
```

**curl**：

```bash
# 浦发银行最近一周（用 limit 控制条数；取区间数据建议显式传 start/end）
curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=600000&start_date=2026-10-20&end_date=20261027&limit=100"

# 深市平安银行最早 2 条
curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=sz000001&limit=2"
```

**Python requests**：

```python
import requests

BASE = "http://127.0.0.1:8000/api/v1"

resp = requests.get(
    f"{BASE}/kline/daily",
    params={"code": "600000", "start_date": "2026-10-26", "end_date": "2026-10-27"},
    timeout=10,
)
bars = resp.json()["data"]["items"]
for bar in bars:
    print(bar["date"], bar["close"], bar["volume"])
# 输出:
# 2026-10-26 9.62 79376048
# 2026-10-27 9.82 80753040
```

**错误码**：

| 场景 | curl | 响应 |
|---|---|---|
| `40001` 缺少 code | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily"` | `{"code":40001,"message":"参数校验失败: code: Field required","data":null}` |
| `40001` 日期格式非法 | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=600000&start_date=2026/10/01"` | `{"code":40001,"message":"日期格式非法: 2026/10/01，应为 YYYY-MM-DD 或 YYYYMMDD","data":null}` |
| `40001` 日期不存在 | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=600000&start_date=2026-02-30"` | `{"code":40001,"message":"日期不存在: 2026-02-30","data":null}` |
| `40001` 起始晚于结束 | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=600000&start_date=2026-10-27&end_date=2026-10-20"` | `{"code":40001,"message":"起始日期晚于结束日期: 2026-10-27 ~ 2026-10-20","data":null}` |
| `40001` limit 越界 | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=600000&limit=5001"` | `{"code":40001,"message":"参数校验失败: limit: Input should be less than or equal to 5000","data":null}` |
| `40401` 证券不存在 | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=bj600000"` | `{"code":40401,"message":"证券不存在: bj600000","data":null}` |
| `40402` 区间无数据 | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=600000&start_date=1990-01-01&end_date=1990-12-31"` | `{"code":40402,"message":"日期范围内无数据: 600000","data":null}` |
| `40402` offset 越界 | `curl -s "http://127.0.0.1:8000/api/v1/kline/daily?code=600000&offset=999999&limit=10"` | `{"code":40402,"message":"日期范围内无数据: 600000","data":null}` |

---

### 3.6 最新一根日线 `GET /api/v1/kline/daily/latest`

**功能**：返回指定证券最新一根日线（文件末条记录）。

**请求参数**：

| 名称 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---|---|---|---|
| `code` | string | 是 | — | `^(SH\|SZ\|BJ)?\d{6}$`（大小写不敏感） | 证券代码 |

**返回字段（`data`）**：单根日线对象，字段同 3.5 的 `items[]` 元素。

**返回示例 1**：`?code=600000`（真实，HTTP 200——浦发银行最新日线）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "date": "2026-10-27",
    "open": 9.56,
    "high": 9.87,
    "low": 9.53,
    "close": 9.82,
    "amount": 789322240.0,
    "volume": 80753040
  }
}
```

**返回示例 2**：`?code=000001`（真实，HTTP 200——无前缀按 sh→sz→bj 命中沪市上证指数，注意指数成交额为数百亿元级）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "date": "2026-10-27",
    "open": 3698.44,
    "high": 3708.2,
    "low": 3648.3,
    "close": 3648.3,
    "amount": 672414367744.0,
    "volume": 417789532
  }
}
```

**curl**：

```bash
curl -s "http://127.0.0.1:8000/api/v1/kline/daily/latest?code=600000"
curl -s "http://127.0.0.1:8000/api/v1/kline/daily/latest?code=bj920002"   # 北交所
```

**Python requests**：

```python
import requests

BASE = "http://127.0.0.1:8000/api/v1"

resp = requests.get(
    f"{BASE}/kline/daily/latest",
    params={"code": "600000"},
    timeout=10,
)
bar = resp.json()["data"]
print(bar["date"], bar["close"])
# 输出: 2026-10-27 9.82
```

**错误码**：`40001`（代码格式非法/缺少参数）、`40401`（证券不存在或文件无有效记录）。

---

## 4. 补充说明

1. **首次调用延迟**：`/system/info` 与冷缓存的 `/securities`/`/kline/daily` 首次调用涉及文件 IO；后续请求命中缓存（日线查询毫秒级）。
2. **指数与股票同文件格式**：`sh000001`（上证指数）等指数文件与个股同为 32 字节日线格式，字段含义一致。
3. **零成交与瑕疵记录**：源数据中的历史零成交日、早期 OHLC 瑕疵记录被忠实透传（解析结果与源数据逐字节一致），未做过滤。
4. **数据更新**：通达信客户端日终更新 `.day` 文件后，服务缓存按文件 mtime/size 自动失效，无需重启。
