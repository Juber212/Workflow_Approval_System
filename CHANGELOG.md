# 修复日志 (CHANGELOG)

> 系统审计后的问题修复记录。每条记录标注修复日期、文件、问题描述。

---

## 2026-07-23 — 系统全面审计修复

### 修复项

| # | 编号 | 严重度 | 问题 | 文件 | 状态 |
|---|------|--------|------|------|------|
| 1 | FIX-1 | 致命 | 文件模板下载 500：`doc.template_id` 引用已删除字段 | `document_service.py` | ✅ |
| 2 | FIX-2 | 致命 | NameError：`TemplateDocumentLink` 未导入 | `tasks.py` | ✅ |
| 3 | FIX-3 | 高危 | 文件模板路径重复拼接 `storage/storage/...` | `document_service.py` | ✅ |

---

### 待修复

| # | 编号 | 严重度 | 问题 | 文件 |
|---|------|--------|------|------|
| 1 | LOW-1 | 低 | 裸字符串代替枚举 | `dashboard_service.py` | ✅ |
| 2 | LOW-2 | 低 | `scalar_one()` 无结果抛500 | `approval_service.py` 等 | ✅ |
| 3 | LOW-3 | 低 | pdf_converter 吞异常无日志 | `pdf_converter.py` | ✅ |
| 4 | LOG-7 | 高 | 方案模板并发可创建重复 | `proposal_service.py` | ✅ |
| 5 | SEC-1 | 高 | 跨组织创建方案 | `proposals.py` | ✅ |
| 6 | LOG-5 | 高 | approve TOCTOU | `approval_service.py` |
| 7 | LOG-6 | 高 | pass_check TOCTOU | `check_service.py` |
| 8 | LOG-2 | 高 | reject 无行锁 | `approval_service.py` |
| 9 | LOG-3 | 高 | return_check 无行锁 | `check_service.py` |
| 10 | LOG-1 | 致命 | 物理文件先删后DB（6处） | 3个service文件 |
| 11 | LOG-4 | 高 | supplement_files 无失败清理 | `instance_service.py` |
| 12 | LOG-8 | 高 | config_service 缓存不一致 | `config_service.py` |
| 13 | FE-1 | 高 | previewFile Blob URL 泄漏 | `task.ts` |
| 14 | FE-2 | 高 | compressSignatureImage Blob URL 泄漏 | `AppLayout.vue` |
| 15 | FE-3 | 高 | formatFileSize MB计算bug | `FlowDesigner.vue` |
| 16 | MED-1 | 中 | terminate_instance 状态覆盖不全 | `instance_service.py` |
| 17 | MED-2 | 中 | task detail 静默改状态 | `task_service.py` |
| 18 | MED-3 | 中 | 前端 catch 块全空 | 15+ 文件 |
| 19 | MED-4 | 中 | TemplateDetail 无 catch | `TemplateDetail.vue` |
