# Changelog

本项目的版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
版本号集中管理：后端 `app/version.py`（`__version__`）为权威来源，前端 `frontend-react/package.json` 同步对齐。
迭代规划见 [ROADMAP.md](./ROADMAP.md)。

## [Unreleased]

## [0.5.2] - 2026-08-19 — 上线前加固

### Fixed

- **SessionSweeper 误杀修复**：LOGIN 超时改用 driver liveness 双重检查，alive driver 跳过并重置 timer
- **restart_session/start_login Grid 孤儿清理**：丢失 driver handle 后重建前强制删除 Grid 孤儿 session
- **complete_login 账号恢复**：LOGIN_EXPIRED 状态在 Complete 后自动恢复 ACTIVE
- **noVNC URL 端口修正**：内部 Grid 优先使用全局 HOST_ADDRESS + NOVNC_PORT
- **Watchdog 重启前清理 Grid 孤儿**：避免 Grid 满槽失败
- **Watchdog datetime 兼容**：修复 offset-naive vs offset-aware 异常

### Added

- **VNC 密码支持**：VNC_PASSWORD 环境变量，Session/Grid API 返回 vnc_password
- **VNC 密码界面展示**：Sessions Detail 弹窗显示密码 + 一键复制

### Changed

- **前端移动端优化**：汉堡菜单 + 底部 Tab + Modal 全屏 + 响应式列表
- **Sweeper LOGIN 超时**：30min → 120min
- **测试覆盖**：新增 test_regression.py 17 测试，全量 70 tests 100%

## [0.5.1] - 2026-08-14 — 稳定性加固

### Added

- **Node Heartbeat 服务**（`app/services/node_heartbeat.py`）：30s 周期探测所有 Grid 节点，自动更新 DB 状态（ONLINE/OFFLINE/DEGRADED），连续 3 次失败触发 Webhook 告警
- **Grid 僵尸 Session 清理**：SessionSweeper 和 Watchdog 每轮扫描 Grid 端孤儿 session，自动调用 Grid REST API 关闭未被 DB 记录的 Chrome 进程
- **Session 最大生命周期保护**：Watchdog 对运行超过 24h 的 session 强制标记 FAILED + 释放 Grid 资源（可配 `SESSION_MAX_LIFETIME_HOURS`）
- **Grid 紧急清理端点**：`POST /api/grids/{id}/force-cleanup` — 强制删除节点上所有活跃 session
- **节点心跳详情端点**：`GET /api/grids/{id}/heartbeat` — 查看节点连续失败计数和最后更新时间
- **Cookie 提取重试机制**：`_extract_session_cookies` 最多 3 次重试（指数退避 1s/2s/4s），CDP 失败回退 Selenium get_cookies()
- **Session 级别互斥锁**：`start_login` 和 `restart` 操作获取 per-session Lock（30s 超时），防止并发创建 driver 导致 Profile 损坏
- **稳定性配置项**：`NODE_HEARTBEAT_INTERVAL`、`SESSION_MAX_LIFETIME_HOURS`、`COOKIE_EXTRACT_MAX_RETRIES`、`ZOMBIE_CLEANUP_INTERVAL` 等环境变量

### Changed

- `/health` 端点增强：返回节点状态一览、活跃 session 计数、后台服务运行状态
- `_close_driver` 增强：同时清理 `_session_locks`，driver.quit() 失败不阻塞后续操作
- `_resolve_novnc_url` 增加空值校验和格式验证
- SessionSweeper 每次 sweep 增加一轮 Grid 僵尸扫描

### Fixed

- 修复潜在 Session 泄漏：Watchdog 检测到 driver 死掉时增加 Grid REST 清理兜底
- 修复可能的 Profile 损坏：start_login/restart 加锁防止并发
- 修复 `_reconnect_via_grid` 临时 session 残留

### 规划中（v0.5.1+ — Phase 3 补全）

- 列表分页与服务端过滤（Accounts / Tasks / Schedules）
- 多 Grid 容量感知调度与自动放置
- 数据库升级路径（SQLite → PostgreSQL 可选）
- 审计日志表
- 结构化日志 / 请求 ID / Prometheus 指标
- RBAC 多用户（JWT）与团队隔离

### 规划中（v0.6.x+ — Phase 4 智能化）

- 登录健康巡检与自愈（掉线自动发现 + 半自动重登）
- 代理池对接（HTTP/SOCKS5 per-account）
- 指纹模板配置化（UA/时区/语言/WebGL per-account）
- 对外 Python/Node SDK + CLI 增强
- 插件市场 / 自定义执行器 SDK

## [0.5.0] - 2026-08-14 — Phase 3 规模化：Session v2 + 集群 + 反检测

### Added

- **Session v2 常驻浏览器架构**：`Session` + `SessionAccount` 模型，一个 Chrome 承载多平台 Account（N:N 绑定），通过 noVNC 统一登录后按平台提取 Cookie
- **Session Watchdog**（`app/session_watchdog.py`）：30s 周期探测 driver 存活，死 driver 自动 Grid 重连（复用 profile）或完整重启
- **多节点集群部署**：`docker-compose.cluster.yml` + `cluster.sh`，Hub + 3 Node 各绑定专属账号，外部 Grid 通过 `/api/grids` 注册
- **Standalone Grid 部署**：`grid-standalone/` — 单容器全合一 Selenium Grid（hub+node+Chrome+VNC+noVNC）
- **反检测注入**（`grid_service.py`）：CDP 脚本覆盖 webdriver / plugins / languages / WebGL / permissions 等检测点
- **UA 池随机旋转**：Windows/macOS Chrome 130+ 共 6 个真实 User-Agent
- **Chrome 反自动化标志位**：`--disable-blink-features=AutomationControlled` + `excludeSwitches`
- **Cookie API**：`GET /api/sessions/{id}/cookies`（JSON）+ `/cookies/plain`（Netscape），按 platform/domain 过滤
- **`cp` CLI 工具**：`cp list/get/session`，支持 `--plain` / `--domain` / `--platform`
- **DSh skill 集成**：`.dsh/skills/cookie-pool/SKILL.md`
- **前端 Sessions 页面**（路由 `/sessions`）：创建 / 列表 / 详情 / 绑定账号 / 登录 / 完成 / 取消 / 重启 / 健康轮询
- 账号 `last_used_at` + IN_USE 锁泄漏自动释放
- Session 重启 → 绑定 Account 退回 WAIT_LOGIN
- 生产部署文档重写（Caddy 反代 + rsync 增量同步 + 外部 Grid Profile 管理）

### Changed

- Login 流程从 Account 页面迁移到 Sessions 页面（Session v2 统一承载）
- `grid_service.py` create_driver 全面重构：反检测 + UA 池 + CDP 注入
- 版本号 `0.5.0`（前后端对齐）

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