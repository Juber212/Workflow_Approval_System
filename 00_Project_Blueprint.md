# 企业流程审批系统 — 项目蓝图

> **版本**：3.0 | **状态**：与代码同步 | **更新**：2026-08-10
>
> 定义系统架构、状态机、业务规则执行细节。**写代码查不到的信息**——架构决策的原因、状态流转的副作用、业务规则的完整影响面。

---

## 1. 项目定位

企业级流程审批管理系统，以流程驱动项目的业务管理平台。

**核心概念**：每一个流程 = 一个业务项目（或方案），每一个节点 = 一个完整工作单元。

```
创建模板 → 发布 → 发起实例 → 节点执行 → 校验 → 审批 → [批准] → 下一节点 → ... → 终审 → 归档
```

---

## 2. 系统规模

| 维度 | 数量 | 说明 |
|------|:--:|------|
| 数据表 | 24 | 5 基础 + 7 定义 + 11 运行 + 1 辅助 |
| API 端点 | 92 HTTP + 1 WebSocket | 18 个路由模块 |
| 前端路由 | 23 | 含 5 个子页面（任务/校验/审批/批准/错误页） |
| 用户角色 | 3 | system_admin / manager / user |
| 流程类型 | 2 | project（项目）/ proposal（方案） |
| Service 文件 | 31 | 23 个顶层 + 8 个 instance 子模块 |
| 通知类型 | 9 | 覆盖分配/退回/驳回/终止全场景 |

---

## 3. 技术栈与选型理由

| 层 | 技术 | 选型理由 |
|----|------|----------|
| 前端框架 | Vue 3 + TypeScript | Composition API，类型安全 |
| 流程设计器 | LogicFlow | 滴滴开源，专为审批流设计，内置节点/连线/撤销重做 |
| UI 组件 | Element Plus | 企业级组件库，中文生态好 |
| 后端 | FastAPI (Python 3.10+) | 异步原生支持，自动生成 Swagger，Pydantic 校验 |
| ORM | SQLAlchemy 2.0 async | 异步 Session，声明式映射，支持 FOR UPDATE 行锁 |
| 数据库 | MySQL 8.0 InnoDB | 成熟稳定，支持分区表（operation_logs 按年分区） |
| 认证 | JWT (python-jose) | 无状态，适合 API 认证 |
| 文件存储 | 服务器本地目录 | 内网部署，NAS 挂载即可扩展 |
| PDF 转换 | LibreOffice headless | 开源免费，支持 Word/Excel→PDF |
| PDF 签名 | pypdf | 纯 Python，轻量，不需系统级依赖 |
| 实时推送 | FastAPI WebSocket | 内置支持，无需额外服务 |
| 任务队列 | Redis + arq | PDF 转换异步化，Redis Pub/Sub 桥接 WebSocket 跨进程推送 |
| 限流 | 自定义中间件 | 内存滑动窗口，三层分级，比 slowapi 更简单可控 |

### 为什么选 arq 而不是 Celery
arq 基于 Redis 实现轻量任务队列，与项目已有的 Redis 基础设施复用。PDF 转换通过 `pdf_queue.py` 入队，worker 进程异步处理，`ws_bridge.py` 通过 Redis Pub/Sub 实现多 Worker 进程间的 WebSocket 消息广播。相比 Celery 省去 RabbitMQ 依赖，运维更简单。

### 为什么自定义限流而不用 slowapi
slowapi 依赖 Redis/内存后端，API 不够简洁。自定义中间件 50 行代码实现三层限流 + 管理员白名单，直接集成到 FastAPI 中间件栈，无外部依赖。

---

## 4. 系统架构

### 4.1 分层架构

```
┌──────────────────────────────────────────────────┐
│  Browser (Vue 3 + LogicFlow + Element Plus)       │
├──────────────────────────────────────────────────┤
│  Nginx (:80)                                      │
│  ├── /          → dist/ (静态文件)                 │
│  └── /api/*     → Uvicorn (:8000)                 │
├──────────────────────────────────────────────────┤
│  FastAPI 应用层                                    │
│  ├── middleware/   (CORS → 限流 → 认证)             │
│  ├── api/          (18 个路由模块)                  │
│  ├── services/     (31 个业务服务)                  │
│  ├── engine/       (Flow Engine 状态推进)           │
│  └── models/       (24 个数据模型)                  │
├──────────────────────────────────────────────────┤
│  MySQL 8.0 (:3306)                                │
│  ├── 24 张业务表                                   │
│  └── operation_logs (按年 RANGE 分区)               │
├──────────────────────────────────────────────────┤
│  文件存储 (storage/)                               │
│  ├── 项目/{实例名称}/                               │
│  ├── 方案/{实例名称}/                               │
│  ├── signatures/                                   │
│  └── document_templates/                           │
└──────────────────────────────────────────────────┘
```

### 4.2 模块依赖图

```
api/          ← 薄层：参数校验、权限检查、调用 Service
  ↓
services/     ← 厚层：业务逻辑、事务管理、通知触发
  ↓
engine/       ← 流程引擎：节点激活、汇合控制、BFS 传播
  ↓
models/       ← 数据定义（SQLAlchemy DeclarativeBase）
```

### 4.3 后端目录结构

```
backend/
├── app/
│   ├── api/              # 路由层（18 个文件）
│   ├── services/         # 业务逻辑层（30 个文件）
│   │   └── instance/     # 实例服务子模块（8 个文件）
│   ├── engine/           # 流程引擎
│   │   └── flow_engine.py
│   ├── models/           # 数据模型（22 个文件）
│   ├── schemas/          # Pydantic 校验
│   ├── core/             # 配置/数据库/异常/错误码
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   ├── error_codes.py
│   │   └── rate_limit.py
│   └── utils/            # 工具（工作日计算等）
├── alembic/              # 数据库迁移
├── tests/                # 测试（326 条用例）
└── storage/              # 文件存储根目录
```

### 4.4 前端目录结构

```
frontend/src/
├── api/            # API 调用封装
├── components/     # 全局组件（NotificationBell, UserSelector, Breadcrumb 等）
├── composables/    # 组合函数
├── layouts/        # 布局组件
├── router/         # 路由配置（23 个路由）
├── stores/         # Pinia 状态
├── types/          # TypeScript 类型定义
├── utils/          # 工具函数
└── views/
    ├── admin/      # 系统管理（用户/组织/角色/配置/文件模板）
    ├── dashboard/  # 首页看板
    ├── error/      # 403/404
    ├── flows/      # 流程管理（设计器/模板详情/实例详情/组织主页）
    ├── login/      # 登录
    ├── profile/    # 个人中心（任务/校验/审批/批准处理页）
    └── proposals/  # 方案管理
```

---

### 4.5 Service 层架构

31 个 Service 文件（23 个顶层 + 8 个 instance 子模块），按职责分为 4 层：

| 层 | 文件 | 职责 |
|----|------|------|
| **流程操作** | `task_service`, `check_service`, `approval_service`, `endorsement_service` | 核心业务：提交/校验/审批/批准，含并发锁和通知触发 |
| **实例管理** | `instance/` (8 文件) | 实例 CRUD，拆分为 create/list/detail/terminate/delete/change/supplement |
| **模板管理** | `template_service`, `designer_service`, `document_service`, `preset_service` | 模板 CRUD、画布保存、文件模板关联、节点预设 |
| **基础支撑** | `user_service`, `organization_service`, `config_service`, `dashboard_service`, `notification_service`, `pdf_converter`, `pdf_signature`, `ws_manager`, `validation_service`, `proposal_service` | 用户/组织/配置管理、看板统计、实时推送、PDF 处理 |

**Service 间调用约定**：
- Service 间可以互相调用（如 `approval_service` → `notification_service`）
- Service 函数接收 `AsyncSession` 作为第一参数，由 API 层传入
- 通知触发统一用 `from app.services.notification_service import create_notification`（延迟导入避免循环依赖）
- 流程推进统一用 `from app.engine.flow_engine import propagate_from_node`

**instance/ 子模块拆分理由**：
实例服务原始为单文件 800+ 行，拆分为 8 个模块降低单文件复杂度。`__init__.py` 统一导出，API 层无感知。

### 4.6 前端架构概要

```
src/
├── api/            # 16 个 API 模块，按后端路由对应（auth/task/check/approval/endorsement/instance/template/...）
│   └── request.ts  # Axios 实例 + 拦截器（自动注入 Token、401 跳转登录、错误提示）
├── stores/         # Pinia 状态管理
│   ├── user.ts         # 用户登录态（token/userInfo/isLoggedIn/isManager/isAdmin）
│   └── notification.ts # 通知未读计数 + WebSocket 连接管理
├── composables/    # 组合函数
│   └── useBreadcrumb.ts  # 面包屑全局状态（模块级 ref 共享）
├── router/         # 23 个路由 + 全局守卫
│   ├── index.ts
│   └── guards.ts   # 登录校验 + 角色校验
├── layouts/        # AppLayout（侧边栏 + 顶栏 + 面包屑 + 内容区）
├── components/     # 全局可复用组件（NotificationBell, UserSelector, ProgressBar, ...）
├── types/          # TypeScript 类型定义
├── utils/          # 工具函数
└── views/          # 页面组件（6 个目录：admin/dashboard/error/flows/login/profile/proposals）
```

**关键设计模式**：

| 模式 | 说明 |
|------|------|
| Axios 拦截器 | 请求自动注入 Bearer Token；响应 401 自动清 Token 跳登录 |
| Pinia stores | `userStore` 管理登录态和角色判断；`notificationStore` 管理 WebSocket 和未读数 |
| Composable 共享状态 | `useBreadcrumb` 使用模块级 `ref` 实现跨组件面包屑同步 |
| API 模块化 | 每个后端路由模块对应一个前端 API 文件，返回类型用泛型约束 |
| 路由守卫 | `beforeEach` 校验登录态和角色权限，未登录跳 `/login?redirect=...`，无权限跳 `/403` |

### 4.7 安全设计

| 层面 | 机制 | 说明 |
|------|------|------|
| 认证 | JWT (python-jose) | Token 有效期 8 小时，存储在 localStorage |
| 密码 | bcrypt (passlib) | 不可逆哈希存储，修改密码需验证旧密码 |
| 权限 | 依赖注入链 | `get_current_active_user` → `require_admin` / `require_manager`，每个端点声明依赖 |
| 传输 | HTTPS（生产） | Nginx 层 SSL 终端，证书由运维管理 |
| 并发 | FOR UPDATE 行锁 | 所有状态变更操作先锁行再校验，消除 TOCTOU |
| 文件 | 权限校验下载 | `GET /files/{fid}/download` 校验用户是否属于该实例相关人员 |
| 限流 | 三层分级 | 登录 20/min/IP、写操作 30/min/用户、读操作 120/min/用户 |
| CORS | 白名单 | `CORS_ORIGINS` 环境变量控制允许的前端域名 |

**JWT 认证流程**：
```
1. POST /auth/login → 验证用户名密码 → 返回 JWT
2. 前端存入 localStorage → Axios 拦截器自动注入 Authorization header
3. 后端 deps.py get_current_active_user → 解码 JWT → 查用户 → 验证 is_active
4. Token 过期 / 无效 → 401 → 前端拦截器清除 Token 跳登录页
```

---

## 5. 角色体系（RBAC）

| 角色 | 标识 | 职责 | 可见菜单 |
|------|------|------|----------|
| 系统管理员 | system_admin | 用户/组织/角色/配置/文件模板维护。**不参与业务** | 首页、项目管理、方案管理、系统管理 |
| 所长 | manager | 设计模板、发起流程、终止流程、终审、参与执行/校验/审批 | 首页、项目管理、方案管理、个人中心 |
| 普通用户 | user | 执行节点、上传文件、校验、审批 | 首页、项目管理、方案管理、个人中心 |

角色存储在 `user_roles` 关联表，一个用户可以有多个角色。权限判断在后端 `deps.py` 完成：
- `get_current_active_user`：校验 JWT + 账号未禁用
- `require_admin`：检查是否包含 system_admin 角色
- `require_manager`：检查是否包含 manager 角色

---

## 6. 核心对象链

```
Organization（组织/所）
    ↓
User（用户，含签名图片路径）
    ↓
FlowTemplate（流程模板，type: project / proposal）
    ↓
FlowInstance（流程实例，快照 template_name + template_type，与模板解耦）
    ↓
InstanceNode（统一节点模型，不分类型，行为由 is_start / is_end 标记决定）
    ↓
Task（任务，仅中间节点生成）
    ↓
├── CheckRecord（校验记录，并行，全部通过后进审批）
├── Approval（审批记录，并行，全部通过后签名上PDF）
└── Endorsement（批准记录，difficulty=4 时，审批全部通过后触发）
    ↓
File（文件，属实例，按 round 区分轮次，upload_type: normal/supplement）
    ↓
Signature（签名记录，多态关联 assignee/checker/approver/endorser）
    ↓
OperationLog（操作日志，只写不删，按年分区）
Notification（通知，9 种类型，WebSocket 实时推送 + DB 持久化）
```

---

## 7. 统一节点模型

所有节点同一种类型（`TemplateNode` / `InstanceNode`），行为由 **位置标记** 决定。

| 属性 | 说明 |
|------|------|
| `is_start = True` | 开始节点——显示发起人姓名，发起后**自动标记 finished，不生成 Task** |
| `is_start = False, is_end = False` | 中间工作节点——负责人执行全流程 |
| `is_end = True` | 结束节点——发起人终审，**不生成 Task**，通过则归档/驳回则选目标节点回退 |

### 7.1 中间节点标准流程

```
Task 激活（pending → 打开详情自动 processing）
  → 负责人上传文件（Word/Excel/图片/PDF）
  → 提交时自动转 PDF（LibreOffice headless）
  → 校验人并行校验（CheckRecord 并行创建）
  → 全部校验通过 → 审批人并行审批（Approval 并行创建）
  → 全部审批通过 → 签名上 PDF → 下一节点
  → [difficulty=4 且有批准人] → 批准人批准 → 签名上 PDF → 下一节点
```

### 7.2 节点的角色配置

| 配置项 | 类型 | 说明 |
|--------|------|------|
| assignee_id | FK→users | 负责人，执行任务 |
| checkers | JSON | 校验人列表 `[{"user_id": N}]`，可多人并行 |
| approvers | JSON | 审批人列表 `[{"user_id": N}]`，可多人并行 |
| endorser_id | FK→users | 批准人，单人，仅 difficulty=4 时生效 |
| time_limit_days | int | 完成时限（工作日） |
| require_file | bool | 是否必须上传文件 |
| file_folders | JSON | 文件夹配置 `[{name, required, file_count}]` |
| approval_strategy | str | V1 固定 "all_approve"（全部通过） |

---

## 8. 完整状态机

### 8.1 FlowInstance（流程实例）状态

```
                    ┌──→ Terminated（发起人终止，文件物理删除）
                    │
Created ──→ Running ──→ Completed
                ↑         ↑
                │         │
                └──── 终审驳回（回到中间节点 running）
```

| 状态 | 进入条件 | 可操作 |
|------|----------|--------|
| created | 发起实例，尚未激活节点 | — |
| running | 开始节点自动完成，首个工作节点激活 | 终止、换人、改优先级 |
| completed | 结束节点全部审批通过 or 方案工作节点全部审批通过 | 终止 |
| terminated | 发起人主动终止 | 管理员永久删除 |

### 8.2 InstanceNode（实例节点）状态

```
waiting ──→ running ──→ waiting_check ──→ waiting_approval ──→ waiting_endorsement ──→ finished
               ↑              ↑  ↓                ↑  ↓                    ↑  ↓
               │              │  returned          │  rejected             │  rejected
               │              └────────────────────┴──────────────────────┘
               │                        校验/审批/批准退回 → running (round+1)
               │
               └── 终审驳回目标节点重新激活 (round+1)
```

| 状态 | 进入条件 | 触发动作 |
|------|----------|----------|
| waiting | 实例创建时的初始状态 | 等待上游节点完成 |
| running | 所有上游 arrived，incoming_count 达标 | 生成 Task（pending），通知负责人 |
| waiting_check | 负责人提交 | 生成 CheckRecord × N，通知校验人 |
| waiting_approval | 全部校验 passed | 生成 Approval × N，通知审批人 |
| waiting_endorsement | 全部审批 approved + difficulty=4 + 有批准人 | 生成 Endorsement，通知批准人 |
| finished | 批准通过 / 全部审批通过（难度<4）/ 结束节点完成 | 传播到下游节点 |
| rejected | 校验退回 / 审批驳回 / 批准驳回 | running (round+1)，旧文件删除，Task→processing |

### 8.3 Task（任务）状态

```
pending ──→ processing ──→ waiting_check ──→ waiting_approval ──→ waiting_endorsement ──→ completed
                ↑                    ↑                ↑                    ↑
                │                    │                │                    │
                └── 校验退回 ─────────┘────────────────┴────────────────────┘
                └── 审批驳回 ──────────────────────────┘
                └── 批准驳回 ───────────────────────────────────────────────┘
```

**特别注意**：
- pending → processing 的转换发生在**负责人打开任务详情时**（无需单独的"开始"按钮）
- submitted_at 在提交时设置，驳回时清除（用于区分首次提交和退回重做）
- 驳回不创建新 Task，而是重用原 Task，状态回到 processing，轮次+1。保留历史 round 的 CheckRecord/Approval 用于追溯。

### 8.4 CheckRecord / Approval / Endorsement 状态

三者状态结构一致：

```
pending ──→ passed/approved ──→ 触发下一阶段
     ↓
  returned/rejected ──→ 节点回到 running
     ↓
  terminated ──→ 实例终止 / 换人被移除 / 驳回时被终止
```

| 状态 | CheckRecord | Approval | Endorsement |
|------|-------------|----------|-------------|
| pending | 等待校验 | 等待审批 | 等待批准 |
| passed/approved | 通过 | 通过（签名上PDF） | 通过（签名上PDF） |
| returned/rejected | 退回负责人 | 驳回（中间→负责人，结束→目标节点） | 驳回负责人 |
| terminated | 系统关闭 | 系统关闭 | 系统关闭 |

---

## 9. Flow Engine（流程引擎）

### 9.1 引擎职责

`app/engine/flow_engine.py` 负责节点间的流转逻辑，是系统的核心调度器。

三个核心函数：

| 函数 | 触发时机 | 做什么 |
|------|----------|--------|
| `activate_start_node()` | 发起实例后 | 开始节点 → finished |
| `propagate_from_node()` | 节点完成后 | BFS 传播到达信号到下游，激活满足条件的节点 |
| `calculate_incoming_counts()` | 发起实例时 | GROUP BY 批量计算每个节点的上游连线数 |

### 9.2 propagate_from_node 详细流程

```
输入：instance_id, finished_node_id

1. 查询所有以 finished_node_id 为源的 InstanceEdge
2. 对每个目标节点: arrived_count += 1
3. 如果 arrived_count == incoming_count（所有上游已到达）:
   → 结束节点: 状态→waiting_approval, 创建 Approval（发起人终审）
   → 中间节点: 状态→running, 生成 Task, 通知负责人
4. 返回新激活的节点 ID 列表
```

### 9.3 并行汇合控制（fork/join）

```
         ┌→ Node B ─┐
Node A ──┤           ├─→ Node D (incoming_count=2, arrived_count=0)
         └→ Node C ─┘
```

- `incoming_count`：预先计算，上游连线数（串联=1，汇合节点≥2）
- `arrived_count`：运行时累加，每次上游完成 +1
- `arrived_count == incoming_count` 时，汇合节点激活
- 支持任意深度的 fork/join 嵌套

### 9.4 工作日截止日期计算

发起实例时，系统按节点 sort_order 顺序累加各节点的 `time_limit_days`：
- 使用 `add_workdays(initiation_date, cumulative_workdays)` 跳过周末和节假日
- 如果节点在 `node_overrides` 中被手动指定了 deadline，则跳过计算
- 节假日列表通过系统配置维护

---

## 10. 业务规则执行细节

### 规则 1：模板与实例分离

- 发起时从 `template_nodes`/`template_edges` **复制**到 `instance_nodes`/`instance_edges`
- `flow_instances.template_name` + `template_type` 快照存储
- `flow_instances.template_id` 无 FK 约束（模板可被删除）
- 模板修改**不影响**已运行实例

### 规则 2：软修改与硬修改

- **软修改**：修改审批人/时限/描述 → 即时生效，不产生新版本
- **硬修改**：修改节点/连线 → 由所长重新发布
- V1 没有 `flow_versions` 表，版本管理由人工控制

### 规则 3：配置快照解耦

发起实例时可逐节点覆盖：
- `node_overrides`：`[{node_id, assignee_id, time_limit_days, approvers, checkers, endorser_id, deadline, ...}]`
- 覆盖优先级：发起覆盖 > 模板默认值
- 签批字段（require_*_signature, signature_x/y/page）也支持覆盖

### 规则 4：开始/结束节点不可删除

- 设计器画布中 `is_start` 和 `is_end` 节点禁止删除
- 发布校验：至少 3 节点（开始 + ≥1 工作 + 结束）

### 规则 5：发布校验

```
1. 节点数量 ≥ 3
2. 中间节点：name、assignee_id、checkers、approvers 全部必填
3. 所有节点 BFS 连通（从开始节点出发可达所有节点）
```

### 规则 6：跨所协作

- 负责人/校验人/审批人/批准人可跨组织选择（UserSelector 不做组织限制）
- 模板的 `organization_id` 决定模板编辑权限（只有所属所的所长可编辑）

### 规则 7：操作日志不可删除

- `operation_logs` 表只执行 INSERT 和 SELECT，无 UPDATE/DELETE
- 复合主键 `(id, created_at)`，按年 RANGE 分区（MySQL 分区要求分区键属于所有唯一键）
- 无任何 FK 约束（分区表限制 + 日志不应因关联记录删除而丢失）
- 操作类型包括：initiate, task_submit, check_pass, check_return, approve, reject, final_reject, endorse, endorse_reject, instance_terminated, personnel_changed, priority_changed, instance_deleted, supplement_file

### 规则 8：V1 不做条件分支

- 支持 fork/join 并行分叉汇合（节点可有多条出边/入边）
- 不做 if/else 条件路由（所有出边同时激活，目标节点并行执行）
- V2 考虑条件表达式 + 动态分支

### 规则 9：发起人终止权

触发：发起人 POST `/instances/{id}/terminate`

完整影响链：
1. 物理删除所有文件（先删 DB 记录，再删磁盘文件）
2. 关闭所有非 finished/terminated 的 InstanceNode → terminated
3. 关闭所有非 completed/terminated 的 Task → terminated
4. 关闭所有 pending 的 CheckRecord → terminated
5. 关闭所有 pending 的 Approval → terminated
6. 关闭所有 pending 的 Endorsement → terminated
7. 实例状态 → terminated，记录终止原因
8. 通知所有待处理人员（负责人/校验人/审批人/批准人）+ 清除待办通知
9. 归档文件物理删除，不可恢复

### 规则 10：审批自动签名

签名时机：
- **负责人签名**：提交时立刻写入 PDF（不等其他人）
- **校验人签名**：全部校验通过后，批量写入 PDF
- **审批人签名**：全部审批通过后，批量写入 PDF
- **批准人签名**：批准通过后立刻写入 PDF

签名存储：
- 用户上传 PNG 签名图片（透明底，≤500KB）存储在 `signatures/`
- 签名元数据存入 `signatures` 表（位置、页码、角色类型、是否已写入）
- `pypdf` 将签名图片插入 PDF 指定坐标和页码

签名配置来源链：
```
系统全局配置 → 节点级配置 → 个人调整
```
最终位置：用户审批时可覆盖默认位置（signature_x, signature_y, signature_page）

### 规则 11：紧急换人

触发：发起人 PUT `/instances/{id}/nodes/{nid}/personnel`

完整影响链：
1. 校验实例存在 + 发起人权限 + 节点非 finished/terminated
2. 对比新旧人员列表：
   - 被移除的 pending CheckRecord → terminated + 清除通知
   - 被移除的 pending Approval → terminated + 清除通知
   - 被移除的 pending Endorsement → terminated + 清除通知
3. 新增人员生成对应的 pending 记录 + 发送通知
4. 负责人变更：更新 Task.assignee_id
5. 批准人变更：更新 node.endorser_id
6. 记录操作日志（含变更描述）

**已完成记录不受影响**——只操作 pending 状态的记录。

### 规则 12：优先级可选/可改

- 发起时选择：urgent / high / normal（默认）/ low
- 发起人可随时修改（仅 running 状态）
- table 列表按优先级排序（urgent 最前）
- dashboard 卡点追踪按优先级排序

---

## 11. 难度等级与批准人机制

### 11.1 难度等级

| 难度 | 值 | 说明 |
|------|-----|------|
| 1 | "1" | 标准流程 |
| 2 | "2" | 标准流程 |
| 3 | "3" | 标准流程 |
| 4 | "4" | 标准流程 + **批准人环节** |

存储在 `flow_instances.difficulty`，发起时设置，发起后不可修改。

### 11.2 批准人流转

```
难度 1-3:  waiting_approval → 全部审批通过 → finished → 下一节点

难度 4:   waiting_approval → 全部审批通过 → waiting_endorsement → 批准通过 → finished → 下一节点
                                                          ↓
                                                  批准驳回 → running (round+1, 负责人重做)
```

### 11.3 批准人触发条件

在 `approval_service.approve()` 中：
```python
if inst.difficulty == "4" and node.endorser_id:
    # 创建 Endorsement，状态 → waiting_endorsement
```

三个条件缺一不可：
1. 实例 difficulty == "4"
2. 节点配置了 endorser_id
3. 非结束节点（结束节点是发起人终审，不触发批准）

---

## 12. 驳回逻辑对比

| 维度 | 校验退回 | 中间节点审批驳回 | 终审总驳回 | 批准驳回 |
|------|----------|-----------------|-----------|---------|
| 触发人 | 任意校验人 | 任意审批人 | 任意终审人 | 任意批准人 |
| 目标 | 当前节点负责人 | 当前节点负责人 | 指定历史中间节点 | 当前节点负责人 |
| 文件处理 | 删除当前轮文件 | 删除当前轮文件 | 删除目标节点及下游文件 | 删除当前轮文件 |
| Task 状态 | processing | processing | processing（目标节点） | processing |
| 轮次变化 | round+1 | round+1 | 目标节点 round+1 | round+1 |
| 其他 pending | CheckRecord→terminated | Approval/CheckRecord→terminated | 终审 Approval→terminated | Approval/CheckRecord→terminated |
| 下游节点 | 不变 | 不变 | 重置为 waiting，round+1 | 不变 |
| 操作日志 | check_return | reject | final_reject | endorse_reject |
| 通知接收人 | 负责人 | 负责人 | 目标节点负责人 | 负责人 |

### 终审总驳回详细流程

结束节点审批人驳回时，必须指定 `target_node_id`（驳回目标）：

1. 结束节点 Approval → rejected
2. 目标节点 round+1，status→running，清除 arrived_count
3. 删除目标节点文件
4. 生成新 Task（指定目标节点负责人）
5. 重置目标节点到结束节点之间的所有下游节点 → waiting
6. 删除下游节点文件，终止下游 Task
7. 终止结束节点其余 pending Approval
8. 通知目标节点负责人

---

## 13. 通知系统

### 13.1 9 种通知类型

| 类型 | 触发时机 | 接收人 | 触发位置 |
|------|----------|--------|----------|
| task_assigned | 节点激活 / 换人 | 负责人 | flow_engine.propagate_from_node / change_personnel |
| check_assigned | 提交后生成校验 | 校验人 | task_service.submit_task / change_personnel |
| approval_assigned | 校验全部通过 / 无校验人直通 / 终审 | 审批人 | check_service.pass_check / task_service.submit_task / flow_engine |
| endorsement_assigned | 审批全部通过（难度4） | 批准人 | approval_service.approve / change_personnel |
| check_returned | 校验退回 | 负责人 | check_service.return_check |
| approval_rejected | 审批驳回（中间节点） | 负责人 | approval_service.reject |
| final_rejected | 终审总驳回 | 目标节点负责人 | approval_service.reject |
| endorsement_rejected | 批准驳回 | 负责人 | endorsement_service.endorse_reject |
| instance_terminated | 实例终止 | 所有待处理人 | instance_service.terminate |

### 13.2 通知生命周期

1. **创建**：业务操作触发 `create_notification()` → 写入 DB + WebSocket 实时推送
2. **清除**：操作完成时 `clear_related()` 物理删除相关通知（如提交后删除 task_assigned 通知）
3. **标记已读**：用户点击或一键已读 → `is_read = True`（不删除）
4. **拉取历史**：分页查询，最新优先

### 13.3 WebSocket 连接管理

- 端点：`/api/v1/ws?token=JWT_TOKEN`
- 连接时验证 JWT，无效 token 返回 4001 关闭
- 使用 `ConnectionManager` 管理用户→连接映射，支持多设备

---

## 14. 并发安全策略

### 14.1 行级锁（FOR UPDATE）

所有可能并发的审批/校验/批准操作均使用 `SELECT ... FOR UPDATE`：

```python
# 先锁行，再校验状态
a = await db.execute(
    select(Approval).where(Approval.id == approval_id).with_for_update()
)
# 锁定同节点其他 pending 行，防止并发操作
await db.execute(
    select(Approval).where(
        Approval.node_id == a.node_id,
        Approval.status == ApprovalStatus.PENDING,
        Approval.id != approval_id,
    ).with_for_update()
)
```

### 14.2 文件删除顺序

先删 DB 记录，再删物理文件。避免事务回滚后物理文件已丢失而 DB 记录还在。

### 14.3 通知失败隔离

所有通知创建和 WebSocket 推送都用 try/except 包裹，失败不影响主流程。

---

## 15. 文件存储与 PDF 转换

### 15.1 存储结构

```
storage/
├── 项目/{实例名称}/           ← 项目文件归档（按 template_type 分目录）
│   ├── {uuid}.pdf
│   └── 文件夹A/               ← 按 file_folders 配置预创建
├── 方案/{实例名称}/           ← 方案文件归档
├── signatures/                ← 用户签名图片
└── document_templates/        ← 文件模板（.docx/.xlsx）
```

### 15.2 文件生命周期

1. 负责人上传（upload_type=normal）
2. 提交时 LibreOffice 自动将非 PDF 转为 PDF
3. 校验/审批/批准过程中可预览
4. 驳回时文件物理删除（DB 记录 + 磁盘）
5. 补交文件（upload_type=supplement）不影响流程状态
6. 已提交文件不可删除

### 15.3 PDF 转换限流

`asyncio.Semaphore(4)` 限制同时最多 4 个 LibreOffice 进程（worker 端 `max_jobs=4`），防止 CPU 打满。

---

## 16. 限流策略

| 档位 | 阈值 | 作用域 | 适用端点 |
|------|------|--------|----------|
| 严格 | 20次/分钟/IP | IP 地址 | POST /auth/login |
| 中等 | 30次/分钟/用户 | JWT user_id | 文件上传、发起、终止、提交 |
| 宽松 | 120次/分钟/用户 | JWT user_id | 其余所有 API（默认） |
| 跳过 | 无限 | — | 系统管理员（uuid 标记）+ /health |

实现：自定义 `RateLimitMiddleware`（BaseHTTPMiddleware），内存滑动窗口，线程安全。

---

## 17. 测试策略

### 17.1 测试分层

| 层 | 位置 | 数量 | 覆盖内容 |
|----|------|:--:|------|
| 单元测试 | `tests/unit/` | 225 | Service 层核心逻辑（校验/审批/任务/实例/限流） |
| 集成测试 | `tests/integration/` | 66 | 全链路流程（发起→提交→校验→审批→完成） |
| MySQL 真实 | `tests/mysql/` | 29 | 真实 MySQL 库，独立建表删表，SAVEPOINT 隔离 |

### 17.2 测试工具

| 工具 | 用途 |
|------|------|
| pytest + pytest-asyncio | 异步测试框架 |
| httpx.AsyncClient | FastAPI TestClient 异步替代 |
| Factory fixtures | `conftest.py` 中定义，提供测试用 DB session、用户、模板、实例 |

### 17.3 测试覆盖重点

1. **状态机正确性**：各状态流转是否符合业务规则（如 pending 才能 approve）
2. **并发安全**：FOR UPDATE 锁是否阻止并发修改
3. **级联完整性**：终止/驳回时是否正确级联关闭所有关联记录
4. **权限边界**：非负责人/非审批人是否被正确拒绝
5. **通知触发**：关键操作是否正确触发通知（含清除逻辑）
6. **限流行为**：超阈值是否返回 429，管理员是否跳过

### 17.4 运行测试

```bash
cd backend
pytest tests/ -v                    # 全部测试
pytest tests/unit/test_rate_limit.py -v  # 限流专项
pytest tests/ -v --tb=short         # 简洁输出
```

---

## 18. 设计原则

1. **Flow First**：所有业务必须依附流程实例
2. **状态驱动**：页面根据状态展示 UI，后端根据状态执行逻辑
3. **SSOT（单一数据源）**：流程状态来自 Instance，任务状态来自 Task，审批状态来自 Approval
4. **日志不可删**：operation_logs 只写不删
5. **权限后端控**：前端仅隐藏按钮，真正权限校验在 API 层
6. **模板实例解耦**：快照机制保证实例独立性
7. **先锁后判**：所有并发操作先 FOR UPDATE 锁行再校验状态
8. **通知不阻塞**：通知失败不影响业务主流程

---

## 19. 错误码体系

所有错误码定义在 `app/core/error_codes.py`：

| 类别 | code 范围 | HTTP 状态码 | 示例 |
|------|-----------|:--:|------|
| 成功 | 20000 | 200 | 操作成功 |
| 参数/校验 | 40000-40908 | 400/409/415/422 | 参数缺失、名称已存在、实例不可终止 |
| 未认证 | 40100-40103 | 401 | Token 过期、无效、无用户 |
| 无权限 | 40300-40304 | 403 | 非管理员、非所长、非发起人 |
| 未找到 | 40400 | 404 | 用户/模板/实例/节点不存在 |
| 限流 | 42900 | 429 | 请求过于频繁 |
| 服务器错误 | 50000-50001 | 500 | 文件转换失败 |

---

## 20. 方案（Proposal）与项目的区别

方案作为第二模板类型（type=proposal），共享全部节点/实例基础设施：

| 维度 | 项目（project） | 方案（proposal） |
|------|----------------|-----------------|
| 存储目录 | 项目/{实例名称}/ | 方案/{实例名称}/ |
| Dashboard | 项目 Tab 统计 | 方案 Tab 统计 |
| 组织卡片 | 项目组织卡片 | 方案组织卡片 |
| 完成逻辑 | 结束节点终审后完成 | 工作节点审批通过后**直接完成**（跳过结束节点） |
| 关联 | 可关联一个已完成方案（proposal_id） | — |
| 前端实例详情 | 复用 InstanceDetail | 复用 InstanceDetail |
| 设计器 | 同 FlowDesigner | 同 FlowDesigner |

---

## 21. MVP 验收清单

- ✅ 登录 + JWT + RBAC 三角色
- ✅ Dashboard（四卡片 + 饼图 + 卡点追踪 + 各所柱状图 + 通知铃铛）
- ✅ 流程设计器（LogicFlow 统一节点 + fork/join + 画布操作 + 节点预设）
- ✅ 流程发布 + 发起（逐节点配置 + 优先级 + 难度等级 + 文件模板）
- ✅ 个人中心（9 Tab 分页搜索：待办/校验/审批/批准/发起 × 项目+方案）
- ✅ 节点执行（上传 → 转 PDF → 负责人签名 → 提交）
- ✅ 校验（并行 + 全部通过后签名上 PDF）
- ✅ 审批（并行 + 全部通过后签名上 PDF + 终审总驳回）
- ✅ 批准（难度4 + 签名上 PDF + 驳回）
- ✅ 终止流程 + 紧急换人 + 优先级修改 + 补交文件
- ✅ 操作日志（按年分区，只写不删）
- ✅ 方案管理（第二模板类型，工作节点审批后直接完成）
- ✅ 通知系统（WebSocket 实时推送 + DB 持久化 + 下拉面板）
- ✅ 文件模板（Word/Excel + 变量替换 + 多对多关联）
- ✅ API 限流（三层分级 + 管理员白名单）
