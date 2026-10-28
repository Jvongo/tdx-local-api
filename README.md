# TDX 本地行情数据服务（TDX Local Market API）

> 纯本地解析通达信行情文件（默认 `D:\new_tdx`）的 HTTP API 服务。**不访问任何在线行情服务**，全部数据来自本地 `.day` 二进制文件的只读解析。

## 1. 项目简介

本服务直接解析本地通达信客户端落盘的日线行情文件（`vipdoc/{sh,sz,bj}/lday/*.day`），对外提供统一的 RESTful HTTP API，覆盖健康检查、系统信息、证券列表/详情与日 K 线查询。适用于量化投研、本地数据工具等需要离线获取 A 股日线数据的场景。

- 数据源：通达信安装目录下的 `vipdoc` 二进制行情文件（沪 sh / 深 sz / 北 bj）
- 纯离线：代码中无任何网络调用（无 requests/urllib/socket 等），仅只读本地文件
- 技术栈：Python 3.13 + FastAPI + uvicorn + pydantic v2，标准库 `struct` 解析

## 2. 功能特性

- **健康检查**：服务状态与行情数据目录可用性探测（目录缺失返回 503）
- **系统信息**：各市场证券数量、总数、全局数据起止日期
- **证券列表**：按市场（sh/sz/bj）过滤，`limit`/`offset` 分页
- **证券详情**：K 线条数、首末交易日期（仅读文件首末 32 字节，O(1) IO）
- **日线查询**：支持起止日期闭区间过滤（`YYYY-MM-DD` 或 `YYYYMMDD` 两种格式）+ 分页
- **最新一根日线**：直接取末条记录
- **跨市场同名代码定位**：无前缀代码按 `sh → sz → bj` 顺序探测（如 `000001` 命中沪市上证指数）
- **两层缓存**：日线记录 LRU 缓存（512 条，按文件 mtime/size 失效）+ 证券目录扫描 TTL 缓存（30 秒）
- **system_info 单飞锁**：TTL 过期重算时并发请求只触发一次全量 IO，防缓存击穿
- **统一响应信封**：`{"code":0,"message":"ok","data":...}`；错误携带业务码与 HTTP 状态码，堆栈仅进日志

## 3. 环境要求

| 项目 | 要求 |
|---|---|
| Python | 3.13+ |
| 操作系统 | Windows / Linux / macOS（路径按 TDX_HOME 配置） |
| 数据 | 通达信行情目录（含 `vipdoc/{sh,sz,bj}/lday/*.day`） |
| 内存 | 数百 MB 级（LRU 缓存上限默认 512 个文件，单文件 ≤210KB） |

安装依赖：

```bash
pip install -r requirements.txt
```

## 4. 快速开始

### 4.1 启动服务

```bash
python run.py
```

或直接用 uvicorn（配置来自环境变量）：

```bash
uvicorn tdx_service.main:app --host 127.0.0.1 --port 8000
```

启动后访问 <http://127.0.0.1:8000/api/v1/health> 验证；交互式 OpenAPI 文档见 `/docs`。

### 4.2 环境变量

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `TDX_HOME` | `D:\new_tdx` | 通达信安装目录，行情数据取其下 `vipdoc/` |
| `TDX_HOST` | `127.0.0.1` | 服务监听地址（默认仅本机） |
| `TDX_PORT` | `8000` | 服务监听端口 |
| `TDX_CACHE_SIZE` | `512` | 日线记录 LRU 缓存的文件数上限 |
| `TDX_LIST_TTL` | `30` | 证券目录扫描 / system_info 结果缓存 TTL（秒） |

示例：

```bash
TDX_HOME=E:/tdx TDX_PORT=9000 python run.py
```

## 5. 配置说明

配置由 `tdx_service/config.py` 的 `Settings` 管理：启动时经 `Settings.from_env()` 从环境变量读取，缺省用默认值；非数字型配置错误直接 fail-fast（启动期立即失败，不带病运行）。`vipdoc` 目录缺失不阻断启动，仅记录告警，`/health` 返回 503。

## 6. 接口一览

Base URL：`http://127.0.0.1:8000`；所有响应为统一信封 `{"code","message","data"}`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/system/info` | 系统信息（各市场证券数、数据日期范围） |
| GET | `/api/v1/securities` | 证券列表（market 过滤 + 分页） |
| GET | `/api/v1/securities/{code}` | 证券详情 |
| GET | `/api/v1/kline/daily` | 日线查询（日期区间 + 分页） |
| GET | `/api/v1/kline/daily/latest` | 最新一根日线 |

各接口的完整参数、返回结构、错误码与调用示例见 **[API_DOC.md](API_DOC.md)**。

## 7. 数据格式说明

### 7.1 日线文件（.day）二进制格式

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | uint32 | 日期，`YYYYMMDD` 整数（如 `20261027`） |
| `open`/`high`/`low`/`close` | uint32 | 开/高/低/收，**价格 ×100 的整数**（分） |
| `amount` | float32 | 成交额，单位元 |
| `volume` | uint32 | 成交量，单位**股**（通达信界面显示为"手"，×100 换算） |
| `reserved` | uint32 | 保留字段，忽略 |

- 定长 **32 字节/条**，小端序，无文件头，`struct` 格式 `<IIIIIfII`
- 文件大小 ÷ 32 = 记录数；记录按日期升序，首条即最早交易日
- 解析时过滤非法日期（1990-01-01 ~ 2036-12-31 外的非真实日历日期）并丢弃尾部残缺记录

### 7.2 API 输出单位换算与精度提示

- 价格：接口输出由分转**元**（`/100`），如文件值 `982` → `9.82` 元
- 成交量：单位**股**（如 `80753040` 表示约 8075 万股）
- 成交额：源数据为 **float32**，存在量化误差——大额成交（数十亿元级）误差约 ±256 元；对精度敏感的场景建议用 `volume × 均价` 交叉验证或接受元级误差

## 8. 测试

```bash
pytest tests/ -v
```

当前基线：**54 个测试全部通过，覆盖率 95%**。测试使用 `tmp_path` 合成假 `.day` 数据，不依赖真实数据目录；QA 阶段另有真实数据（D:/new_tdx）逐字段对账与性能压测记录，见 `review.md`。

## 9. 目录结构

```
selectProductTool/
├── run.py                     # 启动入口（读环境变量，uvicorn 运行）
├── requirements.txt           # 依赖清单
├── tdx_service/               # 服务源码
│   ├── __init__.py
│   ├── config.py              # Settings 配置（环境变量 + 默认值）
│   ├── errors.py              # 统一错误体系（code/http_status/message）
│   ├── cache.py               # 日线 LRU 缓存（mtime/size 失效，线程安全）
│   ├── models.py              # pydantic v2 响应模型与统一信封
│   ├── repository.py          # 数据仓库（证券定位/日线查询/列表/系统信息）
│   ├── services.py            # 业务编排层 MarketService
│   ├── main.py                # FastAPI 应用工厂与异常处理器
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py            # 依赖注入（配置/仓库单例）
│   │   └── routes.py          # 6 个路由定义
│   └── parser/
│       ├── __init__.py
│       ├── base.py            # 行情文件读取器基类
│       ├── day.py             # 日线（.day）解析器
│       └── minute.py          # 分钟线解析器（格式常量预留，未实现）
└── tests/                     # pytest 测试
    ├── conftest.py            # 假 .day 数据构造与 TestClient 工厂
    ├── test_parser_day.py     # 解析器测试
    ├── test_cache.py          # LRU 缓存测试
    ├── test_repository.py     # 数据仓库测试
    └── test_api.py            # API 接口测试
```

## 10. 已知限制

| 限制 | 说明 |
|---|---|
| 无股票名称 | 本地 TDX 数据不含名称库，接口只返回代码，不返回证券名称 |
| 无复权 | 本地日线文件不含除权信息，返回**不复权**价格；复权需外部数据源 |
| 无分钟线/分时 | 本期仅支持日线；`vipdoc/*/minline`、`fzline` 本地为空，`parser/minute.py` 已做格式常量预留 |
| 指数含历史零成交/瑕疵日 | 指数文件含早期零成交交易日及少量 OHLC 瑕疵记录（如 sz000001 1991-09-30 零成交），服务忠实透传源数据，未做过滤 |
| 大分页 meta 实时计算 | `securities` 大 `limit`（如 1000）时当页 meta 需逐文件读边缘记录，约 700ms；默认 `limit=100` 约 74ms |
| `system/info` 首查约 5 秒 | 首次调用需全量读取约 9945 个文件边缘记录；结果按 `TDX_LIST_TTL` 缓存，TTL 内约 2ms |

## 11. Git Flow 分支说明

| 分支 | 用途 |
|---|---|
| `main` | 发布分支，只存放稳定版本，由 `develop` 合入并打 tag |
| `develop` | 集成分支，所有功能在此汇合，保持可发布状态 |
| `feature/*` | 功能分支（如 `feature/day-parser`、`feature/cache-repository`、`feature-api`），从 `develop` 切出，完成后 `--no-ff` 合回 |

历史发布：`v1.0.0`（首个发布版本，通达信本地行情数据服务）。
