# Changelog

本项目的版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
版本号集中管理：后端 `app/version.py`（`__version__`）为权威来源，前端 `frontend-react/package.json` 同步对齐。
迭代规划见 [ROADMAP.md](./ROADMAP.md)。

## [Unreleased]

### 规划中（Phase 3 — 规模化与多用户，目标 v0.5.x）

- 多 Grid 容量感知调度与自动放置
- 数据库升级路径（SQLite → PostgreSQL 可选）
- 列表分页与服务端过滤
- 结构化日志 / Prometheus 指标 / 审计日志
- RBAC 多用户（JWT）与团队隔离
- 账号导入导出与备份恢复

## [0.4.0] - 2026-08-14 — Phase 2 自动化闭环

### Added

- **cron 调度器**：`schedules` 表 + 轻量 cron 解析器（`app/services/cron.py`，支持 `*`/`*/n`/`a-b`/`a,b`）+ 后台调度线程（`app/scheduler.py`），按计划为目标账号创建任务并入队
- **Schedules API 与页面**：CRUD + 启停 + 立即触发（`trigger`）+ 下次执行时间预览
- **任务结果资产化**：截图/文件保存到 `data/artifacts/{task_id}/`，`GET /api/tasks/{id}/artifacts` 列表与下载（含路径穿越防护），前端详情弹窗可预览/下载
- **失败重试**：任务级 `max_retries`/`retry_delay_seconds`，失败自动延迟重投，重试耗尽后 FAILED
- **Webhook 通知**（`app/notifiers.py`）：任务完成/失败事件 POST JSON 到 `NOTIFY_WEBHOOK_URL`，渠道故障不影响主流程
- **任务类型元数据**：`GET /api/tasks/meta/types` 返回类型/描述/参数模板，前端创建表单支持模板下拉
- **批量操作**：`POST /api/tasks/batch-run`、`/batch-cancel`；`POST /api/accounts/import` CSV 批量导入账号（含去重与 Grid 校验）
- 前端 **Schedules 页面**（路由 `/schedules`）与 Tasks 页"Run All Pending"按钮

### Changed

- `POST /api/tasks` 支持 `max_retries`/`retry_delay_seconds` 参数
- Task 模型新增 `retry_count`/`max_retries`/`retry_delay_seconds`/`artifact_paths`（含 SQLite 迁移）
- 任务完成/失败时发送 Webhook 事件
- 版本号 `0.4.0`（前后端对齐）

## [0.3.0] - 2026-08-14 — Phase 1 根基加固

### Added

- **强制 API 认证**：所有 `/api/*` 与文档端点（`/docs` 等）要求 `X-API-Key` 请求头；`/health` 与 SPA 静态资源放行
- **异步任务执行器**（`app/worker.py`）：PENDING 任务入队后台线程执行，`POST /api/tasks/{id}/run` 立即返回，不再同步阻塞 HTTP 请求
- **任务执行器注册机制**（`app/executors/registry.py`）：按 `task.type` 注册与调度，内置 `visit_url`、`check_login_status`
- 账号 `login_indicator` 字段：CSS 选择器登录校验（含 SQLite 迁移）
- **登录会话超时回收** SessionSweeper：默认 60s 周期，按 `SESSION_TIMEOUT_MINUTES` 回收 CREATING/READY/LOGIN 会话并释放 Grid 会话
- 测试体系：后端 pytest（29 例）+ 前端 vitest（7 例）+ GitHub Actions CI（`.github/workflows/ci.yml`）
- 前端 API Key 设置弹窗（🔑，localStorage 持久化）与 401 明确提示
- 前端账号编辑弹窗（名称/平台/备注/Grid/login_indicator）
- `/health` 增强：返回 `version` 与数据库状态
- SQLite 加固：WAL 日志模式、`busy_timeout`、外键约束

### Changed

- `complete_login` 不再新建 driver：改为经 Selenium Grid REST 校验**现有**登录会话（URL 或选择器），避免 Profile 锁竞争
- `POST /api/tasks/{id}/run` 从同步执行改为**入队异步执行**
- `POST /api/tasks` 创建时校验执行器类型与 JSON 参数合法性
- 删除账号时级联关闭活动 Grid 会话并清理磁盘 Profile 目录
- 版本号集中管理：后端 `app/version.py`，前端对齐为 `0.3.0`

### Fixed

- `scripts/init.sh` 过时路径 `/ui/` → `/`
- `SESSION_TIMEOUT_MINUTES` 此前已配置但从未生效（登录会话可能永久悬挂）
- 登录校验此前仅依赖 URL 关键词启发式（误判率高），现支持可配置 indicator 并保留启发式作为回退
- README / ROADMAP 同步至 v0.3.0

## [0.2.0] - 2026-08-14

- Web UI 重设计：卡片式布局视觉系统（Dashboard / Accounts / Tasks / Grids 四页）
- 多 Grid 实例管理：CRUD + 健康探测（`POST /api/grids/{id}/check`）+ 每 Grid noVNC 地址
- 账号 ↔ Grid 绑定（`grid_id` 字段，含 v0.1.0 迁移）

## [0.1.0] - 2026-08-13

- 初始版本：账号管理（创建/列表/详情/删除）与状态机（WAIT_LOGIN → ACTIVE ↔ IN_USE → LOGIN_EXPIRED）
- noVNC 人工登录全流程（start / complete / cancel），Chrome Profile 持久化（非 Cookie 存储）
- 基础任务执行（导航 + 截图）与账号互斥锁
- Docker 多阶段构建（Node 编译 SPA → Python 托管）与 docker-compose 一键部署