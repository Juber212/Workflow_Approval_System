# 企业流程审批系统 — 数据库设计

> **版本**：1.0
> **状态**：设计阶段
> **基于**：00_Project_Blueprint.md V1.0 + 01_PRD.md V1.4
>
> 本文档定义系统全部数据库表结构、字段说明、索引设计和表间关系。

---

# 目录

1. [设计概述](#1-设计概述)
2. [ER 总览](#2-er-总览)
3. [基础数据表](#3-基础数据表)
4. [流程定义表](#4-流程定义表)
5. [流程运行表](#5-流程运行表)
6. [文件与日志表](#6-文件与日志表)
7. [索引策略](#7-索引策略)
8. [附录：完整建表 SQL](#8-附录完整建表-sql)

---

# 1. 设计概述

## 1.1 设计原则

| 原则 | 说明 |
|------|------|
| 模板与实例分离 | flow_templates 负责定义，flow_instances 负责运行，互不干扰 |
| 版本快照 | 发布时 snapshot 完整流程结构到 flow_versions，历史可查 |
| 统一节点模型 | 所有节点存同一张表，is_start / is_end 标志位区分位置 |
| 文件属于实例 | files 表关联 instance_id，不关联 user |
| 日志只写不删 | operation_logs 仅 INSERT 和 SELECT，无 UPDATE / DELETE |
| 状态驱动 | 所有业务对象通过 status 字段驱动流转，不直接删除数据 |
| JSON 存列表 | 审批人列表等简单列表用 JSON 字段，避免过度多表关联 |

## 1.2 核心对象 → 数据表映射

| 业务对象 | 数据表 | 说明 |
|----------|--------|------|
| Organization | organizations | 组织（所） |
| User | users | 用户（含签名图片） |
| Role | roles | 角色定义 |
| — | user_roles | 用户-角色多对多 |
| Flow Template | flow_templates | 流程模板 |
| Work Node（定义） | template_nodes | 模板节点定义 |
| Edge（定义） | template_edges | 模板连线（fork/join 靠连线表达） |
| Flow Version | flow_versions | 发布快照 |
| Flow Instance | flow_instances | 运行实例 |
| Work Node（运行） | instance_nodes | 实例节点（运行时状态） |
| Edge（运行） | instance_edges | 实例连线 |
| Task | tasks | 任务（仅中间节点生成） |
| CheckRecord | check_records | 校验记录 |
| Approval | approvals | 审批记录 |
| File | files | 文件记录 |
| Operation Log | operation_logs | 操作日志（只写不删） |
| — | system_configs | 系统配置 |

共 **17 张表**（新增 check_records）。

## 1.3 命名约定

- 表名：小写 + 下划线 + 复数（`flow_instances`）
- 主键：`id`，INT 自增
- 外键：`{table}_id`（`organization_id`、`template_id`）
- 时间戳：`created_at`（创建）、`updated_at`（更新）、`xxx_at`（业务时间）
- 枚举：MySQL ENUM 类型，可读性优先
- JSON：审批人列表等简单列表，不建额外关联表

---

# 2. ER 总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        基础数据层                                  │
│                                                                    │
│  organizations ──┬── users ──┬── user_roles ── roles              │
│                  │           │                                     │
│                  │           └── signature_image (JSON可扩展)       │
│                  │                                                 │
│  system_configs（独立配置表）                                       │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        流程定义层                                  │
│                                                                    │
│  flow_templates ──┬── template_nodes ── template_edges            │
│                   │                                                │
│                   └── flow_versions（快照 nodes+edges JSON）        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        流程运行层                                  │
│                                                                    │
│  flow_instances ──┬── instance_nodes ── instance_edges            │
│                   │── tasks                                       │
│                   │── check_records                               │
│                   │── approvals                                   │
│                   │── files                                       │
│                   └── operation_logs                              │
└──────────────────────────────────────────────────────────────────┘
```

### 关键关系

```
flow_templates  1 ── N  template_nodes     (一个模板多个节点)
flow_templates  1 ── N  template_edges     (一个模板多条连线)
flow_templates  1 ── N  flow_versions      (一个模板多个版本)
flow_versions   1 ── N  flow_instances     (一个版本多个实例)
flow_instances  1 ── N  instance_nodes     (一个实例多个节点)
flow_instances  1 ── N  instance_edges     (一个实例多条连线)
instance_nodes  1 ── 1  tasks              (一个中间节点一个Task；开始/结束节点无Task)
tasks           1 ── N  check_records      (一个Task多个校验)
check_records   全部passed → 生成 approvals
tasks           1 ── N  approvals          (一个Task多个审批)
instance_nodes  1 ── N  approvals          (结束节点审批直接关联node，无task)
flow_instances  1 ── N  files              (一个实例多个文件)
flow_instances  1 ── N  operation_logs     (一个实例多条日志)
```

---

# 3. 基础数据表

## 3.1 organizations（组织）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| name | VARCHAR(50) | NOT NULL, UNIQUE | 组织名称（通用所、高速所、特装所、标准所） |
| description | VARCHAR(500) | — | 组织描述 |
| is_active | TINYINT(1) | DEFAULT 1 | 是否启用 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **设计说明**：V1 支持新增、编辑、停用/启用组织，不物理删除。所长的关联通过 users.organization_id + user_roles(manager) 查找，不在 organizations 表存 manager_id。

## 3.2 users（用户）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| username | VARCHAR(30) | NOT NULL, UNIQUE | 登录用户名 |
| password_hash | VARCHAR(255) | NOT NULL | 加密密码（bcrypt） |
| real_name | VARCHAR(20) | NOT NULL | 真实姓名 |
| organization_id | INT | NOT NULL, FK→organizations | 所属组织 |
| email | VARCHAR(100) | — | 邮箱 |
| phone | VARCHAR(20) | — | 手机号 |
| signature_image | VARCHAR(500) | — | 签名图片路径（PNG透明底，200×60px，<500KB），NULL=未上传 |
| is_active | TINYINT(1) | DEFAULT 1 | 是否启用（禁用后不可登录） |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **设计说明**：
> - 签名图片存文件路径，不存 BLOB。文件存储在 `storage/signatures/user_{id}.png`
> - 一个用户属于一个组织，一个用户可有多个角色（通过 user_roles）
> - 禁用用户后 JWT Token 立即失效

## 3.3 roles（角色）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| name | VARCHAR(50) | NOT NULL | 角色名称 |
| code | VARCHAR(30) | NOT NULL, UNIQUE | 角色标识（system_admin / manager / user） |
| description | VARCHAR(200) | — | 角色描述 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |

> **预置数据**：
> ```sql
> INSERT INTO roles (name, code, description) VALUES
> ('系统管理员', 'system_admin', '系统维护者，管理用户和组织'),
> ('所长', 'manager', '组织管理者，设计流程、发起流程'),
> ('普通用户', 'user', '流程执行者与审批参与者');
> ```

## 3.4 user_roles（用户角色关联）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| user_id | INT | NOT NULL, FK→users | 用户 |
| role_id | INT | NOT NULL, FK→roles | 角色 |

> **约束**：UNIQUE(user_id, role_id)，一个用户不能重复拥有同一角色。

## 3.5 system_configs（系统配置）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| config_key | VARCHAR(100) | NOT NULL, UNIQUE | 配置键 |
| config_value | VARCHAR(500) | NOT NULL | 配置值 |
| description | VARCHAR(200) | — | 配置说明 |

> **预置数据**：
> ```sql
> INSERT INTO system_configs (config_key, config_value, description) VALUES
> ('file_max_size_mb', '50', '单文件上传大小限制(MB)'),
> ('allowed_file_types', '.doc,.docx,.xls,.xlsx,.pdf,.png,.jpg,.jpeg', '允许上传的文件类型'),
> ('token_expire_hours', '24', 'JWT Token过期时间(小时)'),
> ('system_name', '企业流程审批系统', '系统名称'),
> ('pdf_signature_x', '400', 'PDF签名起始X坐标(像素)'),
> ('pdf_signature_y', '100', 'PDF签名Y坐标(像素)'),
> ('pdf_signature_offset_x', '150', '多签名水平偏移量(像素)'),
> ('pdf_signature_page', '-1', '签名所在页码(-1=最后一页)'),
> ('archive_dir', 'storage/archive', '流程归档根目录'),
> ('libreoffice_path', '/usr/bin/libreoffice', 'LibreOffice可执行文件路径');
> ```

---

# 4. 流程定义表

## 4.1 flow_templates（流程模板）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| name | VARCHAR(50) | NOT NULL | 流程名称（同组织内唯一） |
| description | VARCHAR(500) | — | 流程描述 |
| organization_id | INT | NOT NULL, FK→organizations | 所属组织 |
| status | ENUM('draft','published','disabled') | DEFAULT 'draft' | 模板状态 |
| current_version | INT | DEFAULT 0 | 当前最新版本号（0=从未发布） |
| created_by | INT | NOT NULL, FK→users | 创建人 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **状态流转**：draft → published → disabled。published 后不可直接编辑，需创建新版本（复制为草稿，版本号+1）。

## 4.2 template_nodes（模板节点—统一节点模型）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| template_id | INT | NOT NULL, FK→flow_templates | 所属模板 |
| name | VARCHAR(30) | NOT NULL | 节点名称 |
| description | VARCHAR(500) | — | 节点描述 |
| is_start | TINYINT(1) | DEFAULT 0 | 是否开始节点（第一个） |
| is_end | TINYINT(1) | DEFAULT 0 | 是否结束节点（最后一个） |
| assignee_id | INT | FK→users, NULL | 负责人（开始/结束节点为NULL） |
| time_limit_days | INT | NULL | 完成时限天数（开始/结束为NULL） |
| require_file | TINYINT(1) | DEFAULT 0 | 是否必须上传文件 |
| approvers | JSON | — | 审批人列表 `[{"user_id":1,"name":"张三"},...]` |
| checkers | JSON | — | 校验人列表 `[{"user_id":1,"name":"张三"},...]` |
| approval_strategy | VARCHAR(30) | DEFAULT 'all_approve' | 审批策略（V1固定 all_approve） |
| is_optional | TINYINT(1) | DEFAULT 0 | 是否可选节点（发起实例时可选择跳过） |
| position_x | DECIMAL(10,2) | DEFAULT 0 | LogicFlow 画布 X 坐标 |
| position_y | DECIMAL(10,2) | DEFAULT 0 | LogicFlow 画布 Y 坐标 |
| sort_order | INT | DEFAULT 0 | 展示排序序号 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **JSON 字段说明**：
> ```json
> // approvers 字段示例
> [
>   {"user_id": 3, "name": "李四"},
>   {"user_id": 5, "name": "王五"}
> ]
> 
> // checkers 字段示例
> [
>   {"user_id": 3, "name": "李四"},
>   {"user_id": 5, "name": "王五"}
> ]
> ```

> **设计说明**：
> - 开始节点（is_start=1）：新建模板时自动生成，assignee_id/time_limit_days=NULL，仅展示发起人姓名
> - 结束节点（is_end=1）：新建模板时自动生成，approvers为空（运行时审批人=发起人），assignee_id=NULL
> - 中间节点：所有必填字段完整配置（含校验人、审批人）
> - 审批人用 JSON 存，避免额外关联表。V1 不涉及复杂的审批人查询

## 4.3 template_edges（模板连线）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| template_id | INT | NOT NULL, FK→flow_templates | 所属模板 |
| source_node_id | INT | NOT NULL, FK→template_nodes | 源节点 |
| target_node_id | INT | NOT NULL, FK→template_nodes | 目标节点 |

> **约束**：
> - UNIQUE(source_node_id, target_node_id) — 同一对节点不重复连线
> - 自循环不允许（source ≠ target，应用层校验）
> - is_start=1 的节点不可作为 target_node
> - is_end=1 的节点不可作为 source_node

> **连线表达 fork/join**：
> ```
> -- 串联：start → A → B → end
> edges: (start, A), (A, B), (B, end)
>
> -- 并行：A fork→ B, C；B,C join→ D
> edges: (A, B), (A, C), (B, D), (C, D)
> ```
> 无需额外的分支/合并节点类型，连线关系本身即表达分叉与汇合。

## 4.4 flow_versions（流程版本）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| template_id | INT | NOT NULL, FK→flow_templates | 所属模板 |
| version_number | INT | NOT NULL | 版本号（1, 2, 3…） |
| status | ENUM('published','disabled') | DEFAULT 'published' | 版本状态 |
| nodes_snapshot | JSON | NOT NULL | 节点快照（发布时的完整节点配置） |
| edges_snapshot | JSON | NOT NULL | 连线快照（发布时的完整连线关系） |
| published_by | INT | NOT NULL, FK→users | 发布人 |
| published_at | DATETIME | DEFAULT NOW() | 发布时间 |
| soft_config_overrides | JSON | — | 当前版本节点软配置覆盖层，仅允许 description/assignee/time_limit/checkers/approvers |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |

> **约束**：UNIQUE(template_id, version_number) — 同一模板内版本号唯一。

> **nodes_snapshot 格式**：
> ```json
> [
>   {
>     "template_node_id": 1,
>     "name": "资料上传",
>     "description": "上传项目相关资料",
>     "is_start": false,
>     "is_end": false,
>     "assignee_id": 4,
>     "time_limit_days": 7,
>     "require_file": true,
>     "approvers": [{"user_id": 3, "name": "李四"}],
>     "approval_strategy": "all_approve",
>     "sort_order": 1
>   },
>   ...
> ]
> ```

> **edges_snapshot 格式**：
> ```json
> [
>   {"source_template_node_id": 1, "target_template_node_id": 2},
>   {"source_template_node_id": 2, "target_template_node_id": 3},
>   ...
> ]
> ```

> **设计说明**：
> - 快照使用 template_node_id 作为引用键。创建实例时，按快照生成 instance_nodes，再通过 ID 映射（template_node_id → instance_node_id）生成 instance_edges。
> - 快照数据一旦生成不可修改。已发布模板软修改写入 `soft_config_overrides`，只影响此版本之后发起的新实例；实例创建时合并快照与覆盖层并完整复制，已发起实例完全隔离。`is_optional` 属硬修改。

---

# 5. 流程运行表

## 5.1 flow_instances（流程实例）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| name | VARCHAR(100) | NOT NULL | 流程实例名称（发起时填写，如"XT2026-001产品设计"） |
| description | VARCHAR(500) | — | 补充说明 |
| template_id | INT | NOT NULL, FK→flow_templates | 使用的模板 |
| version_id | INT | NOT NULL, FK→flow_versions | 基于的版本 |
| organization_id | INT | NOT NULL, FK→organizations | 所属组织 |
| initiator_id | INT | NOT NULL, FK→users | 发起人（所长） |
| priority | ENUM('urgent','high','normal','low') | DEFAULT 'normal' | 优先级（紧急/高/普通/低） |
| status | ENUM('created','running','completed','terminated') | DEFAULT 'created' | 主状态 |
| archive_status | ENUM('not_archived','archived') | DEFAULT 'not_archived' | 独立归档状态 |
| termination_reason | VARCHAR(500) | — | 终止原因（仅terminated状态） |
| initiated_at | DATETIME | DEFAULT NOW() | 发起时间 |
| completed_at | DATETIME | — | 完成时间 |
| archived_at | DATETIME | — | 归档时间 |
| terminated_at | DATETIME | — | 终止时间 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **状态流转**：
> ```
> created → running → completed
> 任意未 terminated 状态 → terminated；归档独立为 not_archived → archived
> ```
> - 优先级可在发起后由发起人修改（兜底机制）

> **设计说明**：
> - 实例基于 version_id 快照创建，不受后续模板修改影响
> - completed 和 archived 在第一版中同时发生（终审通过即刻归档），后续可扩展为两步

## 5.2 instance_nodes（实例节点—运行时状态）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| instance_id | INT | NOT NULL, FK→flow_instances | 所属实例 |
| name | VARCHAR(30) | NOT NULL | 节点名称（从模板快照复制） |
| description | VARCHAR(500) | — | 节点描述 |
| is_start | TINYINT(1) | DEFAULT 0 | 是否开始节点 |
| is_end | TINYINT(1) | DEFAULT 0 | 是否结束节点 |
| assignee_id | INT | FK→users, NULL | 负责人 |
| time_limit_days | INT | NULL | 完成时限天数 |
| deadline | DATETIME | — | 截止时间（节点激活时根据 time_limit_days 计算） |
| require_file | TINYINT(1) | DEFAULT 0 | 是否必须上传文件 |
| approvers | JSON | — | 审批人列表（从模板快照复制） |
| checkers | JSON | — | 校验人列表（从模板快照复制） |
| approval_strategy | VARCHAR(30) | DEFAULT 'all_approve' | 审批策略 |
| is_optional | TINYINT(1) | DEFAULT 0 | 是否可选节点（发起实例时可选择跳过） |
| is_skipped | TINYINT(1) | DEFAULT 0 | 是否被跳过（发起时选择跳过则置1） |
| status | ENUM('waiting','running','waiting_check','waiting_approval','finished','rejected','terminated','skipped') | DEFAULT 'waiting' | 节点状态 |
| sort_order | INT | DEFAULT 0 | 排序序号 |
| incoming_count | INT | DEFAULT 0 | 汇合节点上游连线数（发起实例时从 edges 计算；串联节点=1，并行汇合点>1） |
| arrived_count | INT | DEFAULT 0 | 已完成的上游分支数（每完成一个分支+1；arrived_count==incoming_count 时激活汇合节点） |
| round | INT | DEFAULT 1 | 轮次（被驳回重新进入时+1，正常流转保持当前值） |
| started_at | DATETIME | — | 节点激活时间 |
| completed_at | DATETIME | — | 节点完成时间 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **状态流转（中间工作节点）**：
> ```
> waiting → running → waiting_check → waiting_approval → finished
>                      ↓                ↓
>               running（节点内退回）  rejected（仅终审总驳回跨节点）
> ```
> 开始节点：`waiting → finished`（发起后自动跳过）
> 结束节点：`waiting → waiting_approval → finished`
> 终止时：进行中的节点 → `terminated`

> **设计说明**：
> - 发起实例时从 version 快照复制节点数据，生成 instance_nodes
> - deadline 在节点激活（running）时计算：`NOW() + time_limit_days`
> - 驳回后重新执行时，节点 round+1，新 instance_node 不创建，当前节点重置为 running，deadline 重新计算
> - 校验退回时（check_records.status=returned），节点回到 running 状态，Task 回到 processing。不改变 round
> - 校验人和审批人的区别：校验不通过=退回（节点内循环），审批驳回=驳回（跨节点回退）
>
> **并行汇合控制（incoming_count / arrived_count）**：
> - 发起实例时，为每个节点计算 `incoming_count`：查询 `instance_edges WHERE target_node_id = ?` 统计上游连线数。串联节点 = 1，汇合点 > 1
> - 每个节点完成或可选工作节点跳过时，仅其直接下游节点的 `arrived_count` + 1；当前节点自身不增加
> - 当 `arrived_count == incoming_count` 时，所有上游分支均已到达，激活汇合节点
> - 这两个字段由流程引擎维护，前端只读

## 5.3 instance_edges（实例连线）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| instance_id | INT | NOT NULL, FK→flow_instances | 所属实例 |
| source_node_id | INT | NOT NULL, FK→instance_nodes | 源节点 |
| target_node_id | INT | NOT NULL, FK→instance_nodes | 目标节点 |

> **约束**：UNIQUE(source_node_id, target_node_id)

> **设计说明**：
> - 发起实例时从 edges_snapshot + template_node→instance_node ID 映射生成
> - 流程引擎通过此表导航节点流转。查询下游节点：`SELECT target_node_id FROM instance_edges WHERE source_node_id = ?`
> - 判断汇合：`SELECT COUNT(*) FROM instance_edges WHERE target_node_id = ?` > 1 即为 join 节点

## 5.4 tasks（任务）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| instance_id | INT | NOT NULL, FK→flow_instances | 所属流程实例 |
| node_id | INT | NOT NULL, FK→instance_nodes | 所属节点 |
| assignee_id | INT | NOT NULL, FK→users | 负责人（任务执行者） |
| status | ENUM('pending','processing','waiting_check','waiting_approval','completed','rejected','terminated') | DEFAULT 'pending' | 任务状态；无 returned 伪状态 |
| assignee_note | VARCHAR(500) | — | 负责人提交时的备注 |
| submitted_at | DATETIME | — | 提交时间 |
| completed_at | DATETIME | — | 完成时间 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **状态流转**：
> ```
> pending → processing → waiting_check → waiting_approval → completed
>                      ↓                ↓
>               processing（节点内退回） rejected（终审总驳回关闭旧Task）
> ```
> 终止时：进行中的 Task → `terminated`

> **生成为规则**：
> - 开始节点（is_start=1）：**不生成 Task**，发起后自动跳过
> - 中间节点：节点激活时自动生成 Task，assignee_id = instance_nodes.assignee_id
> - 结束节点（is_end=1）：**不生成 Task**，发起人直接在 approvals 中处理

> **驳回后**：原 Task 状态→rejected，重新生成一个 Task（新记录），状态从头开始。

## 5.5 approvals（审批记录）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| instance_id | INT | NOT NULL, FK→flow_instances | 所属流程实例 |
| node_id | INT | NOT NULL, FK→instance_nodes | 所属节点 |
| task_id | INT | FK→tasks, NULL | 关联的 Task（中间节点审批有值，结束节点审批为NULL） |
| approver_id | INT | NOT NULL, FK→users | 审批人 |
| status | ENUM('pending','approved','rejected','terminated') | DEFAULT 'pending' | 审批状态 |
| opinion | VARCHAR(500) | — | 审批意见（通过时可空，驳回时必填） |
| reject_target_node_id | INT | FK→instance_nodes, NULL | 仅结束节点终审总驳回填写；中间审批必须为 NULL |
| signature_applied | TINYINT(1) | DEFAULT 0 | 签名是否已插入 PDF |
| decided_at | DATETIME | — | 审批决定时间 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **状态流转**：
> ```
> pending → approved  （通过，签名自动上PDF）
> pending → rejected  （驳回）
> 终止时 → terminated
> ```

> **生成为规则**：
> - **中间节点**：负责人提交 Task 后，按 instance_nodes.approvers 列表为每个审批人创建一条 Approval，task_id 指向该 Task
> - **结束节点**：所有中间节点完成后，为发起人创建一条 Approval，task_id = NULL
> - 多个审批人并行审批，各自独立决定；完成判定必须限定当前 `task_id + instance_nodes.round` 的有效审批记录（排除 terminated）
> - 中间节点全部 approved → 节点 finished；任一 rejected → 删除当前轮文件并固定退回当前负责人，节点回到 running、原 Task 回到 processing
> - 结束节点终审通过 → 主状态 completed 且同步归档；终审总驳回 → 节点 rejected 并执行跨节点回退

> **退回处理**：
> - 中间节点审批：`reject_target_node_id = NULL`，不得选择目标；立即删除当前 `task_id + round` 文件及 files 记录，不生成新 Task
> - 仅结束节点发起人终审总驳回填写 `reject_target_node_id`；目标必须为已执行的中间工作节点，开始/结束/未执行/跳过节点不可选
> - 总驳回时目标节点文件立即删除；受影响下游回退为 waiting，并在重新执行到达时删除旧文件；目标节点生成新 Task、round+1

---

# 6. 文件与日志表

## 5.6 check_records（校验记录）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| instance_id | INT | NOT NULL, FK→flow_instances | 所属流程实例 |
| node_id | INT | NOT NULL, FK→instance_nodes | 所属节点 |
| task_id | INT | NOT NULL, FK→tasks | 关联的 Task |
| checker_id | INT | NOT NULL, FK→users | 校验人 |
| status | ENUM('pending','passed','returned','terminated') | DEFAULT 'pending' | 校验状态 |
| opinion | VARCHAR(500) | — | 校验意见（通过时可空，退回时必填） |
| decided_at | DATETIME | — | 校验决定时间 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **状态流转**：
> ```
> pending → passed  （校验通过，等待其他校验人）
> pending → returned（校验退回，Task 回到 processing）
> ```

> **生成为规则**：
> - 负责人提交且全部文件转换成功后，按 instance_nodes.checkers 为当前 `task_id + round` 创建 CheckRecord
> - 同一 `task_id + round` 的校验人并行处理；判定时排除 terminated 记录
> - 当前轮有效记录全部 passed → 进入审批并创建关联当前 task_id 的 Approval
> - 当前轮任一 returned → 其余 pending 记录置 terminated，删除当前轮文件，Task 回到 processing；重新提交后为同一 Task 的新提交批次重建本轮校验记录


## 6.1 files（文件）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| instance_id | INT | NOT NULL, FK→flow_instances | 所属流程实例 |
| node_id | INT | FK→instance_nodes, NULL | 上传节点 |
| task_id | INT | FK→tasks, NULL | 正常上传对应任务；补交可为 NULL |
| round | INT | DEFAULT 1 | 文件所属执行轮次 |
| uploader_id | INT | NOT NULL, FK→users | 上传人 |
| upload_type | ENUM('normal','supplement') | DEFAULT 'normal' | 上传类型（normal=正常流程，supplement=补交文件） |
| original_name | VARCHAR(255) | NOT NULL | 原始文件名 |
| stored_name | VARCHAR(255) | NOT NULL | 存储文件名（UUID防冲突） |
| file_path | VARCHAR(500) | NOT NULL | 最终 PDF 存储相对路径 |
| file_size | BIGINT | — | 最终 PDF 大小（字节） |
| mime_type | VARCHAR(100) | 固定 application/pdf | 最终文件 MIME 类型 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | ON UPDATE NOW() | 更新时间 |

> **设计说明**：
> - 文件无 `status` 字段，不存在"已删除"软删除概念。驳回时物理删除文件记录+磁盘文件
> - `updated_at` 用于记录 PDF 转换完成时间
> 
> **文件存储路径**：
> ```
> storage/archive/{实例名称}/   ← 当前文件
> 转换成功后仅保留 PDF，原件删除；转换失败清理临时原件且不创建可流转记录
> ```
> `file_path` 存储最终 PDF 相对路径，如 `{实例名称}/abc123.pdf`；`original_name` 仅保留用户上传名称作为元数据。

> **设计说明**：
> - 文件业务归属流程实例，并通过 node_id/task_id/round 定位来源
> - 三种退回按规则物理删除磁盘文件和 files 记录
> - 非 PDF 转换成功后删除源文件，仅保留最终 PDF，`mime_type` 统一为 `application/pdf`
> - 转换失败不得进入校验，清理临时转换产物，不创建最终 files 记录
> - 审批签名原地修改 `file_path` 指向的最终 PDF

## 6.2 operation_logs（操作日志）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 主键 |
| instance_id | INT | FK→flow_instances, NULL | 所属流程实例（非流程操作可为NULL） |
| operator_type | ENUM('user','system') | DEFAULT 'user' | 操作者类型 |
| operator_id | INT | NULL | 用户操作人；system 时为 NULL |
| triggered_by | INT | NULL | 可选触发人 |
| node_id | INT | NULL | 关联实例节点 |
| operation_type | VARCHAR(50) | NOT NULL | 操作类型 |
| round | INT | DEFAULT 1 | 所属轮次（节点重新进入时递增，用于区分同一节点的多次执行） |
| description | VARCHAR(500) | NOT NULL | 自动生成的描述文本 |
| detail | JSON | — | 操作详情（上下文信息） |
| created_at | DATETIME | DEFAULT NOW() | 操作时间 |

> **operation_type 枚举（代码层维护）**：
> | 类型 | 说明 |
> |------|------|
> | create_template | 创建流程模板 |
> | update_template | 修改流程模板 |
> | publish_template | 发布流程版本 |
> | disable_template | 停用流程 |
> | delete_template | 删除草稿模板 |
> | start_instance | 发起流程实例 |
> | terminate_instance | 终止流程实例 |
> | enter_node | 进入节点（自动记录） |
> | upload_file | 上传文件 |
> | submit_node | 提交节点（含PDF转换） |
> | approve | 审批通过 |
> | reject | 审批驳回 |
> | complete_instance | 流程完成 |
> | archive_instance | 流程归档 |
> | supplement_file | 补交文件 |

> **设计说明**：
> - 日志表只做 INSERT 和 SELECT，无 UPDATE / DELETE
> - detail 字段存 JSON，不同操作存不同上下文：
>   ```json
>   // 审批通过
>   {"approval_id": 42, "opinion": "同意"}
>   // 审批驳回
>   {"approval_id": 42, "reject_target_node_id": 5, "reason": "方案不合格"}
>   // 终止流程
>   {"reason": "项目取消"}
>   ```
> - instance_id 可为 NULL（非流程操作不关联，如系统级操作）
> - 按 created_at 倒序分页查询
>
> **日志长期方案（按年分区表）**：
> - 建表时按 `YEAR(created_at)` 进行 RANGE 分区，提前建好未来 10 年分区
> - 查询完全透明：无需 WHERE 带上年份，MySQL 自动裁剪分区
> - 日志永久保存，禁止 `DELETE` 和 `DROP PARTITION`
> - 新增分区：每年 `ADD PARTITION` 一次，一条命令
> - 正常业务只做 INSERT 和 SELECT，不手动 DELETE

---

# 7. 索引策略

## 7.1 高频查询索引

| 查询场景 | 索引 | 说明 |
|----------|------|------|
| 用户登录 | users.username (UNIQUE) | 登录校验 |
| 用户所属组织 | users.organization_id | 按组织查用户 |
| 某组织的模板列表 | flow_templates(organization_id, status) | 流程管理页 |
| 模板的节点和连线 | template_nodes(template_id), template_edges(template_id) | 设计器加载 |
| 模板版本列表 | flow_versions(template_id, version_number) | 版本历史 |
| 运行中实例 | flow_instances(status) | Dashboard统计 |
| 我发起的流程 | flow_instances(initiator_id, status) | 所长个人中心 |
| 我的待办 | tasks(assignee_id, status) | 个人中心待办列表 |
| 我的审批 | approvals(approver_id, status) | 个人中心审批列表 |
| 我的校验 | check_records(checker_id, status) | 个人中心校验列表 |
| 实例的节点和连线 | instance_nodes(instance_id), instance_edges(instance_id) | 流程详情页 |
| 某节点的当前Task | tasks(node_id, status) | 流程引擎判断节点状态 |
| 某Task的审批记录 | approvals(task_id) | 审批进度查询 |
| 实例的全部文件 | files(instance_id) | 文件记录查询 |
| 实例的操作日志 | operation_logs(instance_id, created_at) | 日志列表（倒序） |
| 逾期检测 | instance_nodes(status, deadline) | Dashboard预警 |

## 7.2 索引设计原则

- 外键默认建索引（MySQL InnoDB 自动创建）
- 高频 WHERE 字段建索引（status 类字段）
- 联合索引遵循最左前缀原则
- JSON 字段不建索引（V1 不需要按审批人查模板）

---

# 8. 附录：完整建表 SQL

```sql
-- ============================================================
-- 企业流程审批系统 — 完整建表 SQL
-- 数据库：MySQL 8.0+
-- 字符集：utf8mb4
-- ============================================================

CREATE DATABASE IF NOT EXISTS workflow_approval
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE workflow_approval;

-- ------------------------------
-- 1. 组织表
-- ------------------------------
CREATE TABLE organizations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE COMMENT '组织名称',
    description VARCHAR(500) COMMENT '组织描述',
    is_active   TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '组织（所）';

-- ------------------------------
-- 2. 用户表
-- ------------------------------
CREATE TABLE users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(30) NOT NULL UNIQUE COMMENT '登录用户名',
    password_hash   VARCHAR(255) NOT NULL COMMENT '加密密码',
    real_name       VARCHAR(20) NOT NULL COMMENT '真实姓名',
    organization_id INT NOT NULL COMMENT '所属组织',
    email           VARCHAR(100) COMMENT '邮箱',
    phone           VARCHAR(20) COMMENT '手机号',
    signature_image VARCHAR(500) COMMENT '签名图片路径',
    is_active       TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org (organization_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
) COMMENT '用户';

-- ------------------------------
-- 3. 角色表
-- ------------------------------
CREATE TABLE roles (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50) NOT NULL COMMENT '角色名称',
    code        VARCHAR(30) NOT NULL UNIQUE COMMENT '角色标识',
    description VARCHAR(200) COMMENT '角色描述',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) COMMENT '角色';

-- ------------------------------
-- 4. 用户角色关联表
-- ------------------------------
CREATE TABLE user_roles (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    UNIQUE KEY uk_user_role (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) COMMENT '用户角色关联';

-- ------------------------------
-- 5. 系统配置表
-- ------------------------------
CREATE TABLE system_configs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    config_key   VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value VARCHAR(500) NOT NULL COMMENT '配置值',
    description  VARCHAR(200) COMMENT '配置说明',
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '系统配置';

-- ------------------------------
-- 6. 流程模板表
-- ------------------------------
CREATE TABLE flow_templates (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(50) NOT NULL COMMENT '流程名称',
    description      VARCHAR(500) COMMENT '流程描述',
    organization_id  INT NOT NULL COMMENT '所属组织',
    status           ENUM('draft','published','disabled') DEFAULT 'draft' COMMENT '模板状态',
    current_version  INT DEFAULT 0 COMMENT '当前最新版本号',
    created_by       INT NOT NULL COMMENT '创建人',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_name (organization_id, name),
    INDEX idx_org (organization_id),
    INDEX idx_org_status (organization_id, status),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
) COMMENT '流程模板';

-- ------------------------------
-- 7. 模板节点表（统一节点模型）
-- ------------------------------
CREATE TABLE template_nodes (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    template_id       INT NOT NULL COMMENT '所属模板',
    name              VARCHAR(30) NOT NULL COMMENT '节点名称',
    description       VARCHAR(500) COMMENT '节点描述',
    is_start          TINYINT(1) DEFAULT 0 COMMENT '是否开始节点',
    is_end            TINYINT(1) DEFAULT 0 COMMENT '是否结束节点',
    assignee_id       INT COMMENT '负责人（开始/结束节点为NULL）',
    time_limit_days   INT COMMENT '完成时限天数',
    require_file      TINYINT(1) DEFAULT 0 COMMENT '是否必须上传文件',
    approvers         JSON COMMENT '审批人列表',
    checkers          JSON COMMENT '校验人列表',
    approval_strategy VARCHAR(30) DEFAULT 'all_approve' COMMENT '审批策略',
    is_optional       TINYINT(1) DEFAULT 0 COMMENT '是否可选节点（发起实例时可选择跳过）',
    position_x        DECIMAL(10,2) DEFAULT 0 COMMENT '画布X坐标',
    position_y        DECIMAL(10,2) DEFAULT 0 COMMENT '画布Y坐标',
    sort_order        INT DEFAULT 0 COMMENT '排序序号',
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_template (template_id),
    INDEX idx_assignee (assignee_id),
    FOREIGN KEY (template_id) REFERENCES flow_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES users(id)
) COMMENT '模板节点';

-- ------------------------------
-- 8. 模板连线表
-- ------------------------------
CREATE TABLE template_edges (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    template_id    INT NOT NULL COMMENT '所属模板',
    source_node_id INT NOT NULL COMMENT '源节点',
    target_node_id INT NOT NULL COMMENT '目标节点',
    UNIQUE KEY uk_edge (source_node_id, target_node_id),
    INDEX idx_template (template_id),
    FOREIGN KEY (template_id) REFERENCES flow_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (source_node_id) REFERENCES template_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id) REFERENCES template_nodes(id) ON DELETE CASCADE
) COMMENT '模板连线';

-- ------------------------------
-- 9. 流程版本表
-- ------------------------------
CREATE TABLE flow_versions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    template_id     INT NOT NULL COMMENT '所属模板',
    version_number  INT NOT NULL COMMENT '版本号',
    status          ENUM('published','disabled') DEFAULT 'published' COMMENT '版本状态',
    nodes_snapshot  JSON NOT NULL COMMENT '节点快照',
    edges_snapshot  JSON NOT NULL COMMENT '连线快照',
    published_by    INT NOT NULL COMMENT '发布人',
    published_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
    soft_config_overrides JSON COMMENT '版本级节点软配置覆盖层',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_template_version (template_id, version_number),
    INDEX idx_template (template_id),
    FOREIGN KEY (template_id) REFERENCES flow_templates(id),
    FOREIGN KEY (published_by) REFERENCES users(id)
) COMMENT '流程版本';

-- ------------------------------
-- 10. 流程实例表
-- ------------------------------
CREATE TABLE flow_instances (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(100) NOT NULL COMMENT '流程实例名称',
    description         VARCHAR(500) COMMENT '补充说明',
    template_id         INT NOT NULL COMMENT '使用的模板',
    version_id          INT NOT NULL COMMENT '基于的版本',
    organization_id     INT NOT NULL COMMENT '所属组织',
    initiator_id        INT NOT NULL COMMENT '发起人（所长）',
    priority            ENUM('urgent','high','normal','low') DEFAULT 'normal' COMMENT '优先级',
    status              ENUM('created','running','completed','terminated') DEFAULT 'created' COMMENT '主状态',
    archive_status      ENUM('not_archived','archived') DEFAULT 'not_archived' COMMENT '归档状态',
    termination_reason  VARCHAR(500) COMMENT '终止原因',
    initiated_at        DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '发起时间',
    completed_at        DATETIME COMMENT '完成时间',
    archived_at         DATETIME COMMENT '归档时间',
    terminated_at       DATETIME COMMENT '终止时间',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_template (template_id),
    INDEX idx_version (version_id),
    INDEX idx_org (organization_id),
    INDEX idx_initiator (initiator_id),
    INDEX idx_initiator_status (initiator_id, status),
    FOREIGN KEY (template_id) REFERENCES flow_templates(id),
    FOREIGN KEY (version_id) REFERENCES flow_versions(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (initiator_id) REFERENCES users(id)
) COMMENT '流程实例';

-- ------------------------------
-- 11. 实例节点表（运行时状态）
-- ------------------------------
CREATE TABLE instance_nodes (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    instance_id       INT NOT NULL COMMENT '所属实例',
    name              VARCHAR(30) NOT NULL COMMENT '节点名称',
    description       VARCHAR(500) COMMENT '节点描述',
    is_start          TINYINT(1) DEFAULT 0 COMMENT '是否开始节点',
    is_end            TINYINT(1) DEFAULT 0 COMMENT '是否结束节点',
    assignee_id       INT COMMENT '负责人',
    time_limit_days   INT COMMENT '完成时限天数',
    deadline          DATETIME COMMENT '截止时间',
    require_file      TINYINT(1) DEFAULT 0 COMMENT '是否必须上传文件',
    approvers         JSON COMMENT '审批人列表',
    checkers          JSON COMMENT '校验人列表',
    approval_strategy VARCHAR(30) DEFAULT 'all_approve' COMMENT '审批策略',
    is_optional       TINYINT(1) DEFAULT 0 COMMENT '是否可选节点（发起实例时可能被跳过）',
    is_skipped        TINYINT(1) DEFAULT 0 COMMENT '是否被跳过（is_optional=1且发起时选择跳过）',
    status            ENUM('waiting','running','waiting_check','waiting_approval','finished','rejected','terminated','skipped') DEFAULT 'waiting' COMMENT '节点状态',
    sort_order        INT DEFAULT 0 COMMENT '排序序号',
    incoming_count    INT DEFAULT 0 COMMENT '汇合节点上游连线数（串联=1，汇合点>1）',
    arrived_count     INT DEFAULT 0 COMMENT '已完成上游分支数（==incoming_count时激活）',
    round             INT DEFAULT 1 COMMENT '轮次（驳回重新进入时+1）',
    started_at        DATETIME COMMENT '节点激活时间',
    completed_at      DATETIME COMMENT '节点完成时间',
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_instance (instance_id),
    INDEX idx_assignee (assignee_id),
    INDEX idx_status_deadline (status, deadline),
    FOREIGN KEY (instance_id) REFERENCES flow_instances(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES users(id)
) COMMENT '实例节点（运行时状态）';

-- ------------------------------
-- 12. 实例连线表
-- ------------------------------
CREATE TABLE instance_edges (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    instance_id    INT NOT NULL COMMENT '所属实例',
    source_node_id INT NOT NULL COMMENT '源节点',
    target_node_id INT NOT NULL COMMENT '目标节点',
    UNIQUE KEY uk_edge (source_node_id, target_node_id),
    INDEX idx_instance (instance_id),
    INDEX idx_source (source_node_id),
    INDEX idx_target (target_node_id),
    FOREIGN KEY (instance_id) REFERENCES flow_instances(id) ON DELETE CASCADE,
    FOREIGN KEY (source_node_id) REFERENCES instance_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id) REFERENCES instance_nodes(id) ON DELETE CASCADE
) COMMENT '实例连线';

-- ------------------------------
-- 13. 任务表
-- ------------------------------
CREATE TABLE tasks (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    instance_id    INT NOT NULL COMMENT '所属流程实例',
    node_id        INT NOT NULL COMMENT '所属节点',
    assignee_id    INT NOT NULL COMMENT '负责人',
    status         ENUM('pending','processing','waiting_check','waiting_approval','completed','rejected','terminated') DEFAULT 'pending' COMMENT '任务状态',
    assignee_note  VARCHAR(500) COMMENT '负责人备注',
    submitted_at   DATETIME COMMENT '提交时间',
    completed_at   DATETIME COMMENT '完成时间',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_instance (instance_id),
    INDEX idx_node (node_id),
    INDEX idx_assignee (assignee_id),
    INDEX idx_assignee_status (assignee_id, status),
    FOREIGN KEY (instance_id) REFERENCES flow_instances(id),
    FOREIGN KEY (node_id) REFERENCES instance_nodes(id),
    FOREIGN KEY (assignee_id) REFERENCES users(id)
) COMMENT '任务';

-- ------------------------------
-- 14. 审批记录表
-- ------------------------------
CREATE TABLE approvals (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    instance_id            INT NOT NULL COMMENT '所属流程实例',
    node_id                INT NOT NULL COMMENT '所属节点',
    task_id                INT COMMENT '关联的Task（结束节点为NULL）',
    approver_id            INT NOT NULL COMMENT '审批人',
    status                 ENUM('pending','approved','rejected','terminated') DEFAULT 'pending' COMMENT '审批状态',
    opinion                VARCHAR(500) COMMENT '审批意见',
    reject_target_node_id  INT COMMENT '仅结束节点终审总驳回目标；中间审批为NULL',
    signature_applied      TINYINT(1) DEFAULT 0 COMMENT '签名是否已上PDF',
    decided_at             DATETIME COMMENT '审批决定时间',
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_instance (instance_id),
    INDEX idx_node (node_id),
    INDEX idx_task (task_id),
    INDEX idx_approver (approver_id),
    INDEX idx_approver_status (approver_id, status),
    FOREIGN KEY (instance_id) REFERENCES flow_instances(id),
    FOREIGN KEY (node_id) REFERENCES instance_nodes(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (approver_id) REFERENCES users(id),
    FOREIGN KEY (reject_target_node_id) REFERENCES instance_nodes(id)
) COMMENT '审批记录';

-- ------------------------------
-- 15. 校验记录表
-- ------------------------------
CREATE TABLE check_records (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    instance_id    INT NOT NULL COMMENT '所属流程实例',
    node_id        INT NOT NULL COMMENT '所属节点',
    task_id        INT NOT NULL COMMENT '关联的Task',
    checker_id     INT NOT NULL COMMENT '校验人',
    status         ENUM('pending','passed','returned','terminated') DEFAULT 'pending' COMMENT '校验状态',
    opinion        VARCHAR(500) COMMENT '校验意见',
    decided_at     DATETIME COMMENT '校验决定时间',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_instance (instance_id),
    INDEX idx_node (node_id),
    INDEX idx_task (task_id),
    INDEX idx_checker (checker_id),
    INDEX idx_checker_status (checker_id, status),
    FOREIGN KEY (instance_id) REFERENCES flow_instances(id),
    FOREIGN KEY (node_id) REFERENCES instance_nodes(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (checker_id) REFERENCES users(id)
) COMMENT '校验记录';

-- ------------------------------
-- 16. 文件表
-- ------------------------------
CREATE TABLE files (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    instance_id   INT NOT NULL COMMENT '所属流程实例',
    node_id       INT COMMENT '上传节点',
    task_id       INT COMMENT '关联任务（补交可为NULL）',
    round         INT DEFAULT 1 COMMENT '文件所属轮次',
    uploader_id   INT NOT NULL COMMENT '上传人',
    upload_type   ENUM('normal','supplement') DEFAULT 'normal' COMMENT '上传类型',
    original_name VARCHAR(255) NOT NULL COMMENT '原始文件名',
    stored_name   VARCHAR(255) NOT NULL COMMENT '存储文件名（UUID）',
    file_path     VARCHAR(500) NOT NULL COMMENT '最终PDF存储相对路径',
    file_size     BIGINT COMMENT '最终PDF大小（字节）',
    mime_type     VARCHAR(100) NOT NULL DEFAULT 'application/pdf' COMMENT '最终文件MIME类型',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_instance (instance_id),
    INDEX idx_node (node_id),
    INDEX idx_task (task_id),
    INDEX idx_uploader (uploader_id),
    FOREIGN KEY (instance_id) REFERENCES flow_instances(id),
    FOREIGN KEY (node_id) REFERENCES instance_nodes(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (uploader_id) REFERENCES users(id)
) COMMENT '文件';

-- ------------------------------
-- 17. 操作日志表（按年分区）
-- ------------------------------
-- 注意：分区键 created_at 必须在主键中（MySQL 分区要求）
CREATE TABLE operation_logs (
    id             INT AUTO_INCREMENT,
    instance_id    INT COMMENT '所属流程实例（非流程操作为NULL）',
    operator_type  ENUM('user','system') DEFAULT 'user' COMMENT '操作者类型',
    operator_id    INT COMMENT '操作人；系统操作为NULL',
    triggered_by   INT COMMENT '可选触发人',
    node_id        INT COMMENT '关联实例节点',
    operation_type VARCHAR(50) NOT NULL COMMENT '操作类型',
    round          INT DEFAULT 1 COMMENT '所属轮次',
    description    VARCHAR(500) NOT NULL COMMENT '自动生成的描述文本',
    detail         JSON COMMENT '操作详情',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间（分区键）',
    PRIMARY KEY (id, created_at),          -- created_at 加入主键（分区要求，对代码零影响）
    INDEX idx_instance (instance_id),
    INDEX idx_operator (operator_id),
    INDEX idx_type (operation_type),
    INDEX idx_created (created_at),
    INDEX idx_instance_created (instance_id, created_at),
    -- 分区表不建立与 users/instances 的外键，归属一致性由应用层校验；避免 MySQL 分区与外键不兼容
    INDEX idx_node_round (node_id, round)
) COMMENT '操作日志（只写不删，按年分区）'
PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2026 VALUES LESS THAN (2027),
    PARTITION p2027 VALUES LESS THAN (2028),
    PARTITION p2028 VALUES LESS THAN (2029),
    PARTITION p2029 VALUES LESS THAN (2030),
    PARTITION p2030 VALUES LESS THAN (2031),
    PARTITION p2031 VALUES LESS THAN (2032),
    PARTITION p2032 VALUES LESS THAN (2033),
    PARTITION p2033 VALUES LESS THAN (2034),
    PARTITION p2034 VALUES LESS THAN (2035),
    PARTITION p2035 VALUES LESS THAN (2036),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

---

> **文档版本**：1.0
> **完成日期**：2026-07-07
> **基于**：00_Project_Blueprint.md V1.0 + 01_PRD.md V1.4
> **状态**：设计完成，等待评审
