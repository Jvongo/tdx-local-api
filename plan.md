# 实施计划 — 通达信本地行情数据服务

> 角色：交付总监 ｜ 版本：v1.0 ｜ 日期：2026-10-28
> 上游文档：design.md（PRD）、ARCHITECTURE.md

## 环境准备（主理人执行，工程师前完成）

- venv：`C:\Users\10255\.workbuddy\binaries\python\envs\default`
- 依赖：fastapi、uvicorn[standard]、pydantic、pytest、httpx
- 运行/测试统一用该 venv 的 python

## 任务分解（每个任务 TDD：先红 → 绿 → 重构 → 提交）

### 分支 feature/day-parser

| # | 任务 | 产出文件 | 验证 |
|---|---|---|---|
| T1 | 项目骨架 + 配置 + 错误体系 | `tdx_service/{__init__,config,errors}.py`、`requirements.txt` | 导入通过；`Settings.from_env()` 默认值正确 |
| T2 | 日线解析器（TDD） | `tdx_service/parser/{__init__,base,day}.py`、`tests/test_parser_day.py` | 合成 .day：正常/残缺尾/非法日期/空文件 4 类用例 |
| T3 | 提交合并 develop | — | git 提交，feature 合入 develop |

### 分支 feature/cache-repository

| # | 任务 | 产出文件 | 验证 |
|---|---|---|---|
| T4 | LRU 缓存（TDD） | `tdx_service/cache.py`、`tests/test_cache.py` | 命中/mtime 失效/淘汰/LRU 顺序 |
| T5 | 响应模型 | `tdx_service/models.py` | pydantic 字段与单位（元/股）正确 |
| T6 | 数据仓库（TDD） | `tdx_service/repository.py`、`tests/test_repository.py` | tmp_path 三市场假数据：解析/前缀/跨市场/bisect 分页/404 |
| T7 | 提交合并 develop | — | git 提交，feature 合入 develop |

### 分支 feature-api

| # | 任务 | 产出文件 | 验证 |
|---|---|---|---|
| T8 | 业务编排 + 依赖注入 | `tdx_service/services.py`、`api/deps.py` | 单测 |
| T9 | 路由（TDD） | `tdx_service/api/{__init__,routes}.py`、`tests/test_api.py` | 6 接口 + 错误码 + 参数校验全用例 |
| T10 | 应用工厂 + 启动入口 | `tdx_service/main.py`、`run.py` | uvicorn 启动冒烟（/health 200） |
| T11 | 提交合并 develop | — | git 提交，feature 合入 develop |

### 分支 feature/docs-qa

| # | 任务 | 产出文件 | 验证 |
|---|---|---|---|
| T12 | 真实数据集成测试 | `tests/test_integration.py` | 对 D:\new_tdx 抽样断言（无数据则 skip） |
| T13 | README + API 文档 | `README.md`、`API_DOC.md` | 示例与实际行为一致 |
| T14 | 合并 develop → main，打 tag v1.0.0 | — | git flow 收尾 |

## 质量门禁

- 每个任务：pytest 全绿才允许提交
- 提交信息：`feat/fix/docs/test: 中文简述`
- 覆盖率目标：parser + api ≥ 85%（`pytest --cov`）

## 验收回溯（对应 PRD 第 6 节）

1. sh600000/sz000001/bj430047 抽样对账 → T12 + QA 人工
2. 9945 只证券可查 → T9/T12
3. 非法参数规范错误码 → T9
4. 覆盖率 ≥85% → T13 前执行
5. API 文档完整 → T13
