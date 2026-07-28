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
