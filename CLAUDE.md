# 企业流程审批系统 — AI 开发指南

> 本文件为 AI 辅助开发提供项目上下文。每次会话自动加载。
> 详细设计见 `00_Project_Blueprint.md` 和 `01_PRD.md`。

---

## 项目定位

企业级流程审批管理系统。不是传统 OA 请假系统，是以流程驱动项目的业务管理平台。

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端框架 | Vue 3 + TypeScript | Composition API |
| 流程设计器 | LogicFlow | 滴滴开源，专为审批流设计 |
| UI 组件库 | Element Plus | 企业级组件库 |
| 后端 | FastAPI (Python 3.10+) | 异步框架 |
| ORM | SQLAlchemy 2.0 | 异步模式 |
| 数据库 | MySQL 8.0 | InnoDB，操作日志表按年分区 |
| 文件存储 | 服务器本地目录 | `storage/archive/{实例名称}/` |
| 认证 | JWT | python-jose |
| PDF 转换 | LibreOffice 无头模式 + Pillow | asyncio.Semaphore 限流 4 并发 |
| PDF 签名 | pypdf | 签名图片插入 PDF |
| 异步 | FastAPI BackgroundTasks | V1 不引入 Celery |

## 角色体系（RBAC）

| 角色 | 标识 | 核心职责 |
|------|------|----------|
| 系统管理员 | system_admin | 用户/组织/角色维护，不参与业务 |
| 所长 | manager | 设计流程、发起流程、终止流程、终审 |
| 普通用户 | user | 执行节点、上传文件、审批 |

## 核心对象

Organization → User → Flow Template → Flow Instance（含 priority 优先级属性 + difficulty 难度等级 1-4，默认 normal/1，发起人可随时修改）→ Instance Node → Task → Check → Approval → Endorsement → File → Signature → Operation Log → Notification

## 节点模型（关键！）

**统一节点类型**——不区分开始/工作/分支/结束，所有节点同一类型，行为由位置决定：

| 位置 | 行为 |
|------|------|
| 第一个（开始） | 系统默认生成，显示发起人姓名，无配置，发起后自动跳过，不生成 Task |
| 中间（工作） | 负责人执行 → 上传文件 → 自动转PDF → 提交 → 校验人校验 → 审批人审批 → (难度4) 批准人签阅 → 全部通过后签名上PDF → 下一节点 |
| 最后一个（结束） | 发起人终审：查看全部文件 → 通过则归档；驳回则选择目标节点。不生成 Task |

## 每个节点的标准流程

```
负责人收到 Task
  → 上传文件（Word/Excel/图片/PDF）
  → 提交时系统自动将非 PDF 转为 PDF（LibreOffice 无头模式）
  → 校验人校验
  → 校验通过 → 审批人收到审批
  → 审批通过（支持 all_approve / single_approve 两种策略）
  → [难度4] 批准人签阅（Endorse）
  → 签名自动插入 PDF 固定位置（pypdf 库）
  → 进入下一节点
```

- 驳回时审批人从之前的节点列表中选择目标 → 旧文件删除 → 重新生成 Task
- 负责人和审批人可为同一人，系统不拦截
- 审批策略支持"全部通过"（all_approve）和"一人通过"（single_approve）两种模式
- 校验人/审批人前端 UI 简化为单选（一人），后端存储仍为数组，兼容历史多选数据
- 审批驳回时可选择驳回到已完成的历史节点（中间节点驳回也能指定目标节点，复用终审驳回逻辑）

## PDF 签名机制

- 用户预先上传签名图片（PNG 透明底，200×60px，<500KB）
- 审批通过时，系统用 pypdf 将签名插入 PDF 指定坐标
- 多审批人签名按审批顺序排列，不覆盖
- 签名位置在系统配置中设定

## 流程生命周期

```
Created → Running → Completed
    ↓         ↓           ↓
    └─────────┴───────────┘
           Terminated（发起人终止，文件删除，不可恢复）
```

## 文件存储

```
storage/archive/{实例名称}/
  ├── abc123.pdf
  └── ...
```

- 文件属于流程实例，不属于用户或节点
- 驳回重提交：旧文件删除，上传新文件
- 驳回场景下文件可删除，正常流程不可随意删除

## 模块结构

```
├── Dashboard（首页看板）
├── 项目管理（含流程设计器 + 组织卡片，内部页面导航，方案通过 Tab 切换）
├── 方案管理（同项目管理模型，独立菜单入口）
├── 个人中心（卡片分区，一页展示；个人信息/密码在右上角下拉；系统管理员不显示此菜单）
└── 系统管理（Tab 切换，仅管理员可见）
```

> 一级菜单无二级菜单。个人中心仅所长和普通用户可见（系统管理员不参与业务，无个人中心）。系统管理内部用 Tab 切换。

## 关键业务规则

1. 一个流程模板 → 多个实例（模板与实例完全分离，实例发起时配置快照）
2. 模板修改直接生效（模板与实例解耦，运行中实例不受影响）
3. 实例发起时可逐节点调整审批人/负责人/截止日期，发起后生成配置快照，与模板解耦
4. 开始和结束节点由系统默认生成，不可删除
5. 发布校验：至少3个节点 + 中间节点完整配置 + 全部连通
6. 跨所协作：负责人和审批人可跨组织，但模板编辑权限属于所属所
7. 所有操作记录日志，不可删除
8. 第一版不做条件分支（支持 fork/join 并行分叉汇合）
9. 仅发起人可终止自己发起的流程（任意未 terminated 状态均可终止，包括 Created/Running/Completed（含已归档））
10. 用户上传签名图片后才能审批时自动签名，未上传则跳过签名
11. 发起人可随时更换运行中实例未完成节点的负责人/校验人/审批人（紧急换人），待处理的校验/审批记录自动更新，已完成的保留不动
12. 发起流程实例时可选择优先级（urgent/high/normal/low），默认 normal。发起后发起人可随时修改优先级（兜底机制）
13. 实例有难度等级（1-4 级）。难度 4 级时需配置批准人（Endorser），在所有审批人通过后操作
14. 通知系统：WebSocket 推送 + 个人中心 30s 轮询兜底。侧边栏角标、个人中心 Tab 页签、首页红点均实时刷新
15. 节点可配置文件提交分类（文件夹模式）：多个命名文件夹，各自可设必填/可选 + 精确数量限制
16. 补交文件：已完成实例的已完成节点可追加文件，节点有文件夹配置时必选目标文件夹
17. 文件模板（.docx/.xlsx）：管理员上传，下载时自动替换 15 个占位符（如 {{项目名称}}、{{发起日期}} 等）；支持模板分类（包），包内多模板可一键打包 ZIP 下载
18. 方案（Proposal）：与项目并列的流程类型，相同节点模型
19. 全系统待办/超期（Dashboard 超期列表 + 超期汇总页 `/notifications/overdue`）全员可见，不分组织 —— 产品确认（2026-08-03 内网部署校准），数据可见性为产品需求而非漏洞

## 当前进度

- ✅ Blueprint (00_Project_Blueprint.md) — 技术栈、FlowEngine设计、LogicFlow选型、分区表
- ✅ PRD (01_PRD.md) — 轮次日志、连通性校验算法
- ✅ Database Design (02_Database_Design.md) — 24 表 + 完整SQL含分区
- ✅ API Design (03_API_Design.md) — 99 端点 + 批量保存 + 并发安全 + 错误码
- ✅ Frontend (Vue3 + LogicFlow + Element Plus) — 全部页面完成
- ✅ Backend (FastAPI + SQLAlchemy + JWT) — 全部模块完成
- ✅ Flow Engine (FlowEngine 类 → API 层调用) — BFS 激活/传播/fork-join 汇合
- ✅ 自动化测试 317 条（225 单元 + 65 集成 + 27 MySQL 真实），无已知未修复问题
- ✅ 首页柱状图重写、签批预览、通知系统（WebSocket + 30s 轮询兜底）
- ✅ 批准人（Endorser）+ 难度等级、方案（Proposal）模块、文件模板、节点预设
- ✅ 截止时间逾期/临期行标色（全部列表页）
- ✅ 管理员可不归属组织（organization_id 改可空）
- ✅ UI 简化：校验人/审批人改为单选 + 中间节点支持驳回到历史节点 + 安全加固
- ✅ 第三轮全量审计修复：致命 5 + 高危 4 + 中危 13，共 22 项（Phase 11-14）
- ✅ 第四轮全栈深度审计：5 代理并行扫描 100+ 文件，修复致命 6 + 高危 10 + 中危 15，共 31 项（Phase 15）
- ✅ 数据库隔离级别加固：READ COMMITTED 防 fork-join 并发竞态
- ✅ 前后端字段对齐：NodeOverride 签名字段 / template type / endorsements 等
- ✅ 第五轮架构增强：JWT 黑名单（Redis DB 2）+ must_change_password 前后端双重拦截 + 401 跳转状态保持 + 低危项清零（Phase 16）
- ✅ 第六轮全栈审查（2026-08-03）P0 上线阻断全部修复：模板ZIP下载鉴权 / folder_name路径穿越 / 签名file_id越权 / fork-join驳回卡死 / must_change_password死循环+改密流程 / 前端57个TS错误清零（vue-tsc -b 0 + build 通过） / WS鉴权完整化 / 角色降级即时生效（P0-4 审批死锁经确认撤销）
- - [ ] 中危项按需修复
- ✅ 数据量性能防护（2026-08-05）：首页/超期页删 3 个白耗查询（任务分布/超期列表/个人计数——前端均不消费）；卡点追踪 SQL 层 limit 100 + 超期 4 类 limit 50，均返回真实总数供前端提示；四张运行时表加 `idx_status` 单列索引（Alembic `b1c2d3e4f5a6`），EXPLAIN 验证超期查询转索引 range scan。**观察项**：列表页 keyword ngram 全文索引、通知 `(user_id, created_at)` 索引（数据量极大时再评估）
- ✅ 首页发起/归档趋势图（2026-08-05）：统计卡片下方新增全宽卡片，发起量 vs 归档量双折线（手绘 SVG，无第三方图表库，与 PieChart/BarChart 风格一致），月度（默认近 12 个月 + 年份下拉回看历史）/ 年度（全部年份）粒度切换，跟随项目/方案 Tab；新接口 `/dashboard/trends`（独立聚合不塞大接口，月/年 GROUP BY + 补零连续，口径与统计卡片一致）；flow_instances 加 `idx_initiated_at` / `idx_completed_at`（Alembic `c2d3e4f5a6b7`）。**观察项**：年度全历史聚合百万级再评估
- ✅ 第七轮全栈审查修复（2026-08-05）：7 代理并行扫 230+ 文件 → 0 致命 / 2 高危 / 34 中危全部修复 + 部分低危，296 测试全过 + vue-tsc 0 错 + build 过。**产品口径确认**：项目/方案列表与详情全员可见（H2 resolve_org_scope 改纯透传）。高危：发起模式不再写回共享模板（改 node_overrides 快照解耦，新增节点发起拦截）。中危重点：实例详情/WS 密码版本/换人/方案人员校验、实例行锁+节点行锁+签名进程锁补全、上传流式限大小+尺寸预检、ZIP 条目清洗、方案签名丢失、同名实例查重、dashboard 改 template_type 快照口径、发起模板结构校验、前端筛选重置页码/弹窗不丢数据/WS 全局单例/竞态序号防护/本月归档跳转筛选。**低危剩余（评估后保留，改动面大或低风险）**：reject 驳回 N+1、通知 WS 先于提交（幽灵通知）、storage.py 死代码删除、签名路径 CWD 依赖、pdf_signature_offset 无效配置、前端上传 30s 超时/下载助手抽取等
- ✅ 轻量快扫（2026-08-06）：4 代理快扫第七轮改动域，修 6 项回归——①WS manualClose 残留（登出再登录+网络抖动后不再重连，connect 入口重置）②M3 签名图尺寸预检被 except 吞掉（预检移出 try）③M19 本月归档竞态覆盖（子组件带日期 vs 父无日期并发，fetchInstances 兜底 initDateRange）④InstanceTable 日期 watch 深页码/残留 ⑤ABBA 死锁（approve/endorse/check 统一「实例→节点→记录」锁序，与 change_personnel 一致，消除换人 vs 审批/校验死锁窗口）⑥M2 改密/重置密码后踢旧 WS 连接（disconnect_user）。**产品口径确认**：文件下载同组织成员可下载（跨所参与者保留）。**部署口径确认**：单进程部署（约 100 人同时在线），M25 进程内签名锁够用。323 测试全过 + vue-tsc 0 错 + build 过。**低危排队**：GET_LOCK 早于 commit 释放（撞唯一索引 500）、validate_user_ids_exist 不查 is_active、_pdf_locks 字典不清理、pass_check 无审批人分支终态校验

- ✅ 部署就绪修复（2026-08-06）：上线前核对部署链路，实测发现全新库建表阻断（alembic 迁移链 cdc82f5bf321 起是「修正注释」的增量迁移、不建主表，全新空库 upgrade head 报 1146 表不存在）→ 新增 `app/core/deploy_db.py`（create_all 建当前结构 + operation_logs 分区 p2026-p2028+p_future 兜底 + alembic stamp head，`python -m app.core.deploy_db` 一条命令建库，不动历史迁移，已有库升级仍走 upgrade head）；PDF 转换依赖独立 ARQ worker 进程 → 04_Deployment.md 补 `python -m arq app.worker.WorkerSettings` + systemd 双 unit；Redis 硬依赖配置补全（.env.example/文档）；部署口径单进程落文档（--workers 4 → 单进程）；LibreOffice Semaphore 2→4；seed 替换手动 INSERT roles；/api/v1/health 加 DB/Redis 探活（异常 503，供监控）。324 测试全过。**低危排队**：GET_LOCK 早于 commit 释放（撞唯一索引 500）、validate_user_ids_exist 不查 is_active、_pdf_locks 字典不清理、pass_check 无审批人分支终态校验

- ✅ 低危项修复（2026-08-06）：①GET_LOCK 早于 commit 释放撞唯一索引——`ensure_proposal_template` 改**锁内 commit**（GET_LOCK 绑定连接、commit 不释放锁；释放前完成事务，后到请求复用模板不重复创建）②`validate_user_ids_exist` 加 is_active 过滤（禁用用户视为不可用，4 处调用方文案改「不存在或已停用」，防任务派给无法登录用户卡死）③`_pdf_locks` 改 `weakref.WeakValueDictionary` 防内存增长（持局部强引用防「创建即回收」KeyError）④reject 驳回下游文件查询改批量 IN（终审/中间 2 处 N+1）⑤pass_check 无审批人终态校验、幽灵通知**评估后保持记录**（并发已被节点行锁覆盖 / 改动面大）。新增 2 个 MySQL 集成测试（is_active 过滤 + GET_LOCK 并发只建 1 模板）。326 测试全过。**低危排队**：pass_check 无审批人分支终态校验、幽灵通知（WS 先于提交）、storage.py 死代码删除、签名路径 CWD 依赖、pdf_signature_offset 无效配置、前端上传 30s 超时/下载助手抽取

- ✅ 剩余低危项修复（2026-08-06）：①删除死代码 `app/core/storage.py`（确认 app+tests 零引用，路径解析已由 `utils/file_utils.py resolve_file_path` 统一承担）②STORAGE_ROOT CWD 依赖防御——config.py 加 field_validator 把相对路径解析为基于 backend 目录的绝对路径（消除「从错误 CWD 启动」存储漂移）③前端上传 30s 超时放宽（uploadTaskFile 单独 120s，覆盖 ≤50MB 大文件）④前端下载逻辑抽取 `api/download.ts downloadBlobResponse`（task/template 4 处重复 blob 下载统一，非 2xx 时解析后端错误消息）。**调查确认**：pdf_signature_offset 为无效配置（`_SIG_KEYS` 读取但签名坐标计算只用 x/y，offset 从未参与；清理需删 settings/_SIG_KEYS/seed/configs 白名单/.env 共 7 处入口，待定）。326 测试全过 + vue-tsc 0 错 + build 过。**低危排队**：pass_check 无审批人分支终态校验、幽灵通知（WS 先于提交）、pdf_signature_offset 无效配置（待定是否清理）

- ✅ 文档全量对齐（2026-08-10）：3 代理并行扫描 6 份使用/设计文档 vs 代码现状，修正——README/Developer_Documentation（测试 317/190→326、端点 99→92、建库命令→deploy_db、补 Redis/LibreOffice 必需 + ARQ worker、删无效 DATABASE_URL）；00_Blueprint/01_PRD/02_Database_Design/03_API_Design（表数 22/21→24、端点 90/72→92、Semaphore 2→4、通知 8→9、roles 改 seed 创建、分区改 deploy_db 创建、迁移历史修正「初始迁移不建主表」、更新日期统一 2026-08-10）。历史记录文档（CHANGELOG/AUDIT_FIX_LOG/Learning_Journal/docs/audit）作为历史快照保留不改。326 测试全绿。

- ✅ 注释质量快扫修复（2026-08-10）：3 代理扫 23 条确定注释问题全修——后端（pdf_converter Semaphore 2→4、`_helpers` 状态集合/已删函数引用、delete 删除顺序补 Endorsement、endorsement 签名位置改「API 层写 PDF」、supplement 重复编号、config isolation_level 机制、rate_limit 阈值 300、check 退回必填描述、error_codes 分组移 PDF_CONVERSION_FAILED）；前端（BarChart/TrendChart niceMax 示例、TaskDetail 轮询间隔 1s、签名应用范围、序列化共用注释、toast 噪音、编号残留、router 菜单补方案管理、instance 错位注释）。**顺带修**：`_batch_get_active_deadlines` 硬编码 `arrived/pending/processing` 无效状态值（非 InstanceNodeStatus 合法值，P1-16 教训残留），改复用 `ACTIVE_NODE_STATUSES`（行为不变）。326 测试全绿 + vue-tsc 0 错。

- ✅ 内网部署就绪增强（2026-08-10）：①`deploy_db.py` 分区改为**当年起未来 10 年 + p_future 兜底**（动态生成 `_build_partition_ddl`，实测 11 分区 p2026-p2035+p_future，10 年内免维护）②新增 `docs/部署实操教程-Linux.md` 从零到上线 11 阶段（含内网专项：离线 pip wheels / 前端异地构建 dist / 打包上传替代 git clone，因公司内网访问不了 GitHub）③04/02 分区说明同步（p_future 拆分改为 10 年后）。

- ✅ 文件权限口径变更（2026-08-10）：文件下载/预览由「同组织/参与者」放开为**全员可见**——与实例详情全员可见一致，解决「详情能看到文件、跨所点开 403」的矛盾（产品确认；`tasks.py download_file` 移除归属校验，清理未用 import）。326 测试全过。

- ✅ 柱状图「已完成」改「本月已完成」口径（2026-08-10）：`_get_org_overview` 的 completed_count 改为按 `completed_at >= 本月月初` 统计（非累计），避免累计完成数把各所 Y 轴拉高、运行中/终止柱不可见；前端标签改「本月完成」。饼图不受影响（只用 running_count）。2 个单元测试适配本月口径。326 测试全过。

- ✅ 柱状图已完成加「日/月/年」粒度切换（2026-08-10）：后端 `_get_org_overview` 单次 SUM(CASE) 同时统计今日/本月/本年完成数（`day/month/year_completed_count`，仅扫今年内 completed 记录），前端柱状图图例右侧加「日/月/年」切换按钮，即时切换显示对应列（默认本月，标签随粒度变「今日完成/本月完成/本年完成」）。326 测试全过 + vue-tsc 0 错 + build 过。

- ✅ 超期待办口径修复（2026-08-10）：`get_overdue_items` 超期待办任务的 task_base 状态条件由 `notin_(completed/terminated)` 改为 `in_(pending/processing)`——已提交等校验/审批/批准的 Task（WAITING_*）不再计入「待办」，归对应分类，避免超期待办重复显示校验/审批/批准环节。326 测试全过。

- ✅ 本月归档删日期回不到全部已完成修复（2026-08-10）：`FlowManagement.fetchInstances` 区分「InstanceTable 主动上抛 query」（含空日期=用户已清除，优先使用）与「无参调用」（onMounted/status 变化才 fallback initDateRange）；用户清空日期时**同步清除 URL 的 date_from/date_to**，避免 initDateRange（读 URL 参数）残留、后续无参调用又把日期补回。方案页无此逻辑（无日期预筛）。vue-tsc 0 错 + build 过。

**状态：可部署上线**

## 测试体系

| 类型 | 数量 | 位置 | 说明 |
|------|:--:|------|------|
| 单元测试 | 225 | `tests/unit/` | 内存运行，毫秒级 |
| 集成测试 | 66 | `tests/integration/` | TestClient + mock_db（含真实 SQLite 单表测试） |
| MySQL 真实测试 | 29 | `tests/mysql/` | 每测试独立引擎建表删表，SAVEPOINT 隔离 |
| **合计** | **326** | | 当前全量通过（P1-47 后测试库凭据走环境变量） |

运行：`pytest tests/ -v`（mock 测试）或 `pytest tests/mysql/ -v`（MySQL 测试，需要本地 MySQL `workflow_approval_test` 库）

## 设计约定

1. 签名坐标在系统配置中统一管理（角色维度默认位置），不在设计器节点配置中设置
2. 文件模板占位符共 15 个，日期格式统一为「YYYY年MM月DD日」
3. 表格分页统一右下角（`justify-content: flex-end`）
4. 表格操作列按钮左对齐（`justify-content: flex-start`，保留正常内边距）
5. 模板保存时自动校验结构合法性（≥3节点 + 中间节点必须配置校验人和审批人 + 全连通），不合法设计拒绝保存

每次沟通结尾都加一句"喵"

你每次在执行之前先向我提问，根据我的回答继续追问，直到你有95%的信心，完全理解我的真实需求和目标时再给出最终方案
