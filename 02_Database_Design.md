# 企业流程审批系统 — 数据库设计

> **版本**：3.0 | **状态**：与代码同步 | **更新**：2026-08-10
>
> 基于 24 个 SQLAlchemy 模型。所有字段定义以 `models/*.py` 中的 `comment=` 和类型声明为准。

---

## 1. 数据库配置

| 配置项 | 值 |
|--------|-----|
| 引擎 | MySQL 8.0 InnoDB |
| 字符集 | utf8mb4 + utf8mb4_unicode_ci |
| ORM | SQLAlchemy 2.0 async（`AsyncSession`） |
| 基类 | `Base` = `DeclarativeBase`（无共享 mixin） |
| 迁移 | Alembic（`alembic/versions/`） |
| 分区 | `operation_logs` 按年 RANGE 分区（分区键 `created_at`） |

### 连接参数

```python
# config.py
"mysql+aiomysql://user:pass@host:3306/dbname?charset=utf8mb4"

# database.py — aiomysql 兜底
connect_args={"charset": "utf8mb4"}
```

> aiomysql 不支持 `collation` URL 参数，collation 在数据库级别设置：
> ```sql
> ALTER DATABASE workflow_approval CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> ```

---

## 2. 表清单（24 张）

### 2.1 基础数据层（5 张）

#### `organizations` — 组织（所）

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | name | VARCHAR(50) | NOT NULL, UNIQUE | 组织名称 |
| 3 | description | VARCHAR(500) | NULL | 组织描述 |
| 4 | is_active | BOOLEAN | DEFAULT TRUE | 是否启用（软删除） |
| 5 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 6 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 关联：`users.organization_id` FK → `organizations.id`

#### `users` — 用户

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | username | VARCHAR(30) | NOT NULL, UNIQUE | 登录用户名 |
| 3 | password_hash | VARCHAR(255) | NOT NULL | bcrypt 加密密码 |
| 4 | real_name | VARCHAR(20) | NOT NULL | 真实姓名 |
| 5 | organization_id | INT | FK→organizations, NULL | 所属组织（管理员可选空） |
| 6 | email | VARCHAR(100) | NULL | 邮箱 |
| 7 | phone | VARCHAR(20) | NULL | 手机号 |
| 8 | signature_image | VARCHAR(500) | NULL | 签名图片路径 |
| 9 | is_active | BOOLEAN | DEFAULT TRUE | 是否启用（软禁用） |
| 10 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 11 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 关联：User.organization → Organization（relationship back_populates）

#### `roles` — 角色定义

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | name | VARCHAR(50) | NOT NULL | 角色名称 |
| 3 | code | VARCHAR(30) | NOT NULL, UNIQUE | 角色标识：system_admin / manager / user |
| 4 | description | VARCHAR(200) | NULL | 角色描述 |
| 5 | created_at | DATETIME | DEFAULT NOW | 创建时间 |

> 预置数据：system_admin、manager、user（由 `python -m app.core.seed` 幂等创建，无需手工 INSERT）

#### `user_roles` — 用户-角色关联

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | user_id | INT | NOT NULL（无 FK） | 用户 ID |
| 3 | role_id | INT | NOT NULL（无 FK） | 角色 ID |

> 无 FK 约束——应用层保证数据完整性

#### `system_configs` — 系统配置

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | config_key | VARCHAR(50) | NOT NULL, UNIQUE | 配置键（如 max_file_size_mb） |
| 3 | config_value | VARCHAR(500) | NOT NULL | 配置值 |
| 4 | config_type | VARCHAR(20) | DEFAULT 'string' | 值类型：string / int / float / bool / json |
| 5 | description | VARCHAR(200) | NULL | 配置说明 |
| 6 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 7 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 读取时使用内存缓存（避免每次查 DB）

---

### 2.2 流程定义层（7 张）

#### `flow_templates` — 流程模板

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | name | VARCHAR(50) | NOT NULL | 流程名称 |
| 3 | description | VARCHAR(500) | NULL | 流程描述 |
| 4 | type | VARCHAR(20) | DEFAULT 'project' | 模板类型：project / proposal |
| 5 | organization_id | INT | FK→organizations, NOT NULL | 所属组织 |
| 6 | created_by | INT | FK→users, NOT NULL | 创建人 |
| 7 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 8 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 关联：template_nodes、template_edges 均有 FK CASCADE

#### `template_nodes` — 模板节点（统一节点模型）

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | template_id | INT | FK→flow_templates CASCADE, NOT NULL | 所属模板 |
| 3 | name | VARCHAR(30) | NOT NULL | 节点名称 |
| 4 | description | VARCHAR(500) | NULL | 节点描述 |
| 5 | is_start | BOOLEAN | DEFAULT FALSE | 是否开始节点 |
| 6 | is_end | BOOLEAN | DEFAULT FALSE | 是否结束节点 |
| 7 | assignee_id | INT | FK→users, NULL | 负责人 |
| 8 | time_limit_days | INT | NULL | 完成时限（工作日） |
| 9 | require_file | BOOLEAN | DEFAULT FALSE | 是否必须上传文件 |
| 10 | file_folders | JSON | NULL | 文件提交文件夹配置 `[{name, required, file_count}]` |
| 11 | approvers | JSON | NULL | 审批人列表 `[{"user_id": N}]` |
| 12 | checkers | JSON | NULL | 校验人列表 `[{"user_id": N}]` |
| 13 | approval_strategy | VARCHAR(30) | DEFAULT 'all_approve' | 审批策略（V1 固定全部通过） |
| 14 | require_assignee_signature | BOOLEAN | DEFAULT TRUE | 负责人提交时是否签名 |
| 15 | require_checker_signature | BOOLEAN | DEFAULT TRUE | 校验人通过时是否签名 |
| 16 | require_approver_signature | BOOLEAN | DEFAULT TRUE | 审批人通过时是否签名 |
| 17 | endorser_id | INT | FK→users, NULL | 批准人（仅 difficulty=4 生效） |
| 18 | require_endorser_signature | BOOLEAN | DEFAULT TRUE | 批准人通过时是否签名 |
| 19 | signature_x | FLOAT | DEFAULT 400 | 签名默认 X 坐标 |
| 20 | signature_y | FLOAT | DEFAULT 100 | 签名默认 Y 坐标 |
| 21 | signature_page | INT | DEFAULT -1 | 签名默认页码（-1=最后一页） |
| 22 | position_x | FLOAT | DEFAULT 0 | 画布 X 坐标 |
| 23 | position_y | FLOAT | DEFAULT 0 | 画布 Y 坐标 |
| 24 | sort_order | INT | DEFAULT 0 | 排序序号 |
| 25 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 26 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

#### `template_edges` — 模板连线

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | template_id | INT | FK→flow_templates CASCADE, NOT NULL | 所属模板 |
| 3 | source_node_id | INT | FK→template_nodes CASCADE, NOT NULL | 源节点 |
| 4 | target_node_id | INT | FK→template_nodes CASCADE, NOT NULL | 目标节点 |
| 5 | created_at | DATETIME | DEFAULT NOW | 创建时间 |

> UNIQUE(source_node_id, target_node_id)

#### `document_templates` — 文件模板

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | organization_id | INT | FK→organizations CASCADE, NOT NULL | 所属组织 |
| 3 | name | VARCHAR(100) | NOT NULL | 模板名称（显示给用户） |
| 4 | original_name | VARCHAR(200) | NOT NULL | 原始文件名 |
| 5 | file_path | VARCHAR(500) | NOT NULL | 文件存储路径（相对 STORAGE_ROOT） |
| 6 | file_size | INT | DEFAULT 0 | 文件大小（字节） |
| 7 | file_type | VARCHAR(10) | NOT NULL | 文件类型：docx / xlsx |
| 8 | created_by | INT | FK→users, NOT NULL | 上传人 |
| 9 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 10 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

#### `template_document_links` — 模板↔文件模板关联

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | template_id | INT | FK→flow_templates CASCADE, NOT NULL | 流程模板 ID |
| 3 | document_id | INT | FK→document_templates CASCADE, NULL | 文件模板 ID（与 category_id 互斥） |
| 4 | category_id | INT | FK→template_categories CASCADE, NULL | 分类 ID（模板包，与 document_id 互斥） |
| 5 | created_at | DATETIME | DEFAULT NOW | 创建时间 |

> UNIQUE(template_id, document_id)，UNIQUE(template_id, category_id)

#### `template_categories` — 模板分类（模板包），按组织隔离

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | organization_id | INT | FK→organizations CASCADE, NOT NULL | 所属组织 |
| 3 | name | VARCHAR(100) | NOT NULL | 分类名称 |
| 4 | description | VARCHAR(200) | NULL | 分类描述 |
| 5 | created_by | INT | FK→users, NOT NULL | 创建人 |
| 6 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 7 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

#### `template_category_documents` — 分类↔文件模板 多对多

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | category_id | INT | FK→template_categories CASCADE, NOT NULL | 分类 ID |
| 3 | document_id | INT | FK→document_templates CASCADE, NOT NULL | 文件模板 ID |
| 4 | created_at | DATETIME | DEFAULT NOW | 创建时间 |

> UNIQUE(category_id, document_id)

---

### 2.3 流程运行层（11 张）

#### `flow_instances` — 流程实例

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | name | VARCHAR(100) | NOT NULL | 项目名称（实例名称） |
| 3 | description | VARCHAR(500) | NULL | 补充说明 |
| 4 | template_id | INT | NOT NULL（无 FK） | 使用的模板 ID（冗余，模板可删除） |
| 5 | template_name | VARCHAR(100) | NOT NULL | 模板名称快照 |
| 6 | template_type | VARCHAR(20) | DEFAULT 'project' | 模板类型快照：project / proposal |
| 7 | organization_id | INT | FK→organizations, NOT NULL | 所属组织 |
| 8 | initiator_id | INT | FK→users, NOT NULL | 发起人 |
| 9 | priority | VARCHAR(20) | DEFAULT 'normal' | 优先级：urgent / high / normal / low |
| 10 | difficulty | VARCHAR(20) | DEFAULT '1' | 难度等级：1 / 2 / 3 / 4 |
| 11 | contract_no | VARCHAR(100) | NULL | 合同号 |
| 12 | product_model | VARCHAR(100) | NULL | 产品型号 |
| 13 | sales_manager | VARCHAR(50) | NULL | 销售经理 |
| 14 | proposal_id | INT | FK→flow_instances(id), NULL | 关联的方案 ID（仅项目类型可用） |
| 15 | doc_template_ids | JSON | NULL | 实例级文件模板 ID 列表 |
| 16 | status | VARCHAR(20) | DEFAULT 'created' | 主状态：created / running / completed / terminated |
| 17 | termination_reason | VARCHAR(500) | NULL | 终止原因 |
| 18 | initiated_at | DATETIME | DEFAULT NOW | 发起时间 |
| 19 | completed_at | DATETIME | NULL | 完成时间 |
| 20 | terminated_at | DATETIME | NULL | 终止时间 |
| 21 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 22 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 关键设计：`template_id` 无 FK（模板可删除），`template_name` + `template_type` 快照解耦

#### `instance_nodes` — 实例节点（运行时状态）

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | instance_id | INT | FK→flow_instances CASCADE, NOT NULL | 所属实例 |
| 3 | name | VARCHAR(30) | NOT NULL | 节点名称 |
| 4 | description | VARCHAR(500) | NULL | 节点描述 |
| 5 | is_start | BOOLEAN | DEFAULT FALSE | 是否开始节点 |
| 6 | is_end | BOOLEAN | DEFAULT FALSE | 是否结束节点 |
| 7 | assignee_id | INT | FK→users, NULL | 负责人 |
| 8 | time_limit_days | INT | NULL | 完成时限（工作日） |
| 9 | deadline | DATETIME | NULL | 截止时间（发起时预计算） |
| 10 | require_file | BOOLEAN | DEFAULT FALSE | 是否必须上传文件 |
| 11 | file_folders | JSON | NULL | 文件提交文件夹配置快照 |
| 12 | approvers | JSON | NULL | 审批人列表快照 |
| 13 | checkers | JSON | NULL | 校验人列表快照 |
| 14 | approval_strategy | VARCHAR(30) | DEFAULT 'all_approve' | 审批策略 |
| 15 | require_assignee_signature | BOOLEAN | DEFAULT TRUE | 负责人签名开关 |
| 16 | require_checker_signature | BOOLEAN | DEFAULT TRUE | 校验人签名开关 |
| 17 | require_approver_signature | BOOLEAN | DEFAULT TRUE | 审批人签名开关 |
| 18 | endorser_id | INT | FK→users, NULL | 批准人 |
| 19 | require_endorser_signature | BOOLEAN | DEFAULT TRUE | 批准人签名开关 |
| 20 | signature_x | FLOAT | DEFAULT 400 | 签名默认 X |
| 21 | signature_y | FLOAT | DEFAULT 100 | 签名默认 Y |
| 22 | signature_page | INT | DEFAULT -1 | 签名默认页码 |
| 23 | status | VARCHAR(20) | DEFAULT 'waiting' | 节点状态（见枚举） |
| 24 | sort_order | INT | DEFAULT 0 | 排序序号 |
| 25 | incoming_count | INT | DEFAULT 0 | 汇合节点上游连线数 |
| 26 | arrived_count | INT | DEFAULT 0 | 已完成上游分支数 |
| 27 | round | INT | DEFAULT 1 | 执行轮次（驳回+1） |
| 28 | started_at | DATETIME | NULL | 节点激活时间 |
| 29 | completed_at | DATETIME | NULL | 节点完成时间 |
| 30 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 31 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> `incoming_count` + `arrived_count` 实现 fork/join 汇合控制
> `round` 字段记录执行轮次，驳回时 +1

#### `instance_edges` — 实例连线

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | instance_id | INT | FK→flow_instances CASCADE, NOT NULL | 所属实例 |
| 3 | source_node_id | INT | FK→instance_nodes CASCADE, NOT NULL | 源节点 |
| 4 | target_node_id | INT | FK→instance_nodes CASCADE, NOT NULL | 目标节点 |

> UNIQUE(source_node_id, target_node_id)

#### `tasks` — 任务

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | instance_id | INT | FK→flow_instances, NOT NULL | 所属项目 |
| 3 | node_id | INT | FK→instance_nodes, NOT NULL | 所属节点 |
| 4 | assignee_id | INT | FK→users, NOT NULL | 负责人 |
| 5 | status | VARCHAR(20) | DEFAULT 'pending' | 任务状态 |
| 6 | assignee_note | VARCHAR(500) | NULL | 负责人备注 |
| 7 | submitted_at | DATETIME | NULL | 提交时间（驳回时清除） |
| 8 | completed_at | DATETIME | NULL | 完成时间 |
| 9 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 10 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 仅中间节点（is_start=0, is_end=0）生成 Task
> 驳回不创建新 Task，复用原 Task，清除 submitted_at + round+1

#### `check_records` — 校验记录

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | instance_id | INT | FK→flow_instances, NOT NULL | 所属项目 |
| 3 | node_id | INT | FK→instance_nodes, NOT NULL | 所属节点 |
| 4 | task_id | INT | FK→tasks, NOT NULL | 关联 Task |
| 5 | checker_id | INT | FK→users, NOT NULL | 校验人 |
| 6 | status | VARCHAR(20) | DEFAULT 'pending' | 校验状态 |
| 7 | opinion | VARCHAR(500) | NULL | 校验意见 |
| 8 | round | INT | DEFAULT 1 | 节点轮次 |
| 9 | decided_at | DATETIME | NULL | 校验决定时间 |
| 10 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 11 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 由任务提交时创建，每个校验人一条记录，并行处理

#### `approvals` — 审批记录

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | instance_id | INT | FK→flow_instances, NOT NULL | 所属项目 |
| 3 | node_id | INT | FK→instance_nodes, NOT NULL | 所属节点 |
| 4 | task_id | INT | FK→tasks, NULL | 关联 Task（结束节点为 NULL） |
| 5 | approver_id | INT | FK→users, NOT NULL | 审批人 |
| 6 | status | VARCHAR(20) | DEFAULT 'pending' | 审批状态 |
| 7 | opinion | VARCHAR(500) | NULL | 审批意见 |
| 8 | round | INT | DEFAULT 1 | 节点轮次 |
| 9 | reject_target_node_id | INT | FK→instance_nodes, NULL | 终审驳回目标节点 |
| 10 | signature_applied | BOOLEAN | DEFAULT FALSE | 签名是否已上 PDF |
| 11 | signature_x | FLOAT | NULL | 审批人调整后的签名 X |
| 12 | signature_y | FLOAT | NULL | 审批人调整后的签名 Y |
| 13 | signature_page | INT | NULL | 审批人选择的签名页码 |
| 14 | decided_at | DATETIME | NULL | 审批决定时间 |
| 15 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 16 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 结束节点审批：`task_id=NULL`，`reject_target_node_id` 指向驳回目标
> 审批全部通过后批量签名上 PDF

#### `endorsements` — 批准记录

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | instance_id | INT | FK→flow_instances, NOT NULL | 所属项目 |
| 3 | node_id | INT | FK→instance_nodes, NOT NULL | 所属节点 |
| 4 | task_id | INT | FK→tasks, NULL | 关联 Task（结束节点为 NULL） |
| 5 | endorser_id | INT | FK→users, NOT NULL | 批准人 |
| 6 | status | VARCHAR(20) | DEFAULT 'pending' | 批准状态 |
| 7 | opinion | VARCHAR(500) | NULL | 批准意见 |
| 8 | round | INT | DEFAULT 1 | 节点轮次 |
| 9 | signature_applied | BOOLEAN | DEFAULT FALSE | 签名是否已上 PDF |
| 10 | signature_x | FLOAT | NULL | 批准人调整后的签名 X |
| 11 | signature_y | FLOAT | NULL | 批准人调整后的签名 Y |
| 12 | signature_page | INT | NULL | 批准人选择的签名页码 |
| 13 | decided_at | DATETIME | NULL | 批准决定时间 |
| 14 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 15 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 仅 difficulty=4 + 有 endorser_id 时创建
> 单人决策，与 Approval 结构相似但语义独立

#### `files` — 文件记录

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | instance_id | INT | FK→flow_instances, NOT NULL | 所属项目 |
| 3 | node_id | INT | FK→instance_nodes, NULL | 上传节点 |
| 4 | task_id | INT | FK→tasks, NULL | 关联任务（补交可为 NULL） |
| 5 | round | INT | DEFAULT 1 | 文件所属轮次 |
| 6 | uploader_id | INT | FK→users, NOT NULL | 上传人 |
| 7 | upload_type | VARCHAR(20) | DEFAULT 'normal' | 上传类型：normal / supplement |
| 8 | folder_name | VARCHAR(100) | NULL | 所属文件夹名称 |
| 9 | original_name | VARCHAR(255) | NOT NULL | 原始文件名 |
| 10 | stored_name | VARCHAR(255) | NOT NULL | 存储文件名（UUID） |
| 11 | file_path | VARCHAR(500) | NOT NULL | 最终 PDF 存储相对路径 |
| 12 | file_size | BIGINT | NULL | 最终 PDF 大小（字节） |
| 13 | mime_type | VARCHAR(100) | DEFAULT 'application/pdf' | 最终文件 MIME 类型 |
| 14 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 15 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 提交时所有非 PDF 自动转为 PDF，路径和 MIME 类型更新为 PDF
> `upload_type=supplement` 的文件不影响流程状态，仅做补充

#### `signatures` — 签名记录

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | file_id | INT | FK→files CASCADE, NOT NULL | 签在哪个文件 |
| 3 | signer_id | INT | FK→users, NOT NULL | 签名人 |
| 4 | role_type | VARCHAR(20) | NOT NULL | 签名角色：assignee / checker / approver / endorser |
| 5 | source_id | INT | NOT NULL（无 FK） | 业务记录 ID（task_id / check_id / approval_id / endorsement_id） |
| 6 | node_id | INT | FK→instance_nodes, NOT NULL | 所属节点 |
| 7 | signature_x | FLOAT | DEFAULT 400 | 签名 X 坐标 |
| 8 | signature_y | FLOAT | DEFAULT 100 | 签名 Y 坐标 |
| 9 | signature_page | INT | DEFAULT -1 | 签名页码（-1=最后一页） |
| 10 | signature_width | FLOAT | NULL | 签名指定宽度（NULL=使用全局配置） |
| 11 | signature_height | FLOAT | NULL | 签名指定高度（NULL=使用全局配置） |
| 12 | applied | BOOLEAN | DEFAULT FALSE | 是否已写入 PDF |
| 13 | sort_order | INT | DEFAULT 0 | 同文件同角色多次签名排序 |
| 14 | created_at | DATETIME | DEFAULT NOW | 创建时间 |

> `source_id` 无 FK——多态关联（task/check/approval/endorsement 四张表）
> `applied=False` → 等全部通过后批量写入；`applied=True` → 已写入 PDF

#### `operation_logs` — 操作日志

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK (复合), AUTO_INCREMENT | 自增 ID |
| 2 | instance_id | INT | NULL（无 FK） | 所属项目 |
| 3 | operator_type | VARCHAR(20) | DEFAULT 'user' | 操作者类型：user |
| 4 | operator_id | INT | NULL | 操作人（系统操作为 NULL） |
| 5 | triggered_by | INT | NULL | 可选触发人 |
| 6 | node_id | INT | NULL（无 FK） | 关联实例节点 |
| 7 | operation_type | VARCHAR(50) | NOT NULL | 操作类型 |
| 8 | round | INT | DEFAULT 1 | 所属轮次 |
| 9 | description | VARCHAR(500) | NOT NULL | 自动生成的描述文本 |
| 10 | detail | JSON | NULL | 操作详情（自由格式） |
| 11 | created_at | DATETIME | PK (复合), DEFAULT NOW | 操作时间（分区键） |

> **复合主键 `(id, created_at)`**：MySQL 分区表强制要求分区键属于所有唯一键
> **按年 RANGE 分区**：每年一个分区，需提前创建未来年份分区
> **无任何 FK**：日志独立存在，不因关联数据删除而丢失
> **只写不删**：仅 INSERT + SELECT，无 UPDATE/DELETE

#### `notifications` — 通知

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | user_id | INT | FK→users, NOT NULL | 接收人 |
| 3 | type | VARCHAR(30) | NOT NULL | 通知类型（8 种） |
| 4 | title | VARCHAR(200) | NOT NULL | 通知标题 |
| 5 | content | VARCHAR(500) | NOT NULL | 通知内容 |
| 6 | link | VARCHAR(300) | NULL | 点击跳转路径 |
| 7 | is_read | BOOLEAN | DEFAULT FALSE | 是否已读 |
| 8 | created_at | DATETIME | DEFAULT NOW | 通知时间 |

> 通知类型：task_assigned / check_assigned / approval_assigned / endorsement_assigned / check_returned / approval_rejected / final_rejected / endorsement_rejected
> 某些通知在操作完成时物理删除（clear_related），其余标记已读

---

### 2.4 辅助层（1 张）

#### `node_presets` — 节点预设

| # | 字段 | 类型 | 约束 | 说明 |
|---|------|------|------|------|
| 1 | id | INT | PK, AUTO_INCREMENT | 自增主键 |
| 2 | user_id | INT | FK→users, NOT NULL | 所属用户 |
| 3 | name | VARCHAR(30) | NOT NULL | 预设名称（列表中显示） |
| 4 | node_name | VARCHAR(30) | NOT NULL | 拖出后默认节点名称 |
| 5 | assignee_id | INT | FK→users, NULL | 负责人 ID |
| 6 | checkers | JSON | NULL | 校验人列表 `[{"user_id": N}]` |
| 7 | approvers | JSON | NULL | 审批人列表 `[{"user_id": N}]` |
| 8 | time_limit_days | INT | NULL | 完成时限（工作日） |
| 9 | require_file | BOOLEAN | DEFAULT FALSE | 是否必须上传文件 |
| 10 | sort_order | INT | DEFAULT 0 | 排序序号 |
| 11 | created_at | DATETIME | DEFAULT NOW | 创建时间 |
| 12 | updated_at | DATETIME | DEFAULT NOW, ON UPDATE | 更新时间 |

> 用户个人快捷模板，设计器中拖出到画布自动填充配置

---

## 3. 枚举定义

定义在 `app/models/enums.py`，不产生数据库表。

| 枚举类 | 值 | 使用表 |
|--------|----|--------|
| InstanceStatus | created, running, completed, terminated | flow_instances.status |
| Priority | urgent, high, normal, low | flow_instances.priority |
| Difficulty | "1", "2", "3", "4" | flow_instances.difficulty |
| InstanceNodeStatus | waiting, running, waiting_check, waiting_approval, waiting_endorsement, finished, rejected, terminated | instance_nodes.status |
| TaskStatus | pending, processing, waiting_check, waiting_approval, waiting_endorsement, completed, rejected, terminated | tasks.status |
| ApprovalStatus | pending, approved, rejected, terminated | approvals.status |
| CheckStatus | pending, passed, returned, terminated | check_records.status |
| EndorsementStatus | pending, approved, rejected, terminated | endorsements.status |
| OperatorType | user | operation_logs.operator_type |
| UploadType | normal, supplement | files.upload_type |

---

## 4. 关键设计决策

### 4.1 模板与实例分离

- `flow_instances.template_id` 无 FK（模板可被删除，实例独立存在）
- `flow_instances.template_name` + `template_type` 创建时快照存储
- 没有 `flow_versions` 表——用快照字段替代版本管理
- 发起时从 `template_nodes`/`template_edges` **全量复制**到 `instance_nodes`/`instance_edges`

### 4.2 统一节点模型

- `is_start=1` / `is_end=1` 标记开始/结束节点
- 节点不分类型，全存一张表
- 开始节点：系统默认，发起后自动 finished，不生成 Task
- 结束节点：发起人终审，不生成 Task，审批时 task_id=NULL

### 4.3 JSON 字段使用

| 表 | 字段 | 格式 | 理由 |
|----|------|------|------|
| template_nodes / instance_nodes | approvers | `[{"user_id": N}]` | 审批人列表，可增删，避免额外关联表 |
| template_nodes / instance_nodes | checkers | `[{"user_id": N}]` | 同上 |
| template_nodes / instance_nodes | file_folders | `[{name, required, file_count}]` | 文件夹配置，灵活 |
| flow_instances | doc_template_ids | `[1, 2, 3]` | 实例级文件模板 ID 列表 |
| node_presets | approvers / checkers | `[{"user_id": N}]` | 同上 |
| operation_logs | detail | `{...}` | 自由格式，不同操作类型不同结构 |

### 4.4 并行汇合控制

```
incoming_count  ← 实例创建时 GROUP BY 计算（不变）
arrived_count   ← 运行时上游完成时 +1
激活条件：arrived_count == incoming_count
```

### 4.5 无外键约束的例外

| 表 | 字段 | 原因 |
|----|------|------|
| user_roles | user_id, role_id | 应用层保证完整性 |
| flow_instances | template_id | 模板可被删除 |
| operation_logs | 全部关联字段 | 分区表限制 + 日志不删 |
| signatures | source_id | 多态关联（四张表） |

### 4.6 ON DELETE CASCADE 分布

**使用 CASCADE**：模板侧 + InstanceNode/InstanceEdge/File/Signature（附属数据）

**不使用 CASCADE**：Task/CheckRecord/Approval/Endorsement（运行时核心表）
→ 由 Service 层逻辑控制级联（终止、驳回、换人），确保状态一致性。

### 4.7 索引现状

- `UNIQUE(username)` — users 表已定义
- `UNIQUE(source_node_id, target_node_id)` — template_edges / instance_edges
- `UNIQUE(template_id, document_id)` — template_document_links
- 运行时热点索引（模型 `__table_args__` 声明，与 DB 手工对账）：
  - `INDEX(instance_id)` / `INDEX(node_id)` — tasks / check_records / approvals / endorsements / files
  - `INDEX(assignee_id, status)` on tasks
  - `INDEX(checker_id, status)` on check_records
  - `INDEX(approver_id, status)` on approvals
  - `INDEX(instance_id, created_at)` on operation_logs（按年分区表内二级索引）
  - `INDEX(status)` on tasks / check_records / approvals / endorsements / flow_instances —— 全局超期/统计查询（`Task.status NOT IN`）走索引，EXPLAIN 验证转索引 range scan
  - `INDEX(initiated_at)` / `INDEX(completed_at)` on flow_instances —— 首页发起/归档趋势图按时间范围聚合（月度近 12 个月 range 过滤走索引）
  - `INDEX(user_id, is_read)` on notifications
- 观察项（数据量极大时评估）：
  - `INDEX(user_id, created_at)` on notifications（列表按时间排序分页，单人通知量级大时再评估）
  - 列表页 keyword 模糊搜索 `LIKE '%关键词%'` 无索引可走（前导通配符），量级大时可评估 MySQL 8 ngram 全文索引

---

## 5. 操作日志分区

```sql
-- operation_logs 按年 RANGE 分区（由 python -m app.core.deploy_db 建库时创建，含 p_future=MAXVALUE 兜底）
ALTER TABLE operation_logs PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2026 VALUES LESS THAN (2027),
    PARTITION p2027 VALUES LESS THAN (2028),
    PARTITION p2028 VALUES LESS THAN (2029),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

**注意**：
- 复合主键 `(id, created_at)` 是 MySQL 分区的强制要求
- `id` 使用 AUTO_INCREMENT，在 InnoDB 中 (id, created_at) 复合键下仍自增唯一
- `p_future` 兜底保证忘加年份分区也不写入失败；建议每年初拆分 p_future（见 `04_Deployment.md` 8.6）

---

## 6. 迁移历史

| 迁移文件 | 说明 |
|----------|------|
| cdc82f5bf321 | 列注释规范修正（假设表已存在；**全新库建表用 `python -m app.core.deploy_db`**，见 04_Deployment.md） |
| 6247827b186e | flow_instances 新增 doc_template_ids 字段 |
| fix_charset_comments | 修复数据库注释乱码（201 列 + 22 表） |
| b1c2d3e4f5a6 | 性能：tasks / check_records / approvals / endorsements 各加 `idx_status` 单列索引（全局超期/统计查询走索引） |
| c2d3e4f5a6b7 | 性能：flow_instances 加 `idx_initiated_at` / `idx_completed_at` 单列索引（首页趋势图按时间范围聚合走索引） |

> 完整迁移见 `backend/alembic/versions/`（含 P1-20 索引对账 `a7b8c9d0e1f2`）。
