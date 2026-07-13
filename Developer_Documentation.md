# 开发者文档

> 每次 Task 完成后更新，记录技术决策、架构说明和开发指引。

---

## 2026-07-13 — Task001: 前端脚手架创建

- **技术栈**：Vue 3.5 + TypeScript + Vite 8.1
- **包管理**：npm（48 个依赖）
- **类型检查**：vue-tsc 6.0.3
- **构建**：vite build，18 模块，196ms
- **项目路径**：`frontend/`
- **目录结构**：Vite 默认模板（src/assets/、src/components/、src/）
- **备注**：后续 Task 将替换默认模板文件为项目实际结构

---

## 2026-07-13 — Task002: Element Plus 安装与主题配置

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

## 2026-07-13 — Task003: 前端公共模块

- **路由**：Vue Router 4，7 条路由（/ → AppLayout children：dashboard/flows/profile/admin/*、/login、404），全部懒加载
- **状态管理**：Pinia，user store（token + userInfo + isLoggedIn + setLogin + logout）
- **HTTP 客户端**：Axios，baseURL 默认 /api/v1（可通过 VITE_API_BASE_URL 覆盖），请求拦截器自动注入 Bearer Token，响应拦截器统一错误提示 + 401 跳转登录
- **布局**：AppLayout（el-header 顶部导航 + el-menu 水平菜单 + el-dropdown 用户下拉 + el-main router-view）
- **类型**：src/types/user.ts（UserInfo 接口）
- **路径别名**：`@` → `src/`（vite.config.ts resolve.alias + tsconfig.app.json paths）
- **env 声明**：src/env.d.ts（VITE_API_BASE_URL + Vue SFC 类型声明）
- **目录结构**：src/router/ src/stores/ src/api/ src/layouts/ src/views/（dashboard/flows/profile/admin/login/error） src/types/

---

## 2026-07-13 — Task004: FastAPI 后端脚手架

- **框架**：FastAPI 0.115+、Uvicorn 0.34+
- **配置**：Pydantic Settings（自动读取 .env）
- **日志**：控制台（DEBUG 级别彩色输出）+ 按日滚动文件（logs/app.log，保留 30 天）
- **数据库预留**：SQLAlchemy 2.0 异步引擎 + sessionmaker + Base 基类 + get_db FastAPI 依赖注入
- **CORS**：通过环境变量 CORS_ORIGINS 配置，默认 localhost:5173
- **健康检查**：GET /api/v1/health
- **Swagger**：/docs + /redoc
- **启动命令**：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

---

## 2026-07-13 — Task005: 数据库连接配置

- **MySQL**：9.6 Community Server、InnoDB、utf8mb4
- **数据库名**：workflow_approval
- **驱动**：aiomysql（SQLAlchemy 2.0 异步）
- **连接池**：pool_size=10、max_overflow=20、pool_pre_ping=True
- **依赖注入**：`get_db()` → FastAPI Depends，自动 commit/rollback
- **环境变量**：DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME → database_url
- **.env 位置**：backend/.env（开发环境已配置，生产用 .env.example 模板）

---

## 2026-07-13 — Task006: 统一响应与异常处理

- **响应格式**：`{code: int, message: str, data: T | null}`
- **分页**：`{items, total, page, page_size}`
- **异常类型**：`AppException(code, message)` / `RequestValidationError` / `Exception`
- **错误码**：IntEnum，40xxx 客户端错误、50xxx 服务端错误，含默认中文提示
- **关键设计**：所有异常返回 HTTP 200，通过 `code` 字段区分业务结果；未知异常打印日志不泄露堆栈
- **目录**：backend/app/{api,models,schemas,services,core,engine,utils}/

---

## 2026-07-13 — Task007+Task008: 代码规范工具

- **前端**：ESLint 9 flat config + Prettier 3
- **后端**：Black (line-length=100) + isort (profile=black) + mypy
- **ESLint 规则**：js recommended + tsescript recommended + vue3 recommended
- **Husky**：跳过（项目尚未 git init，待后续配置）

---

## 2026-07-13 — Task009: 数据库建表

- **17 张表**：organizations/users/roles/user_roles/system_configs/flow_templates/template_nodes/template_edges/flow_versions/flow_instances/instance_nodes/instance_edges/tasks/approvals/check_records/files/operation_logs
- **分区**：operation_logs 按年 RANGE 分区（p2026–p2035 + p_future）
- **字符集**：utf8mb4 + utf8mb4_unicode_ci
- **引擎**：InnoDB
- **执行方式**：mysql CLI 直接导入 DDL SQL

---

## 2026-07-13 — Task010: ORM 模型定义

- **17 个 Model**：每个表一个独立 .py 文件，含中文注释和类型注解
- **11 个 Enum**：TemplateStatus/VersionStatus/InstanceStatus/ArchiveStatus/Priority/InstanceNodeStatus/TaskStatus/ApprovalStatus/CheckStatus/OperatorType/UploadType
- **字段**：Mapped + mapped_column 声明式风格
- **关系**：ForeignKey 外键全部定义，Organization↔User 双向 relationship
- **JSON**：approvers/checkers/nodes_snapshot/edges_snapshot/soft_config_overrides 使用 JSON 类型

---

## 2026-07-13 — Task011: 种子数据

- **脚本位置**：app/core/seed.py
- **运行命令**：python -m app.core.seed
- **角色**：system_admin/manager/user
- **组织**：通用所/结构所/电气所/暖通所
- **配置**：文件扩展名/大小限制/PDF签名坐标/默认时限
- **管理员**：admin / admin123
- **密码哈希**：bcrypt（直接调用，不用 passlib 封装）

---

## 2026-07-13 — Task012: Alembic 迁移

- **迁移工具**：Alembic 1.14+
- **配置**：alembic.ini + env.py（异步引擎 + Base.metadata）
- **初始迁移**：alembic/versions/cdc82f5bf321_initial_schema.py
- **命令**：python -m alembic revision --autogenerate -m "desc"
- **注意**：alembic.ini 不要含中文字符（Windows GBK 编码）

---

## 2026-07-13 — Task013: 登录 API

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
