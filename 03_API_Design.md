# 企业流程审批系统 — API 接口设计

> **版本**：1.0
> **状态**：设计阶段
> **基于**：00_Project_Blueprint.md + 01_PRD.md + 02_Database_Design.md
>
> 本文档定义系统全部 RESTful API 端点、请求/响应格式、权限校验和业务逻辑说明。

---

# 目录

1. [设计概述](#1-设计概述)
2. [认证模块](#2-认证模块)
3. [用户管理](#3-用户管理)
4. [组织管理](#4-组织管理)
5. [角色管理](#5-角色管理)
6. [流程模板管理](#6-流程模板管理)
7. [流程设计器](#7-流程设计器)
8. [流程实例](#8-流程实例)
9. [任务处理](#9-任务处理)
10. [校验处理](#10-校验处理)
11. [审批处理](#11-审批处理)
12. [文件管理](#12-文件管理)
13. [操作日志](#13-操作日志)
14. [Dashboard](#14-dashboard)
15. [系统配置](#15-系统配置)
16. [个人中心](#16-个人中心)
17. [附录：错误码](#17-附录错误码)

---

# 1. 设计概述

## 1.1 设计原则

| 原则 | 说明 |
|------|------|
| RESTful | 资源用名词，操作用 HTTP 方法（GET/POST/PUT/DELETE） |
| 统一响应 | 所有响应包裹在 `{code, message, data}` 结构中 |
| 后端校验 | 权限和业务规则全部在后端校验，前端仅做展示层拦截 |
| JWT 认证 | 除登录外所有接口需携带 `Authorization: Bearer <token>` |
| 分页统一 | 列表接口默认分页，`page` + `page_size`，返回 `{items, total, page, page_size}` |

## 1.2 基础 URL

```
开发环境：http://localhost:8000/api/v1
生产环境：https://{domain}/api/v1
```

## 1.3 统一响应格式

```json
// 成功
{
  "code": 200,
  "message": "ok",
  "data": { ... }
}

// 分页列表
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [ ... ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}

// 失败
{
  "code": 40001,
  "message": "流程名称已存在",
  "data": null
}
```

## 1.4 认证方式

- 登录成功后返回 `access_token`（JWT），有效期 24 小时
- 所有业务接口在 Header 中携带：`Authorization: Bearer <access_token>`
- 每个接口标注所需角色，后端中间件统一校验

## 1.5 跨父对象归属校验

所有嵌套资源接口必须同时校验路径父对象与资源真实归属：template/version/node/edge、instance/node/task/check/approval/file 等 ID 不得跨模板、跨版本或跨实例混用；不匹配统一返回 404，避免泄露其他父对象资源。

---

## 1.5 权限标注说明

每个接口标注权限要求：

| 标注 | 含义 |
|------|------|
| `ALL` | 所有已登录用户 |
| `ADMIN` | 仅系统管理员 |
| `MANAGER` | 仅所长（含本所数据权限） |
| `ASSIGNEE` | 仅节点负责人 |
| `CHECKER` | 仅校验人 |
| `APPROVER` | 仅审批人 |
| `INITIATOR` | 仅流程发起人 |

---

# 2. 认证模块

## 2.1 登录

```
POST /auth/login
```

**权限**：无（无需 Token）

**请求体**：
```json
{
  "username": "zhangsan",
  "password": "123456"
}
```

**响应**：
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": 1,
      "username": "zhangsan",
      "real_name": "张三",
      "organization_id": 1,
      "organization_name": "通用所",
      "roles": ["manager"],
      "has_signature": true
    }
  }
}
```

**业务规则**：
- 校验用户名密码（bcrypt）
- 检查 `users.is_active = 1`，被禁用则返回"账号已被禁用"
- 生成 JWT Token，payload 含 `{user_id, username, roles, org_id}`

**错误码**：
| code | message |
|------|---------|
| 40101 | 用户名或密码错误 |
| 40102 | 账号已被禁用，请联系管理员 |

---

## 2.2 获取当前用户

```
GET /auth/me
```

**权限**：`ALL`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 1,
    "username": "zhangsan",
    "real_name": "张三",
    "organization_id": 1,
    "organization_name": "通用所",
    "email": "zhangsan@example.com",
    "phone": "13800138000",
    "roles": ["manager"],
    "has_signature": true,
    "is_active": true,
    "created_at": "2026-06-01T09:00:00"
  }
}
```

---

## 2.3 退出登录

```
POST /auth/logout
```

**权限**：`ALL`

**响应**：
```json
{
  "code": 200,
  "message": "已退出登录",
  "data": null
}
```

**业务规则**：V1 不做 Token 黑名单（过期后自然失效）。

---

# 3. 用户管理

> 仅系统管理员可操作。

## 3.1 用户列表

```
GET /users
```

**权限**：`ADMIN`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| page | int | ❌ | 页码，默认 1 |
| page_size | int | ❌ | 每页条数，默认 20 |
| keyword | string | ❌ | 按用户名或姓名模糊搜索 |
| organization_id | int | ❌ | 按组织筛选 |
| is_active | bool | ❌ | 按启用状态筛选 |

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "username": "zhangsan",
        "real_name": "张三",
        "organization_id": 1,
        "organization_name": "通用所",
        "roles": ["manager"],
        "is_active": true,
        "created_at": "2026-06-01T09:00:00"
      }
    ],
    "total": 30,
    "page": 1,
    "page_size": 20
  }
}
```

---

## 3.2 新增用户

```
POST /users
```

**权限**：`ADMIN`

**请求体**：
```json
{
  "username": "lisi",
  "password": "123456",
  "real_name": "李四",
  "organization_id": 1,
  "role_ids": [3],
  "email": "lisi@example.com",
  "phone": "13800138001"
}
```

**响应**：
```json
{
  "code": 200,
  "message": "用户创建成功",
  "data": { "id": 2 }
}
```

**校验规则**：
- `username`：必填，3-30 字符，字母数字下划线，唯一
- `password`：必填，最少 6 位
- `real_name`：必填，2-20 字符
- `organization_id`：必填，组织必须存在
- `role_ids`：必填，至少选一个角色

---

## 3.3 编辑用户

```
PUT /users/{user_id}
```

**权限**：`ADMIN`

**请求体**：
```json
{
  "real_name": "李四改",
  "organization_id": 2,
  "role_ids": [2, 3],
  "email": "new_email@example.com",
  "phone": "13900139000"
}
```

**说明**：`username` 不可修改。`password` 通过重置密码接口单独修改。

---

## 3.4 启用/禁用用户

```
PUT /users/{user_id}/status
```

**权限**：`ADMIN`

**请求体**：
```json
{
  "is_active": false
}
```

**业务规则**：
- 禁用后用户不可登录
- 后续版本：禁用后使已有 Token 失效（需配合 Redis 黑名单）
- V1 简化：每次请求时实时查询 `users.is_active`

---

## 3.5 重置密码

```
PUT /users/{user_id}/reset-password
```

**权限**：`ADMIN`

**请求体**：
```json
{
  "new_password": "654321"
}
```

**说明**：管理员无需输入原密码，直接设置新密码。

---

# 4. 组织管理

> 仅系统管理员可操作。

## 4.1 组织列表

```
GET /organizations
```

**权限**：`ADMIN`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "通用所",
        "description": "负责城区项目",
        "manager_id": 2,
        "manager_name": "张三",
        "user_count": 15,
        "is_active": true,
        "created_at": "2026-06-01T09:00:00"
      }
    ]
  }
}
```

---

## 4.2 新增组织

```
POST /organizations
```

**权限**：`ADMIN`

**请求体**：
```json
{
  "name": "第五所",
  "description": "新设立的所"
}
```

---

## 4.3 组织选项

```
GET /organizations/options
```

**权限**：`ALL`

**说明**：返回启用组织的 `{id,name,manager_id,manager_name}` 轻量选项，供筛选和表单使用。

---

## 4.4 编辑组织

```
PUT /organizations/{org_id}
```

**权限**：`ADMIN`

**请求体**：
```json
{
  "name": "第五所（改）",
  "description": "更新描述"
}
```

---

## 4.5 启用/停用组织

```
PUT /organizations/{org_id}/status
```

**权限**：`ADMIN`

**请求体**：`{"is_active": false}`。V1 不提供 DELETE 组织接口；停用组织不得用于新建用户、模板或实例。

---

# 5. 角色管理

> 仅系统管理员可查看。V1 三个角色为系统预置，不可增删。

## 5.1 角色列表

```
GET /roles
```

**权限**：`ADMIN`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "系统管理员",
        "code": "system_admin",
        "description": "系统维护者",
        "user_count": 2
      },
      {
        "id": 2,
        "name": "所长",
        "code": "manager",
        "description": "组织管理者",
        "user_count": 4
      },
      {
        "id": 3,
        "name": "普通用户",
        "code": "user",
        "description": "流程执行者",
        "user_count": 24
      }
    ]
  }
}
```

---

# 6. 流程模板管理

## 6.1 组织选择页

```
GET /templates/organizations
```

**权限**：`ALL`

**说明**：返回所有组织及其模板数量，用于流程管理入口的组织选择页。

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "通用所",
        "running_instance_count": 12,
        "latest_update_time": "2026-07-09T14:30:00",
        "is_current_user_org": true
      }
    ]
  }
}
```

---

## 6.2 模板列表

```
GET /templates
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| organization_id | int | ✅ | 组织 ID |
| page | int | ❌ | 页码，默认 1 |
| page_size | int | ❌ | 每页条数，默认 20 |
| keyword | string | ❌ | 按流程名称模糊搜索 |
| status | string | ❌ | 按状态筛选（draft/published/disabled） |

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "产品设计流程",
        "description": "标准产品设计审批流程",
        "status": "published",
        "current_version": 3,
        "node_count": 5,
        "created_by_name": "张三",
        "updated_at": "2026-07-05T14:00:00",
        "can_edit": true,
        "can_publish": false,
        "can_start": true
      }
    ],
    "total": 8,
    "page": 1,
    "page_size": 20
  }
}
```

> `can_edit` / `can_publish` / `can_start` 由后端根据当前用户角色和模板状态计算。

---

## 6.3 创建模板

```
POST /templates
```

**权限**：`MANAGER`（本所）

**请求体**：
```json
{
  "name": "设备采购流程",
  "description": "标准设备采购审批",
  "organization_id": 1
}
```

**业务规则**：
- 创建后自动在 `template_nodes` 中生成开始节点（is_start=1）和结束节点（is_end=1）
- 状态为 `draft`
- `organization_id` 默认当前用户所属组织（所长只能在本所创建）
- 记录操作日志

**响应**：
```json
{
  "code": 200,
  "message": "模板创建成功",
  "data": { "id": 5 }
}
```

---

## 6.4 模板详情

```
GET /templates/{template_id}
```

**权限**：`ALL`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 1,
    "name": "产品设计流程",
    "description": "标准产品设计审批流程",
    "organization_id": 1,
    "organization_name": "通用所",
    "status": "published",
    "current_version": 3,
    "created_by_name": "张三",
    "created_at": "2026-06-01T09:00:00",
    "updated_at": "2026-07-05T14:00:00",
    "versions": [
      {
        "id": 10,
        "version_number": 3,
        "status": "published",
        "published_by_name": "张三",
        "published_at": "2026-07-05T14:00:00"
      },
      {
        "id": 5,
        "version_number": 2,
        "status": "disabled",
        "published_by_name": "张三",
        "published_at": "2026-06-15T10:00:00"
      },
      {
        "id": 1,
        "version_number": 1,
        "status": "disabled",
        "published_by_name": "张三",
        "published_at": "2026-06-01T10:00:00"
      }
    ]
  }
}
```

---

## 6.5 更新模板基本信息

```
PUT /templates/{template_id}
```

**权限**：`MANAGER`（本所，且模板状态为 draft）

**请求体**：
```json
{
  "name": "产品设计流程（修订）",
  "description": "更新后的描述"
}
```

**说明**：仅可修改名称、描述。节点和连线通过设计器接口（第 7 章）修改。记录操作日志。

---

## 6.6 删除模板

```
DELETE /templates/{template_id}
```

**权限**：`MANAGER`（本所，且模板状态为 draft）

**业务规则**：
- 仅 draft 状态可删除
- 已发布/已停用不可删除
- 删除时级联删除 template_nodes 和 template_edges
- 记录操作日志

---

## 6.7 发布模板

```
POST /templates/{template_id}/publish
```

**权限**：`MANAGER`（本所）

**业务规则**（校验全部通过才发布）：

1. 流程名称必填，2-50 字符
2. 节点数量 ≥ 3（开始 + ≥1 个工作节点 + 结束）
3. 每个工作节点：名称、负责人、校验人（≥1人）、审批人（≥1人）、时限必填
4. 所有节点连通（无孤立节点）
5. 分叉/汇合连线合法

校验通过后：
1. 记录操作日志
2. `flow_templates.current_version + 1`
2. 生成 `flow_versions` 记录，快照当前 nodes + edges 为 JSON
3. 模板状态 → `published`

**响应**：
```json
{
  "code": 200,
  "message": "发布成功，当前版本 V3",
  "data": { "version_id": 10, "version_number": 3 }
}
```

**校验失败响应**：
```json
{
  "code": 40010,
  "message": "发布校验未通过",
  "data": {
    "errors": [
      { "node_id": 5, "field": "name", "message": "节点名称不能为空" },
      { "node_id": 6, "field": "assignee_id", "message": "必须指定负责人" },
      { "field": "connectivity", "message": "节点「方案设计」未连通" }
    ]
  }
}
```

---

## 6.8 停用模板

```
POST /templates/{template_id}/disable
```

**权限**：`MANAGER`（本所，且模板状态为 published）

**业务规则**：
- 停用后该模板不可再发起新实例
- 已运行的实例不受影响
- 记录操作日志

---

## 6.9 创建新版本（从已发布模板复制）

```
POST /templates/{template_id}/new-version
```

**权限**：`MANAGER`（本所，且模板状态为 published）

**说明**：复制当前模板的节点和连线为草稿，状态变为 draft，版本号不增（发布时才 +1）。

---

# 7. 流程设计器

> 设计器接口操作模板的节点和连线。所有操作要求模板状态为 draft。

## 7.1 加载设计器数据

```
GET /templates/{template_id}/design
```

**权限**：`ALL`（编辑需 MANAGER 本所）

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "template_id": 1,
    "template_name": "产品设计流程",
    "status": "draft",
    "nodes": [
      {
        "id": 1,
        "name": "开始",
        "description": null,
        "is_start": true,
        "is_end": false,
        "assignee_id": null,
        "assignee_name": null,
        "time_limit_days": null,
        "require_file": false,
        "approvers": [],
        "checkers": [],
        "approval_strategy": "all_approve",
        "position_x": 120,
        "position_y": 200,
        "sort_order": 0
      },
      {
        "id": 2,
        "name": "需求分析",
        "description": "完成项目技术方案",
        "is_start": false,
        "is_end": false,
        "assignee_id": 4,
        "assignee_name": "李四",
        "time_limit_days": 7,
        "require_file": true,
        "approvers": [
          { "user_id": 3, "name": "王五" },
          { "user_id": 5, "name": "赵六" }
        ],
        "checkers": [
      { "user_id": 6, "name": "钱七", "status": "pending" },
      { "user_id": 7, "name": "孙八", "status": "pending" }
    ],
    "check_status": "waiting_check",
    "approval_strategy": "all_approve",
        "is_optional": false,
        "position_x": 360,
        "position_y": 200,
        "sort_order": 1
      },
      {
        "id": 3,
        "name": "结束",
        "description": null,
        "is_start": false,
        "is_end": true,
        "assignee_id": null,
        "assignee_name": null,
        "time_limit_days": null,
        "require_file": false,
        "approvers": [],
        "checkers": [],
        "approval_strategy": "all_approve",
        "sort_order": 2
      }
    ],
    "edges": [
      { "id": 1, "source_node_id": 1, "target_node_id": 2 },
      { "id": 2, "source_node_id": 2, "target_node_id": 3 }
    ]
  }
}
```

---

## 7.2 添加工作节点

```
POST /templates/{template_id}/nodes
```

**权限**：`MANAGER`（本所，draft）

**请求体**：
```json
{
  "name": "新节点",
  "position_x": 360,
  "position_y": 200,
  "sort_order": 2
}
```

**响应**：
```json
{
  "code": 200,
  "message": "节点已添加",
  "data": { "id": 10 }
}
```

**业务规则**：
- 只能添加中间工作节点（is_start=0, is_end=0）
- 默认名称"新节点"，默认不配置负责人/审批人/时限
- sort_order 用于决定画布上的显示位置

---

## 7.3 更新节点

```
PUT /templates/{template_id}/nodes/{node_id}
```

**权限**：`MANAGER`（本所，允许 draft 和 published 状态）

**请求体**：
```json
{
  "name": "需求分析",
  "description": "完成项目技术方案和预算方案",
  "assignee_id": 4,
  "time_limit_days": 7,
  "require_file": true,
  "checkers": [{"user_id": 6, "name": "钱七"}],
  "approvers": [
    { "user_id": 3, "name": "王五" },
    { "user_id": 5, "name": "赵六" }
  ],
  "is_optional": false,
  "position_x": 360,
  "position_y": 200,
  "sort_order": 1
}
```

**修改模式自动判定**：

| 模板状态 | 修改字段 | 模式 | 结果 |
|----------|------|:--:|------|
| `draft` | 全部字段 | 自由编辑 | 直接保存，不产生版本 |
| `published` | `assignee_id`, `time_limit_days`, `description`, `checkers`, `approvers` | 软修改 | 即时生效，不产生新版本 |
| `published` | `name`, `require_file`, `is_optional`, 新增/删除节点, 修改连线 | 硬修改 | 还需进入设计器，不在此接口处理 |

**业务规则**：
- 开始节点（is_start=1）和结束节点（is_end=1）不可修改，返回 403
- 审批策略 V1 固定 `all_approve`，即使前端传了也忽略
- `approvers` 数组校验：不得包含重复的 `user_id`（返回 40906）
- `published` 状态下若尝试修改硬修改字段（name/require_file），返回 422 提示"请通过设计器进行结构修改"

---

## 7.4 删除节点

```
DELETE /templates/{template_id}/nodes/{node_id}
```

**权限**：`MANAGER`（本所，draft）

**业务规则**：
- 开始/结束节点不可删除
- 删除时自动移除关联的所有连线

---

## 7.5 添加连线

```
POST /templates/{template_id}/edges
```

**权限**：`MANAGER`（本所，draft）

**请求体**：
```json
{
  "source_node_id": 2,
  "target_node_id": 3
}
```

**校验规则**：
- source ≠ target（不自循环）
- 开始节点（is_start=1）不可作为 target
- 结束节点（is_end=1）不可作为 source
- 同一对节点不可重复连线

---

## 7.6 删除连线

```
DELETE /templates/{template_id}/edges/{edge_id}
```

**权限**：`MANAGER`（本所，draft）

---

## 7.7 批量保存设计器内容

```
PUT /templates/{template_id}/design
```

**权限**：`MANAGER`（本所，draft）

**请求体**：
```json
{
  "nodes": [
    { "id": 1, "name": "开始", "is_start": true, "is_end": false, "position_x": 120,
        "position_y": 200,
        "sort_order": 0 },
    { "id": 2, "name": "需求分析", "is_start": false, "is_end": false, "assignee_id": 3, "time_limit_days": 7, "approvers": [{"user_id": 4}, {"user_id": 5}], "sort_order": 1 },
    { "id": null, "name": "方案设计", "is_start": false, "is_end": false, "sort_order": 2 },
    { "id": 4, "name": "结束", "is_start": false, "is_end": true, "sort_order": 3 }
  ],
  "edges": [
    { "id": null, "source_node_id": 1, "target_node_id": 2 },
    { "id": 2, "source_node_id": 2, "target_node_id": 4 }
  ]
}
```

**说明**：
- `id` 为已有节点/连线 ID → 更新；`id` 为 null → 新增；列表中不存在的已有 ID → 删除
- 所有操作在同一事务中完成，保证原子性
- 前端设计器点击"保存"时调用此接口，一次性提交全部内容

---

## 7.8 用户搜索（设计器用）

```
GET /users/search
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| keyword | string | ✅ | 按姓名模糊搜索，最少 1 字符 |

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      { "id": 4, "real_name": "李四", "organization_name": "高速所" },
      { "id": 5, "real_name": "李明明", "organization_name": "通用所" }
    ]
  }
}
```

**说明**：支持跨组织搜索，用于设计器中配置负责人和审批人。

---

# 8. 流程实例

## 8.0 组织级流程实例列表

```
GET /instances
```

**权限**：`ALL`（仅返回有权限查看的组织的实例）

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `organization_id` | int | ❌ | 组织 ID（不传则返回全部组织的实例） |
| `page` | int | ❌ | 页码，默认 1 |
| `page_size` | int | ❌ | 每页条数，默认 20 |
| `status` | string | ❌ | 筛选状态：created/running/completed/terminated。默认全部 |
| `priority` | string | ❌ | 优先级筛选：urgent/high/normal/low。默认全部 |
| `keyword` | string | ❌ | 按实例名称模糊搜索 |

**响应**：
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": 1,
        "name": "XT2026-001产品设计",
        "organization_name": "通用所",
        "template_name": "产品设计流程",
        "current_assignee_name": "李四",
        "current_node_index": 3,
        "total_nodes": 6,
        "status": "running",
        "archive_status": "not_archived",
        "archived_at": null,
        "priority": "normal",
        "initiated_at": "2026-07-03T10:00:00"
      }
    ],
    "total": 25,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段 | 说明 |
|------|------|
| `current_node_index` | 当前节点序号（如 3） |
| `total_nodes` | 总节点数（含开始/结束，不含跳过节点。如 6） |
| `current_assignee_name` | 当前节点负责人姓名 |

> 前端用 `current_node_index/total_nodes` 拼接显示"3/6"格式。

---

## 8.1 发起流程实例

```
POST /instances
```

**权限**：`MANAGER`（本所，且模板状态为 published）

**请求参数**：
| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| template_id | int | ✅ | 模板 ID |
| version_id | int | ✅ | 版本 ID |
| name | string | ✅ | 实例名称，2-100 字符 |
| description | string | ❌ | 实例描述 |
| priority | string | ❌ | 优先级，默认 normal。可选值：urgent/high/normal/low |
| node_overrides | array | ❌ | 节点覆盖配置，格式见下方说明 |

**请求体**：
```json
{
  "template_id": 1,
  "version_id": 10,
  "name": "XT2026-001产品设计",
  "description": "2026年江津区域供电站建设",
  "priority": "normal",
  "node_overrides": [
    {
      "node_id": 5,
      "assignee_id": 6,
      "deadline": "2026-07-21",
      "checkers": [{ "user_id": 6 }, { "user_id": 7 }],
        "approvers": [{ "user_id": 3 }, { "user_id": 4 }]
    },
    {
      "node_id": 7,
      "skip": true
    }
  ]
}
```
> `node_overrides` 可选。格式：`node_id` 必填，其余字段选填（未提供的字段使用模板默认值）。

| 覆盖字段 | 说明 |
|----------|------|
| `assignee_id` | 更换节点负责人 |
| `deadline` | 调整截止日期（ISO 日期，如 `"2026-07-21"`，默认 = 发起日期 + 模板天数） |
| `checkers` | 更换或增加校验人（覆盖模板配置） |
| `approvers` | 更换或增加审批人（覆盖模板配置） |
| `skip` | 跳过该节点（仅 is_optional=1 的节点可跳过） |

**校验**：
- 模板状态必须为 published
- 实例名称必填，2-100 字符
- `node_overrides` 中的 `node_id` 必须在模板中存在
- `skip: true` 仅对模板中 `is_optional=1` 的节点有效
- 审批人、负责人不能为空（覆盖后的结果至少保留 1 人）

**后端处理**：
1. 创建 `flow_instances` 记录，status = `created`
2. 从模板快照复制生成 `instance_nodes` 和 `instance_edges`
3. 应用 `node_overrides`：覆盖 assignee_id / deadline / checkers / approvers / is_skipped
4. 跳过的可选普通工作节点状态 → `skipped`，不生成 Task；开始/结束/fork/join 不可选
5. `incoming_count` 始终按原始 instance_edges 计算；跳过节点沿原图传播信号，不改边。完成/跳过节点只增加直接下游的 `arrived_count`，自身不增加
6. 开始节点状态 → `finished`（自动跳过），记录 `started_at` / `completed_at`
7. 推进到第一个非跳过的工作节点：状态 → `running`，生成 Task，计算 deadline
8. 实例状态 → `running`
9. 记录操作日志

**响应**：
```json
{
  "code": 200,
  "message": "流程发起成功",
  "data": { "id": 1 }
}
```

---

## 8.2 我发起的流程

```
GET /instances/my-initiated
```

**权限**：`MANAGER`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| page | int | ❌ | 页码，默认 1 |
| page_size | int | ❌ | 每页条数，默认 20 |
| status | string | ❌ | 按状态筛选 |
| keyword | string | ❌ | 按实例名称模糊搜索 |

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "XT2026-001产品设计",
        "template_name": "产品设计流程",
        "organization_name": "通用所",
        "status": "running",
        "current_node_name": "需求分析",
        "termination_reason": null,
        "initiated_at": "2026-07-07T09:00:00",
        "can_terminate": true
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

> `can_terminate`：当前用户为发起人且实例 `status != terminated` 时为 true。

---

## 8.3 流程实例详情

```
GET /instances/{instance_id}
```

**权限**：`ALL`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 1,
    "name": "XT2026-001产品设计",
    "description": "2026年江津区域供电站建设",
    "template_id": 1,
    "template_name": "产品设计流程",
    "version_number": 3,
    "organization_name": "通用所",
    "initiator_id": 2,
    "initiator_name": "张三",
    "status": "running",
    "archive_status": "not_archived",
    "archived_at": null,
    "terminated_at": null,
    "priority": "normal",
    "termination_reason": null,
    "initiated_at": "2026-07-07T09:00:00",
    "completed_at": null,
    "nodes": [
      {
        "id": 101,
        "name": "开始",
        "is_start": true,
        "is_end": false,
        "description": "流程开始",
        "assignee_name": null,
        "status": "finished",
        "round": 1,
        "require_file": false,
        "incoming_count": 0,
        "arrived_count": 0,
        "files": [],
        "checks": [],
        "approvals": [],
        "logs": [],
        "checkers": [],
      },
      {
        "id": 102,
        "name": "需求分析",
        "is_start": false,
        "is_end": false,
        "description": "编写项目技术方案",
        "assignee_name": "李四",
        "time_limit_days": 7,
        "deadline": "2026-07-14T09:00:00",
        "status": "running",
        "round": 1,
        "require_file": true,
        "incoming_count": 1,
        "arrived_count": 1,
        "approvers": [
          { "user_id": 3, "name": "王五", "status": "pending" },
          { "user_id": 5, "name": "赵六", "status": "pending" }
        ],
        "checkers": [
          { "checker_id": 6, "name": "钱七", "status": "pending", "opinion": null, "decided_at": null },
          { "checker_id": 7, "name": "孙八", "status": "pending", "opinion": null, "decided_at": null }
        ],
        "started_at": "2026-07-07T09:00:00",
        "completed_at": null,
        "is_overdue": false
      },
      {
        "id": 103,
        "name": "结束",
        "is_start": false,
        "is_end": true,
        "description": "流程结束（发起人终审）",
        "assignee_name": null,
        "status": "waiting",
        "round": 1,
        "require_file": false,
        "incoming_count": 1,
        "arrived_count": 0,
        "approvers": [
          { "user_id": 2, "name": "张三（发起人）", "status": "pending" }
        ],
        "checkers": [],
        "started_at": null,
        "completed_at": null
      }
    ],
    "edges": [
      { "source_node_id": 101, "target_node_id": null },
      { "source_node_id": 102, "target_node_id": 103 }
    ]
  }
}
```

---

## 8.4 终止流程

```
POST /instances/{instance_id}/terminate
```

**权限**：`INITIATOR`（仅发起人）

**请求体**：
```json
{
  "reason": "项目取消，不再需要执行"
}
```

**校验**：
- 任意未 terminated 实例均可终止，包括 completed 且 archive_status=archived
- `reason` 必填，最多 500 字符

**后端处理**：
1. 实例状态 → `terminated`，记录 `termination_reason`、`terminated_at`
2. 所有非终态 instance_nodes/tasks → `terminated`
3. 所有 pending check_records/approvals → `terminated`
4. 物理删除实例全部文件、目录及 files 记录；日志永久保留
6. 记录操作日志

**响应**：
```json
{
  "code": 200,
  "message": "流程已终止",
  "data": null
}
```

---

## 8.5 流程实例的审批记录

```
GET /instances/{instance_id}/approvals
```

**权限**：`ALL`

**响应**：按节点分组，每个节点展示全部审批记录。

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "nodes": [
      {
        "node_id": 102,
        "node_name": "需求分析",
        "approvals": [
          {
            "id": 50,
            "approver_name": "王五",
            "status": "approved",
            "opinion": "方案合格",
            "signature_applied": true,
            "decided_at": "2026-07-08T10:00:00"
          },
          {
            "id": 51,
            "approver_name": "赵六",
            "status": "pending",
            "opinion": null,
            "signature_applied": false,
            "decided_at": null
          }
        ]
      }
    ]
  }
}
```

---

## 8.6 流程实例的文件记录

```
GET /instances/{instance_id}/files
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| node_id | int | ❌ | 按节点筛选 |
| round | int | ❌ | 按执行轮次筛选 |


**响应**：按节点分组。

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "nodes": [
      {
        "node_id": 102,
        "node_name": "需求分析",
        "files": [
          {
            "id": 10,
            "original_name": "技术方案.docx",
            "task_id": 20,
            "round": 1,
            "upload_type": "normal",
            "pdf_available": true,
            "file_size": 1024000,
            "mime_type": "application/pdf",
            "uploader_name": "李四",
            "created_at": "2026-07-07T15:00:00"
          }
        ]
      }
    ]
  }
}
```

---

## 8.7 流程实例的操作日志

```
GET /instances/{instance_id}/logs
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| page | int | ❌ | 页码，默认 1 |
| page_size | int | ❌ | 每页条数，默认 50 |
| node_id | int | ❌ | 按节点筛选 |
| round | int | ❌ | 按执行轮次筛选 |

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 100,
        "operation_type": "enter_node",
        "round": 1,
        "description": "进入节点「需求分析」（第1轮），负责人：李四",
        "operator_type": "system",
        "operator_id": null,
        "operator_name": "系统",
        "triggered_by": 2,
        "created_at": "2026-07-07T09:00:00"
      },
      {
        "id": 99,
        "operation_type": "start_instance",
        "description": "发起流程实例「XT2026-001产品设计」",
        "operator_name": "张三",
        "created_at": "2026-07-07T09:00:00"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 50
  }
}
```

---

## 8.8 修改节点人员（紧急换人）

```
PUT /instances/{instance_id}/nodes/{node_id}/personnel
```

**权限**：`INITIATOR`（仅流程发起人）

**请求体**：
```json
{
  "assignee_id": 8,
  "checkers": [
    { "user_id": 6, "name": "钱七" },
    { "user_id": 9, "name": "周九" }
  ],
  "approvers": [
    { "user_id": 3, "name": "李四" },
    { "user_id": 5, "name": "王五" }
  ]
}
```

> 只需传要修改的字段，未传字段保持原值。如只改负责人，可仅传 `{"assignee_id": 8}`。

**校验**：
- 实例状态必须为 `running`
- 节点状态必须为未完成（waiting / running / waiting_check / waiting_approval）
- 已完成节点（finished / skipped / terminated）不可修改，返回 409
- `assignee_id` / `checkers[].user_id` / `approvers[].user_id` 必须为有效用户
- checkers 和 approvers 至少各保留 1 人

**后端处理**：
1. 更新 `instance_nodes` 中对应字段（assignee_id / checkers / approvers）
2. **校验人变更处理**：
   - 已有 CheckRecord 不在新校验人列表中且状态为 pending → 关闭为 terminated
   - 已有 CheckRecord 状态为 passed → 保留不动
   - 新校验人生成 CheckRecord（status=pending）
3. **审批人变更处理**：
   - 已有 Approval 不在新审批人列表中且状态为 pending → 关闭为 terminated
   - 已有 Approval 状态为 approved / rejected → 保留不动
   - 新审批人生成 Approval（status=pending）
4. 若节点状态为 running 且仅换了负责人 → Task.assignee_id 同步更新，不影响流程进度
5. 记录操作日志（变更详情：字段名、旧值、新值）

**响应**：
```json
{
  "code": 200,
  "message": "节点人员已更新",
  "data": {
    "node_id": 102,
    "changes": ["assignee_id", "checkers"]
  }
}
```

**错误码**：
| code | message |
|------|---------|
| 40910 | 节点已完成，不可修改人员 |
| 40911 | 实例已终止，不可修改 |
| 40912 | 校验人或审批人不能为空 |

---

## 8.9 修改优先级

```
PUT /instances/{instance_id}/priority
```

**权限**：`INITIATOR`（仅流程发起人）

**请求体**：
| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| priority | string | ✅ | 优先级，可选值：urgent / high / normal / low |

**校验**：
- 实例状态必须为 `running`
- priority 必须为有效值

**后端处理**：
1. 更新 `flow_instances.priority` 字段
2. 记录操作日志（变更详情：字段名、旧值、新值）

**响应**：
```json
{
  "code": 200,
  "message": "优先级修改成功",
  "data": { "id": 5, "priority": "urgent" }
}
```

---

# 9. 任务处理

## 9.1 我的待办列表

```
GET /tasks
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| page | int | ❌ | 页码，默认 1 |
| page_size | int | ❌ | 每页条数，默认 20 |
| status | string | ❌ | pending / processing（默认全部） |
| keyword | string | ❌ | 按实例名称模糊搜索 |

**说明**：
- 仅返回当前用户作为 `assignee_id` 的任务
- 默认按 deadline 升序（最紧急排前面）
- 逾期任务红色标记

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 20,
        "instance_id": 1,
        "instance_name": "XT2026-001产品设计",
        "template_name": "产品设计流程",
        "node_id": 102,
        "node_name": "需求分析",
        "initiator_name": "张三",
        "status": "processing",
        "deadline": "2026-07-14T09:00:00",
        "is_overdue": false,
        "days_remaining": 7,
        "created_at": "2026-07-07T09:00:00"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

> **注意**：开始节点和结束节点不生成 Task，所以不会出现在待办列表中。

---

## 9.2 任务详情

```
GET /tasks/{task_id}
```

**权限**：`ASSIGNEE`（仅任务负责人）

**后端行为**：若 Task 当前状态为 `pending`，自动更新为 `processing`（表示"已开始处理"），记录首次打开时间。

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 20,
    "instance_id": 1,
    "instance_name": "XT2026-001产品设计",
    "template_name": "产品设计流程",
    "node_id": 102,
    "node_name": "需求分析",
    "node_description": "完成项目技术方案和预算方案",
    "initiator_name": "张三",
    "status": "processing",
    "assignee_note": "正在整理方案",
    "deadline": "2026-07-14T09:00:00",
    "is_overdue": false,
    "days_remaining": 7,
    "require_file": true,
    "approvers": [
      { "user_id": 3, "name": "王五" },
      { "user_id": 5, "name": "赵六" }
    ],
    "checkers": [
      { "user_id": 6, "name": "钱七", "status": "pending" },
      { "user_id": 7, "name": "孙八", "status": "pending" }
    ],
    "check_status": "waiting_check",
    "approval_strategy": "all_approve",
    "history_files": [
      {
        "id": 5,
        "original_name": "需求文档.pdf",
        "uploader_name": "发起人",
        "node_name": "开始",
        "created_at": "2026-07-01T09:00:00"
      }
    ],
    "current_files": [
      {
        "id": 10,
        "original_name": "技术方案_v1.docx",
        "file_size": 1024000,
        "can_delete": true,
        "created_at": "2026-07-07T15:00:00"
      }
    ]
  }
}
```

> **字段说明**：
> - `history_files`：之前节点上传的文件（只读，可下载）
> - `current_files`：本节点上传的文件（未提交前可删除，`can_delete=true`）

---

## 9.3 上传文件

```
POST /tasks/{task_id}/files
```

**权限**：`ASSIGNEE`

**请求**：`multipart/form-data`
| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| file | file | ✅ | 文件，限制 50MB，类型：.doc/.docx/.xls/.xlsx/.pdf/.png/.jpg/.jpeg |

**校验**：
- Task 状态必须为 pending 或 processing
- 文件大小 ≤ 50MB
- 文件类型在白名单内

**响应**：
```json
{
  "code": 200,
  "message": "文件上传成功",
  "data": {
    "id": 11,
    "original_name": "预算明细.xlsx",
    "file_size": 512000,
    "created_at": "2026-07-07T16:00:00"
  }
}
```

---

## 9.4 删除文件

```
DELETE /tasks/{task_id}/files/{file_id}
```

**权限**：`ASSIGNEE`

**业务规则**：
- 仅本节点上传且未提交的文件可删除（`can_delete=true`）
- 已提交的文件和历史文件不可删除

---

## 9.5 保存草稿

```
PUT /tasks/{task_id}
```

**权限**：`ASSIGNEE`

**请求体**：
```json
{
  "assignee_note": "方案已按需求完成，请审批"
}
```

**业务规则**：
- Task 状态保持 `processing`
- 仅更新备注，不触发审批

---

## 9.6 提交节点

```
POST /tasks/{task_id}/submit
```

**权限**：`ASSIGNEE`

**请求体**：
```json
{
  "assignee_note": "方案已按需求完成，请审批"
}
```

**校验**：
- Task 状态必须为 pending 或 processing
- 若节点配置 `require_file=true`，至少上传了 1 个文件

**后端处理**：
1. Task 保持 `processing`，先校验当前 `task_id + round` 的文件集合。
2. 在 `asyncio.Semaphore(2)` 限流下完成全部非 PDF 文件转换；Word/Excel 使用 LibreOffice，图片使用 Pillow。
3. **全部转换成功后**：删除原始文件，仅保留最终 PDF；更新 files 的 `file_path`、`stored_name`、`file_size`，并统一 `mime_type = application/pdf`。
4. 在同一数据库事务中原子执行：Task → `waiting_check` 并记录 `submitted_at`/备注；instance_node → `waiting_check`；按当前 `task_id + round` 和 instance_nodes.checkers 创建 CheckRecord（status=pending）；记录日志。
5. 后续仅在当前 `task_id + round` 的 CheckRecord 全部 passed 后，按该轮配置创建 Approval。
6. **任一转换失败**：Task/Node 保持 `processing/running`，不创建 CheckRecord，不进入校验；清理转换产物和临时原件，保留用户已上传的待处理源文件以便修正或重试，并返回 PDF 转换失败。

**说明**：节点提交以全部文件转换成功为前置条件，不存在“已进入校验但 PDF 仍在转换”的中间状态。

**成功响应**：
```json
{
  "code": 200,
  "message": "节点提交成功，文件已转换为 PDF 并进入校验",
  "data": {
    "task_status": "waiting_check",
    "activated_node_ids": []
  }
}
```

转换失败返回业务错误码 `50001`，此时 `task_status` 仍为 `processing`。

> **activated_node_ids 说明**：提交操作不会直接激活下游节点（需要等校验和审批全部通过后才激活），所以提交时此数组始终为空。前端此时代码统一处理：如果 `activated_node_ids` 为空，说明流程在等待校验阶段。

---

# 10. 校验处理

## 10.1 我的校验列表

```
GET /checks
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| page | int | ❌ | 页码，默认 1 |
| page_size | int | ❌ | 每页条数，默认 20 |
| status | string | ❌ | pending / passed / returned（默认 pending） |
| keyword | string | ❌ | 按实例名称模糊搜索 |

**说明**：
- 返回当前用户作为 `checker_id` 的校验记录
- 默认按 created_at 升序（最早提交的排前面）

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 30,
        "instance_id": 1,
        "instance_name": "XT2026-001产品设计",
        "node_id": 102,
        "node_name": "需求分析",
        "submitter_name": "李四",
        "submitted_at": "2026-07-07T16:00:00",
        "status": "pending",
        "created_at": "2026-07-07T16:00:00"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

---

## 10.2 校验详情

```
GET /checks/{check_id}
```

**权限**：`CHECKER`（仅该校验记录的校验人）

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 30,
    "instance_name": "XT2026-001产品设计",
    "node_name": "需求分析",
    "assignee_name": "李四",
    "assignee_note": "方案已按需求完成，请校验",
    "submitted_at": "2026-07-07T16:00:00",
    "files": [
      {
        "id": 10,
        "original_name": "技术方案_v1.pdf",
        "pdf_ready": true,
        "created_at": "2026-07-07T15:00:00"
      }
    ],
    "check_progress": [
      { "checker_name": "钱七", "status": "passed", "opinion": "文件合规", "decided_at": "2026-07-07T17:00:00" },
      { "checker_name": "孙八", "status": "pending", "opinion": null, "decided_at": null }
    ]
  }
}
```

---

## 10.3 校验通过

```
POST /checks/{check_id}/pass
```

**权限**：`CHECKER`

**请求体**：
```json
{
  "opinion": "文件内容合规，格式正确"
}
```

**校验**：
- CheckRecord 状态必须为 pending
- `opinion` 可选，最多 500 字符

**后端处理**：
1. 更新 CheckRecord：status → `passed`，记录 `opinion`、`decided_at`
2. 记录操作日志
3. **检查是否全部通过**：仅查询当前 `task_id + round` 的有效 CheckRecord（排除 terminated）是否均为 passed
   - **未全部通过**：不做额外操作，等待本轮其他校验人
   - **全部通过**：
     - instance_node → `waiting_approval`
     - Task → `waiting_approval`
     - 按当前轮 instance_nodes.approvers 创建 Approval，并关联当前 task_id；文件在提交进入校验前已经全部转换完成

**响应**：
```json
{
  "code": 200,
  "message": "校验通过",
  "data": {
    "all_passed": true,
    "hint": "已进入审批环节"
  }
}
```

---

## 10.4 校验退回

```
POST /checks/{check_id}/return
```

**权限**：`CHECKER`

**请求体**：
```json
{
  "opinion": "文件数据有误，请核实后重新提交"
}
```

**校验**：
- CheckRecord 状态必须为 pending
- `opinion` 必填，最多 500 字符

**后端处理**：
1. 更新 CheckRecord：status → `returned`；其余 pending 校验记录关闭为 `terminated`，记录 `opinion`、`decided_at`
2. 删除当前 task_id + round 的全部物理文件及 files 记录；Task 状态 → `processing`（固定退回当前负责人，不生成新 Task）
3. instance_node 状态 → `running`
4. 记录操作日志
5. 负责人下次打开任务详情页时可看到校验退回意见

> **与审批驳回的区别**：校验退回不改变节点位置（不跳节点），Task 仍是同一个（状态回到 processing），不生成新 Task。审批驳回会跳转到之前节点，原 Task 变为 rejected，生成新 Task。

**响应**：
```json
{
  "code": 200,
  "message": "已退回负责人修改",
  "data": null
}
```

---

# 11. 审批处理

## 11.1 我的审批列表

```
GET /approvals
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| page | int | ❌ | 页码，默认 1 |
| page_size | int | ❌ | 每页条数，默认 20 |
| status | string | ❌ | pending / approved / rejected（默认 pending） |
| keyword | string | ❌ | 按实例名称模糊搜索 |

**说明**：
- 返回当前用户作为 `approver_id` 的审批记录
- 包括中间节点审批（有 task_id）和结束节点终审（task_id=NULL）

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 51,
        "instance_id": 1,
        "instance_name": "XT2026-001产品设计",
        "node_id": 102,
        "node_name": "需求分析",
        "is_end_node": false,
        "submitter_name": "李四",
        "submitted_at": "2026-07-07T16:00:00",
        "status": "pending",
        "created_at": "2026-07-07T16:00:00"
      },
      {
        "id": 60,
        "instance_id": 2,
        "instance_name": "测试项目",
        "node_id": 205,
        "node_name": "结束",
        "is_end_node": true,
        "submitter_name": null,
        "submitted_at": null,
        "status": "pending",
        "created_at": "2026-07-07T10:00:00"
      }
    ],
    "total": 3,
    "page": 1,
    "page_size": 20
  }
}
```

> `is_end_node`：true 表示这是结束节点终审，前端跳转到终审页面（展示全部节点文件）。

---

## 11.2 审批详情

```
GET /approvals/{approval_id}
```

**权限**：`APPROVER`（仅该审批记录的审批人）

**响应**：分为两种场景。

### 中间节点审批

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 51,
    "is_end_node": false,
    "instance_name": "XT2026-001产品设计",
    "node_name": "需求分析",
    "assignee_name": "李四",
    "assignee_note": "方案已按需求完成，请审批",
    "submitted_at": "2026-07-07T16:00:00",
    "files": [
      {
        "id": 10,
        "original_name": "技术方案_v1.pdf",
        "pdf_ready": true,
        "created_at": "2026-07-07T15:00:00"
      }
    ],
    "approval_progress": [
      { "approver_name": "王五", "status": "approved", "opinion": "同意", "decided_at": "2026-07-07T17:00:00" },
      { "approver_name": "赵六", "status": "pending", "opinion": null, "decided_at": null }
    ],
    "available_target_nodes": []
  }
}
```

### 结束节点终审

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "id": 60,
    "is_end_node": true,
    "instance_name": "测试项目",
    "all_nodes_files": [
      {
        "node_id": 201,
        "node_name": "需求分析",
        "files": [
          { "id": 20, "original_name": "技术方案.pdf", "created_at": "..." }
        ]
      },
      {
        "node_id": 202,
        "node_name": "设计评审",
        "files": [
          { "id": 21, "original_name": "实施报告.pdf", "created_at": "..." }
        ]
      }
    ],
    "nodes_approval_summary": [
      { "node_name": "需求分析", "approvers": ["王五 ✅", "赵六 ✅"] },
      { "node_name": "设计评审", "approvers": ["李四 ✅"] }
    ],
    "available_target_nodes": [
      { "node_id": 201, "node_name": "需求分析" },
      { "node_id": 202, "node_name": "设计评审" }
    ]
  }
}
```

> `available_target_nodes`：仅结束节点终审返回；只含已执行的中间工作节点，开始/结束/未执行/跳过节点排除。中间节点审批固定退回当前负责人，返回空数组。

---

## 11.3 审批通过

```
POST /approvals/{approval_id}/approve
```

**权限**：`APPROVER`

**请求体**：
```json
{
  "opinion": "方案合格，同意通过"
}
```

**校验**：
- Approval 状态必须为 pending
- `opinion` 可选，最多 500 字符

**后端处理**：

> **前置条件**：当前 `task_id + round` 的所有 CheckRecord 均为 passed，且本轮 Approval 已生成。

1. **加锁**：`SELECT ... FOR UPDATE` 锁定 instance_node 行，防止并发审批导致状态计算错误（在事务中完成以下全部步骤）
2. 更新 Approval：status → `approved`，记录 `opinion`、`decided_at`
3. **签名上 PDF**（串行化，按 node_id 加锁）：若审批人已上传签名图片，将签名插入当前 `task_id + round` 的节点 PDF
4. 记录操作日志
5. **检查是否全部通过**：仅查询当前 `task_id + round` 的有效 Approval（排除 terminated）是否均为 approved
   - **未全部通过**：不做额外操作，等待本轮其他审批人
   - **全部通过**：
     - instance_node → `finished`，当前节点自身的 `arrived_count` 不增加
     - **若为结束节点**：实例主状态 → `completed`，同时 `archive_status → archived`、写入 `completed_at/archived_at`；V1 同步完成归档
     - **若为中间节点**：遍历该节点的所有直接下游（通过 instance_edges），对每个直接下游节点：
       - 将下游节点的 `arrived_count` + 1
       - 若 `arrived_count == incoming_count`（汇合条件满足）：
         - 若下游是结束节点（is_end=1）：**直接创建 Approval**（task_id=NULL, approver=发起人, status=pending）。结束节点不生成 Task
         - 若下游是中间节点：节点 → `running`，生成 Task，计算 deadline
       - 若 `arrived_count < incoming_count`：该下游节点继续等待
       - 收集本轮被激活的节点 ID，放入 `activated_node_ids` 返回

**响应**：
```json
{
  "code": 200,
  "message": "审批通过",
  "data": {
    "all_approved": true,
    "activated_node_ids": [204],
    "hint": "已进入「方案设计」节点"
  }
}
```

> **activated_node_ids 说明**：
> - 为空数组 `[]`：流程仍在当前阶段（等待其他审批人，或等待并行分支完成）
> - 有值：表示下游节点已被激活。前端可根据此字段提示用户"已进入下一节点"或自动刷新
> - 若激活的节点是结束节点（终审），对应审批人（发起人）的「我的审批」列表将出现新的审批单
> - `all_approved: true` 表示该节点全部审批已完成

---

## 11.4 审批驳回

```
POST /approvals/{approval_id}/reject
```

**权限**：`APPROVER`

**请求体**：
```json
{
  "opinion": "方案数据有误，请重新编写",
  "target_node_id": null
}
```

**校验**：
- Approval 状态必须为 pending
- `opinion` 必填，最多 500 字符
- 中间节点审批时 `target_node_id` 必须为空，目标固定为当前负责人；仅结束节点终审总驳回时必填，且必须是已执行中间工作节点

**后端处理**：

1. 更新 Approval：status → `rejected`，记录 `opinion`、`reject_target_node_id`、`decided_at`
2. 中间节点审批退回：当前轮文件立即删除，instance_node → `running`，当前 Task → `processing`，不跨节点
3. 结束节点终审总驳回：目标节点文件立即删除；目标及受影响下游回退，受影响下游在重新执行到达时删除旧文件
5. **并行分支处理**：驳回节点在某个分支内 → 仅该分支及下游回退；驳回节点在分叉点之前 → 所有分支回退
6. 目标节点重新激活：status → `running`，生成新 Task，重新计算 deadline
7. 记录操作日志

**响应**：
```json
{
  "code": 200,
  "message": "已退回当前负责人修改",
  "data": null
}
```

---

# 12. 文件管理

## 12.1 下载文件

```
GET /files/{file_id}/download
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| type | string | ❌ | V1 仅支持 `pdf`；非 PDF 转换成功后原文件已删除 |

**说明**：
- 返回文件流，浏览器触发下载
- 文件访问通过接口鉴权，不直接暴露 URL

---

## 12.2 补交文件

```
POST /instances/{instance_id}/files/supplement
```

**权限**：running：`INITIATOR` 或当前节点 `ASSIGNEE`；completed（含已归档）：`INITIATOR` 或对应节点历史负责人；terminated 禁止

**请求**：`multipart/form-data`
| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| file | file | ✅ | 文件，限制 50MB，类型同正常上传 |
| node_id | int | — | 关联节点ID（进行中节点补交时必填，全局补交时可选） |

**校验**：
- 进行中节点：当前用户必须是发起人或当前节点负责人
- 已完成/已归档：当前用户必须是发起人或曾参与该流程的节点负责人
- 若传入 node_id，校验该节点属于当前实例

**后端处理**：
1. 保存文件至 `storage/archive/{实例名称}/`（同正常文件）
2. 自动转换为 PDF（同正常文件的转换规则：Semaphore 限流 2 并发，超时 60 秒，失败重试 1 次）
3. 转换成功 → 删除源文件，仅保留最终 PDF，并创建 files 记录：`node_id = <参数或对应节点>`、`task_id = <running 时当前任务，否则 NULL>`、`round = <对应节点轮次>`、`upload_type = 'supplement'`、`file_path = <最终 PDF 相对路径>`、`mime_type = 'application/pdf'`
4. 转换失败 → 清理临时原件，不创建 files 记录，返回 PDF 转换失败；不得进入后续业务状态
5. 记录操作日志
6. 不影响流程状态和节点推进

**响应**：
```json
{
  "code": 200,
  "message": "文件补交成功",
  "data": { "id": 30 }
}
```

---

# 13. 操作日志

## 13.1 全局操作日志

```
GET /logs
```

**权限**：`ADMIN`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| page | int | ❌ | 页码 |
| page_size | int | ❌ | 每页条数，默认 50 |
| node_id | int | ❌ | 按节点筛选 |
| round | int | ❌ | 按执行轮次筛选 |
| keyword | string | ❌ | 按实例名称或操作人姓名模糊搜索 |
| instance_id | int | ❌ | 按流程实例筛选 |
| operation_type | string | ❌ | 按操作类型筛选 |
| operator_id | int | ❌ | 按操作人筛选 |
| date_from | string | ❌ | 开始日期 |
| date_to | string | ❌ | 结束日期 |

**说明**：日志不可修改、不可删除，仅支持查询。

---

# 14. Dashboard

## 14.1 统计数据

```
GET /dashboard/stats
```

**权限**：`ALL`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "running_instances": 23,
    "archived_total": 156,
    "archived_this_month": 12,
    "total_instances": 191,
    "overdue_tasks": 2
  }
}
```

> **说明**：全部为全局统计数据，所有角色看到的内容一致。`archived_this_month` 统计本月新增 Archived 的实例数，`archived_total` 为全系统累计归档数。

---

## 14.2 任务状态分布饼图

```
GET /dashboard/task-status-distribution
```

**权限**：`ALL`

**说明**：统计全系统所有 Task 的状态分布（不含开始/结束节点），用于饼图展示。

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      { "status": "pending", "label": "待处理", "count": 15, "percentage": 34.9, "color": "#FAAD14" },
      { "status": "waiting_check", "label": "待校验", "count": 5, "percentage": 10.4, "color": "#13C2C2" },
      { "status": "processing", "label": "处理中", "count": 8, "percentage": 18.6, "color": "#1890FF" },
      { "status": "waiting_approval", "label": "待审批", "count": 12, "percentage": 27.9, "color": "#722ED1" },
      { "status": "completed", "label": "已完成", "count": 8, "percentage": 18.6, "color": "#52C41A" }
    ],
    "total": 43
  }
}
```

> **说明**：`completed` 仅统计近 30 天内完成的 Task，避免历史数据冲淡饼图。`total` 为五类之和。`color` 为前端推荐颜色，前端可覆盖。

---

## 14.3 流程卡点追踪

```
GET /dashboard/bottlenecks
```

**权限**：`ALL`

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| organization_id | int | ❌ | 按组织筛选 |

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "instance_id": 1,
        "instance_name": "XT2026-001产品设计",
        "template_name": "产品设计流程",
        "organization_name": "通用所",
        "nodes": [
          { "name": "资料上传", "status": "completed", "assignee_name": "张三" },
          { "name": "设计评审资料", "status": "completed", "assignee_name": "李四" },
          { "name": "毛坯图下发", "status": "current", "assignee_name": "王五" },
          { "name": "全套图纸下发", "status": "pending", "assignee_name": "赵六" },
          { "name": "整机BOM下发", "status": "pending", "assignee_name": "钱七" }
        ],
        "days_elapsed": 6,
        "deadline": "2026-07-14T09:00:00",
        "priority": "urgent",
        "risk_level": "normal"
      }
    ]
  }
}
```

> `nodes[].status`：`completed`（已完成）、`current`（进行中）、`pending`（待开始）。只包含工作节点，不含开始/结束。`risk_level`：`overdue`（已逾期）、`warning`（≤2天）、`normal`（正常）。排序规则：优先级优先（urgent → high → normal → low），同优先级内按逾期→即将逾期→正常排序。

---

## 14.4 逾期任务预警

```
GET /dashboard/overdue-tasks
```

**权限**：`ALL`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "instance_name": "项目B",
        "node_name": "设计评审",
        "assignee_name": "王五",
        "deadline": "2026-07-05T09:00:00",
        "remaining_days": -2,
        "remaining_text": "已逾期 2 天",
        "organization_name": "高速所"
      }
    ]
  }
}
```

---

## 14.5 各所流程概览

```
GET /dashboard/org-flow-overview
```

**权限**：`ALL`

**响应**：
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "items": [
      {
        "organization_id": 1,
        "organization_name": "通用所",
        "template_count": 4,
        "total_instance_count": 30,
        "running_count": 12,
        "completed_count": 16,
        "archived_count": 14,
        "terminated_count": 2,
        "instances": [{"instance_id": 1, "instance_name": "XT2026-001产品设计", "status": "running"}],
        "templates": [
          {
            "template_id": 1,
            "template_name": "产品设计流程",
            "current_version": 3,
            "running_count": 5
          }
        ]
      }
    ]
  }
}
```

---

# 15. 系统配置

## 15.1 配置列表

```
GET /configs
```

**权限**：`ADMIN`

**说明**：配置值在应用启动时从数据库加载到内存缓存，运行时每 5 分钟刷新一次。文件上传、签名等需要读取配置的后端模块调用 `ConfigService.get(key)` 从内存读取，不查数据库。

---

## 15.2 更新配置

```
PUT /configs
```

**权限**：`ADMIN`

**请求体**：
```json
{
  "configs": [
    { "config_key": "file_max_size_mb", "config_value": "100" },
    { "config_key": "pdf_signature_x", "config_value": "450" }
  ]
}
```

---

# 16. 个人中心

## 16.1 我的流程记录

```
GET /profile/participations
```

**权限**：`ALL`

**说明**：聚合查询当前用户作为发起人、负责人、审批人参与过的所有流程实例。

**查询参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `role` | string | ❌ | 筛选角色：initiator/assignee/approver |
| `page` | int | ❌ | 默认 1 |
| `page_size` | int | ❌ | 默认 20 |
| `keyword` | string | ❌ | 按实例名称模糊搜索 |

**响应**：
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "instance_id": 1,
        "instance_name": "XT2026-001产品设计",
        "template_name": "产品设计流程",
        "my_role": "approver",
        "participated_node": "需求分析",
        "completed_at": "2026-07-04T15:00:00",
        "status": "completed"
      }
    ],
    "total": 23,
    "page": 1,
    "page_size": 20
  }
}
```

| 字段 | 说明 |
|------|------|
| `my_role` | 我在这个流程中的角色：initiator（发起人）/ assignee（负责人）/ approver（审批人） |
| `participated_node` | 我参与的节点名称（发起人为"-"，审批人为审批的节点名） |
| `completed_at` | 流程完成时间（运行中为 null） |

> 一个实例如果用户以多种角色参与（如既是发起人又是某节点审批人），可能返回多条记录，每条对应一个角色。

---

## 16.2 个人信息

```
GET /profile
```

**权限**：`ALL`

**响应**：同 `/auth/me`。

---

## 16.3 上传签名图片

```
POST /profile/signature
```

**权限**：`ALL`

**请求**：`multipart/form-data`
| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| image | file | ✅ | PNG 格式，透明底，≤500KB，建议 200×60px |

**后端处理**：
- 保存到 `storage/signatures/user_{user_id}.png`
- 更新 `users.signature_image` 字段
- 已有签名则覆盖旧文件

**响应**：
```json
{
  "code": 200,
  "message": "签名上传成功",
  "data": { "signature_url": "/api/v1/profile/signature/preview" }
}
```

---

## 16.4 预览签名

```
GET /profile/signature/preview
```

**权限**：`ALL`

**说明**：返回当前用户的签名图片，用于上传后预览。

---

## 16.5 修改密码

```
PUT /profile/password
```

**权限**：`ALL`

**请求体**：
```json
{
  "old_password": "123456",
  "new_password": "654321"
}
```

**校验**：
- `old_password` 必须正确
- `new_password` 最少 6 位
- 新旧密码不能相同

**响应**：
```json
{
  "code": 200,
  "message": "密码修改成功，请重新登录",
  "data": null
}
```

---

# 17. 附录：错误码

## 17.1 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证（Token 缺失或过期） |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 业务冲突（如重复名称、状态不允许） |
| 413 | 文件大小超限 |
| 415 | 文件类型不支持 |
| 500 | 服务器内部错误 |

## 17.2 业务错误码

| code | message | 说明 |
|------|---------|------|
| 40001 | 参数校验失败 | 请求参数不符合要求 |
| 40002 | 流程名称已存在 | 同组织内模板名称重复 |
| 40010 | 发布校验未通过 | 附带 errors 列表 |
| 40011 | 节点数量不足 | 至少需要 3 个节点 |
| 40012 | 存在未配置的节点 | 工作节点必填项未填 |
| 40013 | 存在孤立节点 | 节点未连通 |
| 40101 | 用户名或密码错误 | |
| 40102 | 账号已被禁用 | |
| 40103 | Token 已过期 | |
| 40301 | 无此操作权限 | |
| 40302 | 非本所流程不可编辑 | |
| 40303 | 仅草稿状态可编辑 | |
| 40304 | 非节点负责人不可操作 | |
| 40305 | 非审批人不可审批 | |
| 40306 | 仅发起人可终止流程 | |
| 40307 | 开始/结束节点不可修改或删除 | |
| 40901 | 该状态不允许此操作 | |
| 40902 | 用户已被禁用 | |
| 40401 | 模板不存在 | |
| 40402 | 实例不存在 | |
| 40403 | 任务不存在 | |
| 40404 | 审批记录不存在 | |
| 40903 | 连线已存在 | 同一对节点不可重复连线 |
| 40904 | 任务已提交，不可重复提交 | |
| 40905 | 模板已停用，不可再次停用 | |
| 40906 | 审批人列表含重复用户 | |
| 40907 | 终审总驳回目标节点不合法 | 目标必须是已执行的中间工作节点 |
| 40908 | 校验记录不存在或无权操作 | |
| 40909 | 校验已处理，不可重复操作 | |
| 50001 | PDF 转换失败 | 后端处理异常 |
| 50002 | 签名插入失败 | pypdf 异常 |
| 50003 | 文件物理丢失 | 数据库记录存在但文件已从磁盘删除 |

---

> **文档版本**：1.0
> **完成日期**：2026-07-07
> **基于**：00_Project_Blueprint.md V1.0 + 01_PRD.md V1.4 + 02_Database_Design.md V1.0
> **状态**：设计完成，等待评审
