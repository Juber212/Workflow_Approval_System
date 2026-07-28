# 开发者文档

> 每次 Task 完成后更新，记录技术决策、架构说明和开发指引。

---

## Task001: 前端脚手架创建

- **技术栈**：Vue 3.5 + TypeScript + Vite 8.1
- **包管理**：npm（48 个依赖）
- **类型检查**：vue-tsc 6.0.3
- **构建**：vite build，18 模块，196ms
- **项目路径**：`frontend/`
- **目录结构**：Vite 默认模板（src/assets/、src/components/、src/）
- **备注**：后续 Task 将替换默认模板文件为项目实际结构

---

## Task002: Element Plus 安装与主题配置

- **组件库**：element-plus 2.11 + @element-plus/icons-vue 2.3
- **SCSS**：sass-embedded（Vite 8 内置 rolldown 的 SCSS 预处理器）
- **主题色**：#1a6fb5（主色）、#3da36a（成功）、#e6a23c（警告）、#e65d5d（危险）
- **圆角**：6px
- **全局样式入口**：`src/styles/index.scss`
- **主题变量**：`src/styles/element-variables.scss`（通过 vite.config.ts additionalData 全局注入）
- **中文语言包**：`element-plus/dist/locale/zh-cn.mjs`
- **Vite 别名**：`@` → `/src`
- **注意**：如果构建报 "Preprocessor dependency sass-embedded not found"，需 `npm install -D sass-embedded`

---

## Task003: 前端公共模块

- **路由**：Vue Router 4，7 条路由（/ → AppLayout children：dashboard/flows/profile/admin/*、/login、404），全部懒加载
- **状态管理**：Pinia，user store（token + userInfo + isLoggedIn + setLogin + logout）
- **HTTP 客户端**：Axios，baseURL 默认 /api/v1（可通过 VITE_API_BASE_URL 覆盖），请求拦截器自动注入 Bearer Token，响应拦截器统一错误提示 + 401 跳转登录
- **布局**：AppLayout（el-header 顶部导航 + el-menu 水平菜单 + el-dropdown 用户下拉 + el-main router-view）
- **类型**：src/types/user.ts（UserInfo 接口）
- **路径别名**：`@` → `src/`（vite.config.ts resolve.alias + tsconfig.app.json paths）
- **env 声明**：src/env.d.ts（VITE_API_BASE_URL + Vue SFC 类型声明）
- **目录结构**：src/router/ src/stores/ src/api/ src/layouts/ src/views/（dashboard/flows/profile/admin/login/error） src/types/

---

## Task004: FastAPI 后端脚手架

- **框架**：FastAPI 0.115+、Uvicorn 0.34+
- **配置**：Pydantic Settings（自动读取 .env）
- **日志**：控制台（DEBUG 级别彩色输出）+ 按日滚动文件（logs/app.log，保留 30 天）
- **数据库预留**：SQLAlchemy 2.0 异步引擎 + sessionmaker + Base 基类 + get_db FastAPI 依赖注入
- **CORS**：通过环境变量 CORS_ORIGINS 配置，默认 localhost:5173
- **健康检查**：GET /api/v1/health
- **Swagger**：/docs + /redoc
- **启动命令**：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

---

## Task005: 数据库连接配置

- **MySQL**：8.0 Community Server、InnoDB、utf8mb4
- **数据库名**：workflow_approval
- **驱动**：aiomysql（SQLAlchemy 2.0 异步）
- **连接池**：pool_size=10、max_overflow=20、pool_pre_ping=True
- **依赖注入**：`get_db()` → FastAPI Depends，自动 commit/rollback
- **环境变量**：DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME → database_url
- **.env 位置**：backend/.env（开发环境已配置，生产用 .env.example 模板）

---

## Task006: 统一响应与异常处理

- **响应格式**：`{code: int, message: str, data: T | null}`
- **分页**：`{items, total, page, page_size}`
- **异常类型**：`AppException(code, message)` / `RequestValidationError` / `Exception`
- **错误码**：IntEnum，40xxx 客户端错误、50xxx 服务端错误，含默认中文提示
- **关键设计**：所有异常返回 HTTP 200，通过 `code` 字段区分业务结果；未知异常打印日志不泄露堆栈
- **目录**：backend/app/{api,models,schemas,services,core,engine,utils}/

---

## Task007+Task008: 代码规范工具

- **前端**：ESLint 9 flat config + Prettier 3
- **后端**：Black (line-length=100) + isort (profile=black) + mypy
- **ESLint 规则**：js recommended + typescript-eslint recommended + vue3 recommended
- **Husky**：跳过（项目尚未 git init，待后续配置）

---

## Task009: 数据库建表

- **17 张表**：organizations/users/roles/user_roles/system_configs/flow_templates/template_nodes/template_edges/flow_versions/flow_instances/instance_nodes/instance_edges/tasks/approvals/check_records/files/operation_logs
- **分区**：operation_logs 按年 RANGE 分区（p2026–p2035 + p_future）
- **字符集**：utf8mb4 + utf8mb4_unicode_ci
- **引擎**：InnoDB
- **执行方式**：mysql CLI 直接导入 DDL SQL

---

## Task010: ORM 模型定义

- **17 个 Model**：每个表一个独立 .py 文件，含中文注释和类型注解
- **11 个 Enum**：TemplateStatus/VersionStatus/InstanceStatus/ArchiveStatus/Priority/InstanceNodeStatus/TaskStatus/ApprovalStatus/CheckStatus/OperatorType/UploadType
- **字段**：Mapped + mapped_column 声明式风格
- **关系**：ForeignKey 外键全部定义，Organization↔User 双向 relationship
- **JSON**：approvers/checkers/nodes_snapshot/edges_snapshot/soft_config_overrides 使用 JSON 类型

---

## Task011: 种子数据

- **脚本位置**：app/core/seed.py
- **运行命令**：python -m app.core.seed
- **角色**：system_admin/manager/user
- **组织**：通用所/结构所/电气所/暖通所
- **配置**：文件扩展名/大小限制/PDF签名坐标/默认时限
- **管理员**：admin / admin123
- **密码哈希**：bcrypt（直接调用，不用 passlib 封装）

---

## Task012: Alembic 迁移

- **迁移工具**：Alembic 1.14+
- **配置**：alembic.ini + env.py（异步引擎 + Base.metadata）
- **初始迁移**：alembic/versions/cdc82f5bf321_initial_schema.py
- **命令**：python -m alembic revision --autogenerate -m "desc"
- **注意**：alembic.ini 不要含中文字符（Windows GBK 编码）

---

## Task013: 登录 API

- **端点**：POST /api/v1/auth/login
- **JWT**：HS256、payload={sub,username,roles,org_id}、过期 8h
- **密码哈希**：bcrypt
- **安全模块**：app/core/security.py（hash_password/verify_password/create_access_token/decode_access_token）
- **aiomysql**：pool_pre_ping=False（新版 ping() 签名不兼容）

## Task015: GET /auth/me 与 POST /auth/logout

### UserInfoResponse Schema
```python
class UserInfoResponse(BaseModel):
    user_id: int
    username: str
    real_name: str
    email: str | None = None
    phone: str | None = None
    roles: list[str]
    organization_id: int | None = None
    organization_name: str | None = None
    has_signature: bool = False  # 是否已上传签名图片
```

### GET /auth/me
- 依赖 `get_current_active_user`，自动校验 JWT 和账号启用状态
- 查库获取完整信息（joinedload organization）
- `has_signature` 由 `signature_image IS NOT NULL` 判断

### POST /auth/logout
- V1 无 Token 黑名单，直接返回成功
- 客户端自行删除 localStorage 中的 Token

## Task016: 登录页面

### API 层 (src/api/auth.ts)
- `loginApi(params)` — POST /auth/login，返回 LoginData
- `getMeApi()` — GET /auth/me，返回完整用户信息
- `logoutApi()` — POST /auth/logout
- `toUserInfo(data)` — 将后端 user_id 映射为前端 id

### Store 重构 (src/stores/user.ts)
- `login(username, password)` — 异步调用 API → 存 token → 解析 userInfo
- `fetchUserInfo()` — 从 /auth/me 刷新用户信息（页面刷新恢复用）
- `logout()` — 异步调用 logout API → 清除本地状态
- `restoreToken(token)` — 仅恢复 token，不调 API

### 登录页面 (src/views/login/index.vue)
- el-form + el-input 带前缀图标（User/Lock）
- 表单校验：用户名必填、密码必填
- 登录按钮 loading 态 + 禁用重复提交
- 错误信息双反馈：ElMessage toast + 卡片内 el-alert
- 记住用户名：存 localStorage，下次自动填充
- 登录成功跳转支持 redirect 查询参数

## Task017: 路由守卫与角色权限

### 全局守卫流程 (src/router/guards.ts)
1. **Token 过期检测** — 解析 JWT payload exp，提前 60s 判定，过期则 clearToken()
2. **公开页面放行** — /login、/404、/403 免鉴权
3. **已登录访问 /login** — 重定向 /dashboard
4. **未登录拦截** — 跳转 /login?redirect=原路径
5. **用户信息恢复** — token 有效但刷新丢了 userInfo → fetchUserInfo()
6. **角色校验** — route.meta.roles 与 userInfo.roles 求交集

### 路由 meta 扩展
```typescript
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    roles?: string[]  // 允许访问的角色
  }
}
```

### 菜单角色控制
- `isAdmin` computed: userInfo?.roles.includes('system_admin')
- 个人中心: `v-if="!isAdmin"`
- 系统管理: `v-if="isAdmin"`

## Task018: 用户管理后端

### 三层架构
```
api/users.py       → 端点定义 + 权限守卫 + 参数校验
services/user_service.py → 业务逻辑（校验/查询/写入）
schemas/user.py    → DTO（请求/响应模型）
```

### 端点一览
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /users | 分页列表（keyword/org_id/is_active 筛选） |
| POST | /users | 新增用户（含角色分配） |
| PUT | /users/{id} | 编辑用户（不改 username，替换角色） |
| PUT | /users/{id}/status | 启禁用 |
| PUT | /users/{id}/reset-password | 管理员重置密码 |

### 权限守卫
```python
def _require_admin(current_user: CurrentUser):
    if not current_user.is_admin():
        raise AppException(ErrorCode.FORBIDDEN, "仅系统管理员可执行此操作")
```

### 批量角色查询
用 JOIN 查询一次查出所有用户的角色，避免 N+1 问题：
```sql
SELECT user_roles.user_id, roles.code
FROM user_roles JOIN roles ON roles.id = user_roles.role_id
WHERE user_roles.user_id IN (...)
```

## Task019: 用户管理前端

### 组件架构
```
admin/index.vue              ← Tab 容器（用户管理/组织管理/角色管理/系统配置）
  └── UserManagement.vue     ← 用户管理主页面（搜索+表格+分页）
        ├── UserFormDialog   ← 新增/编辑弹窗（表单校验+角色反向映射）
        └── ResetPasswordDialog ← 重置密码弹窗
```

### 角色标签映射
```typescript
const roleNameMap = {
  system_admin: '系统管理员',  // danger (红色)
  manager: '所长',            // warning (橙色)
  user: '普通用户',            // info (灰色)
}
```

### 编辑时角色反向映射
用户列表返回 roles: ["user", "manager"]（code 列表），表单需要 role_ids: [6, 5]（ID 列表）。
通过 `roleOptions` 构建 code→id Map 进行转换。

### 后端补充接口
- `GET /api/v1/organizations/options` — 返回启用组织的 id/name/is_active
- `GET /api/v1/roles/options` — 返回所有角色的 id/code/name

## Task020: 用户搜索组件

### UserSelector 组件 API
| Prop | 类型 | 默认 | 说明 |
|------|------|------|------|
| modelValue | number \| number[] | - | v-model 绑定 |
| multiple | boolean | false | 是否多选 |
| placeholder | string | "请搜索并选择用户" | 占位文本 |
| disabled | boolean | false | 禁用 |
| clearable | boolean | true | 可清除 |

### 后端搜索接口
`GET /api/v1/users/search?keyword=xxx&limit=20`
- 按 real_name / username LIKE 搜索
- 仅返回启用状态的用户
- 返回 id/username/real_name/organization_name
- limit 上限 100

### 使用示例
```vue
<UserSelector v-model="assigneeId" />
<UserSelector v-model="checkerIds" :multiple="true" placeholder="选择校验人" />
```

## Task021: 组织管理后端

### 端点
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /organizations | 列表（user_count + manager_name 计算字段） |
| POST | /organizations | 新增（名称唯一性校验） |
| PUT | /organizations/{id} | 编辑（名称唯一性排除自身） |
| PUT | /organizations/{id}/status | 启停（V1 不删除） |
| GET | /organizations/options | 轻量选项（仅启用状态） |

### 计算字段实现
- **user_count**: `SELECT organization_id, COUNT(*) FROM users WHERE org_id IN (...) GROUP BY org_id`
- **manager_name**: `SELECT org_id, real_name FROM users JOIN user_roles ... WHERE role.code = "manager"`，每组织取第一个

## Task022: 组织管理前端

### 页面组件
- `OrganizationManagement.vue` — 组织列表+搜索+分页+操作
- `OrgFormDialog.vue` — 新增/编辑弹窗（名称+描述）
- admin/index.vue Tab 容器集成

### 列设计
| 列 | 宽度 | 说明 |
|----|------|------|
| ID | 60 | |
| 组织名称 | min-150 | |
| 描述 | min-200 | 空显示"-" |
| 所长 | 120 | 计算字段，未设置显示"未设置" |
| 用户数 | 80 | 居中 |
| 状态 | 80 | 启用/停用 Tag |
| 创建时间 | 170 | |
| 操作 | 160 | 编辑+启停（无删除）|

## Task023: 角色管理
- V1 只读，3 个预置角色：system_admin/manager/user
- 后端 GET /roles 批量计算 user_count
- 前端 RoleManagement.vue 纯展示表格

## Task024: 系统配置
- ConfigService 单例：`_cache: dict[str, SystemConfig]` + 类型安全 getter（get/get_int/get_float/get_bool）
- 启动时 lifespan 中加载，更新后即时刷新
- GET /configs 缓存命中，PUT /configs 批量写 DB + 日志

## Task025: 系统配置前端
- 编辑模式切换：点击编辑->行内 el-input -> 保存/取消
- 仅提交变更项（diff original vs editMap），减少不必要写操作

---
## Phase 3 — 流程模板与设计器

## Task026: 流程模板 CRUD 后端

### 端点
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /templates | 列表（含 can_edit/can_publish/can_start 权限标识） |
| POST | /templates | 创建（自动生成开始+结束节点） |
| GET | /templates/{id} | 详情（节点+连线+版本历史） |
| PUT | /templates/{id} | 更新基本信息（名称变更→硬修改） |
| DELETE | /templates/{id} | 删除（仅 draft 状态） |
| GET | /templates/organizations | 组织卡片摘要（template_count + running_instance_count） |

### MySQL ENUM 大小写问题
SQLAlchemy Enum 写入 lowercase 但 MySQL ENUM 定义可能为 UPPERCASE，导致 LookupError。
**解决**：全部状态字段改用 `String(20)` 替代 `Enum()`，应用层枚举仅作常量使用。

## Task027-028: 模板前端页面

### 组件架构
```
flows/index.vue                      ← 路由入口
  └── FlowManagement.vue             ← 流程管理主页
        ├── OrgCardList.vue          ← 组织卡片网格
        ├── TemplateTable.vue        ← 模板表格（搜索/筛选/分页/操作）
        └── InstanceTab.vue          ← 实例列表 Tab（按状态筛选）
  └── TemplateDetail.vue             ← 模板详情页
        ├── TemplateInfo.vue         ← 基础信息 el-descriptions
        ├── 节点配置表格
        └── VersionHistory.vue       ← 版本时间线
```

### 权限标识
```typescript
interface TemplateItem {
  can_edit: boolean     // 创建者+所属组织管理员
  can_publish: boolean  // 组织管理员
  can_start: boolean    // 任何已登录用户（流程已发布）
}
```

## Task029: 软修改即时生效

### 软字段覆盖机制
- **软字段**：assignee_id, time_limit_days, description, checkers, approvers
- **存储**：flow_versions.soft_config_overrides（JSON `{node_id: {field: value}}`）
- **生效**：仅影响新发起的实例，运行中实例使用原始快照
- **硬字段**：name, require_file, is_optional → 变更需发布新版本

### 端点
`PUT /api/v1/templates/{id}/nodes/{nid}/soft-config`
- 校验：仅 published 模板可软修改，硬字段返回 422
- 写入：读→合并→写 soft_config_overrides

## Task030: 版本发布 API

### 发布流程
1. 7项校验（名称/>=3节点/配置完整/BFS连通/自环/结束无出边）
2. 生成 nodes_snapshot（全量节点配置）+ edges_snapshot
3. 版本号递增、状态→published
4. 返回 version_id + version_number + node_count + edge_count

### 校验项列表
| # | 校验 | 错误格式 |
|---|------|----------|
| 1 | 模板名称不能为空 | "模板名称不能为空" |
| 2 | 节点数 >= 3 | "至少需要 3 个节点" |
| 3 | 必须有开始/结束节点 | "缺少开始节点" / "缺少结束节点" |
| 4 | 工作节点配置完整性 | "节点「XX」缺少负责人" |
| 5 | BFS 连通性 | "节点「XX」无法从开始节点到达" |
| 6 | 无自环 | "节点「XX」存在自环连线" |
| 7 | 结束节点无出边 | "结束节点「XX」不应有出边" |

## Task031: 禁用与新版本

### POST /templates/{id}/disable
- 仅 published 可停用
- 停用后不可发起新实例，运行中不受影响

### POST /templates/{id}/new-version
- published / disabled → 复制全部节点+连线 → 重置为 draft
- 节点 ID 重映射，保持连线关系
- 版本号不变化（下次发布时+1）

## Task032-034: LogicFlow 设计器

### 画布技术选型
- **LogicFlow 2.2.4**（滴滴开源，专为审批流设计）
- 内部使用 **Preact** 渲染（非 Vue），通过 `lf.register()` 注册自定义节点
- 扩展包：@logicflow/extension（Control/MiniMap/DndPanel）

### 画布配置
```typescript
const DEFAULT_CONFIG = {
  grid: { size: 20, visible: true, type: 'dot' },
  keyboard: { enabled: true },
  history: true,          // 撤销/重做
  history.maxSize: 50,    // 上限 50 步
  guards: {
    beforeDelete: (data) => !(data?.properties?.is_start || data?.properties?.is_end),
  },
}
```

### 三种自定义节点
| 节点 | 颜色 | 尺寸 | 规则 |
|------|------|------|------|
| StartNode | 绿 #67c23a | 120×50 | targetRules: [{validate: () => false}] |
| EndNode | 蓝 #409eff | 120×50 | sourceRules: [{validate: () => false}] |
| WorkNode | 蓝边框 #1a6fb5 | 160×64 | 无规则限制 |

### 拖拽添加节点
- `lf.dnd.startDrag()` + HTML5 drag 事件
- 鼠标释放坐标 → 画布坐标转换

## Task035: 软/硬修改判定

### 判定规则
```python
_TEMPLATE_HARD_FIELDS = {"name"}  # 模板级硬字段

_NODE_SOFT_FIELDS = {"assignee_id", "time_limit_days", "description", "checkers", "approvers"}
# 除此之外的节点字段变更 → 硬修改

def _is_hard_node_change(old, new):
    for key, new_val in new.items():
        if key in _NODE_SOFT_FIELDS: continue
        if new_val != old.get(key): return True
    return False
```

## Task037-038: 设计器后端服务

### 批量保存流程
```
save_design_data(template_id, nodes[], edges[])
  1. 校验模板存在且为 draft/published
  2. 加载现有节点/连线
  3. 节点：id 已有→更新，id 为空/null→新建，不在列表→删除
     - 系统节点自动映射（ID不匹配时匹配已有系统节点）
     - 系统节点不可删除
  4. 连线：同上 + 临时ID→真实ID映射
  5. published 模板 → hard_modify_template (版本+1→draft)
```

### 连线校验
| 规则 | 错误 |
|------|------|
| source != target | "连线不能连接自身（禁止自环）" |
| 开始不可作 target | "开始节点不可作为连线的目标" |
| 结束不可作 source | "结束节点不可作为连线的源" |
| 禁止重复 | "连线已存在（X → Y）" |

## Task040: HtmlNode 工作节点

### 架构变化
```
RectNode/RectNodeModel → HtmlNode/HtmlNodeModel

setHtml(rootEl: SVGForeignObjectElement) {
  rootEl.innerHTML = buildNodeHtml(properties)
  // 显示：名称 | 负责人 | 时限 | 审批人(≤2+ "+N")
}

shouldUpdate() {
  // 仅在 properties JSON 变化时重新渲染
  // 坐标变化不触发
}
```

### 视觉状态判定
```typescript
function isConfigured(props): boolean {
  return !!(props.name && props.assignee_id &&
    props.checkers?.length > 0 && props.approvers?.length > 0 &&
    props.time_limit_days >= 1)
}
```

### 样式注入
WorkNode.css 通过 `import './WorkNode.css'` 导入，样式作用于 SVG foreignObject 内 HTML。

## Task044: 发布弹窗

### 错误解析
```typescript
// "节点「审批节点」缺少负责人"
//          ↑ parseErrorParts 解析为可点击 el-link
function parseErrorParts(error: string): ErrorPart[] {
  // regex /「([^」]+)」/g 提取节点名
}

function locateNode(nodeName: string) {
  // getGraphData → find → selectNodeById → focusOn
}
```

## Task046: 版本快照

### 端点
`GET /api/v1/templates/{id}/versions/{version_id}`
```json
{
  "version_number": 11,
  "status": "published",
  "nodes_snapshot": [
    {"id": 42, "name": "审批节点", "assignee_id": 1, "checkers": [1], ...}
  ],
  "edges_snapshot": [
    {"id": 18, "source_node_id": 19, "target_node_id": 42}
  ],
  "soft_config_overrides": null,
  "published_by_name": "系统管理员"
}
```

### 快照不可变性
- 发布时生成，永不可修改（无 UPDATE 端点）
- 作为后续发起实例的基准数据
- 软修改写入 soft_config_overrides 而非修改快照

---
## 🎉 Phase 3 完成！

---

# Phase 4 — 流程实例

## 1. 发起流程实例 (POST /instances)

### 架构概览
```
Request → API (instances.py) → Service (instance_service.py) → FlowEngine (flow_engine.py)
                                      │                              │
                                      ├── 快照复制                   ├── activate_start_node
                                      ├── 配置合并                   ├── propagate_from_node
                                      ├── 连线复制                   └── calculate_incoming_counts
                                      └── 操作日志
```

### 涉及文件
| 文件 | 职责 |
|------|------|
| `app/api/instances.py` | POST /instances 端点，权限校验（manager） |
| `app/schemas/instance.py` | CreateInstanceRequest / NodeOverride / InstanceResponse |
| `app/services/instance_service.py` | 核心业务编排：验证→快照复制→配置合并→节点初始化 |
| `app/engine/flow_engine.py` | 流程引擎：节点激活、信号传播、incoming_count 计算 |

### 配置合并三层模型
```
发起覆盖 (node_overrides)     ← 发起人逐节点调整，最高优先级
      ↓ 覆盖
软覆盖 (soft_config_overrides) ← 模板发布后软修改累积
      ↓ 覆盖
快照默认值 (nodes_snapshot)    ← 发布时固化，不可变基准
```

### 节点激活流程 (BFS 队列)
1. 开始节点 `status=finished`
2. 查询 `instance_edges WHERE source_node_id = 开始节点ID`
3. 所有目标节点 `arrived_count + 1`
4. `arrived_count == incoming_count` → 激活：
   - `is_skipped` → `status=skipped`，继续向下游传播（入队）
   - `is_end` → `status=waiting_approval`
   - 普通工作节点 → `status=running`，创建 `Task(status=pending)`

### API 端点

**POST /api/v1/instances**
- 权限：`manager`
- 请求体：`CreateInstanceRequest`（template_id, version_id, name, description?, priority?, node_overrides?）
- 响应：`InstanceResponse`（含完整节点列表和状态）
- 校验：模板存在+已发布、版本归属、节点覆盖合法性（skip 仅可选节点）

### 修改的模型
全部实例相关模型的状态/枚举字段从 `Enum(XxxStatus)` 改为 `String(20)`：
- `FlowInstance`: status, priority
- `InstanceNode`: status
- `Task`: status
- `CheckRecord`: status
- `Approval`: status
- `File`: upload_type
- `OperationLog`: operator_type

---

## 前端设计风格统一

### 全局设计系统（common.scss）

参照 `pages/` 原型设计，创建了全局通用样式：

| Class | 用途 |
|-------|------|
| `.page-container` | 页面最大宽度容器（1200px） |
| `.page-breadcrumb` | 面包屑导航（`/` 分隔、链接可点击） |
| `.page-header` | 页面头部（标题 + 副标题 + 操作按钮区） |
| `.card` / `.card__header` / `.card__body` | 卡片分区布局 |
| `.status-tag--*` | 状态圆角标签（running/completed/terminated/draft/published/overdue/pending） |
| `.info-grid` / `.info-grid__item` | 4 列信息网格 |
| `.stat-num` / `.stat-num--warn` | 统计大数字 |
| `.page-actions` | 页面底部操作栏（右对齐 + 顶部分割线） |
| `.topnav-logo-icon` | 导航栏品牌 Logo 图标（蓝底白字"流"） |

### AppLayout 顶栏增强
- 品牌区域：`<router-link>` 包裹的「流」Logo 图标 + 系统名称
- 用户头像：圆形首字头像（`user-avatar`，蓝底白字，首字符取自 `real_name`）
- 菜单项高度与顶栏对齐（56px line-height）

### 登录页增强
- 品牌 Logo（44×44 蓝底"流"字）
- 英文副标题 "Enterprise Workflow Approval System"
- 演示账号提示卡片（蓝底区域）

---

## Task050 — 实例列表 API

### API 设计

**GET /api/v1/instances**

| 参数 | 类型 | 说明 |
|------|------|------|
| `organization_id` | int? | 按组织筛选 |
| `status` | str? | 逗号分隔多选（running,completed,terminated） |
| `priority` | str? | 单选（urgent/high/normal/low） |
| `keyword` | str? | 实例名称模糊搜索 |
| `page` | int | 页码（默认 1） |
| `page_size` | int | 每页条数（1-100，默认 20） |

### 技术决策
- **联表查询**：LEFT JOIN flow_templates + organizations + users 获取名称字段
- **进度计算**：`func.lower(status).in_(["finished", "skipped"])` 大小写不敏感
- **当前处理人**：子查询 `instance_nodes WHERE status='running' → users.real_name`
- **输出标准化**：所有值 `lower()` 转为小写（兼容旧 ENUM 大写数据）

---

## Task051 — 实例详情 API

### API 设计

**GET /api/v1/instances/{id}**

返回完整聚合数据：

```
{
  id, name, description, priority, status,
  template_name, organization_name, initiator_name,
  current_node_index, total_nodes,
  initiated_at, completed_at, terminated_at,
  nodes: [{
    name, status, assignee_name, deadline, round,
    checkers, approvers (标准化为 [{"user_id": N}]),
    files: [{original_name, uploader_name, ...}],
    checks: [{checker_name, status, opinion, ...}],
    approvals: [{approver_name, status, signature_applied, ...}]
  }],
  logs: {items: [...], total: N}
}
```

### 技术决策
- **批量查询防 N+1**：先查全部 instance_nodes → 收集 user_ids → 一次 IN 查询 → 内存映射
- **文件/校验/审批按 node_id 分组**：用 Python dict 做内存分组（`files_by_node[node_id] = [...]`）
- **人员数据标准化**：`_normalize_personnel()` 自动将 `[1, 2]` 转为 `[{"user_id": 1}, {"user_id": 2}]`
- **日志限制**：最近 50 条（后续可加 node_id/round 筛选参数）

---

## 实例详情前端页面（Task052）

### 组件树

```
InstanceDetail.vue（路由页面 /flows/instances/:id）
├─ InstanceInfo.vue（粘性头部 sticky top:56px）
│   └─ ProgressBar.vue（横向步骤指示器）
├─ NodeCard.vue × N（可折叠节点卡片）
└─ OperationTimeline.vue（el-timeline 操作日志）
```

### 组件 Props/职责

| 组件 | Props | 职责 | 关键状态 |
|------|-------|------|---------|
| InstanceInfo | `detail`, `isInitiator` | 名称/状态/优先级/操作按钮/4列info-grid/进度条 | 按钮按角色+状态显隐 |
| ProgressBar | `nodes` | 横向步骤指示器 | is-done(蓝底✓)/is-current(蓝环+阴影)/is-wait(灰点) |
| NodeCard | `node` | 折叠面板：配置网格+文件+校验+审批 | is-active(蓝边)/is-wait(opacity:0.65) |
| OperationTimeline | `logs`, `total` | 操作日志时间线 | 类型颜色(通过=绿/退回=红/发起=蓝) |

### 实例列表集成（FlowManagement.vue）

- 筛选 Tabs：全部/运行中/已完成/已终止（设计参考 P12）
- 300ms 防抖搜索
- 行点击 → `router.push(/flows/instances/${id})`
- `watch(activeTab)` 首次切换到实例 Tab 自动加载

---

## 终止流程后端 API（Task053）

### 端点

| 方法 | 路径 | 权限 | 功能 |
|------|------|------|------|
| POST | `/api/v1/instances/{id}/terminate` | 发起人 | 终止流程，级联关闭所有关联记录 |

### 请求

```json
{ "reason": "终止原因（必填，1-500字符）" }
```

### 处理流程（按顺序）

```
1. 查询 FlowInstance → NOT_FOUND 若不存在
2. 校验 initiator_id == current_user.id → NOT_INITIATOR (40301)
3. 校验 status != "terminated" → INSTANCE_ALREADY_TERMINATED (40902)
4. 查询全部 files → 逐个 os.remove() 物理删除
5. DELETE FROM files WHERE instance_id = ?
6. UPDATE instance_nodes SET status='terminated' WHERE NOT IN (finished,terminated,skipped)
7. UPDATE tasks SET status='terminated' WHERE NOT IN (completed,terminated)
8. UPDATE check_records SET status='terminated' WHERE status='pending'
9. UPDATE approvals SET status='terminated' WHERE status='pending'
10. UPDATE flow_instances SET status='terminated', terminated_at, termination_reason
11. INSERT operation_logs (operator_type=user, operation_type=instance_terminated)
```

### 关键设计决策

- **文件删除不可逆**：物理 `os.remove()` + SQL DELETE，不软删除
- **文件删除容错**：`OSError` 被捕获不阻断流程（文件可能已不存在）
- **终态不重复关闭**：已 finished/terminated/skipped 的 node 和已完成 task 保持不变
- **操作日志含 reason**：完整记录终止原因到 `detail` JSON 字段

---

## 终止流程前端确认弹窗（Task054）

### TerminateDialog 组件

| 属性 | 说明 |
|------|------|
| Props | `modelValue`, `instanceId`, `instanceName`, `instanceStatus` |
| Emits | `update:modelValue`, `close`, `terminated` |
| 引用设计 | D06_terminate.html — ⚠️标题 + 流程信息展示 + 警告框 + 终止并删除按钮 |

### 交互流程

```
InstanceDetail → 点击"终止流程" → 打开 TerminateDialog
  → 填写终止原因（必填 1-500）
  → 确认"终止并删除"（loading 状态）
  → 调用 POST /instances/{id}/terminate
  → 成功：ElMessage.success + 关闭弹窗 + emit('terminated')
  → 失败：ElMessage.error（不关闭弹窗，用户可重试）
  → InstanceDetail 收到 'terminated' → fetchDetail() 刷新
```

### 关键设计

- **`close-on-click-modal: false`**：点击遮罩不可关闭，防止误操作
- **`close-on-press-escape: false`**：按 ESC 不可关闭
- **`canConfirm` 计算属性**：reason 非空 + 非 submitting 时按钮才可点击
- **v-if 条件渲染**：仅 `detail` 存在时挂载，避免空实例 ID 传入

---

## 紧急换人后端 API（Task055）

### 端点

| 方法 | 路径 | 权限 | 功能 |
|------|------|------|------|
| PUT | `/api/v1/instances/{id}/nodes/{nid}/personnel` | 发起人 | 更换节点负责人/校验人/审批人 |

### 请求

```json
{
  "assignee_id": 5,           // 可选
  "checkers": [{"user_id": 3}],  // 可选
  "approvers": [{"user_id": 4}]  // 可选
}
```

### 核心算法：差集对比

```
old_ids = extract(node.checkers)    // 当前校验人 ID 集合
new_ids = extract(body.checkers)    // 请求中的校验人 ID 集合
removed = old_ids - new_ids         // 被移除的 → pending CheckRecord → terminated
added = new_ids - old_ids           // 新增的 → 创建 CheckRecord(status=pending)
// 已在列表中且已 passed/approved 的记录 → 保留不动
```

### 关键设计

- **仅差集操作**：不重建全部记录，只处理 removed 和 added，已完成的保持不变
- **assignee 变更联动 Task**：若节点处于 running/arrived 状态且仅换负责人，同步更新 Task.assignee_id
- **操作日志含变更详情**：`"节点「方案设计」人员变更：校验人: 移除 ID:3、新增 ID:5；负责人: ID:2 → ID:6"`

---

## 说明：后续功能

Task056 之后的功能详见 [`CHANGELOG.md`](CHANGELOG.md) 的完整变更记录。主要后续功能包括：

- 补交文件（supplement files）
- 实例永久删除
- 超期预警页面 `/overdue`
- 通知系统（WebSocket + Redis Pub/Sub + 30s 轮询兜底）
- Redis + arq 异步任务队列（PDF 转换）
- 方案（Proposal）类型支持
- 批准人（Endorser）机制
- 角色维度 PDF 签名默认位置
- 文件模板变量替换（15 个占位符）
- 全量代码审计与修复（38 项，详见 `AUDIT_FIX_LOG.md`）
- API 限流（三层分级 + 管理员白名单）
