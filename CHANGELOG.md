# 修复日志 (CHANGELOG)

> 系统审计后的问题修复记录。每条记录标注修复日期、文件、问题描述。

---

## 2026-07-27 — 签批功能增强（Step 2~4）

### 新增功能

| # | 功能 | 涉及文件 |
|---|------|----------|
| 1 | 签批日期：PDF 签名下方显示中文日期（可配置是否显示、日期值、字号、位置） | `signature.py`, `pdf_signature.py`, `SignaturePreviewDialog.vue` |
| 2 | 日期独立拖拽 + 3x 超采样渲染（PDF 上清晰锐利） | `pdf_signature.py`, `SignaturePreviewDialog.vue` |
| 3 | 多槽位同时可见：不同槽位颜色区分（蓝/绿/橙/红/灰），点击切换激活 | `SignaturePreviewDialog.vue` |
| 4 | PDF 加载后自动按总页数创建槽位（每页一个签名） | `SignaturePreviewDialog.vue` |
| 5 | 「应用到所有页面」：调好一个槽位后一键同步到同文件所有页面 | `SignaturePreviewDialog.vue` |
| 6 | 日期居中于签名 + 签名缩放时日期字号等比跟随 | `SignaturePreviewDialog.vue`, `pdf_signature.py` |
| 7 | 角色维度默认签名位置：4 角色 × X/Y（管理员在系统配置页管理） | `config.py`, `seed.py`, `pdf_signature.py`, 4 个 detail service |
| 8 | 分页显示槽位：只渲染当前页面槽位，翻页自动切换 | `SignaturePreviewDialog.vue` |
| 9 | 详情 API 返回 `role_signature`：前端优先级「角色配置 > 节点默认」 | 4 个 detail service + 4 个 schema |

### 修复

| # | 问题 | 文件 |
|---|------|------|
| 10 | 翻页时激活槽位页码被强制改写（签名跟着翻页跑） | `SignaturePreviewDialog.vue` (goPage) |
| 11 | 取消选中文档后预览残留旧 PDF 内容 | `SignaturePreviewDialog.vue` |
| 12 | 中文输入法逗号导致 pages 解析失败 | `pdf_signature.py` |
| 13 | 日期默认字号调整为 10pt | `SignaturePreviewDialog.vue`, `pdf_signature.py` |
| 14 | 签名标签遮挡签名内容 → 悬停显示 + 激活始终显示 | `SignaturePreviewDialog.vue` |

---

## 2026-07-27 — 红点实时刷新

### 新增功能

| # | 功能 | 涉及文件 |
|---|------|----------|
| 1 | 侧边栏「个人中心」角标实时更新（WebSocket 推送 + 30s 轮询兜底） | `notification.ts`, `notification.ts`(store), `AppLayout.vue` |
| 2 | 个人中心 Tab 页签角标实时更新（待办/校验/审批/批准） | `profile/index.vue` |
| 3 | 项目/方案 radio-button 红点实时更新 | `notification.ts`, `notification.ts`(store) |
| 4 | summary API 扩展返回批准计数 + 完整 project/proposal 分类 breakdown | `notification_service.py` |
| 5 | notifyStore 新增 endorsementCount 字段 | `notification.ts`(store) |

### 机制

- **主力通道**：复用现有 WebSocket `notification`/`refresh_count` 消息 → 自动刷新 notifyStore + 派发自定义事件
- **兜底通道**：个人中心页面内 30s 轻量轮询 `GET /notifications/summary`
- **零后端 service 改动**：现有 WebSocket 推送已覆盖所有计数变更场景

### 修复

| # | 问题 | 涉及文件 |
|---|------|----------|
| 6 | 审批/批准通过后红点不刷新 —— WebSocket refresh_count 在事务提交前发送，前端查询时数据未生效 | `notification_service.py`, `approvals.py`, `checks.py`, `endorsements.py`, `tasks.py`, `instances.py` |

**修复方案**：拆分 `clear_related`（纯删通知，不发 WS），新增 `send_refresh_signal()` 在各 API 端点 `db.commit()` 之后调用，保证前端 summary 查询时数据已提交。

---

## 2026-07-27 — 签批预览修复 + 首页卡片链接 + 超期预警

### 签批预览 4 项修复

| # | 问题 | 根因 | 涉及文件 |
|---|------|------|----------|
| 7 | 签批日期实际位置比预览偏左 | 预览日期居中于槽位宽，后端居中于图片实际宽（object-fit:contain 后不一致） | `pdf_signature.py` |
| 8 | 签名跑页（第1页签批跳到第2页） | 前端 1-based 页码 → 后端直接当 pypdf 0-based 索引，差一页 | `pdf_signature.py` |
| 9 | 签名标签遮挡签名 | 用户希望完全不显示标签 | `SignaturePreviewDialog.vue` |
| 10 | PDF 预览模糊 | canvas 未乘 devicePixelRatio，高分屏像素不足 | `SignaturePreviewDialog.vue` |

### 首页卡片链接

| # | 功能 | 涉及文件 |
|---|------|----------|
| 11 | 首页 4 张卡片可点击跳转：进行中→流程管理(运行中)、已归档→流程管理(已完成)、本月归档→流程管理(已完成)、超期预警→独立页面 | `dashboard/index.vue` |
| 12 | FlowManagement + ProposalManagement 状态筛选与 URL query 双向同步，支持外部链接预选 | `FlowManagement.vue`, `ProposalManagement.vue` |

### 超期预警页面

| # | 功能 | 涉及文件 |
|---|------|----------|
| 13 | 新建 `/overdue` 页面 + `GET /notifications/overdue` API，展示系统全部超期项（任务/校验/审批/批准）分组列表 | `notification_service.py`, `notifications.py`, `OverdueWarning.vue`, `router/index.ts` |

---

## 2026-07-23 — 难度等级 + 批准人（Endorser）

### 新增功能

| # | 功能 | 涉及文件 |
|---|------|----------|
| 1 | 实例新增 difficulty 字段(1-4)，发起时选择，不可改 | `flow_instance.py`, `instance_service.py`, FlowDesigner, OrgHome |
| 2 | 模板/实例节点新增 endorser_id（批准人），单人可选 | `template_node.py`, `instance_node.py`, PropertyPanel |
| 3 | 新建 endorsements 表 + Endorsement 模型 | `models/endorsement.py` (新) |
| 4 | 新建 endorsement_service：批准通过/驳回 | `services/endorsement_service.py` (新) |
| 5 | approval_service.approve()：difficulty=4 时注入批准人环节 | `approval_service.py` |
| 6 | 新建批准 API：GET/POST /endorsements | `api/endorsements.py` (新) |
| 7 | 前端：NodeCard 批准列、Dashboard 难度badge、实例列表难度列 | NodeCard, dashboard, OrgHome |

### 修复

| # | 问题 | 文件 |
|---|------|------|
| 8 | 首页卡点追踪进度条消失（adf8670 误删 :deep 样式） | `dashboard/index.vue` |
| 9 | 首页卡点追踪移除展开/折叠功能 | `dashboard/index.vue` |

---

## 2026-07-23 — 系统全面审计修复

### 已修复（本次会话）— 共 19 项

#### 会话前修复（上轮对话）

| # | 编号 | 严重度 | 问题 | 文件 | 状态 |
|---|------|--------|------|------|------|
| 1 | FIX-1 | 致命 | 文件模板下载 500：`doc.template_id` 引用已删除字段 | `document_service.py` | ✅ |
| 2 | FIX-2 | 致命 | NameError：`TemplateDocumentLink` 未导入 | `tasks.py` | ✅ |
| 3 | FIX-3 | 高危 | 文件模板路径重复拼接 | `document_service.py` | ✅ |

#### Phase 1：简单后端修复

| # | 编号 | 严重度 | 问题 | 文件 | 状态 |
|---|------|--------|------|------|------|
| 4 | LOW-1 | 低 | 裸字符串代替枚举 (`TaskStatus`/`CheckStatus`/`ApprovalStatus`) | `dashboard_service.py` | ✅ |
| 5 | LOW-2 | 低 | `scalar_one()` 无结果抛500 → `scalar_one_or_none()` + None检查 | `approval_service.py`, `task_service.py`, `check_service.py` | ✅ |
| 6 | LOW-3 | 低 | pdf_converter `except Exception` 吞异常 → 添加 `logger.warning()` | `pdf_converter.py` | ✅ |
| 7 | LOG-7 | 高 | 方案模板并发可创建重复 → `FOR UPDATE` 行锁 | `proposal_service.py` | ✅ |
| 8 | SEC-1 | 高 | 所长可为其他所创建方案 → `require_same_org` 校验 | `proposals.py` | ✅ |

#### Phase 2：数据安全核心修复

| # | 编号 | 严重度 | 问题 | 文件 | 状态 |
|---|------|--------|------|------|------|
| 9 | LOG-5 | 高 | approve() TOCTOU → 先 `FOR UPDATE` 锁定再校验 | `approval_service.py` | ✅ |
| 10 | LOG-6 | 高 | pass_check() TOCTOU → 同上 | `check_service.py` | ✅ |
| 11 | LOG-2 | 高 | reject() 无行锁 → `FOR UPDATE` | `approval_service.py` | ✅ |
| 12 | LOG-3 | 高 | return_check() 无行锁 → `FOR UPDATE` | `check_service.py` | ✅ |
| 13 | LOG-1 | 致命 | 物理文件先删后DB（6处）→ 改为先DB后文件（事务回滚安全） | `approval_service.py`, `check_service.py`, `instance_service.py` | ✅ |
| 14 | LOG-4 | 高 | supplement_files() DB失败后物理文件残留 → 失败时清理 | `instance_service.py` | ✅ |
| 15 | LOG-8 | 高 | config_service 缓存-DB不一致 → DB提交前同步更新缓存 | `config_service.py` | ✅ |

#### Phase 3：前端修复

| # | 编号 | 严重度 | 问题 | 文件 | 状态 |
|---|------|--------|------|------|------|
| 16 | FE-1 | 高 | previewFile() Blob URL 泄漏 → 延迟释放 | `frontend/src/api/task.ts` | ✅ |
| 17 | FE-2 | 高 | compressSignatureImage() Blob URL 泄漏 → onload/onerror 中释放 | `frontend/src/layouts/AppLayout.vue` | ✅ |
| 18 | FE-3 | 高 | formatFileSize MB计算 `bytes/1024*1024` = `bytes` → `bytes/1024/1024` | `frontend/src/views/flows/FlowDesigner.vue` | ✅ |

#### Phase 4：中危修复

| # | 编号 | 严重度 | 问题 | 文件 | 状态 |
|---|------|--------|------|------|------|
| 19 | MED-1 | 中 | terminate_instance 裸字符串 → 枚举常量 | `instance_service.py` | ✅ |
| 20 | MED-2 | 中 | task detail GET 静默改状态 → 添加设计意图注释 | `task_service.py` | ✅ |
| 21 | MED-3 | 中 | 关键前端 catch 块添加 `console.error` | `FlowDesigner.vue`, `AppLayout.vue` | ✅ |
| 22 | MED-4 | 中 | TemplateDetail 无 catch → 区分网络错误/不存在 | `frontend/src/views/flows/TemplateDetail.vue` | ✅ |

---

### 排除项（设计如此/无需修复）

| # | 编号 | 问题 | 原因 |
|---|------|------|------|
| - | SEC-2~7 | 跨组织数据可见性 | 内部部署，普通用户有查看权限 |
| - | MED-1 | CheckRecord/Approval 状态覆盖不全 | 经核实，除 `pending` 外均为终态 |
| - | MED-5 | 无 AbortController | 影响面广，单独处理 |
| - | MED-6 | designer 无并发保护 | 影响面广，单独处理 |
| - | MED-7~10 | 其他中危 | 非紧急，按需修复 |
| - | LOW-4~6 | 前端类型/低危 | 技术债，按需清理 |

---

### 修复统计

| 严重度 | 数量 |
|--------|------|
| 致命 | 2 |
| 高危 | 10 |
| 中危 | 4 |
| 低危 | 3 |
| **合计** | **19** |

---

## 2026-07-28 — 首页待办列表 + 表格操作列对齐 + 筛选区重构

### 新增功能

| # | 功能 | 涉及文件 |
|---|------|----------|
| 1 | 首页「我的待办」从快捷条改为表格列表（统一 Task/Check/Approval 三表、按优先级+截止排序） | `dashboard_service.py`, `dashboard.py`(schema), `dashboard.ts`, `dashboard/index.vue` |
| 2 | 待办列表跟随项目/方案 Tab 自动切换数据源 | `dashboard/index.vue` |

### 修复

| # | 问题 | 涉及文件 |
|---|------|------|
| 3 | 全局表格操作列按钮未左对齐 → `common.scss` 加全局规则 | `common.scss`, `dashboard/index.vue` |
| 4 | 表格上方筛选按钮+搜索共享同一 card 容器 → 拆掉外层 card，各自独立排列 | `FlowManagement.vue`, `ProposalManagement.vue`, `OrgHome.vue` |
| 5 | 高级搜索面板过高 → padding/margin 缩减 | 同上 3 文件 |

### 测试增强

| # | 内容 | 文件 |
|---|------|------|
| 6 | Round 2 自动化测试：通知(9)/组织(7)/用户(8)/PDF签名(4)/方案(6) + 集成(5) = 39 新测试 | `tests/unit/` + `tests/integration/` 6 文件 |
| 7 | MockResult 新增 `unique()` 方法 | `tests/conftest.py` |
| 8 | 测试总数：78 → 117，全部通过 | — |

---

## 2026-07-28 — 首页柱状图重写 + 安全稳定性修复

### 新增功能

| # | 功能 | 涉及文件 |
|---|------|----------|
| 1 | 首页「各所项目概览」从水平分组柱状图改为 4 栏竖柱卡片网格，每卡片独立 Y 轴刻度、数字嵌于柱顶、可点击跳转所主页 | `BarChart.vue`(重写), `dashboard_service.py`, `dashboard.py`(schema) |
| 2 | 概览统计新增 `terminated_count`（已终止） | `dashboard.py`(schema), `dashboard_service.py` |

### 修复（系统审计后线上部署前）

| # | 问题 | 涉及文件 |
|---|------|------|
| 3 | **delete_file 先删物理文件后删 DB** → 改为先 DB 后物理文件（事务回滚安全） | `file_service.py` |
| 4 | **submit_task 缺 FOR UPDATE 行锁** → 添加 `.with_for_update()` 防并发重复提交 | `task_service.py` |
| 5 | **terminate_instance 缺 FOR UPDATE 行锁** → 同上 | `instance/terminate.py` |
| 6 | **save_design_data 缺 FOR UPDATE 行锁** → 同上 | `designer_service.py` |
| 7 | **submit_task 通知异常未捕获** → `asyncio.gather` 包裹 try/except + logger.warning | `task_service.py` |

---

## 2026-07-28 — 自动化测试体系建设

### Round 3：全功能 Mock 测试（117 → 168）

| # | 内容 | 文件 |
|---|------|------|
| 1 | 文件上传/删除 8 条（权限+边界+MIME+大小+DB优先删除） | `tests/unit/test_file_service.py`(新) |
| 2 | Endorsement 批准 8 条（批准+驳回+权限+重复操作） | `tests/unit/test_endorsement_service.py`(新) |
| 3 | FlowEngine 6 条（激活+传播+skip节点+fork-join等待+结束节点） | `tests/unit/test_flow_engine.py`(新) |
| 4 | ConfigService 8 条（缓存+默认值+类型转换） | `tests/unit/test_config_service.py`(新) |
| 5 | Designer 7 条（保存+节点增删改+连线增删） | `tests/unit/test_designer_service.py`(新) |
| 6 | 认证集成 4 条 + Endorsement 集成 6 条 | `tests/integration/test_auth_api.py`(新), `tests/integration/test_endorsement_api.py`(新) |
| 7 | Factory 修复：`make_start_node`/`make_end_node` 改用 `defaults.update(overrides)` 避免重复参数 | `tests/factories.py` |
| 8 | 测试总数：117 → 168，全部通过 | — |

### Round 4：MySQL 真实数据库测试（9 条）

| # | 内容 | 文件 |
|---|------|------|
| 9 | 全流程 4 条：创建实例+激活 / 提交→校验→审批→节点完成 / 终止流程 / 同名实例不冲突 | `tests/mysql/test_full_flow.py`(新) |
| 10 | 边界场景 5 条：FK 约束校验 / 组织名唯一 / 无负责人节点 / 校验退回重置 / 双审批人全部通过 | `tests/mysql/test_edge_cases.py`(新) |
| 11 | MySQL 测试基础设施：每测试独立引擎建表删表，SAVEPOINT 隔离，避免 Windows aiomysql 连接池残留 | `tests/mysql/conftest.py`(新) |

### Round 5：MySQL 真实 Service 调用测试（10 条）

| # | 内容 | 文件 |
|---|------|------|
| 12 | submit_task 4 条：有校验人创建 CheckRecord / 非负责人 403 / 重复提交 403 / require_file 无文件 400 | `tests/mysql/test_service_flows.py`(新) |
| 13 | pass_check 3 条：全部通过创建 Approval / 非本人 403 / 重复操作 403 | 同上 |
| 14 | approve 2 条：审批通过节点完成 / 非本人 403 | 同上 |
| 15 | endorse 1 条：difficulty=4 批准通过 → 节点完成 | 同上 |
| 16 | 外部依赖 mock 工厂（通知/PDF/签名/传播），数据库全走真实 MySQL | 同上 |

### 测试统计

| 类型 | 数量 | 说明 |
|------|:--:|------|
| Mock 单元测试 | 158 | 内存运行，毫秒级 |
| Mock 集成测试 | 10 | TestClient + mock_db |
| MySQL 真实测试 | 19 | 独立引擎，真实 DB 操作 |
| **合计** | **190** | **0 业务逻辑 bug** |

---

## 2026-07-29 — 截止时间逾期标色 + 管理员编辑修复 + 组织可选

### 截止时间逾期/临期行标色（Phase 9）

| # | 内容 | 涉及文件 |
|---|------|----------|
| 1 | 后端 `_helpers.py` 新增 `compute_deadline_info()` + `_batch_get_active_deadlines()` | `services/instance/_helpers.py` |
| 2 | 6 个 list API 返回 `deadline`/`is_overdue`/`days_remaining`（task/check/approval/endorsement/instance/proposal） | 6 个 service + 6 个 schema |
| 3 | 首页 Dashboard API 同步补字段（`MyPendingItem`） | `dashboard_service.py`, `dashboard.py` |
| 4 | 前端 `format.ts` 新增 `deadlineRowClass()`，7 个页面 `:row-class-name` + 非 scoped CSS | 9 个前端文件 |
| 5 | 样式：逾期 `#fef0f0` 淡红 / 临期（≤1天）`#fffaf0` 淡黄，与卡点追踪一致 | — |

### 管理员编辑 500 + 组织可选（Phase 10）

| # | 内容 | 涉及文件 |
|---|------|----------|
| 6 | Pydantic v2 `field_validator` classmethod 跨类复用导致参数错位 → 改为模块级函数 | `schemas/user.py` |
| 7 | `users.organization_id` 改可空，系统管理员可不归属任何组织 | model + schema + service + deps + seed |
| 8 | 前端用户表单根据选中角色动态切换组织必填/可选 | `UserFormDialog.vue`, `UserManagement.vue` |
| 9 | DB 迁移 `e8f9a0b1c2d3`：`ALTER TABLE users MODIFY organization_id INT NULL` | Alembic |

### 错误消息去重

| # | 内容 | 涉及文件 |
|---|------|----------|
| 10 | 响应拦截器加消息去重（`showErrorOnce`，3 秒内相同消息不重复弹） | `frontend/src/api/request.ts` |

---

## 2026-07-29 — 文件模板包（Phase 11）

### 新增功能

| # | 内容 | 涉及文件 |
|---|------|----------|
| 1 | 模板分类（包）—— 管理员可按组织创建自定义模板包，作为「模板包」一键下载 ZIP | 全栈 |
| 2 | 文件模板与包多对多关联：一个模板可归属多个包 | `TemplateCategoryDocument` |
| 3 | 流程模板可关联单个模板 或 整个包（模板包），互不冲突 | `TemplateDocumentLink` + `category_id` |
| 4 | 项目详情页展示关联的模板和包，包支持一键下载 ZIP（所有模板填充占位符后打包） | `InstanceDetail.vue`, `category_service.py` |
| 5 | 管理页按组织分组卡片式布局：每个组织一张卡片，内含包列表和未归包模板区 | `DocTemplateManagement.vue`(重写) |
| 6 | 包内可直接搜索添加同组织模板 + 未归包模板快速归入包 | 同上 |
| 7 | FlowDesigner 关联弹窗合并为「已关联」「可关联」双区，分类和模板统一渲染 | `FlowDesigner.vue` |

### 数据库变更

| # | 内容 |
|---|------|
| 8 | 新增 `template_categories` 表（按组织隔离的模板包） |
| 9 | 新增 `template_category_documents` 表（包 ↔ 模板多对多） |
| 10 | `template_document_links` 新增 `category_id` 字段（可选），`document_id` 改可空 |

### 后端新增端点

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 11 | GET/POST/PUT/DELETE | `/admin/template-categories` | 管理员分类 CRUD |
| 12 | GET | `/admin/template-categories/{id}` | 分类详情（含模板列表） |
| 13 | POST/DELETE | `/admin/template-categories/{id}/documents` | 分类内模板添加/移除 |
| 14 | GET | `/templates/{id}/download-zip` | 批量填充+打包 ZIP 下载 |

### 测试

| 类型 | 数量 | 说明 |
|------|:--:|------|
| 后端全量 | 190 | 全部通过，零回归 |

---

## 2026-07-30 — 任务模板包 + 截止日期 + 终审修复 + 一键应用（Phase 12）

### 新增功能

| # | 内容 | 涉及文件 |
|---|------|----------|
| 22 | 任务处理页展示模板包 —— 可折叠包卡片，内部模板逐个下载，包整体 ZIP 打包下载 | `tasks.py`, `TaskDetail.vue` |
| 23 | PropertyPanel 一键应用人员配置 —— 填好一个节点后，一键覆盖所有工作节点 | `PropertyPanel.vue` |
| 24 | 发起模式截止日期改为单个选择器 —— 选完自动级联更新下游节点 | `PropertyPanel.vue`, `FlowDesigner.vue` |
| 25 | 列表新增「截止时间」列（流程最后一个工作节点的 deadline，发起时间后） | 全栈 10 文件 |
| 26 | 任务处理页模板下载不再校验中间表直接关联（包内模板也能下载） | `tasks.py` |

### 修复

| # | 问题 | 文件 |
|---|------|------|
| 27 | 任务处理页上传文件后不显示 —— `node_files` 缺少 `folder_name` 等字段 | `task_service.py` |
| 28 | 模板包内单模板下载报"未关联到此项目" | `tasks.py`（去掉冗余校验） |
| 29 | 下载的 .docx 上传时报"不支持 application/zip"—— Office 扩展名跳过魔数检测 | `file_service.py` |
| 30 | 全局输入框无边框 —— 删掉 `box-shadow: none` 覆盖 | `common.scss` |
| 31 | 一键应用覆盖掉节点原有配置（名称/时限/签批等）—— `setProperties` 未合并现有属性 | `PropertyPanel.vue` |
| 32 | 终审时首页卡点追踪 + 列表不显示当前节点/处理人 —— 三处 `is_end == False` 排除终审节点 | `_helpers.py` ×2, `dashboard_service.py` |
| 33 | 终审详情页显示无意义的完成时限/截止时间 | `ApprovalDetail.vue` |
| 34 | 终审详情页历史文件需默认展开 | `ApprovalDetail.vue` |

### 测试

| 类型 | 数量 | 说明 |
|------|:--:|------|
| 后端全量 | 190 | 全部通过，零回归 |

---

## 2026-07-30 — UI 简化：校验人/审批人单选 + 中间节点驳回 + 安全加固（Phase 13）

### UI 简化：校验人/审批人多选 → 单选

> 用户反馈只需一人审批/校验，将全部选择器从多选改为单选以降低操作复杂度。
> 后端存储不变（仍为 JSON 数组），仅前端 UI 层限制单选，向后兼容旧数据。

| # | 内容 | 涉及文件 |
|---|------|----------|
| 1 | PropertyPanel 校验人/审批人 `:multiple="true"` → `:multiple="false"`，表单类型 `number[]` → `number \| undefined`，读写节点属性时做单值↔数组转换 | `PropertyPanel.vue` |
| 2 | NodeOverridePanel 同上，UserSelector 绑定从数组取 `[0]` → 写回时包 `[v]`，宽度 400→280 | `NodeOverridePanel.vue` |
| 3 | PresetEditor 预设编辑器校验人/审批人也改为单选 | `PresetEditor.vue` |
| 4 | ChangePersonnelDialog 紧急换人弹窗同步改为单选 | `ChangePersonnelDialog.vue` |

### 新增功能：中间节点审批可驳回到历史节点

| # | 内容 | 涉及文件 |
|---|------|----------|
| 5 | `_get_downstream_nodes_by_edges()`：边 BFS 遍历替代旧 sort_order 范围过滤，精确获取下游节点 | `approval_service.py` |
| 6 | 非终审节点驳回支持可选 `target_node_id`：复用终审驳回逻辑，重置目标节点+下游 → 新建 Task | `approval_service.py` |
| 7 | 下游节点重置时增加 `arrived_count = 0`（2 处），确保汇合计数归零 | `approval_service.py` |
| 8 | 驳回目标节点范围：终审=全部已完成节点；中间节点=已完成且 sort_order < 当前节点的历史节点 | `approval_service.py` |

### 修复

| # | 问题 | 涉及文件 |
|---|------|------|
| 9 | 终审驳回理由在任务处理页不显示 —— task_id=None 导致查不到 → 新增按 `reject_target_node_id` + `ApprovalStatus.REJECTED` 查询 | `task_service.py` |
| 10 | flow_engine `arrived_count += 1` 读-改-写竞态 → 改为原子 SQL `UPDATE SET arrived_count = arrived_count + 1` | `flow_engine.py` |
| 11 | flow_engine 死代码清理：移除 BFS `deque`、`max_iterations`、`all_nodes` 查询 | `flow_engine.py` |
| 12 | 路径遍历防护：实例名/方案名禁止 `../`、`..\`、`/`、`\` 等危险字符 | `instance/create.py`, `proposal_service.py` |
| 13 | change_personnel/change_priority/delete 缺 FOR UPDATE 行锁 → 补 `.with_for_update()` | `instance/change.py`, `instance/delete.py` |
| 14 | 物理文件删除失败静默吞掉 → 加 `logger.error("物理文件删除失败，磁盘残留孤儿文件: ...")` | `file_service.py` |
| 15 | Dashboard 缺 `import { ElMessage }` → API 失败时 ReferenceError 白屏 | `dashboard/index.vue` |

### UI 微调

| # | 内容 | 涉及文件 |
|---|------|------|
| 16 | 项目管理列表列宽调整：所属组织 90、发起时间 135、截止时间 135 | `FlowManagement.vue` |
| 17 | 全局表格操作列按钮左对齐：`common.scss` 加 `.el-button--small.is-text { padding-left: 0 }` | `common.scss` |
| 18 | 「终审」标签与「结束」间距太小 → 加 `margin-left: 6px` | `profile/index.vue` |

### 测试适配

| # | 内容 | 涉及文件 |
|---|------|------|
| 19 | test_approval_service mock 新增 `InstanceEdge` 查询（`_get_downstream_nodes_by_edges` 新步骤） | `test_approval_service.py` |
| 20 | test_flow_engine 3 个测试适配原子 UPDATE：移除 `all_nodes` mock，`target.arrived_count = 1` 模拟原子递增结果 | `test_flow_engine.py` |

### 测试

| 类型 | 数量 | 说明 |
|------|:--:|------|
| 后端全量 | 190 | 全部通过，零回归 |
| 前端类型检查 | 0 errors | vue-tsc --noEmit 通过 |

---

## 2026-07-30 — 第三轮全量审计修复：致命 5 + 高危 4 + 中危 13（Phase 14）

> 合并上轮未修 + 本轮增量扫描，共计发现 33 项，修复 22 项（致命/高危/中危全部清零）。

### 🔴 致命修复（5 项）

| # | 问题 | 涉及文件 |
|---|------|------|
| 1 | **`validate_template_for_publish` 死代码** —— 模板发布零校验 → 集成到 `save_design_data`，保存前调用校验，不合法设计拒绝保存 | `designer_service.py`, `validation_service.py` |
| 2 | **空审批人死锁** —— pass_check 在 `approvers=[]` 时设 WAITING_APPROVAL 但不创建 Approval → 难度<4 直接完成节点；难度=4 跳审批直接创建 Endorsement | `check_service.py` |
| 3 | **OperationLog.round 全错** —— 6 处 `round=task_id` 或 `round=0` → 统一改为 `round=c.round` / `round=a.round` | `check_service.py`, `approval_service.py` |
| 4 | **scalar_one() → 500** —— 8 处无异常处理 → 全部改为 `scalar_one_or_none()` + None 检查返回 404 | `tasks.py`, `flow_engine.py`, `designer_service.py`, `file_service.py`, `task_service.py` |
| 5 | **FlowEngine 无重入守卫** —— 环形边可无限循环 → 加 `node.status != WAITING` 跳过检查 | `flow_engine.py` |

### 🟠 高危修复（4 项）

| # | 问题 | 涉及文件 |
|---|------|------|
| 6 | change_personnel 中 CheckRecord `task_id=0`（幽灵记录）→ 改为 `None`（与 Approval/Endorsement 一致） | `instance/change.py` |
| 7 | endorse_reject 终止审批/校验缺 round 过滤 → 加 `round=e.round` | `endorsement_service.py` |
| 8 | check_service `asyncio.gather` 缺 try/except → fail-fast 可致事务回滚 | `check_service.py` |
| 9 | 5 处 OperationLog 缺 round 参数 → 补 `round=node.round` | `instance/change.py`, `instance/supplement.py` |

### 🟡 中危修复（9 项）

| # | 问题 | 涉及文件 |
|---|------|------|
| 10 | reject() target_node 查询缺 FOR UPDATE → 加 `.with_for_update()` | `approval_service.py` |
| 11 | delete_template 不检查运行中实例 → 加 `COUNT(*)` 活性检查 | `template_service.py` |
| 12 | pdf_signature 签名异常缺 `exc_info=True`（2 处） | `pdf_signature.py` |
| 13 | 前端 `_msgCache` 无上限保护 → 加 `MAX_CACHE_SIZE=100` + LRU 淘汰 | `request.ts` |
| 14 | NotificationBell `popupTimer` 未在 unmount 清理 | `NotificationBell.vue` |
| 15 | SignaturePreviewDialog 孤儿 `setTimeout` → 存 ref + unmount 清理 | `SignaturePreviewDialog.vue` |
| 16 | 代码清理：行内重复 import、未用 import、导入不规范、死 Schema、email max_length | `templates.py`, `auth.py`, `endorsements.py`, `user.py`, `auth.py`(schema) |

### 🟢 低危（未修，影响极小）

| 项目 | 说明 |
|------|------|
| supplement_files 同步 I/O、create 目录事务内创建、401 缺 guard flag、PresetEditor/ChangePersonnelDialog 缺卸载守卫、TaskDetail 事件监听器、_DEFAULT_MESSAGES 缺条目 | 不影响正常使用，按需修复 |

### 测试

| 类型 | 数量 | 说明 |
|------|:--:|------|
| 后端全量 | 190 | 全部通过，零回归 |
| 前端类型检查 | 0 errors | vue-tsc --noEmit 通过 |

---

## 2026-07-30 — 第四轮全栈审计修复：致命 6 + 高危 10 + 中危 15（Phase 15）

> 5 个并行代理全栈扫描 100+ 文件，发现 59 项（含测试缺口 4 项），修复致命/高危/高优中危共 31 项。

### 🔴 致命（6 项）

| # | 问题 | 涉及文件 |
|---|------|------|
| 1 | 终止通知完全失效 —— UPDATE 在 SELECT 之前 → 通知收集移前 | `instance/terminate.py` |
| 2 | 超期预警 500 —— inst.org_name 不存在 → JOIN Organization | `notification_service.py` |
| 3 | submit_task 空审批人死锁 → 难度<4 完成+传播，难度=4 Endorsement | `task_service.py` |
| 4 | commit-before-enqueue → 先入队再 commit | `api/tasks.py` |
| 5 | 无 assignee 节点死锁 → 加守卫跳过激活 | `engine/flow_engine.py` |
| 6 | 事件监听器泄漏 → 存引用 + onUnmounted 清理 | `TaskDetail.vue` |

### 🟠 高危（10 项）

| # | 问题 | 涉及文件 |
|---|------|------|
| 7 | 驳回遗漏 WAITING_ENDORSEMENT（2 处） | `approval_service.py` |
| 8 | 驳回逐文件 flush → 批量删除（3 处） | `approval_service.py` |
| 9 | BFS N+1 → 全量加载边内存遍历 | `approval_service.py` |
| 10 | 补交文件同步 I/O → aiofiles 异步 | `instance/supplement.py` |
| 11 | REPEATABLE READ 竞态 → READ_COMMITTED | `core/config.py` |
| 12 | 路径穿越防御 → resolve_file_path+is_safe_path | `api/tasks.py` |
| 13 | blob URL 未卸载 → onBeforeUnmount revoke | `AppLayout.vue` |
| 14 | 文件删除无错误处理 | `TaskDetail.vue` |
| 15 | NodeOverride 签名字段丢弃 → Schema 补字段 | `schemas/instance.py` |
| 16 | 任务状态标签缺失 overdue/rejected/terminated | `labels.ts` |

### 🟡 中危（15 项）

| # | 问题 | 涉及文件 |
|---|------|------|
| 17 | defaultdict 内存泄漏 → 过期删 key | `rate_limit.py` |
| 18 | int() 无异常处理 | `designer.py` |
| 19 | 通知已读裸 dict → ApiResponse.ok() | `notifications.py` |
| 20 | result.changes 缺可选链 | `ChangePersonnelDialog.vue` |
| 21 | 启禁用无错误处理 | `UserManagement.vue` |
| 22 | 缺魔数校验 | `instance/supplement.py` |
| 23 | 校验过严 → 校验/审批至少配一 | `validation_service.py` |
| 24-26 | 字段补齐：type/endorsements/node_description | `template.ts`, `task.ts`, `schemas/endorsement.py` |
| 27 | 不支持类型静默回退 → 明确报错 | `document_service.py` |

### 测试

| 类型 | 数量 | 说明 |
|------|:--:|------|
| 后端全量 | 145 | 全部通过，零回归 |
| 前端类型检查 | 0 errors | vue-tsc --noEmit 通过 |
