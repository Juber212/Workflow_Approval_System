# 开发日志

> 每次 Task 完成后追加。

---

## 2026-07-13

### Task001 — Vue 3 + TypeScript + Vite 脚手架创建

- **状态**：✅ 完成
- **修改**：使用 `npm create vite@latest frontend -- --template vue-ts` 创建项目，npm install 安装 48 个依赖
- **验证**：vite build 构建成功（196ms，18 模块），vue-tsc 6.0.3
- **Review**：通过
- **Bug**：0

---

### Task002 — Element Plus 安装与主题配置

- **状态**：✅ 完成
- **修改**：安装 element-plus + @element-plus/icons-vue + sass-embedded；main.ts 全局注册 + 中文语言包；创建 SCSS 主题变量文件；vite.config.ts SCSS 全局注入 + @ 别名
- **验证**：vite build 通过（1573 模块，1.79s）
- **自检**：el-button/el-icon 正常渲染，中文语言包生效，主题色 #1a6fb5 覆盖
- **Review**：通过
- **Bug**：1（构建失败 → sass-embedded 缺失）

---

### Task003 — 前端公共模块搭建

- **状态**：✅ 完成
- **修改**：安装 vue-router + pinia + axios；创建 router/stores/api/layouts/views 目录和 16 个源文件
- **验证**：vue-tsc 零错误、vite build 1600 模块 573ms
- **自检**：路由懒加载分包正常、Axios Token 注入 + 401 跳转、Pinia user store、AppLayout 布局
- **Review**：通过
- **Bug**：0

---

### Task004 — FastAPI 后端脚手架创建

- **状态**：✅ 完成
- **修改**：创建 backend/ 目录结构（7 子包）、Pydantic Settings 配置、日志双输出、FastAPI 入口 + CORS + health
- **验证**：uvicorn 启动正常、/docs 可访问、/api/v1/health 返回 ok

---

### Task005 — SQLAlchemy 2.0 异步引擎与数据库连接配置

- **状态**：✅ 完成
- **修改**：创建 .env 配置文件、MySQL 9.6 创建 workflow_approval 库、验证 async engine 连接
- **验证**：Python asyncio SELECT 1 返回 1，连接成功
- **Review**：通过
- **Bug**：1（asyncio 清理时 RuntimeError，uvicorn 正常）

---

### Task006 — 统一响应模型与全局异常处理

- **状态**：✅ 完成
- **修改**：创建 app/schemas/common.py（ApiResponse + PaginatedData）、app/core/error_codes.py（ErrorCode 枚举 30+ 错误码）、app/core/exceptions.py（AppException + 中文消息映射）、更新 main.py（3 个全局异常处理器）
- **验证**：httpx GET /api/v1/health 返回 `{code:200, message:"ok", data:{...}}`
- **Review**：通过
- **Bug**：0
- **Review**：通过
- **Bug**：0

---

### Task007+Task008 — 代码规范工具（前后端合并）

- **状态**：✅ 完成
- **修改**：前端 eslint.config.js + .prettierrc；后端 pyproject.toml
- **验证**：ESLint 0 errors、Black 格式化 4 文件
- **Review**：通过
- **Bug**：0

---

### Task009 — 执行完整建表 SQL

- **状态**：✅ 完成
- **修改**：从 02_Database_Design.md 提取并执行 17 张表 DDL
- **验证**：17 张表创建成功、operation_logs 11 分区、字符集 utf8mb4
- **Review**：通过
- **Bug**：0

---

### Task010 — 17 个 SQLAlchemy ORM Model

- **状态**：✅ 完成
- **修改**：创建 17 个 Model 类 + 11 个 Python Enum + models/__init__.py
- **验证**：全部导入成功、Base.metadata 注册 17 表、枚举值正确
- **Review**：通过
- **Bug**：0

---

### Task011 — 预置数据种子脚本

- **状态**：✅ 完成
- **修改**：app/core/seed.py（幂等设计，已存在跳过）
- **验证**：3 角色 + 4 组织 + 5 配置 + 1 管理员写入成功
- **Review**：通过
- **Bug**：1（passlib+bcrypt 不兼容→改用 bcrypt 直接哈希）

---

### Task012 — Alembic 数据库迁移配置

- **状态**：✅ 完成
- **修改**：alembic init + 异步 env.py + 初始迁移文件
- **验证**：autogenerate 生成 migration、current 连接正常
- **Review**：通过
- **Bug**：1（alembic.ini 中文注释编码错误→改用英文）

---

### Task013 — 登录 API 与 JWT

- **状态**：✅ 完成
- **修改**：app/core/security.py + app/api/auth.py + app/schemas/auth.py
- **验证**：正确登录返回 token+roles、错误密码 40103、不存在用户 40103
- **Bug**：1（pool_pre_ping 与 aiomysql 不兼容→禁用）

### Task015: GET /auth/me 与 POST /auth/logout 接口

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：新增两个认证端点。GET /auth/me 通过 get_current_active_user 依赖获取当前用户并返回完整信息（含签名状态）；POST /auth/logout V1 直接返回成功，客户端删除 Token
- **修改文件**：app/schemas/auth.py（新增 UserInfoResponse）、app/api/auth.py（新增 /me 和 /logout 端点）
- **验证**：/auth/me 返回 user_id/username/real_name/email/phone/roles/org/has_signature；/auth/logout 返回退出成功；无 Token/无效 Token 均返回 401

### Task016: 登录页面开发

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：开发完整的登录页面 UI 及交互逻辑。含用户名/密码表单校验、登录 loading 态、错误提示、记住用户名功能、登录成功后跳转 Dashboard
- **修改文件**：src/api/auth.ts（新建，loginApi/getMeApi/logoutApi/toUserInfo）、src/stores/user.ts（重构，异步 login/fetchUserInfo/logout）、src/views/login/index.vue（完整登录页面）、src/types/shims.d.ts（element-plus 中文 locale 类型声明）、tsconfig.app.json（TS 7.0 baseUrl 兼容）
- **Bug Fix**：修复 vue-tsc TS5101 (baseUrl deprecated) 和 TS7016 (zh-cn.mjs 无类型声明) 两个预置构建错误
- **验证**：vue-tsc 类型检查通过，vite build 构建成功

### Task017: 前端路由守卫与角色权限控制

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：实现全局路由守卫（鉴权+角色权限+Token过期检测）、路由 meta 角色配置、AppLayout 菜单按角色显隐、403 无权限页面
- **修改文件**：src/router/guards.ts（新建，5步鉴权流程）、src/router/index.ts（meta.roles + 守卫挂载 + 路由扩展声明）、src/stores/user.ts（新增 clearToken 方法）、src/layouts/AppLayout.vue（isAdmin 角色计算 + v-if 菜单显隐）、src/views/error/403.vue（新建）
- **关键逻辑**：
  1. JWT exp 字段解析 → 提前 60s 判定过期 → 自动清 token
  2. 未登录 → /login?redirect=原路径
  3. 已登录+无 userInfo → fetchUserInfo() 恢复
  4. 角色不匹配 → /403
  5. 已登录访问 /login → 重定向 /dashboard
- **验证**：vue-tsc + vite build 构建成功，403 页面独立 chunk（0.43KB）

### Task018: 用户管理后端 API

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：实现完整用户管理 CRUD 接口（5 端点），含分页/搜索/筛选、用户名唯一性校验、角色分配、启禁用、密码重置。全部端点仅 system_admin 可访问
- **修改文件**：app/schemas/user.py（新建，5 DTO）、app/services/__init__.py（新建）、app/services/user_service.py（新建，6 业务函数）、app/api/users.py（新建，5 端点+权限守卫）、app/main.py（注册 users_router）
- **Bug Fix**：update_user 中角色替换使用 `sql_delete()` 语句替代 `await db.delete(ur)` 避免 async 兼容问题
- **验证**：
  - GET /users 列表含分页+搜索+筛选 ✅
  - POST /users 校验用户名唯一/组织存在/角色存在 ✅
  - PUT /users/{id} 编辑不可改 username ✅
  - PUT /users/{id}/status 启禁用 ✅
  - PUT /users/{id}/reset-password 密码 bcrypt 加密 ✅
  - 非 admin 用户访问全部返回 403 ✅
  - 重置密码后可用新密码登录 ✅

### Task019: 用户管理前端页面

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：开发完整的用户管理前端页面，含列表表格（分页+筛选）、新增/编辑弹窗、启禁用二次确认、重置密码弹窗。同时新增组织/角色选项后端接口以支持表单下拉框
- **修改文件**：
  - 后端：app/api/users.py（新增 GET /organizations/options + GET /roles/options）
  - 前端：src/api/admin.ts（新建，6 个用户管理 API + 2 个选项 API）、src/views/admin/components/UserFormDialog.vue（新建）、src/views/admin/components/ResetPasswordDialog.vue（新建）、src/views/admin/UserManagement.vue（新建，完整 CRUD 页面）、src/views/admin/index.vue（改造为 Tab 容器）
- **Bug Fix**：UserFormDialog 未使用的 ElMessage import；UserManagement 中使用 Vue 组件作为类型的方式错误
- **验证**：vue-tsc 类型检查通过，vite build 构建成功（admin chunk 12.61KB）

### Task020: 用户搜索组件（UserSelector）

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：实现可复用的用户搜索选择组件（el-select remote 模式），后端新增 GET /users/search 快速搜索端点。支持单选/多选、300ms 防抖、显示姓名+组织
- **修改文件**：
  - 后端：app/api/users.py（新增 GET /users/search，keyword 必填 + is_active 过滤 + limit 上限）
  - 前端：src/components/UserSelector.vue（新建，可复用组件）、src/api/admin.ts（新增 searchUsers API + UserSearchItem 类型）
- **验证**：后端搜索端点按 keyword/中文均能查到用户；前端 vue-tsc + vite build 构建成功

### Task021: 组织管理后端 API

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：实现完整组织管理接口（5 端点），含 manager_name/user_count 计算字段、名称唯一性校验、启停控制
- **修改文件**：app/schemas/organization.py（新建，4 DTO）、app/services/organization_service.py（新建，4 业务函数）、app/api/organizations.py（新建，5 端点+options）、app/main.py（注册 orgs_router）、app/api/users.py（移除重复的 /organizations/options）
- **关键实现**：
  - user_count：GROUP BY 批量统计
  - manager_name：JOIN user_roles + roles WHERE code="manager" 批量查询
  - 名称唯一性：新增全量校验，编辑排除自身
- **验证**：列表/新增/编辑/启停/options 全部测试通过

### Task022: 组织管理前端页面

- **日期**：2026-07-13
- **状态**：✅ Done
- **摘要**：开发组织管理页面，含列表（所长+用户数）、新增/编辑弹窗、启停二次确认。V1 不显示删除按钮
- **修改文件**：src/api/admin.ts（新增 4 个组织 API）、src/views/admin/components/OrgFormDialog.vue（新建）、src/views/admin/OrganizationManagement.vue（新建）、src/views/admin/index.vue（集成 OrganizationManagement）
- **验证**：vue-tsc + vite build 构建成功，admin chunk 18.25KB

### Task023: 角色管理（后端+前端，仅查看）
- **日期**：2026-07-13 | **状态**：✅ Done
- **摘要**：实现角色只读列表。后端 GET /roles 含 user_count；前端只读表格展示 3 个预置角色，不可新增/删除
- **修改**：app/schemas/role.py、app/api/roles.py、app/main.py、src/api/admin.ts、src/views/admin/RoleManagement.vue、src/views/admin/index.vue
- **验证**：system_admin=1人, manager=0人, user=1人；vue-tsc+vite build 通过

### Task024: 系统配置后端 API + 内存缓存
- **日期**：2026-07-13 | **状态**：✅ Done
- **摘要**：实现 ConfigService 内存缓存单例（启动加载+更新即时刷新），GET/PUT /configs 接口
- **修改**：app/schemas/config.py、app/services/config_service.py（ConfigService 单例+get/get_int/get_bool/get_all/load/update）、app/api/configs.py、app/main.py（lifespan 初始化缓存）
- **验证**：启动加载 5 项配置，GET 从缓存读，PUT 写 DB+刷新缓存

### Task025: 系统配置前端页面
- **日期**：2026-07-13 | **状态**：✅ Done
- **摘要**：开发系统配置只读表格+编辑模式+批量保存。仅变更项提交，保存后更新本地列表
- **修改**：src/api/admin.ts（getConfigs/updateConfigs）、src/views/admin/ConfigManagement.vue、src/views/admin/index.vue
- **验证**：vue-tsc+vite build 通过

---
## 🎉 Phase 2 完成！认证与基础数据模块（13/13 Task，100
### Task025: 系统配置前端页面
- **日期**：2026-07-13 | **状态**：Done
- **摘要**：开发系统配置只读表格+编辑模式+批量保存。仅变更项提交，保存后更新本地列表
- **修改**：src/api/admin.ts（getConfigs/updateConfigs）、src/views/admin/ConfigManagement.vue、src/views/admin/index.vue
- **验证**：vue-tsc+vite build 通过

---
## Phase 2 完成！认证与基础数据模块（13/13 Task，100%）

Phase 2 实现了：
- JWT 认证（登录/me/logout/路由守卫）
- 用户管理（CRUD+搜索+启禁用+密码重置）
- 组织管理（CRUD+启停+所长/用户数计算字段）
- 角色管理（只读列表）
- 系统配置（内存缓存+批量更新）
- UserSelector 可复用组件
- 系统管理 Tab 页面框架

### Task026: 流程模板 CRUD 后端 API
- **日期**：2026-07-13 | **状态**：Done
- **摘要**：6 个模板管理端点：组织卡片、列表(权限标识)、创建(自动生成开始/结束节点)、详情(节点/连线/版本)、更新、删除(仅draft)
- **修改**：app/schemas/template.py、app/services/template_service.py、app/api/templates.py、app/main.py、app/models/flow_template.py（Enum→String修复）、app/models/enums.py（枚举值修正）
- **Bug Fix**：MySQL ENUM 与 SQLAlchemy Enum 大小写冲突 → flow_template.status 改用 String(20)；枚举值统一 lowercase；批量查询替代 joinedload 缺失的 relationship
- **验证**：6 端点全部测试通过

### Task027: 流程模板前端列表页
- **日期**：2026-07-13 | **状态**：Done
- **摘要**：流程管理入口页 — 组织卡片网格 + 模板 Tab 表格（搜索/筛选/分页）+ 实例 Tab 占位。含新建/编辑模板弹窗、动态操作按钮（编辑/发布/发起/删除）
- **修改**：src/api/template.ts（新建）、src/views/flows/components/OrgCardList.vue、TemplateTable.vue（新建）、src/views/flows/FlowManagement.vue（新建）、src/views/flows/index.vue
- **验证**：vue-tsc + vite build 通过

### Task028: 模板详情+版本历史前端页面
- **日期**：2026-07-13 | **状态**：Done
- **摘要**：模板详情页 — 基础信息（el-descriptions）、节点配置表格、连线列表、版本历史时间线
- **修改**：src/views/flows/TemplateDetail.vue（新建）、src/views/flows/components/TemplateInfo.vue、VersionHistory.vue（新建）、src/router/index.ts（新增路由）、src/views/flows/FlowDesigner.vue（占位）
- **验证**：vite build 通过

### Task029: 软修改即时生效逻辑
- **日期**：2026-07-13 | **状态**：Done
- **摘要**：已发布模板节点软修改 → 写入 flow_versions.soft_config_overrides，不产生新版本，已运行实例不受影响。硬字段（name/require_file/is_optional）返回 422
- **修改**：app/services/version_service.py（新建，apply_soft_config / get_effective_node_config）、app/api/templates.py（新增 PUT /templates/{id}/nodes/{nid}/soft-config）
- **验证**：draft 模板/硬字段校验均返回预期错误

### Task030: 版本发布 API（校验+快照）
- **日期**：2026-07-13 | **状态**：Done
- **摘要**：POST /templates/{id}/publish — 7 项校验（名称/>=3节点/配置完整性/BFS连通性/自环/结束无出边）+ 快照生成 + 版本递增。AppException 扩展 data 字段支持结构化错误返回
- **修改**：app/services/validation_service.py（新建，BFS连通性+6项校验）、app/services/version_service.py（publish_template）、app/api/templates.py（publish端点）、app/core/exceptions.py（data字段）、app/main.py（异常处理器含data）
- **验证**：仅2节点的模板发布校验返回 errors: ["至少需要 3 个节点..."]
