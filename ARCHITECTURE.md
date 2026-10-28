# 架构设计 — 通达信本地行情数据服务

> 角色：架构师 ｜ 版本：v1.0 ｜ 日期：2026-10-28 ｜ 状态：待评审
> 上游文档：design.md（PRD v1.0）

## 1. 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.13 | 环境已具备（managed 3.13.12） |
| Web 框架 | FastAPI + uvicorn | 自动参数校验、OpenAPI 文档、生态成熟 |
| 数据模型 | pydantic v2 | 与 FastAPI 同源，响应序列化统一 |
| 解析 | 标准库 `struct` | 二进制定长解析，零依赖零歧义 |
| 测试 | pytest + FastAPI TestClient | TDD 标准组合 |
| 明确不引入 | pandas / numpy / ORM | 日线单文件 ≤210KB，原生结构足够；降低内存与启动开销 |

## 2. 总体架构

```
HTTP Client
    │  GET /api/v1/...
    ▼
┌─────────────────────────────────────────────┐
│ FastAPI (uvicorn)                           │
│  routes.py ── 参数校验(pydantic) ── 依赖注入 │
│      │                                      │
│  services.py (MarketService) 业务编排        │
│      │                                      │
│  repository.py (SecurityRepository)         │
│      ├── SecurityListCache (TTL 30s)        │
│      │      └── 目录扫描 vipdoc/{sh,sz,bj}/lday │
│      └── BarCache (LRU 512, mtime 失效)      │
│             └── parser/day.py (TdxDayReader) │
│                    struct.iter_unpack 解析    │
│  errors.py (AppError → 统一 envelope)        │
└─────────────────────────────────────────────┘
                    │ 只读
                    ▼
        D:\new_tdx\vipdoc\...\*.day
```

## 3. 模块设计

### 3.1 `config.py` — 配置

| 配置 | 环境变量 | 默认值 | 说明 |
|---|---|---|---|
| 数据根目录 | `TDX_HOME` | `D:\new_tdx` | 通达信安装路径 |
| 监听地址 | `TDX_HOST` | `127.0.0.1` | 默认仅本机 |
| 端口 | `TDX_PORT` | `8000` | |
| 缓存文件数 | `TDX_CACHE_SIZE` | `512` | LRU 上限 |
| 列表缓存 TTL | `TDX_LIST_TTL` | `30` 秒 | 证券目录扫描缓存 |

配置类 `Settings`（dataclass + `from_env()`），启动时校验 `TDX_HOME/vipdoc` 存在，否则 fail-fast。

### 3.2 `errors.py` — 错误体系

```python
class AppError(Exception):
    code: int          # 业务错误码
    http_status: int   # HTTP 状态
```

| 异常 | code | HTTP | 触发场景 |
|---|---|---|---|
| `ParamError` | 40001 | 400 | 参数校验失败 |
| `SecurityNotFound` | 40401 | 404 | 代码无对应文件 |
| `NoDataInRange` | 40402 | 404 | 日期范围无数据 |
| `DataFileError` | 50001 | 500 | 文件不可读/格式非法 |
| `DataRootUnavailable` | 50301 | 503 | 数据根目录缺失 |

全局 exception handler：`AppError` → envelope；未捕获异常 → 50001 + 日志记堆栈，响应不含堆栈。

### 3.3 `parser/base.py` + `parser/day.py` — 解析层

- `MarketFileReader`（ABC）：`read_file(path) -> list[Record]`，为分钟线预留
- `TdxDayReader`：
  - `DAY_FMT = struct.Struct("<IIIIIfII")`，32 字节/条
  - `iter_unpack` 全量解包；长度非整数倍 → 丢弃尾部残缺并 `logger.warning`
  - 日期合法性过滤（1990-01-01 ~ 2036-12-31），非法条跳过并计数
  - 输出 `DayRecord(date:int, open/high/low/close:int(分), amount:float, volume:int)`，按日期升序（防御性排序）
- `parser/minute.py`：本期仅放格式常量与 TODO 占位，不实现

### 3.4 `cache.py` — 双层缓存

| 缓存 | 键 | 值 | 失效策略 |
|---|---|---|---|
| `SecurityListCache` | 单例 | `list[SecurityEntry]` | TTL 30s，`/system/refresh` 可手动刷新 |
| `BarCache` | 文件绝对路径 | `(mtime, size, records)` | 每次访问校验 `st_mtime`+`st_size`；LRU 淘汰（默认 512） |

- 线程安全：`threading.Lock` 保护 LRU 写路径（FastAPI 同步路由跑在线程池）
- 命中路径零 I/O；未命中才 `os.stat` + 读文件

### 3.5 `repository.py` — 数据仓库

- `resolve_security(code) -> SecurityEntry`：代码规范化（去空格转大写、可选 `sh/sz/bj` 前缀）→ 先按前缀定位，无前缀时按 sh→sz→bj 顺序探测文件存在性；都不存在抛 `SecurityNotFound`
- `scan_securities()`：三市场 `lday` 目录 `glob("*.day")`，解析文件名得代码，组装 `SecurityEntry(market, code, file_path, bars, first_date, last_date)`（首末日期读取文件首尾记录，不入缓存，仅扫描时算一次）
- `get_daily_bars(entry, start, end, limit, offset)`：缓存取 records → `bisect` 定位日期区间 → 切片分页

### 3.6 `models.py` — 响应模型（pydantic）

- `DailyBar(date: str(YYYY-MM-DD), open/high/low/close: float(元), amount: float, volume: int(股))`
- `SecurityInfo(market, code, bars, first_date, last_date)`
- `SecurityBrief(market, code, bars, first_date, last_date)`
- `SystemInfo(tdx_home, markets: dict[str,int], total_securities, data_from, data_to, cache_size)`
- 价格输出统一**元**（解析层 ÷100 转换在序列化边界完成）

### 3.7 `api/routes.py` — 路由

| 路由 | 入参 | 备注 |
|---|---|---|
| `GET /api/v1/health` | — | 数据根可用性 |
| `GET /api/v1/system/info` | — | 概况统计 |
| `GET /api/v1/securities` | `market?, limit=100(1-1000), offset≥0` | 分页 |
| `GET /api/v1/securities/{code}` | 路径参数 | 元信息 |
| `GET /api/v1/kline/daily` | `code, start_date?, end_date?, limit=500(1-5000), offset≥0` | 历史日线 |
| `GET /api/v1/kline/daily/latest` | `code` | 最新一根 |

日期校验：正则 `^\d{4}-?\d{2}-?\d{2}$` + `datetime.strptime` 真实性校验；`start>end` → 40001。

## 4. 关键流程

**历史日线查询**：
```
code → resolve_security（前缀/探测，缓存列表辅助）
     → BarCache.get(path)：命中且 mtime/size 未变 → 直接用
     → 未命中 → TdxDayReader.read_file → 写入缓存
     → bisect 定位 [start,end] → 切片(limit/offset) → 空则 40402
     → DailyBar 序列化 → envelope
```

**客户端补数据后可见性**：TDX 写新文件 → 30s 后列表缓存过期重新扫描即可见；已缓存文件更新 → mtime 变化即时失效重读。

## 5. 性能预算

| 指标 | 设计值 | 手段 |
|---|---|---|
| 缓存命中查询 | < 5ms | 纯内存 + bisect |
| 未命中单文件解析 | < 20ms | iter_unpack 批量解包 |
| 列表接口 | < 100ms | 30s TTL 目录缓存 |
| P95（≤5000 条） | < 200ms | 上两项叠加 |
| 内存 | < 300MB | LRU 512 × ~210KB ≈ 108MB 上限 |

## 6. 项目结构

```
selectProductTool/
├── design.md / ARCHITECTURE.md / plan.md
├── README.md / API_DOC.md / review.md / final_report.md
├── requirements.txt
├── run.py                  # 启动入口
├── tdx_service/
│   ├── __init__.py
│   ├── config.py
│   ├── errors.py
│   ├── models.py
│   ├── parser/{__init__,base,day,minute}.py
│   ├── cache.py
│   ├── repository.py
│   ├── services.py
│   ├── api/{__init__,deps,routes}.py
│   └── main.py
└── tests/
    ├── conftest.py
    ├── test_parser_day.py
    ├── test_cache.py
    ├── test_repository.py
    ├── test_api.py
    └── test_integration.py
```

## 7. Git Flow 与分支策略

- `main`：发布分支（仅里程碑合入）
- `develop`：集成分支
- feature 分支：`feature/day-parser` → `feature/cache-repository` → `feature-api` → `feature-docs-qa`，逐个合入 develop

## 8. 测试策略

- **单元**：解析器（合成二进制，含残缺尾/非法日期/空文件）、缓存（命中/失效/淘汰/LRU 顺序）
- **集成**：tmp_path 构造三市场假数据，全接口走 TestClient
- **真实数据**：`test_integration.py` 对 `D:\new_tdx` 抽样断言（目录不存在则 skip），QA 阶段人工对账
- 目标：解析器 + API 覆盖率 ≥ 85%

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| float32 成交额大额误差 | API 文档明示；同时返回 volume |
| 跨市场同代码（如 001 在 sh/sz 均存在） | 支持 `sh001` 显式前缀；无前缀按 sh→sz→bj 顺序，列表接口可查全部 |
| 客户端写文件中途被读 | 容忍非 32 倍数尾部 + mtime/size 双校验 |
| 9945 文件目录扫描耗时 | TTL 缓存 + glob（实测毫秒级） |
