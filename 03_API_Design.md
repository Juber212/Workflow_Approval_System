# 企业流程审批系统 — API 接口设计

> **版本**：3.1 | **状态**：与代码同步 | **更新**：2026-07-29
>
> 90 HTTP 端点 + 1 WebSocket。完整定义见 FastAPI Swagger `/docs`。

---

## 1. 基础规范

### 1.1 请求格式

- Content-Type: `application/json`（文件上传用 `multipart/form-data`）
- 认证：`Authorization: Bearer <JWT_TOKEN>`
- Base URL: `/api/v1`

### 1.2 统一响应格式

```json
{
  "code": 20000,
  "message": "操作成功",
  "data": { ... }
}
```

| 状态 | code 格式 | HTTP 状态码 |
|------|-----------|:--:|
| 成功 | 20000 | 200 |
| 参数/校验错误 | 40000 / 40001 / 40900-40908 | 400 / 409 / 422 |
| 未认证 | 40100-40103 | 401 |
| 无权限 | 40300-40310 | 403 |
| 未找到 | 40400 | 404 |
| 不支持的格式 | 41500-41501 | 415 |
| 限流 | 42900 | 429 |
| 服务器错误 | 50000-50001 | 500 |

### 1.3 分页格式

```json
{
  "items": [ ... ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 1.4 查询参数约定

- 分页：`?page=1&page_size=20`（page_size 可选值：20/50/100）
- 搜索：`?keyword=xxx`
- 筛选：`?status=pending&instance_type=project`
- 排序：各端点自行约定

---

## 2. 端点清单（72 个）

### 2.1 认证（6 个）— `/api/v1/auth`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| POST | `/auth/login` | 无 | 用户名密码登录 |
| GET | `/auth/me` | 用户 | 当前用户完整信息（含角色、组织、签名、强制改密标记） |
| POST | `/auth/logout` | 用户 | 退出（Token 加入 Redis 黑名单即时失效） |
| PUT | `/auth/password` | 用户 | 修改密码 |
| POST | `/auth/signature` | 用户 | 上传签名图片 |
| GET | `/auth/users/{user_id}/signature-image` | 用户 | 获取用户签名图片 |

#### POST `/auth/login`

请求：
```json
{
  "username": "admin",
  "password": "123456"
}
```

响应：
```json
{
  "code": 20000,
  "data": {
    "access_token": "eyJhbG...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "username": "admin",
      "real_name": "管理员",
      "organization_id": 1,
      "organization_name": "一所",
      "roles": ["system_admin"],
      "signature_image": null
    }
  }
}
```

限流：**20次/分钟/IP**。失败返回 42900。

#### PUT `/auth/password`

请求：
```json
{
  "old_password": "old",
  "new_password": "new123",
  "confirm_password": "new123"
}
```

成功响应 20000，旧密码错误返回 40000。

#### POST `/auth/signature`

- Content-Type: `multipart/form-data`
- 字段：`file`（PNG 图片，透明底，≤500KB）
- 系统自动去白底 + 缩放
- 成功返回签名图片 URL

---

### 2.2 用户管理（7 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/users` | 管理员 | 用户列表（分页+搜索+组织筛选） |
| POST | `/users` | 管理员 | 新增用户 |
| PUT | `/users/{id}` | 管理员 | 编辑用户 |
| PUT | `/users/{id}/status` | 管理员 | 启用/禁用 |
| PUT | `/users/{id}/reset-password` | 管理员 | 重置密码 |
| GET | `/users/search` | 管理员/所长 | 用户搜索（active only） |
| GET | `/roles/options` | 管理员 | 角色下拉选项 |

#### GET `/users`

查询参数：`?page=1&page_size=20&keyword=张三&organization_id=1`

响应 data：
```json
{
  "items": [{
    "id": 1,
    "username": "zhangsan",
    "real_name": "张三",
    "organization_id": 1,
    "organization_name": "一所",
    "email": "zs@example.com",
    "phone": "13800000000",
    "roles": ["user"],
    "is_active": true,
    "created_at": "2026-01-01T00:00:00"
  }],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

#### POST `/users`

请求：
```json
{
  "username": "lisi",
  "password": "123456",
  "real_name": "李四",
  "organization_id": 1,
  "role_ids": [3],
  "email": "ls@example.com",
  "phone": "13800000001"
}
```

#### PUT `/users/{id}/reset-password`

请求：
```json
{
  "new_password": "new_password"
}
```

---

### 2.3 组织管理（5 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/organizations` | 管理员 | 组织列表（分页+含所长名+用户数） |
| POST | `/organizations` | 管理员 | 新增组织 |
| PUT | `/organizations/{id}` | 管理员 | 编辑组织 |
| PUT | `/organizations/{id}/status` | 管理员 | 启用/停用 |
| GET | `/organizations/options` | 用户 | 组织下拉选项（仅启用的） |

#### GET `/organizations`

响应 data：
```json
{
  "items": [{
    "id": 1,
    "name": "一所",
    "description": "第一研究所",
    "manager_name": "王所长",
    "user_count": 15,
    "is_active": true,
    "created_at": "2026-01-01T00:00:00"
  }],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

#### POST `/organizations`

请求：
```json
{
  "name": "三所",
  "description": "第三研究所"
}
```

---

### 2.4 角色管理（1 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/roles` | 管理员 | 角色列表 |

响应 data：
```json
{
  "items": [{
    "id": 1,
    "name": "系统管理员",
    "code": "system_admin",
    "description": "系统维护者",
    "user_count": 2
  }]
}
```

V1 只读，不可新增/编辑/删除角色。

---

### 2.5 系统配置（2 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/configs` | 管理员 | 所有配置项（内存缓存） |
| PUT | `/configs` | 管理员 | 批量更新配置 |

#### GET `/configs`

响应 data：
```json
{
  "items": [{
    "id": 1,
    "config_key": "max_file_size_mb",
    "config_value": "50",
    "config_type": "int",
    "description": "文件上传大小限制（MB）"
  }]
}
```

#### PUT `/configs`

请求：
```json
{
  "configs": [
    {"config_key": "max_file_size_mb", "config_value": "100"},
    {"config_key": "access_token_expire_minutes", "config_value": "960"}
  ]
}
```

成功响应后自动刷新内存缓存。

#### 签名相关配置项

管理员可在系统配置页管理以下角色默认签名位置（X/Y 坐标）：

| config_key | 默认值 | 说明 |
|------------|--------|------|
| `pdf_signature_assignee_x` | 400 | 负责人签名默认 X 坐标 |
| `pdf_signature_assignee_y` | 100 | 负责人签名默认 Y 坐标 |
| `pdf_signature_checker_x` | 400 | 校验人签名默认 X 坐标 |
| `pdf_signature_checker_y` | 100 | 校验人签名默认 Y 坐标 |
| `pdf_signature_approver_x` | 400 | 审批人签名默认 X 坐标 |
| `pdf_signature_approver_y` | 100 | 审批人签名默认 Y 坐标 |
| `pdf_signature_endorser_x` | 400 | 批准人签名默认 X 坐标 |
| `pdf_signature_endorser_y` | 100 | 批准人签名默认 Y 坐标 |

> 优先级：个体微调 > 节点配置 > 角色配置 > Settings 默认值
> 签名页码不再配置，改为 PDF 加载后自动按总页数创建槽位。

---

### 2.6 流程模板（9 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/templates/organizations` | 用户 | 组织卡片（含各状态实例统计） |
| GET | `/templates` | 用户 | 模板列表（分页+搜索+组织筛选） |
| POST | `/templates` | 所长 | 创建模板 |
| GET | `/templates/{id}` | 用户 | 模板详情（含 nodes+edges） |
| PUT | `/templates/{id}` | 所长 | 编辑模板 |
| DELETE | `/templates/{id}` | 所长 | 删除模板 |
| GET | `/templates/{id}/documents` | 用户 | 已关联+可用的文件模板 |
| POST | `/templates/{id}/documents/link` | 所长 | 关联文件模板 |
| DELETE | `/templates/{id}/documents/{doc_id}/link` | 所长 | 取消关联 |

#### GET `/templates/organizations`

响应 data：
```json
{
  "items": [{
    "id": 1,
    "name": "一所",
    "running_count": 5,
    "completed_count": 10,
    "terminated_count": 2,
    "total_count": 17,
    "recent_updated_at": "2026-07-24T10:00:00"
  }]
}
```

#### GET `/templates`

查询参数：`?page=1&page_size=20&keyword=技术&organization_id=1&type=project`

响应 data：
```json
{
  "items": [{
    "id": 1,
    "name": "技术方案审批流程",
    "description": "用于技术方案评审",
    "type": "project",
    "organization_id": 1,
    "organization_name": "一所",
    "node_count": 5,
    "status": "published",   // draft / published / disabled
    "created_by_name": "王所长",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-07-24T10:00:00"
  }],
  "total": 10,
  "page": 1,
  "page_size": 20
}
```

#### GET `/templates/{id}`

响应 data：
```json
{
  "id": 1,
  "name": "技术方案审批流程",
  "description": "...",
  "type": "project",
  "organization_id": 1,
  "status": "published",
  "nodes": [{
    "id": 1, "name": "开始", "is_start": true, "is_end": false,
    "assignee_id": null, "checkers": null, "approvers": null,
    "position_x": 100, "position_y": 300, "sort_order": 1
  }, {
    "id": 2, "name": "技术方案编写", "is_start": false, "is_end": false,
    "assignee_id": 5, "assignee_name": "张三",
    "checkers": [{"user_id": 6, "user_name": "李四"}],
    "approvers": [{"user_id": 7, "user_name": "王五"}],
    "endorser_id": null,
    "time_limit_days": 5,
    "require_file": true,
    "file_folders": [{"name": "技术文档", "required": true, "file_count": 2}],
    "approval_strategy": "all_approve",
    "require_assignee_signature": true,
    "require_checker_signature": true,
    "require_approver_signature": true,
    "require_endorser_signature": true,
    "signature_x": 400, "signature_y": 100, "signature_page": -1,
    "position_x": 300, "position_y": 300, "sort_order": 2
  }, {
    "id": 3, "name": "结束", "is_start": false, "is_end": true,
    "sort_order": 3
  }],
  "edges": [{
    "id": 1, "source_node_id": 1, "target_node_id": 2
  }, {
    "id": 2, "source_node_id": 2, "target_node_id": 3
  }]
}
```

#### POST `/templates/{id}/documents/link`

请求：
```json
[1, 2, 3]
```

body 为文件模板 ID 数组，全量替换关联。

---

### 2.7 流程设计器（6 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| PUT | `/templates/{id}/design` | 所长 | 批量保存画布（nodes+edges JSON） |
| POST | `/templates/{id}/nodes` | 所长 | 添加节点 |
| PUT | `/templates/{id}/nodes/{node_id}` | 所长 | 更新节点属性 |
| DELETE | `/templates/{id}/nodes/{node_id}` | 所长 | 删除节点 |
| POST | `/templates/{id}/edges` | 所长 | 添加连线 |
| DELETE | `/templates/{id}/edges/{edge_id}` | 所长 | 删除连线 |

#### PUT `/templates/{id}/design`

请求：
```json
{
  "nodes": [
    {"id": 1, "name": "开始", "is_start": true, "is_end": false, "position_x": 100, "position_y": 300, "sort_order": 1},
    {"id": 2, "name": "编写", "is_start": false, "is_end": false, "assignee_id": 5, "position_x": 300, "position_y": 300, "sort_order": 2},
    {"id": 3, "name": "结束", "is_start": false, "is_end": true, "position_x": 500, "position_y": 300, "sort_order": 3}
  ],
  "edges": [
    {"source_node_id": 1, "target_node_id": 2},
    {"source_node_id": 2, "target_node_id": 3}
  ]
}
```

> 批量保存——前端画布状态全量提交，后端全量替换。

---

### 2.8 流程实例（10 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/instances/check-name` | 用户 | 检测实例名称是否已存在 |
| POST | `/instances` | 所长 | 发起流程 |
| GET | `/instances` | 用户 | 实例列表 |
| GET | `/instances/my-initiated` | 用户 | 我发起的实例 |
| GET | `/instances/{id}` | 用户 | 实例详情 |
| POST | `/instances/{id}/terminate` | 发起人 | 终止流程 |
| PUT | `/instances/{id}/nodes/{nid}/personnel` | 发起人 | 紧急换人 |
| PUT | `/instances/{id}/priority` | 发起人 | 修改优先级 |
| POST | `/instances/{id}/nodes/{nid}/supplement-files` | 负责人/发起人 | 补交文件 |
| DELETE | `/instances/{id}/permanent` | 管理员 | 永久删除（仅 terminated） |

#### POST `/instances` — 发起流程

请求：
```json
{
  "template_id": 1,
  "name": "2026年Q3技术方案",
  "description": "Q3技术方案审批",
  "priority": "normal",
  "difficulty": "1",
  "contract_no": "HT-2026-001",
  "product_model": "X-100",
  "sales_manager": "销售张三",
  "proposal_id": null,
  "doc_template_ids": [1, 2],
  "node_overrides": [
    {
      "node_id": 2,
      "assignee_id": 5,
      "time_limit_days": 7,
      "deadline": "2026-08-15T00:00:00"
    }
  ]
}
```

响应 data：
```json
{
  "id": 100,
  "name": "2026年Q3技术方案",
  "organization_id": 1,
  "initiator_id": 1,
  "priority": "normal",
  "status": "running",
  "nodes": [
    {"id": 201, "name": "开始", "is_start": true, "is_end": false, "status": "finished", "sort_order": 1},
    {"id": 202, "name": "编写", "is_start": false, "is_end": false, "status": "running", "sort_order": 2},
    {"id": 203, "name": "结束", "is_start": false, "is_end": true, "status": "waiting", "sort_order": 3}
  ],
  "initiated_at": "2026-07-24T10:30:00"
}
```

#### GET `/instances`

查询参数：`?page=1&page_size=20&status=running&keyword=技术&organization_id=1&priority=urgent&date_from=2026-01-01&date_to=2026-12-31&initiator_name=张三`

#### GET `/instances/{id}` — 实例详情

响应 data：
```json
{
  "id": 100,
  "name": "2026年Q3技术方案",
  "description": "...",
  "template_id": 1,
  "template_name": "技术方案审批流程",
  "template_type": "project",
  "organization_id": 1,
  "organization_name": "一所",
  "initiator_id": 1,
  "initiator_name": "王所长",
  "priority": "normal",
  "difficulty": "1",
  "contract_no": "HT-2026-001",
  "product_model": "X-100",
  "sales_manager": "销售张三",
  "proposal_id": null,
  "status": "running",
  "termination_reason": null,
  "initiated_at": "2026-07-24T10:30:00",
  "completed_at": null,
  "terminated_at": null,
  "nodes": [{
    "id": 201, "name": "开始", "is_start": true, "is_end": false,
    "status": "finished", "sort_order": 1, "round": 1,
    "assignee_id": null, "assignee_name": null,
    "checkers": null, "approvers": null, "endorser_id": null,
    "time_limit_days": null, "deadline": null,
    "require_file": false, "file_folders": null,
    "files": [],
    "checks": [],
    "approvals": [],
    "endorsements": []
  }, {
    "id": 202, "name": "技术方案编写", "is_start": false, "is_end": false,
    "status": "running", "sort_order": 2, "round": 1,
    "assignee_id": 5, "assignee_name": "张三",
    "checkers": [{"user_id": 6}], "approvers": [{"user_id": 7}], "endorser_id": null,
    "time_limit_days": 7, "deadline": "2026-08-15T00:00:00",
    "require_file": true,
    "files": [
      {"id": 301, "original_name": "report.docx", "file_size": 102400,
       "mime_type": "application/pdf", "folder_name": "技术文档",
       "upload_type": "normal", "round": 1}
    ],
    "checks": [
      {"id": 401, "checker_id": 6, "checker_name": "李四", "status": "pending", "opinion": null}
    ],
    "approvals": [],
    "endorsements": []
  }],
  "logs": [{
    "id": 501, "operation_type": "initiate",
    "operator_type": "user", "operator_name": "王所长",
    "description": "发起了项目「2026年Q3技术方案」",
    "detail": {"template_id": 1, "node_count": 3},
    "round": 1,
    "created_at": "2026-07-24T10:30:00"
  }]
}
```

#### POST `/instances/{id}/terminate`

请求：
```json
{
  "reason": "项目需求变更，不再需要此流程"
}
```

#### PUT `/instances/{id}/nodes/{nid}/personnel`

请求：
```json
{
  "assignee_id": 10,
  "checkers": [{"user_id": 11}, {"user_id": 12}],
  "approvers": [{"user_id": 13}],
  "endorser_id": 14
}
```

> 每个字段可选。不传的字段保持不变。设置为 null 表示清空。

#### PUT `/instances/{id}/priority`

请求：
```json
{
  "priority": "urgent"
}
```

#### POST `/instances/{id}/nodes/{nid}/supplement-files`

- Content-Type: `multipart/form-data`
- 字段：`files`（多文件上传）、`folder_name`（可选）
- 文件 upload_type 自动设为 `supplement`

---

### 2.9 任务（10 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/tasks` | 用户 | 我的待办（分页+搜索+类型） |
| GET | `/tasks/{id}` | 负责人 | 任务详情（含文件/校验/审批进度） |
| PUT | `/tasks/{id}` | 负责人 | 保存草稿（备注） |
| POST | `/tasks/{id}/submit` | 负责人 | 提交任务 |
| POST | `/tasks/{id}/prepare-sign` | 负责人 | 预提交（转 PDF + 返回文件列表） |
| POST | `/tasks/{id}/files` | 负责人 | 上传文件 |
| DELETE | `/tasks/{id}/files/{fid}` | 负责人 | 删除未提交文件 |
| GET | `/files/{fid}/download` | 用户 | 下载/预览文件 |
| GET | `/tasks/{id}/document-templates` | 负责人 | 可用文件模板列表（含模板包） |
| GET | `/tasks/{id}/document-templates/{did}/download` | 负责人 | 下载已填充变量的模板 |
| GET | `/tasks/{id}/document-templates/download-zip` | 负责人 | 下载模板包 ZIP（参数 category_id） |

#### GET `/tasks`

查询参数：`?page=1&page_size=20&keyword=技术&instance_type=project`

响应 data：
```json
{
  "items": [{
    "id": 1,
    "instance_id": 100,
    "instance_name": "2026年Q3技术方案",
    "node_id": 202,
    "node_name": "技术方案编写",
    "initiator_name": "王所长",
    "status": "processing",
    "deadline": "2026-08-15T00:00:00",
    "is_overdue": false,
    "days_remaining": 22,
    "priority": "normal",
    "created_at": "2026-07-24T10:30:00"
  }],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

> 逾期排序：deadline 已过优先 → deadline 近优先 → 无 deadline 最后

#### GET `/tasks/{id}` — 任务详情

> 首次打开时 Task 状态 pending → processing（自动开始）

响应 data：
```json
{
  "id": 1,
  "instance_id": 100,
  "instance_name": "2026年Q3技术方案",
  "instance_status": "running",
  "initiator_id": 1,
  "initiator_name": "王所长",
  "priority": "normal",
  "node_id": 202,
  "node_name": "技术方案编写",
  "node_description": "编写技术方案文档",
  "node_status": "running",
  "assignee_id": 5,
  "assignee_name": "张三",
  "status": "processing",
  "assignee_note": "正在编写中...",
  "require_file": true,
  "file_folders": [{"name": "技术文档", "required": true, "file_count": 2}],
  "time_limit_days": 7,
  "deadline": "2026-08-15T00:00:00",
  "round": 1,
  "total_nodes": 3,
  "current_node_index": 1,
  "nodes": [
    {"id": 201, "name": "开始", "is_start": true, "is_end": false, "status": "finished", "sort_order": 1},
    {"id": 202, "name": "编写", "is_start": false, "is_end": false, "status": "running", "sort_order": 2},
    {"id": 203, "name": "结束", "is_start": false, "is_end": true, "status": "waiting", "sort_order": 3}
  ],
  "files": [
    {"id": 301, "original_name": "report.pdf", "mime_type": "application/pdf",
     "file_size": 102400, "folder_name": "技术文档", "upload_type": "normal", "round": 1}
  ],
  "checks": [
    {"id": 401, "checker_id": 6, "checker_name": "李四", "status": "pending", "opinion": null}
  ],
  "approvals": [
    {"id": 501, "approver_id": 7, "approver_name": "王五", "status": "pending", "opinion": null, "signature_applied": false}
  ],
  "rejected_type": null,
  "rejected_reason": null,
  "require_assignee_signature": true,
  "require_checker_signature": true,
  "require_approver_signature": true,
  "signature_x": 400, "signature_y": 100, "signature_page": -1,
  "current_signature_url": "/api/v1/auth/users/5/signature-image",
  "role_signature": {"x": 400, "y": 100},
  "submitted_at": null,
  "created_at": "2026-07-24T10:30:00"
}
```

> `role_signature` 字段同样存在于校验详情、审批详情、批准详情的响应中，值根据当前角色返回对应默认坐标。

#### POST `/tasks/{id}/submit`

请求：
```json
{
  "assignee_note": "已完成技术方案编写",
  "signatures": [
    {
      "file_id": 301,
      "signature_x": 400,
      "signature_y": 100,
      "signature_page": -1
    }
  ]
}
```

响应：
```json
{
  "code": 20000,
  "message": "任务已提交，等待校验"
}
```

> 若无校验人配置，message 为"任务已提交，等待审批"

#### POST `/tasks/{id}/files`

- Content-Type: `multipart/form-data`
- 字段：`files`（多文件）、`folder_name`（可选，指定所属文件夹）

---

### 2.10 校验（4 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/checks` | 用户 | 我的校验列表 |
| GET | `/checks/{id}` | 校验人 | 校验详情 |
| POST | `/checks/{id}/pass` | 校验人 | 通过 |
| POST | `/checks/{id}/return` | 校验人 | 退回 |

#### GET `/checks`

查询参数：`?page=1&page_size=20&keyword=技术&status=pending`

响应 data：
```json
{
  "items": [{
    "id": 401,
    "instance_id": 100,
    "instance_name": "2026年Q3技术方案",
    "node_id": 202,
    "node_name": "技术方案编写",
    "task_id": 1,
    "submitter_name": "张三",
    "status": "pending",
    "round": 1,
    "created_at": "2026-07-24T11:00:00"
  }]
}
```

#### GET `/checks/{id}` — 校验详情

响应 data：包含文件列表、负责人备注、并行校验进度、签批配置。

#### POST `/checks/{id}/pass`

请求：
```json
{
  "opinion": "文件内容正确",
  "signatures": [
    {"file_id": 301, "signature_x": 420, "signature_y": 120, "signature_page": -1}
  ]
}
```

响应：非最后一个校验人 → `{"all_passed": false, "message": "校验通过，等待其他校验人"}`；最后一个校验人 → `{"all_passed": true, "message": "全部校验通过，已进入审批阶段"}`

#### POST `/checks/{id}/return`

请求：
```json
{
  "opinion": "文件格式不正确，请重新提交"
}
```

> 意见必填。退回后：节点→running, Task→processing, 文件删除, round+1。

---

### 2.11 审批（4 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/approvals` | 用户 | 我的审批列表 |
| GET | `/approvals/{id}` | 审批人 | 审批详情 |
| POST | `/approvals/{id}/approve` | 审批人 | 通过 |
| POST | `/approvals/{id}/reject` | 审批人 | 驳回 |

#### GET `/approvals`

查询参数：`?page=1&page_size=20&keyword=技术&status=pending&instance_type=project`

#### POST `/approvals/{id}/approve`

请求：
```json
{
  "opinion": "同意",
  "signatures": [
    {"file_id": 301, "signature_x": 440, "signature_y": 140, "signature_page": -1}
  ]
}
```

响应：
- 非最后一个审批人：`{"all_approved": false, "message": "审批通过，等待其他审批人"}`
- 最后一个审批人 + 难度4 + 有批准人：`{"all_approved": true, "waiting_endorsement": true, "message": "全部审批通过，等待批准人审核"}`
- 最后一个审批人 + 结束节点：`{"all_approved": true, "instance_completed": true, "message": "流程已完成"}`
- 最后一个审批人 + 普通节点：`{"all_approved": true, "message": "全部审批通过，流程已推进到下一节点"}`

#### POST `/approvals/{id}/reject`

中间节点审批：
```json
{
  "opinion": "方案需要修改",
  "target_node_id": null
}
```

终审驳回（指定目标节点）：
```json
{
  "opinion": "资料不全，需完善",
  "target_node_id": 202
}
```

> 中间节点 `target_node_id` 为 null → 固定退回当前节点负责人
> 终审节点必须指定 `target_node_id`（不能是开始或结束节点）

---

### 2.12 批准（4 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/endorsements` | 用户 | 我的批准列表 |
| GET | `/endorsements/{id}` | 批准人 | 批准详情 |
| POST | `/endorsements/{id}/approve` | 批准人 | 通过 |
| POST | `/endorsements/{id}/reject` | 批准人 | 驳回 |

> 仅 difficulty=4 的流程节点触发。结构与审批类似。

#### POST `/endorsements/{id}/reject`

请求：
```json
{
  "opinion": "报告质量不达标"
}
```

> 驳回后节点回到 running 状态，负责人需重新处理。round+1。

---

### 2.13 Dashboard（1 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/dashboard` | 用户 | 全局统计数据 |

响应 data：
```json
{
  "project": {
    "running_count": 12,
    "archived_count": 45,
    "this_month_archived": 8,
    "overdue_warning": 3,
    "total_tasks": 25,
    "my_pending_tasks": 2,
    "my_pending_checks": 1,
    "my_pending_approvals": 3,
    "org_pie": [{"org_id": 1, "org_name": "一所", "count": 5}],
    "tracking_items": [{
      "id": 100, "name": "Q3技术方案", "org_name": "一所",
      "difficulty": "3", "current_node": "技术方案编写",
      "assignee_name": "张三", "progress": 0.33, "is_overdue": false,
      "priority": "urgent"
    }],
    "org_bar": [{
      "org_id": 1, "org_name": "一所",
      "total": 20, "running": 5, "completed": 12, "terminated": 3
    }]
  },
  "proposal": {
    "running_count": 3,
    "archived_count": 8,
    "this_month_archived": 2,
    "total_count": 12
  }
}
```

> 不同角色返回不同数据：管理员无 my_pending_* 字段。

---

### 2.14 通知（6 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/notifications` | 用户 | 通知列表（分页，最新优先） |
| GET | `/notifications/unread-count` | 用户 | 未读计数 |
| GET | `/notifications/summary` | 用户 | 待办/校验/审批/批准汇总计数 |
| GET | `/notifications/overdue` | 用户 | 系统全部超期项（任务/校验/审批/批准） |
| PUT | `/notifications/{id}/read` | 用户 | 标记单条已读 |
| PUT | `/notifications/read-all` | 用户 | 全部已读 |

#### GET `/notifications/summary`

响应（汇总 + 按项目/方案分类 breakdown）：
```json
{
  "code": 20000,
  "data": {
    "task_count": 3,
    "check_count": 1,
    "approval_count": 2,
    "endorsement_count": 0,
    "project_pending": 5,
    "proposal_pending": 1,
    "project_task_count": 2,
    "project_check_count": 1,
    "project_approval_count": 2,
    "project_endorsement_count": 0,
    "proposal_task_count": 1,
    "proposal_approval_count": 0,
    "proposal_endorsement_count": 0
  }
}
```

#### GET `/notifications/unread-count`

响应：
```json
{
  "code": 20000,
  "data": {"count": 5}
}
```

---

### 2.15 WebSocket（1 个）

| 协议 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| WS | `/api/v1/ws?token=xxx` | JWT Query | 实时推送 |

连接流程：
1. 客户端带 JWT token 连接 `ws://host:8000/api/v1/ws?token=eyJ...`
2. 服务端验证 token → 无效则关闭连接（code 4001）
3. 有效 → 注册到 ConnectionManager
4. 推送消息格式：

```json
{
  "type": "notification",
  "data": {
    "id": 1,
    "type": "task_assigned",
    "title": "新的待办任务",
    "content": "节点「技术方案编写」已激活，等待你处理",
    "link": "/profile/task/1",
    "is_read": false,
    "created_at": "2026-07-24T10:30:00"
  }
}
```

---

#### GET `/notifications/overdue`

查询系统**全部**超期项（不限于当前用户），按类型分组返回。

响应：
```json
{
  "tasks": [
    {
      "id": 1, "type": "task",
      "instance_id": 10, "instance_name": "XX项目",
      "node_name": "技术方案", "person_name": "张三",
      "person_id": 5, "deadline": "2026-07-20T18:00:00",
      "priority": "high", "organization_name": "一所"
    }
  ],
  "checks": [ ... ],
  "approvals": [ ... ],
  "endorsements": [ ... ]
}
```

---

### 2.16 方案（3 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| POST | `/proposals` | 所长 | 发起方案 |
| GET | `/proposals` | 用户 | 方案列表 |
| GET | `/proposals/organizations` | 用户 | 组织卡片（含方案统计） |

#### POST `/proposals`

请求结构同 POST `/instances`，但 template_type 自动为 proposal。

#### GET `/proposals`

查询参数同 GET `/instances`，响应结构类似但列较少（无进度条、难度）。

---

### 2.17 节点预设（4 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/node-presets` | 用户 | 我的预设列表 |
| POST | `/node-presets` | 用户 | 创建预设 |
| PUT | `/node-presets/{id}` | 创建者 | 编辑预设 |
| DELETE | `/node-presets/{id}` | 创建者 | 删除预设 |

#### POST `/node-presets`

请求：
```json
{
  "name": "常用技术节点",
  "node_name": "技术方案编写",
  "assignee_id": 5,
  "checkers": [{"user_id": 6}],
  "approvers": [{"user_id": 7}],
  "time_limit_days": 7,
  "require_file": true
}
```

---

### 2.18 文件模板管理（3 个）— `/api/v1/admin`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/admin/document-templates` | 管理员 | 全部文件模板（筛选+分页） |
| POST | `/admin/document-templates` | 管理员 | 上传模板（≤10MB） |
| DELETE | `/admin/document-templates/{id}` | 管理员 | 删除（物理删除文件） |

#### POST `/admin/document-templates`

- Content-Type: `multipart/form-data`
- 字段：`file`（.docx/.xlsx，≤10MB）、`name`（模板名称）、`organization_id`

### 2.19 模板分类（包）管理（7 个）— `/api/v1/admin`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/admin/template-categories` | 管理员 | 分类列表（筛选+分页） |
| POST | `/admin/template-categories` | 管理员 | 创建分类 |
| GET | `/admin/template-categories/{id}` | 管理员 | 分类详情（含内部模板） |
| PUT | `/admin/template-categories/{id}` | 管理员 | 更新分类 |
| DELETE | `/admin/template-categories/{id}` | 管理员 | 删除分类 |
| POST | `/admin/template-categories/{id}/documents` | 管理员 | 向分类中添加模板 |
| DELETE | `/admin/template-categories/{id}/documents` | 管理员 | 从分类中移除模板 |

### 2.20 模板批量下载（1 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/templates/{id}/download-zip` | 用户 | 批量填充+打包 ZIP（参数 doc_ids, instance_id） |

---

### 2.21 工具（1 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| POST | `/utils/calculate-deadlines` | 用户 | 计算截止日期 |

请求：
```json
{
  "start_date": "2026-07-24",
  "workdays": 10
}
```

响应：
```json
{
  "code": 20000,
  "data": {
    "deadline": "2026-08-07",
    "holidays_skipped": 2
  }
}
```

> 跳过周末和法定节假日（节假日通过系统配置维护）。

---

### 2.22 健康检查（1 个）— `/api/v1`

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| GET | `/health` | 无 | 健康检查（不限流） |

---

## 3. 权限依赖

| 依赖函数 | 要求 | 失败返回 |
|----------|------|:--:|
| `get_current_active_user` | 有效 JWT + 账号未禁用 | 40100-40103 / 40300 |
| `require_admin` | 包含 system_admin 角色 | 40301 |
| `require_manager` | 包含 manager 角色 | 40302 |
| `require_same_org` | user.org_id == target.org_id | 40303 |

---

## 4. 限流

| 档位 | 阈值 | 作用域 | 适用端点 |
|------|------|--------|----------|
| 严格 | 20次/分钟/IP | `X-Forwarded-For` / `client.host` | POST /auth/login |
| 中等 | 30次/分钟/用户 | JWT user_id | POST /instances, /proposals, /instances/*/terminate, /tasks/*/submit, 文件上传 |
| 宽松 | 120次/分钟/用户 | JWT user_id | 其余所有 /api/v1 端点（默认） |
| 跳过 | 无限 | — | 系统管理员（uuid 标记）+ /health |

---

## 5. Swagger

开发环境访问 `http://localhost:8000/docs` 查看完整交互式 API 文档（含自动生成的 curl 示例和响应 Schema）。
