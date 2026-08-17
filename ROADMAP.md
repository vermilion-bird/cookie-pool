# Cookie Pool — 后续迭代路线图（Roadmap）

> 版本基线：**v0.5.0**（2026-08-14，commit `5c3c037`）
> 本文档是项目的长期迭代规划，每完成一个阶段后更新版本号与状态。
> **Phase 1（v0.3.x）已于 2026-08-14 实施完成 ✅**
> **Phase 2（v0.4.x）已于 2026-08-14 实施完成 ✅**
> **Phase 3（v0.5.x）部分完成 ⚡** — Session v2 / 集群 / 反检测 / Cookie API 已交付；智能调度 / PostgreSQL / 分页 / RBAC 待补全。

---

## 1. 现状盘点

### 1.1 已完成的能力（v0.2.0）

| 模块 | 能力 |
|------|------|
| 账号管理 | 创建 / 列表 / 详情 / 删除 / 编辑(API) / 状态机（WAIT_LOGIN → ACTIVE ↔ IN_USE ↘ LOGIN_EXPIRED） |
| 人工登录 | noVNC 弹窗登录全流程（start → complete → cancel），Profile 持久化（非 Cookie 存储） |
| 多 Grid | Grid 实例 CRUD、健康探测（`/check`）、账号 ↔ Grid 绑定、每 Grid noVNC 地址 |
| 任务 | 创建 / 列表 / 详情 / 手动运行 / 取消，账号互斥锁（IN_USE）保护 |
| 前端 | Dashboard / Accounts / Tasks / Grids 四页，React 19 + Vite + TS + Tailwind + TanStack Query |
| 部署 | Docker 多阶段构建（Node 编 SPA → Python 托管），docker-compose 一键起 |

### 1.2 核心优势（需在迭代中保持）

- **Profile 持久化**：账号状态不依赖 Cookie 字符串，天然抗掉线、抗校验，可随时人工接管。
- **无桌面服务器**上即可人工登录：Selenium Grid + noVNC 方案轻量、通用。
- 前后端分离但单容器托管，部署成本低；多 Grid 已具备雏形，扩展路径清晰。

### 1.3 已验证的关键短板（技术债清单）

以下为代码中**实际确认存在**的问题（非猜测），是后续迭代优先处理的输入：

| # | 短板 | 证据 | 影响 | 优先级 |
|---|------|------|------|--------|
| T1 | API_KEY 未强制校验 | `config.py` 定义了 `API_KEY`，但所有 API 路由无任何鉴权中间件 | 任何人可访问账号/任务/登录接口，**严重安全风险** | **P0** |
| T2 | 任务同步阻塞执行 | `TaskService.run()` 在 HTTP 请求线程内同步跑 Selenium | 任务耗时长时请求挂起、超时；无法并发；重启丢失运行态 | **P0** |
| T3 | 无调度能力 | 全仓无 scheduler/worker/cron 代码 | 只能手动触发任务，无法定时批量执行 | P1 |
| T4 | 登录校验靠 URL 关键词启发式 | `check_login()` 用 `login/signin/auth` 关键词判断 | 误判率高（平台改 URL 即失效），影响自动巡检 | P1 |
| T5 | 登录完成时重复创建 driver | `complete_login` 重新 `create_driver()` 再 `check_login()` | 与原会话抢 Profile 锁、浪费资源、可能失败 | P1 |
| T6 | SESSION_TIMEOUT_MINUTES 未生效 | 配置存在但无任何使用处 | 登录会话永不超时，`LOGIN` 状态可悬挂 | P1 |
| T7 | 无测试体系 | 全仓无 `test_*.py` / 前端无测试 | 回归无保障，重构风险高 | **P0** |
| T8 | 删除账号不清理 Profile 磁盘 | `AccountService.delete()` 仅删 DB 行 | 磁盘泄漏，Profile 文件残留隐私风险 | P1 |
| T9 | SQLite 并发限制 | `create_engine(sqlite:///...)`，`with_for_update()` 在 SQLite 下是空操作 | 多任务并发下账号锁不可靠；扩展受限于单机 | P2 |
| T10 | 无日志持久化/审计 | 仅 stdout logging | 排障困难，无操作审计 | P2 |
| T11 | 列表无分页 | 账号/任务全量加载 | 账号量级上来后前端卡顿、API 慢 | P2 |
| T12 | 前端缺账号编辑 UI | API 有 PUT，页面只有创建/删除/登录 | 改备注/换 Grid 只能靠 API | P2 |
| T13 | 任务执行器无注册机制 | `DefaultTaskExecutor` 硬编码，注释说"子类化重写" | 业务任务无法插件化接入 | P2 |
| T14 | `scripts/init.sh` 路径过时 | 脚本提示 `http://localhost:8080/ui/`，实际 SPA 在 `/` | 误导用户 | P3 |

---

## 2. 指导原则

1. **稳定性优先于新功能**：先把 T1/T2/T7 这类地基问题清掉，再叠加能力。
2. **核心原则不变**：始终以持久化 Chrome Profile 为账号载体，不退回 Cookie 方案。
3. **每阶段可独立上线**：阶段之间不互相依赖，单个阶段内也按 P0 → P2 顺序交付，随时可发版。
4. **API 向后兼容**：新增端点一律追加，不破坏现有 `GET/POST /api/accounts`、`/api/tasks` 等既有契约；如必须变更，先加 `v2` 前缀或版本协商。
5. **小而稳的发布节奏**：每完成一个里程碑打 tag（`v0.3.0`、`v0.4.0`…），与 README 版本同步。
6. **验收可量化**：每个里程碑有明确验收标准（见 §5）。

---

## 3. 路线图总览

| 阶段 | 目标版本 | 主题 | 核心价值 | 状态 |
|------|---------|------|---------|------|
| **Phase 1** | v0.3.0 ✅ | 根基加固：安全 / 异步执行 / 可靠性 | 系统可安全上线、任务不阻塞、有测试兜底 | ✅ 已完成 |
| **Phase 2** | v0.4.0 ✅ | 自动化闭环：调度 / 模板 / 通知 | 从"手动跑任务"进化到"定时自动跑" | ✅ 已完成 |
| **Phase 3** | v0.5.x | 规模化：多 Grid 调度 / 可观测 / 多用户 | 支撑上百账号、多 Grid 集群、多人协作 | ⚡ 部分完成 |
| **Phase 4** | v0.6+ | 智能化与生态：健康巡检 / 反检测 / SDK | 账号自愈、指纹管理、生态集成 | ⬜ 规划中 |

---

## 4. 分阶段详细规划

### Phase 1 — 根基加固（目标 v0.3.x）

> 一句话：**把系统变成可以安全、可靠地长时间运行的基础设施。**

#### 1.1 强制 API 认证（T1，P0） ✅
- 实现 FastAPI 依赖注入中间件：所有 `/api/*` 请求校验 `X-API-Key` 头（或 `Authorization: Bearer`），与 `config.API_KEY` 比对；`/health` 与 SPA 静态资源放行。
- `API_KEY` 支持环境变量注入（docker-compose 已传 `API_KEY=***`，落地即可生效），禁止默认值上线（`dev-key` 仅限本地）。
- **后续升级点**：Phase 3 升级为 JWT + 用户体系，中间件层预留抽象，不改业务代码。

#### 1.2 异步任务执行器（T2，P0） ✅
- 引入后台执行机制：进程内 `asyncio` 任务队列或独立 worker 进程（建议先做进程内队列 + 线程池，避免引入新基础设施；账号规模上来后 Phase 3 可平滑迁移到独立 worker + Redis 队列）。
- `POST /api/tasks/{id}/run` 改为**入队后立即返回**，任务状态由后台 worker 更新（PENDING → RUNNING → COMPLETED/FAILED）。
- 新增 `GET /api/tasks/{id}/status`（或复用详情接口 + 前端轮询），前端 Tasks 页改为轮询/长轮询刷新运行态。
- 任务运行中服务重启的恢复策略：启动时把残留 `RUNNING` 状态重置为 `FAILED`（标记 interrupted）或 `PENDING` 重试。

#### 1.3 登录会话生命周期完善（T4/T5/T6，P1） ✅
- 启用 `SESSION_TIMEOUT_MINUTES`：后台定时清理超时的 `CREATING/READY/LOGIN` 会话，状态置 `CLOSED`，账号回退 `WAIT_LOGIN`。
- 修复 `complete_login` 重复建 driver 的问题：对**原会话 driver**（若可重连）做校验，或先释放原会话再建校验 driver，避免 Profile 锁竞争。
- 登录校验升级为**可配置**：账号/平台级 `login_indicator`（CSS selector 或 URL 白名单）存入 DB，`check_login()` 优先使用配置，未配置时回退现有启发式。

#### 1.4 Profile 生命周期与磁盘管理（T8，P1） ✅
- 删除账号时级联删除 `data/profiles/account_*` 目录（先确认无活动会话）。
- 收紧 `chmod 0o777` 权限策略：仅对跨容器共享必需时放开，尽量限定最小权限。
- 新增磁盘占用统计（供 Phase 3 的 Dashboard 展示）。

#### 1.5 健康检查增强 ✅
- `/health` 从 `{"status":"ok"}` 升级为聚合视图：API 进程 / DB 可写性 / Grid 状态（复用 `GridService.probe`）/ profiles 磁盘余量。
- 前端 Layout 健康指示灯联动新的 `/health`（当前仅测 API 可达性）。

#### 1.6 任务执行器注册机制（T13，P2） ✅
- 定义 executor 注册表：`register_executor(task_type, ExecutorClass)`，`TaskService.run` 按 `task.type` 查找执行器，找不到则返回明确错误。
- 内置 `visit_url`（现有 navigate+screenshot）与 `check_login` 两个基础 executor，作为模板示例。
- 为 Phase 2 的任务模板库铺路。

#### 1.7 测试体系（T7，P0） ✅
- 后端：pytest + FastAPI TestClient + SQLite 内存库，覆盖账号状态机、锁获取/释放、任务执行成功/失败路径、认证中间件、Grid probe 的 mock 分支。
- 前端：Vitest + React Testing Library，覆盖 FilterBar 过滤、LoginModal 步骤流转（mock api）。
- CI 接入（GitHub Actions）：`pytest` + `npm run test` + `tsc` 类型检查，作为合并门槛。

#### 1.8 前端补齐（T12/T14，P2/P3） ✅
- Accounts 页增加编辑入口（复用 API PUT：改备注、换 Grid、改名）。
- 修正 `scripts/init.sh` 输出路径（`/` 而非 `/ui/`）。
- 统一错误提示：API 鉴权失败时前端给出"API key 无效"的明确提示。

**Phase 1 完成标志（已达成）**：无鉴权漏洞 ✅；任务异步不阻塞（后台 worker 入队执行）✅；登录会话可超时回收（SessionSweeper）✅；核心逻辑有测试覆盖（后端 29 例 + 前端 7 例 + CI）✅；`v0.3.0` 已发布 ✅。

---

### Phase 2 — 自动化闭环（目标 v0.4.x）

> 一句话：**从"手动指挥"到"定时自动执行 + 结果自动送达"。**

#### 2.1 调度器（T3） ✅
- 内置调度表（DB 表 `schedules`）：`cron` 表达式 + 目标账号（或账号组）+ 任务类型 + 参数。
- 后台调度线程按 cron 触发创建任务并入队（复用 Phase 1 的执行器）。
- 前端新增 Schedules 页：创建 / 启停 / 下次执行时间 / 历史触发记录。
- 首选方案：轻量自研（apscheduler 或纯标准库），避免引入外部调度服务；如多实例部署，再考虑外部锁/Redis。

#### 2.2 任务模板库 ✅
- 内置模板：`visit_url`、`screenshot`、`check_login_status`、`click_and_capture`（占位）+ 参数化表单。
- 前端 Tasks 创建表单支持从模板选择，自动填充 type/params。
- 模板与执行器注册表一一对应（Phase 1 的 1.6 是其底座）。

#### 2.3 结果资产化 ✅
- 任务结果中的截图/文件保存到 `data/artifacts/{task_id}/`，DB 记录 `artifact_paths`。
- 新增 `GET /api/tasks/{id}/artifacts`，前端任务详情可预览/下载截图。

#### 2.4 通知渠道 ✅（Webhook 已实现，飞书/邮件后续可扩展）
- 抽象 `Notifier` 接口：Webhook（通用 JSON）、飞书（机器人）、邮件（SMTP）三种实现，按任务结果/账号状态变更触发。
- 订阅规则可配置：任务失败、批量任务完成、账号登录过期等事件 → 指定渠道。

#### 2.5 失败重试与告警 ✅
- 任务级重试策略：`max_retries` / `retry_delay` 参数，FAILED 后自动重排队。
- 连续失败达到阈值触发 Notifier 告警。

#### 2.6 批量操作 ✅（CSV 导入 + batch-run/cancel）
- 批量创建账号（CSV 导入，含 platform/grid 列）。
- 批量运行/取消任务（按账号组或任务类型）。

**Phase 2 完成标志（已达成）**：cron 定时任务 ✅；任务截图可预览下载 ✅；失败可重试 ✅；Webhook 告警 ✅；`v0.4.0` 已发布 ✅。

---

### Phase 3 — 规模化与多用户（目标 v0.5.x）

> 一句话：**支撑上百账号、多 Grid 集群与团队协作。**

#### 3.1 多 Grid 智能调度 ⚡ 部分完成
- ✅ 多节点集群：`docker-compose.cluster.yml` + `cluster.sh`，Hub + 3 Node 各绑定专属账号
- ✅ Standalone Grid 部署：`grid-standalone/` 单容器全合一
- ✅ 外部 Grid 注册：通过 `/api/grids` CRUD 注册远程 Grid 实例
- ✅ Grid 周期探测：`GridService.probe()` 支持 Hub/Standalone 双模式
- ⬜ 容量感知调度：按 `grid.max_sessions` + 实时占用选择放置节点，会话放置失败自动换 Grid 重试

#### 3.2 ⭐ Session v2 — 常驻浏览器架构 ✅ 已完成
- ✅ `Session` + `SessionAccount` 模型：N:N 绑定，一个 Chrome 承载多平台 Account
- ✅ Session 生命周期管理：Create / Start Login / Complete / Cancel / Restart / Delete
- ✅ Session Watchdog：30s 周期探测 driver 存活，死 driver 自动 Grid 重连或完整重启
- ✅ Cookie 按平台提取：`GET /api/sessions/{id}/cookies` + Netscape 格式
- ✅ `cp` CLI 脚本：`cp list/get/session`，支持 `--plain` / `--domain` / `--platform`
- ✅ 前端 Sessions 页面：创建 / 详情 / 绑定账号 / 健康状态轮询

#### 3.3 反检测基础设施 ✅ 已完成
- ✅ CDP 脚本注入：覆盖 webdriver / plugins / languages / WebGL / permissions 等检测点
- ✅ UA 池随机旋转：Windows/macOS Chrome 130+ 共 6 个 UA
- ✅ Chrome 反自动化标志位：`--disable-blink-features=AutomationControlled`

#### 3.4 数据库升级路径 ⬜ 未开始
- 抽象数据访问层，支持 SQLite（默认）与 PostgreSQL（可选 `DATABASE_URL`）双后端；提供迁移脚本。
- `with_for_update()` 行锁在 PostgreSQL 下真正生效，解决 T9 的并发锁问题。

#### 3.5 列表分页与性能（T11）⬜ 未开始
- `/api/accounts`、`/api/tasks`、`/api/schedules` 支持 `page/page_size` + 服务端过滤（status/platform/type）。
- 前端列表接入分页与虚拟滚动，Dashboard 统计改为聚合查询。

#### 3.6 可观测性（T10）⬜ 未开始
- 结构化日志（JSON lines）+ 请求 ID 贯穿。
- 指标：账号状态分布、任务成功率/耗时、Grid 利用率（Prometheus 格式 `/metrics` 端点，或先做内置统计页）。
- 审计日志表：记录账号创建/删除/登录/任务操作（操作人 + 时间 + 结果），支撑追责与合规。

#### 3.7 RBAC 与多用户 ⬜ 未开始
- 在 Phase 1 认证基础上升级：用户表 + 角色（admin / operator / viewer），JWT 登录。
- 账号/Grid 可归属团队，权限隔离。
- 前端登录页与用户菜单。

**Phase 3 完成标志（部分达成）**：Session v2 架构上线 ✅；集群部署就绪 ✅；反检测注入生效 ✅；待补全：智能调度 / 分页 / PostgreSQL / 审计 / RBAC；`v0.5.0` 已打 tag。

---

### Phase 4 — 智能化与生态（目标 v0.6+）

> 一句话：**账号自愈、指纹可控、对外提供 SDK，融入上下游系统。**

#### 4.1 登录健康巡检与自愈
- 周期巡检 ACTIVE 账号：对配置了 `login_indicator` 的账号做轻量校验，发现掉线自动标记 `LOGIN_EXPIRED` 并通知。
- 半自动重登：对无验证码/低风险平台，巡检触发自动重登流程（脚本驱动登录，人工兜底）。

#### 4.2 反检测与指纹管理
- 每账号持久化浏览器指纹配置：UA、时区、语言、Canvas/WebGL 噪声、代理 IP。
- Grid 节点按指纹模板启动 Chrome，降低平台风控命中率。
- 代理池对接（HTTP/SOCKS5，按账号绑定出口 IP）。

#### 4.3 插件市场 / 自定义执行器 SDK
- 执行器以 Python 包或目录形式热加载（约定入口 `register(registry)`），支持第三方贡献。
- 提供 `cookie-pool-sdk`：任务创建/查询/结果获取的 Python 客户端。

#### 4.4 API SDK 与 CLI
- 官方 Python/Node SDK 封装 REST API；CLI 支持 `cp accounts list / task run / grid check`。
- OpenAPI 文档完善（FastAPI 自动生成，补充示例与鉴权说明）。

#### 4.5 上下游集成
- 与 `influencer-platform` 等业务系统对接：账号池作为统一登录/执行底座，提供任务回调。
- Webhook 出站事件（任务完成/账号状态变更）作为集成主通道。

**Phase 4 完成标志**：账号掉线可自动发现并通知；指纹/代理可配置；对外 SDK 与 CLI 可用；`v0.6.0` 打 tag。

---

## 5. 里程碑与验收标准

| 里程碑 | 关键交付 | 验收标准（可量化） |
|--------|---------|-------------------|
| M1（v0.3.0） | 认证 / 异步执行 / 会话超时 / 测试 | ① 无 API_KEY 请求 100% 被拒 ② 任务接口 5s 内返回（异步入队）③ 超时会话 ≤15min 被回收 ④ pytest 覆盖率 ≥60%，CI 全绿 |
| M2（v0.4.0） | 调度器 / 模板 / 截图资产 / 通知 | ① 支持 cron 定时任务 ② 任务截图可在线预览 ③ 失败任务可按策略重试 ④ 通知渠道 ≥2 种实测可用 |
| M3（v0.5.0） | 多 Grid 调度 / 分页 / 审计 / RBAC | ① 100 账号 + 3 Grid 压测通过 ② 列表接口分页 <100ms ③ 关键操作全量审计 ④ 三种角色权限隔离验证通过 |
| M4（v0.6.0） | 健康巡检 / 指纹 / SDK / CLI | ① 巡检周期 ≤15min ② 指纹模板 100% 生效 ③ SDK 完成 3 个端到端用例 ④ CLI 覆盖核心操作 |

---

## 6. 优先级矩阵（影响 × 成本）

```
影响
高 │  T1 认证      T2 异步      T3 调度
   │  T7 测试      T4 登录校验  T5 重复driver
   │
中 │  T6 会话超时  T8 Profile清理  分页 通知
   │  T12 编辑UI   T13 执行器注册
低 │  T14 init.sh  T11 分页(小规模)
   └──────────────────────────────────────
      低            中            高        成本
```

**执行建议**：先在 Phase 1 清掉"高影响"一行（T1/T2/T7/T4/T5），再按 T6/T8 → Phase 2 调度顺序推进；T9/T10 依赖规模化需求，留到 Phase 3。

---

## 7. 风险与依赖

| 风险 | 缓解措施 |
|------|---------|
| Selenium Grid 会话稳定性（节点挂、session 泄漏） | Phase 1 增加会话回收与 Grid 周期探测；SE_NODE_SESSION_TIMEOUT 已配置兜底 |
| Chrome Profile 多进程并发写坏 | 严格执行账号锁；`complete_login` 修复（T5）避免双 driver 抢 Profile |
| 平台风控升级导致登录校验失效 | 校验改为可配置 indicator（1.3），保留人工接管通道 |
| 异步 worker 增加系统复杂度 | 先进程内队列（零依赖），规模上来再迁独立 worker + Redis |
| 反检测需求与合规边界 | 指纹/代理仅用于自有账号的合法自动化，文档明确使用边界 |

**外部依赖**：Selenium Grid 镜像（seleniarm 系列，ARM 架构）；noVNC 访问链路的网络可达性（公网暴露需加鉴权，建议 Phase 1 一并评估 noVNC 访问控制）。

---

## 8. 建议的执行节奏

1. **本周**：立项 Phase 1，先做 T1（认证）+ T7（测试骨架），低风险高收益。
2. **2–4 周**：T2 异步执行 + T5/T6 登录链路修复，完成 v0.3.0。
3. **1–2 月**：Phase 2 调度与通知闭环，v0.4.0。
4. **按需推进**：Phase 3/4 视账号规模与业务需求启动，不盲目铺开。

> 版本号维护：每次里程碑打 tag 并同步更新 `app/main.py` 的 `version` 字段与 README。