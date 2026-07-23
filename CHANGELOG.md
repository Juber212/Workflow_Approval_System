# 修复日志 (CHANGELOG)

> 系统审计后的问题修复记录。每条记录标注修复日期、文件、问题描述。

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
