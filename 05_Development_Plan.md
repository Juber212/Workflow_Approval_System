# 企业流程审批系统 — 开发计划

> **版本**：1.0
> **状态**：计划阶段
> **基于**：00_Project_Blueprint.md + 01_PRD.md + 02_Database_Design.md + 03_API_Design.md
>
> 本文档按 Phase → Milestone → Epic → Task 四层拆分全部开发工作。共 128 个 Task。

---

# 目录

1. [Phase 1: 项目初始化](#phase-1-项目初始化)
2. [Phase 2: 认证与基础数据](#phase-2-认证与基础数据)
3. [Phase 3: 流程模板与设计器](#phase-3-流程模板与设计器)
4. [Phase 4: 流程实例](#phase-4-流程实例)
5. [Phase 5: 任务与校验](#phase-5-任务与校验)
6. [Phase 6: 审批与签名](#phase-6-审批与签名)
7. [Phase 7: FlowEngine 流程引擎](#phase-7-flowengine-流程引擎)
8. [Phase 8: 文件与日志](#phase-8-文件与日志)
9. [Phase 9: Dashboard 首页看板](#phase-9-dashboard-首页看板)
10. [Phase 10: 个人中心](#phase-10-个人中心)
11. [Phase 11: 集成测试](#phase-11-集成测试)
12. [Phase 12: 部署上线](#phase-12-部署上线)

---

# Phase 1: 项目初始化

> 搭建前后端脚手架、创建数据库、初始化项目结构。本阶段共 12 个 Task。

## Milestone 1.1: 项目脚手架搭建

### Epic 1.1.1: 前端项目初始化

#### Task001: Vue 3 + TypeScript + Vite 脚手架创建

- **目标**：搭建前端项目基础框架
- **范围**：Vue 3 + TypeScript + Vite 项目创建、目录结构规划、基础配置文件
- **依赖**：无
- **输入**：Node.js 18+、pnpm
- **输出**：可运行的空项目
- **完成标准**：pnpm dev 正常启动，目录结构按模块划分（views/components/router/api/stores/utils/types），TypeScript 严格模式开启
- **预计修改文件**：package.json、vite.config.ts、tsconfig.json、tsconfig.node.json、index.html、src/main.ts、src/App.vue、src/env.d.ts、.gitignore、.eslintrc.cjs、.prettierrc
- **Git Commit**：`feat(init): 创建 Vue3 + TS + Vite 前端脚手架`
- **状态**：✅ Done

- **Git Commit**：`feat(init): 创建 Vue3 + TS + Vite 前端脚手架`
- **实际修改**：使用 `npm create vite@latest frontend -- --template vue-ts` 创建项目，npm install 安装 48 个依赖，vite build 构建成功（196ms），vue-tsc 6.0.3 可用
- **备注**：默认模板含 HelloWorld 示例组件和 style.css，将在后续 Task 中按项目需求替换

---

#### Task002: Element Plus 安装与主题配置

- **目标**：集成 Element Plus UI 组件库
- **范围**：Element Plus 安装、全局注册、中文语言包、主题变量覆盖、图标库安装
- **依赖**：Task001
- **输入**：Task001 完成后的项目
- **输出**：Element Plus 组件正常渲染，中文语言包生效
- **完成标准**：ElButton/ElTable 正常渲染、中文语言包生效、主题色变量可覆盖
- **预计修改文件**：package.json、src/main.ts、src/styles/element-variables.scss、src/styles/index.scss、vite.config.ts
- **Git Commit**：`feat(init): 集成 Element Plus 组件库与主题配置`
- **状态**：✅ Done

- **自检**：vite build 通过（1573 模块，1.79s）、el-button/el-icon 正常编译、中文语言包生效、主题色 #1a6fb5 已覆盖
- **测试**：无（纯库集成，无自定义逻辑）

---

#### Task003: 前端公共模块搭建（路由、状态管理、HTTP 客户端、布局）

- **目标**：搭建前端公共基础设施
- **范围**：Vue Router 路由配置、Pinia 状态管理初始化、Axios 封装（拦截器/统一错误处理）、AppLayout 基础布局组件（顶部导航 + 主内容区）
- **依赖**：Task002
- **输入**：Element Plus 集成后的项目
- **输出**：路由跳转正常、状态管理可用、HTTP 请求封装完成、基础布局渲染正常
- **完成标准**：
  - 路由配置完成，/dashboard、/flows、/profile、/admin/* 路由占位页面可访问
  - Axios 拦截器处理 Token 注入和 401 跳转
  - Pinia store 初始化，user store 可存储当前用户信息
  - AppLayout 组件含顶部导航 + router-view
- **预计修改文件**：package.json、src/router/index.ts、src/stores/user.ts、src/stores/index.ts、src/api/request.ts、src/api/index.ts、src/layouts/AppLayout.vue、src/views/dashboard/index.vue、src/views/flows/index.vue、src/views/profile/index.vue、src/views/admin/index.vue
- **Git Commit**：`feat(init): 搭建路由/状态管理/HTTP客户端/基础布局`
- **状态**：✅ Done

- **自检**：vue-tsc 零错误、vite build 通过（1600 模块、573ms）、所有路由懒加载分包、Axios Token 注入 + 401 拦截、Pinia user store 可用、AppLayout 顶部导航 + router-view
- **测试**：无（纯基础设施，无自定义业务逻辑）
- **实际修改**：
  - 安装 vue-router + pinia + axios
  - 新增 src/router/index.ts（7 路由，懒加载）
  - 新增 src/stores/index.ts + src/stores/user.ts
  - 新增 src/api/request.ts（Token 注入 + 401 跳转 + 统一错误处理）
  - 新增 src/layouts/AppLayout.vue（顶部导航 + 用户下拉菜单）
  - 新增 src/views/（6 占位页面：dashboard/flows/profile/admin/login/404）
  - 新增 src/types/user.ts（UserInfo 类型）
  - 更新 main.ts（注册 router + pinia）
  - 更新 App.vue（router-view）
  - 更新 tsconfig.app.json（@ 路径别名）

---

### Epic 1.1.2: 后端项目初始化

#### Task004: FastAPI 项目脚手架创建

- **目标**：搭建后端项目基础框架
- **范围**：FastAPI 项目创建、目录结构、配置管理（Pydantic Settings）、CORS 中间件、日志配置
- **依赖**：无
- **输入**：Python 3.10+、Poetry 或 pip
- **输出**：可运行的空项目，uvicorn 正常启动
- **完成标准**：
  - 项目目录结构：app/api/、app/models/、app/schemas/、app/services/、app/core/、app/engine/
  - uvicorn 启动无报错，/docs Swagger 可访问
  - CORS 配置完成（允许前端开发端口）
  - 日志配置完成（控制台 + 文件）
- **预计修改文件**：pyproject.toml、app/main.py、app/core/config.py、app/core/logging.py、app/core/database.py、.env.example、requirements.txt
- **Git Commit**：`feat(init): 创建 FastAPI 后端脚手架`
- **状态**：✅ Done

- **自检**：uvicorn 启动正常（port 18000）、/docs Swagger 可访问、日志双输出（控制台+文件）、CORS 允许 localhost:5173、health 返回 ok
- **测试**：无（脚手架无业务逻辑）

---

#### Task005: SQLAlchemy 2.0 异步引擎与数据库连接配置

- **目标**：配置 SQLAlchemy 2.0 异步引擎、Session 工厂、Base 模型基类
- **范围**：async engine 创建、async session factory、依赖注入 get_db、Base 声明基类
- **依赖**：Task004
- **输入**：MySQL 8.0 数据库已安装、Task004 项目结构
- **输出**：数据库连接正常，Session 可注入到 API 路由
- **完成标准**：
  - async engine 连接 MySQL 成功
  - async session 通过 FastAPI Depends 注入路由
  - 数据库 URL 从环境变量读取
- **预计修改文件**：app/core/database.py、app/core/config.py、app/main.py、.env.example
- **Git Commit**：`feat(db): 配置 SQLAlchemy 2.0 异步引擎与会话管理`
- **状态**：✅ Done

- **自检**：async engine 连接 MySQL 9.6 成功（SELECT 1）、async session factory 可用、FastAPI Depends get_db 就绪
- **测试**：Python asyncio 连接测试通过

---

#### Task006: 统一响应模型与全局异常处理

- **目标**：定义统一 API 响应格式和全局异常处理器
- **范围**：ApiResponse 模型、业务异常类 AppException、全局异常中间件、错误码枚举
- **依赖**：Task004
- **输入**：Task004 项目结构
- **输出**：所有 API 返回统一格式 {code, message, data}，异常被全局捕获
- **完成标准**：
  - 正常响应统一包裹为 {code:200, message:"ok", data:...}
  - 业务异常返回对应错误码和中文提示
  - 未知异常返回 500 且不泄露堆栈信息
- **预计修改文件**：app/schemas/common.py、app/core/exceptions.py、app/core/error_codes.py、app/main.py
- **Git Commit**：`feat(core): 定义统一响应模型与全局异常处理`
- **状态**：✅ Done

- **自检**：health 端点返回 {code:200, message:ok, data:{...}}、AppException 全局捕获返回对应错误码、未知异常 500 不泄露堆栈
- **测试**：httpx 调用验证 ApiResponse 格式正确

---

### Epic 1.1.3: 开发环境与工具链

#### Task007: ESLint + Prettier + Husky 前端代码规范配置

- **目标**：配置前端代码规范工具链
- **范围**：ESLint 规则配置、Prettier 格式化配置、Husky + lint-staged 提交前检查
- **依赖**：Task001
- **输入**：Task001 项目
- **输出**：代码提交前自动格式化和 lint 检查
- **完成标准**：
  - ESLint 规则生效（Vue3/TS 推荐规则）
  - Prettier 格式化统一
  - git commit 时触发 lint-staged 检查
- **预计修改文件**：.eslintrc.cjs、.prettierrc、package.json、.husky/pre-commit
- **Git Commit**：`chore(lint): 配置 ESLint + Prettier + Husky`
- **状态**：✅ Done（与Task008合并）


---

#### Task008: 后端代码质量工具配置（Black + isort + mypy）

- **目标**：配置后端代码规范和质量检查工具
- **范围**：Black 格式化配置、isort 导入排序、mypy 类型检查、pre-commit hooks
- **依赖**：Task004
- **输入**：Task004 项目
- **输出**：代码提交前格式化和类型检查
- **完成标准**：
  - Black 和 isort 在提交前自动执行
  - mypy 类型检查通过（基础配置）
  - pyproject.toml 中配置完整
- **预计修改文件**：pyproject.toml、.pre-commit-config.yaml、mypy.ini
- **Git Commit**：`chore(lint): 配置 Black + isort + mypy 后端代码质量工具`
- **状态**：✅ Done（与Task007合并）


---

## Milestone 1.2: 数据库与基础配置

### Epic 1.2.1: 数据库建表

#### Task009: 执行完整建表 SQL（17 张表 + 分区 + 索引）

- **目标**：在 MySQL 8.0 中执行 02_Database_Design.md 中的完整建表 SQL
- **范围**：创建 workflow_approval 数据库、17 张表、operation_logs 按年分区、全部索引、外键约束
- **依赖**：Task005
- **输入**：02_Database_Design.md 附录 SQL、MySQL 8.0 实例
- **输出**：17 张表在数据库中全部创建成功
- **完成标准**：
  - SHOW TABLES 显示全部 17 张表
  - operation_logs 分区确认（PARTITION BY RANGE）
  - 所有索引、外键约束生效
  - 字符集为 utf8mb4
- **预计修改文件**：database/init.sql、database/migrations/001_create_tables.sql
- **Git Commit**：`feat(db): 执行完整建表 SQL（17表+分区+索引+外键）`
- **状态**：✅ Done


---

#### Task010: SQLAlchemy ORM 模型定义（17 个 Model）

- **目标**：用 SQLAlchemy 2.0 声明式映射定义全部 17 张表的 ORM 模型
- **范围**：organizations、users、roles、user_roles、system_configs、flow_templates、template_nodes、template_edges、flow_versions、flow_instances、instance_nodes、instance_edges、tasks、check_records、approvals、files、operation_logs
- **依赖**：Task005、Task009
- **输入**：02_Database_Design.md 表结构、建好的数据库
- **输出**：17 个 ORM Model 类，每个字段/关系/约束与数据库一致
- **完成标准**：
  - 所有 Model 类定义完成，含中文注释
  - relationship 关联定义正确（如 User.roles、Template.nodes）
  - JSON 字段使用 SQLAlchemy JSON 类型
  - ENUM 字段使用 Python Enum 类
- **预计修改文件**：app/models/__init__.py、app/models/organization.py、app/models/user.py、app/models/role.py、app/models/user_role.py、app/models/system_config.py、app/models/flow_template.py、app/models/template_node.py、app/models/template_edge.py、app/models/flow_version.py、app/models/flow_instance.py、app/models/instance_node.py、app/models/instance_edge.py、app/models/task.py、app/models/check_record.py、app/models/approval.py、app/models/file.py、app/models/operation_log.py
- **Git Commit**：`feat(models): 定义 17 张表的 SQLAlchemy ORM 模型`
- **状态**：✅ Done


---

### Epic 1.2.2: 初始数据与种子脚本

#### Task011: 预置数据种子脚本（角色、配置、示例组织）

- **目标**：编写数据库种子脚本，插入系统初始数据
- **范围**：3 个角色、10 个系统配置项、4 个示例组织、1 个系统管理员账号
- **依赖**：Task009、Task010
- **输入**：蓝图中定义的预置数据
- **输出**：种子脚本可执行，初始数据正确插入
- **完成标准**：
  - 3 个角色存在：system_admin / manager / user
  - 10 个系统配置项存在且有默认值
  - 系统管理员账号 admin 可登录
- **预计修改文件**：database/seeds/001_roles.py、database/seeds/002_configs.py、database/seeds/003_organizations.py、database/seeds/004_admin_user.py、database/seeds/run_all.py
- **Git Commit**：`feat(db): 编写预置数据种子脚本`
- **状态**：✅ Done


---

#### Task012: 数据库迁移工具配置（Alembic）

- **目标**：配置 Alembic 数据库迁移工具
- **范围**：Alembic 初始化、异步迁移模板、自动生成迁移脚本配置
- **依赖**：Task009、Task010
- **输入**：SQLAlchemy 模型定义
- **输出**：alembic upgrade head 可执行，能自动检测模型变更
- **完成标准**：
  - alembic init 完成，使用异步引擎
  - alembic revision --autogenerate 可检测模型变更
  - 首次迁移脚本可正确生成全部表
- **预计修改文件**：alembic.ini、alembic/env.py、alembic/script.py.mako、alembic/versions/
- **Git Commit**：`feat(db): 配置 Alembic 异步数据库迁移`
- **状态**：✅ Done


---


# Phase 2: 认证与基础数据

> JWT 登录认证、Token 刷新、路由守卫、用户/组织/角色 CRUD、系统配置管理。本阶段共 13 个 Task。

## Milestone 2.1: 认证模块

### Epic 2.1.1: JWT 登录认证

#### Task013: 登录 API 与 JWT Token 生成

- **目标**：实现用户名密码登录接口，返回 JWT Token
- **范围**：POST /auth/login 端点、密码 bcrypt 校验、JWT Token 生成（含 user_id/username/roles/org_id）、Token 过期配置
- **依赖**：Task006、Task010、Task011
- **输入**：User 模型、密码哈希工具
- **输出**：登录 API 可用，正确返回 Token 和用户信息
- **完成标准**：
  - 正确用户名密码返回 Token + user 信息
  - 错误密码返回 40101
  - 禁用账号返回 40102
  - Token payload 含 user_id/username/roles/org_id
- **预计修改文件**：app/api/auth.py、app/schemas/auth.py、app/services/auth_service.py、app/core/security.py
- **Git Commit**：`feat(auth): 实现登录 API 与 JWT Token 生成`
- **状态**：✅ Done


---

#### Task014: JWT 认证中间件与依赖注入

- **目标**：实现 JWT Token 校验中间件和 get_current_user 依赖
- **范围**：Bearer Token 提取与校验、Token 过期检测、用户实时状态检查（is_active）、注入当前用户到请求上下文
- **依赖**：Task013
- **输入**：JWT Token 生成逻辑
- **输出**：所有受保护接口可通过 Depends(get_current_user) 获取当前用户
- **完成标准**：
  - 无 Token 返回 401
  - Token 过期返回 40103
  - Token 有效注入 current_user
  - 用户被禁用后旧 Token 拒绝
- **预计修改文件**：app/core/security.py、app/api/deps.py、app/core/exceptions.py
- **Git Commit**：`feat(auth): 实现 JWT 认证中间件与依赖注入`
- **状态**：✅ Done


---

#### Task015: GET /auth/me 与 POST /auth/logout 接口

- **目标**：实现获取当前用户信息和退出登录接口
- **范围**：GET /auth/me 返回当前登录用户完整信息、POST /auth/logout 前端清除 Token
- **依赖**：Task013、Task014
- **输入**：当前用户 Token
- **输出**：/auth/me 返回用户信息（含角色、签名状态），/auth/logout 返回成功
- **完成标准**：
  - /auth/me 返回用户 ID/username/real_name/org/roles/has_signature
  - /auth/logout 返回 200（V1 不做 Token 黑名单）
- **预计修改文件**：app/api/auth.py、app/schemas/auth.py
- **Git Commit**：`feat(auth): 实现 me 和 logout 接口`
- **状态**：Done


---

### Epic 2.1.2: 前端登录与路由守卫

#### Task016: 登录页面开发

- **目标**：开发登录页面 UI 和交互逻辑
- **范围**：登录表单（用户名/密码）、登录按钮 loading 态、错误提示、登录成功后跳转 Dashboard、Token 存储（localStorage）、记住密码
- **依赖**：Task003、Task013
- **输入**：登录 API、路由配置
- **输出**：登录页面可正常完成登录流程
- **完成标准**：
  - 登录成功后 Token 存入 localStorage
  - 登录成功后跳转 /dashboard
  - 登录失败显示中文错误提示
  - 登录中按钮 loading 且禁止重复点击
  - Token 过期后自动跳回登录页
- **预计修改文件**：src/views/login/index.vue、src/api/auth.ts、src/stores/user.ts、src/router/index.ts
- **Git Commit**：`feat(auth): 开发登录页面 UI 和交互逻辑`
- **状态**：Done


---

#### Task017: 前端路由守卫与角色权限控制

- **目标**：实现前端路由守卫，根据登录状态和角色控制页面访问
- **范围**：router.beforeEach 守卫、未登录跳转登录页、根据角色隐藏/显示菜单项、404 页面、无权限页面
- **依赖**：Task016
- **输入**：路由配置、用户角色信息
- **输出**：未登录用户无法访问业务页面，不同角色看到不同菜单
- **完成标准**：
  - 未登录访问任何页面 → 跳转登录页
  - 登录后根据角色显示对应菜单（管理员无个人中心菜单）
  - 访问无权限路由 → 显示 403 页面
  - Token 过期自动清空并跳转登录页
- **预计修改文件**：src/router/index.ts、src/router/guards.ts、src/layouts/AppLayout.vue、src/views/403.vue、src/views/404.vue
- **Git Commit**：`feat(auth): 实现前端路由守卫与角色权限控制`
- **状态**：Done


---

## Milestone 2.2: 基础数据管理

### Epic 2.2.1: 用户管理

#### Task018: 用户管理后端 API（列表/新增/编辑/状态/重置密码）

- **目标**：实现完整用户管理 CRUD 接口
- **范围**：GET /users（分页+搜索+筛选）、POST /users（新增）、PUT /users/{id}（编辑，不可改用户名）、PUT /users/{id}/status（启禁用）、PUT /users/{id}/reset-password（管理员重置密码）
- **依赖**：Task010、Task014
- **输入**：User 模型、角色模型
- **输出**：5 个用户管理 API 端点全部可用
- **完成标准**：
  - 列表支持 keyword/organization_id/is_active 筛选
  - 新增校验：username 唯一/3-30字符/字母数字下划线、password 最少6位、role_ids 至少1个
  - 编辑不可改 username
  - 禁用后用户 is_active=0
  - 重置密码 bcrypt 加密存储
- **预计修改文件**：app/api/users.py、app/schemas/user.py、app/services/user_service.py
- **Git Commit**：`feat(admin): 实现用户管理 CRUD 接口`
- **状态**：Done


---

#### Task019: 用户管理前端页面

- **目标**：开发用户管理页面
- **范围**：用户列表表格、新增/编辑弹窗表单、启用/禁用操作、重置密码弹窗、搜索框、分页
- **依赖**：Task018
- **输入**：用户管理 API
- **输出**：用户管理页面完整可操作
- **完成标准**：
  - 列表支持筛选和分页
  - 新增/编辑弹窗表单校验完整
  - 禁用/启用二次确认
  - 重置密码弹窗
  - 搜索支持按用户名/姓名模糊搜索
- **预计修改文件**：src/views/admin/UserManagement.vue、src/views/admin/components/UserFormDialog.vue、src/views/admin/components/ResetPasswordDialog.vue、src/api/admin.ts
- **Git Commit**：`feat(admin): 开发用户管理前端页面`
- **状态**：Done


---

#### Task020: 用户搜索组件（设计器/表单人员选择器复用）

- **目标**：开发可复用的用户搜索选择组件
- **范围**：远程搜索下拉选择、单选/多选模式、显示用户姓名+组织、支持跨组织搜索
- **依赖**：Task003
- **输入**：GET /users/search API
- **输出**：UserSelector 组件可复用
- **完成标准**：
  - 支持按姓名模糊搜索
  - 单选模式返回 user_id
  - 多选模式返回 user_id 列表
  - 已在选中列表中显示姓名+组织
  - 支持跨组织搜索
- **预计修改文件**：src/components/common/UserSelector.vue、src/api/user.ts
- **Git Commit**：`feat(component): 开发用户搜索选择器公共组件`
- **状态**：Done


---

### Epic 2.2.2: 组织管理

#### Task021: 组织管理后端 API（列表/新增/编辑/启停/选项）

- **目标**：实现组织管理接口
- **范围**：GET /organizations（列表含所长名和用户数计算字段）、POST /organizations（新增）、PUT /organizations/{id}（编辑）、PUT /organizations/{id}/status（启停）、GET /organizations/options（轻量选项）
- **依赖**：Task010、Task014
- **输入**：Organization 模型
- **输出**：5 个组织管理 API 端点全部可用
- **完成标准**：
  - 列表含 manager_name（计算字段）和 user_count
  - 新增校验名称唯一
  - V1 不提供 DELETE，仅支持启停
  - options 返回 id+name 轻量列表
- **预计修改文件**：app/api/organizations.py、app/schemas/organization.py、app/services/organization_service.py
- **Git Commit**：`feat(admin): 实现组织管理 CRUD 接口`
- **状态**：Done


---

#### Task022: 组织管理前端页面

- **目标**：开发组织管理页面
- **范围**：组织列表表格、新增/编辑弹窗、启停操作、所长和用户数展示
- **依赖**：Task021
- **输入**：组织管理 API
- **输出**：组织管理页面完整可操作
- **完成标准**：
  - 列表显示所长姓名和用户数
  - 新增/编辑弹窗校验完整
  - 停用/启用二次确认
  - V1 不显示删除按钮
- **预计修改文件**：src/views/admin/OrganizationManagement.vue、src/views/admin/components/OrgFormDialog.vue、src/api/admin.ts
- **Git Commit**：`feat(admin): 开发组织管理前端页面`
- **状态**：Done


---

### Epic 2.2.3: 角色管理

#### Task023: 角色管理后端 API + 前端页面（仅查看）

- **目标**：实现角色列表查看接口和前端页面
- **范围**：GET /roles（列表含 user_count）、前端只读表格展示三个预置角色及权限说明
- **依赖**：Task010、Task014
- **输入**：Role 模型
- **输出**：角色管理页只读展示三个预置角色
- **完成标准**：
  - 后端返回角色列表含 user_count
  - 前端展示三个预置角色：系统管理员/所长/普通用户
  - V1 不可新增/删除角色
  - 显示角色标识和描述
- **预计修改文件**：app/api/roles.py、app/schemas/role.py、src/views/admin/RoleManagement.vue、src/api/admin.ts
- **Git Commit**：`feat(admin): 实现角色管理查看功能`
- **状态**：Done


---

### Epic 2.2.4: 系统配置

#### Task024: 系统配置后端 API + 内存缓存

- **目标**：实现系统配置读取和更新接口，配合内存缓存
- **范围**：GET /configs（列表）、PUT /configs（批量更新）、ConfigService 内存缓存（启动时加载，每5分钟刷新）
- **依赖**：Task010、Task014
- **输入**：SystemConfig 模型
- **输出**：系统配置读写接口可用，内存缓存生效
- **完成标准**：
  - GET /configs 返回全部配置项
  - PUT /configs 批量更新，含旧值记录日志
  - 配置值从内存缓存读取（不查数据库）
  - 更新后立即刷新缓存
  - 10 个预置配置项有默认值
- **预计修改文件**：app/api/configs.py、app/schemas/config.py、app/services/config_service.py、app/core/config.py
- **Git Commit**：`feat(admin): 实现系统配置管理 API 与内存缓存`
- **状态**：Done


---

#### Task025: 系统配置前端页面

- **目标**：开发系统配置管理页面
- **范围**：配置项表单列表、编辑后批量保存、各配置项说明
- **依赖**：Task024
- **输入**：系统配置 API
- **输出**：系统配置页面可编辑和保存
- **完成标准**：
  - 表单展示 10 个配置项及默认值
  - 修改后点击保存批量提交
  - 保存成功提示
  - 各配置项有中文说明和输入校验
- **预计修改文件**：src/views/admin/SystemConfig.vue、src/api/admin.ts
- **Git Commit**：`feat(admin): 开发系统配置前端页面`
- **状态**：Todo


---

# Phase 3: 流程模板与设计器

> 流程模板 CRUD、发布校验、版本管理、LogicFlow 画布、节点/边操作、属性面板、坐标持久化、批量保存。本阶段共 21 个 Task。

## Milestone 3.1: 流程模板管理

### Epic 3.1.1: 模板 CRUD

#### Task026: 流程模板后端 API（列表/创建/详情/更新/删除）

- **目标**：实现流程模板的基本 CRUD 接口
- **范围**：GET /templates/organizations（组织选择页数据）、GET /templates（列表+筛选）、POST /templates（创建，自动生成开始和结束节点）、GET /templates/{id}（详情含版本历史）、PUT /templates/{id}（更新基本信息）、DELETE /templates/{id}（仅 draft 可删）
- **依赖**：Task010、Task014
- **输入**：FlowTemplate 模型、TemplateNode 模型
- **输出**：6 个模板管理 API 端点全部可用
- **完成标准**：
  - 创建模板时自动生成 is_start=1 和 is_end=1 两个系统节点
  - 列表返回 can_edit/can_publish/can_start 权限标识
  - 详情含版本历史列表
  - 仅 draft 状态可删除
  - 组织选择页返回 running_instance_count
- **预计修改文件**：app/api/templates.py、app/schemas/template.py、app/services/template_service.py
- **Git Commit**：`feat(template): 实现流程模板 CRUD 接口`
- **状态**：Done


---

#### Task027: 流程模板前端列表页（组织卡片 + 实例/模板 Tab）

- **目标**：开发流程管理入口页面
- **范围**：组织卡片页（全部流程卡片 + 各组织卡片）、Tab 切换（流程实例/流程模板）、模板表格（名称/版本/状态/节点数/更新时间/操作按钮）、状态筛选
- **依赖**：Task026
- **输入**：模板管理 API
- **输出**：流程管理入口页面完整可交互
- **完成标准**：
  - 组织卡片显示运行中实例数和最近更新时间
  - 当前用户所属组织高亮
  - 模板 Tab 表格显示全部列和操作按钮
  - 操作按钮根据状态和角色动态显示/隐藏
  - 草稿/已发布/已停用状态筛选
- **预计修改文件**：src/views/flows/FlowManagement.vue、src/views/flows/components/OrgCardList.vue、src/views/flows/components/TemplateTable.vue、src/api/template.ts
- **Git Commit**：`feat(template): 开发流程模板前端列表页`
- **状态**：Done


---

#### Task028: 流程模板详情页（只读）

- **目标**：开发流程模板详情只读页
- **范围**：基础信息展示、流程结构只读视图、节点配置列表、版本历史时间线
- **依赖**：Task026
- **输入**：模板详情 API
- **输出**：模板详情页完整展示
- **完成标准**：
  - 基础信息区显示名称/组织/描述/状态/版本号/时间
  - 节点配置列表显示名称/负责人/审批人/时限
  - 版本历史显示版本号/发布时间/发布人/状态
- **预计修改文件**：src/views/flows/TemplateDetail.vue、src/views/flows/components/TemplateInfo.vue、src/views/flows/components/VersionHistory.vue
- **Git Commit**：`feat(template): 开发流程模板详情页`
- **状态**：Done


---

#### Task029: 软修改即时生效逻辑（已发布模板属性编辑）

- **目标**：实现已发布模板的软修改后端逻辑
- **范围**：已发布模板修改 assignee_id/time_limit_days/description/checkers/approvers 时，写入 soft_config_overrides 覆盖层，不产生新版本
- **依赖**：Task010、Task026
- **输入**：模板节点模型、flow_versions 模型
- **输出**：软修改即时生效，新实例使用覆盖后的配置
- **完成标准**：
  - 软修改字段变更写入 soft_config_overrides
  - 版本号不变
  - 已运行实例不受影响
  - 新发起实例合并快照 + 覆盖层
  - 修改 name/require_file/is_optional 等硬修改字段返回 422
- **预计修改文件**：app/services/template_service.py、app/services/version_service.py、app/api/templates.py
- **Git Commit**：`feat(template): 实现已发布模板软修改即时生效逻辑`
- **状态**：Done


---

### Epic 3.1.2: 版本管理

#### Task030: 版本发布 API（校验 + 生成快照）

- **目标**：实现模板发布接口，含完整校验逻辑
- **范围**：POST /templates/{id}/publish、7 项发布校验（名称/节点数>=3/名称/负责人/校验人/审批人/时限/连通性+BFS）、快照生成（nodes_snapshot + edges_snapshot JSON）、版本号递增
- **依赖**：Task026、Task029
- **输入**：模板节点和连线数据
- **输出**：发布接口可用，校验不通过返回 errors 列表
- **完成标准**：
  - 校验通过生成 flow_versions 记录
  - 版本号 +1，状态变 published
  - 校验失败返回 {code:40010, data:{errors:[...]}}
  - BFS 连通性校验：从开始节点出发检查所有中间节点可达、所有路径可达结束节点
  - 分叉/汇合连线合法、禁止自环
  - 记录操作日志
- **预计修改文件**：app/api/templates.py、app/services/template_service.py、app/services/version_service.py、app/services/validation_service.py
- **Git Commit**：`feat(template): 实现版本发布 API 与完整发布校验`
- **状态**：Todo


---

#### Task031: 版本管理 API（停用/新版本/版本列表）

- **目标**：实现模板版本管理相关接口
- **范围**：POST /templates/{id}/disable（停用）、POST /templates/{id}/new-version（从已发布复制为草稿）、版本历史查询
- **依赖**：Task030
- **输入**：FlowVersion 模型
- **输出**：停用和新版本创建接口可用
- **完成标准**：
  - 停用后模板状态变 disabled，不可再发起新实例
  - new-version 复制当前节点/连线为 draft
  - 版本号在下次发布时才 +1
- **预计修改文件**：app/api/templates.py、app/services/template_service.py、app/services/version_service.py
- **Git Commit**：`feat(template): 实现版本停用与新版本创建接口`
- **状态**：Todo


---

#### Task032: 硬修改自动版本号递增逻辑

- **目标**：实现硬修改（节点/连线变更）自动触发新版本生成
- **范围**：published 状态下检测硬修改（name/require_file/is_optional 等字段变更、节点新增/删除、连线变更）→ 自动变回 draft → 发布时版本号 +1
- **依赖**：Task029、Task030
- **输入**：软修改/硬修改判定规则
- **输出**：硬修改自动触发版本升级流程
- **完成标准**：
  - 硬修改时原版本保留，新 draft 版本号 = 当前版本号 + 1
  - 运行中实例不受影响（基于旧版本快照）
  - 模板当前状态为 draft，确认后发布
- **预计修改文件**：app/services/template_service.py、app/services/version_service.py
- **Git Commit**：`feat(template): 实现硬修改自动版本号递增逻辑`
- **状态**：Todo


---

## Milestone 3.2: 流程设计器基础

### Epic 3.2.1: LogicFlow 画布

#### Task033: LogicFlow 安装与基础画布初始化

- **目标**：在 Vue 3 项目中集成 LogicFlow 并初始化基础画布
- **范围**：@logicflow/core 和 @logicflow/extension 安装、画布容器组件、基础配置（网格/背景/缩放/平移）、自定义统一节点（矩形样式，位置决定行为）
- **依赖**：Task003
- **输入**：LogicFlow 文档、Vue3 项目
- **输出**：可操作的空白画布，支持缩放和平移
- **完成标准**：
  - 画布正常渲染，显示网格背景
  - 鼠标滚轮缩放（10%-200%）
  - 拖拽空白区域平移
  - 缩放按钮（+/-/适应画布）
  - 自定义统一矩形节点注册成功
- **预计修改文件**：package.json、src/views/flows/designer/FlowDesigner.vue、src/views/flows/designer/nodes/WorkNode.ts、src/views/flows/designer/nodes/WorkNode.vue、src/views/flows/designer/FlowCanvas.vue
- **Git Commit**：`feat(designer): 集成 LogicFlow 并初始化基础画布`
- **状态**：Todo


---

#### Task034: 开始/结束节点自动生成与视觉区分

- **目标**：实现开始和结束节点的自动生成和专属样式
- **范围**：开始节点（绿色实线边框，显示"开始" + 发起人姓名）、结束节点（蓝色实线边框，显示"结束（终审）"）、不可拖拽删除限制
- **依赖**：Task033
- **输入**：统一节点模型规范
- **输出**：加载设计器时画布自动显示开始和结束节点
- **完成标准**：
  - 开始节点 is_start=true 显示"开始"标签
  - 结束节点 is_end=true 显示"结束（终审）"标签
  - 两个系统节点不可删除（Delete 无效）
  - 开始节点不可作为连线目标
  - 结束节点不可作为连线源
- **预计修改文件**：src/views/flows/designer/nodes/StartNode.ts、src/views/flows/designer/nodes/EndNode.ts、src/views/flows/designer/FlowCanvas.vue
- **Git Commit**：`feat(designer): 实现开始/结束节点自动生成与视觉区分`
- **状态**：Todo


---

#### Task035: 画布操作（添加节点/拖拽/撤销重做）

- **目标**：实现画布交互操作
- **范围**：左侧节点库面板、点击/拖拽添加工作节点、Delete 删除节点、Ctrl+Z/Y 撤销重做（上限50步）、右键菜单
- **依赖**：Task033
- **输入**：LogicFlow API
- **输出**：画布操作流畅可用
- **完成标准**：
  - 点击"添加节点"按钮在画布上新增工作节点
  - 拖拽从节点库到画布新增节点
  - Delete 键删除选中节点（开始/结束不可删）
  - 删除节点时自动移除关联连线
  - Ctrl+Z 撤销、Ctrl+Y 重做，上限 50 步
- **预计修改文件**：src/views/flows/designer/FlowDesigner.vue、src/views/flows/designer/NodePanel.vue、src/views/flows/designer/FlowCanvas.vue
- **Git Commit**：`feat(designer): 实现画布添加/删除/撤销重做操作`
- **状态**：Todo


---

#### Task036: LogicFlow 坐标持久化（position_x/position_y）

- **目标**：保存和恢复节点画布坐标
- **范围**：节点移动后更新 position_x/position_y、保存时提交到后端 template_nodes、加载时恢复节点位置
- **依赖**：Task033
- **输入**：节点模型中的坐标字段
- **输出**：刷新页面后节点位置保持不变
- **完成标准**：
  - 拖拽节点后坐标实时更新到前端状态
  - 保存时坐标随节点数据提交
  - 加载设计器时按坐标还原节点位置
- **预计修改文件**：src/views/flows/designer/FlowCanvas.vue、src/api/designer.ts、app/api/designer.py、app/services/designer_service.py
- **Git Commit**：`feat(designer): 实现 LogicFlow 节点坐标持久化`
- **状态**：Todo


---

### Epic 3.2.2: 节点与边操作

#### Task037: 设计器后端 API（加载/添加节点/更新节点/删除节点）

- **目标**：实现设计器数据操作的完整后端接口
- **范围**：GET /templates/{id}/design（加载完整设计数据）、POST /templates/{id}/nodes（添加节点）、PUT /templates/{id}/nodes/{nid}（更新节点，含软/硬修改判定）、DELETE /templates/{id}/nodes/{nid}（删除节点）
- **依赖**：Task010、Task026
- **输入**：TemplateNode、TemplateEdge 模型
- **输出**：4 个设计器节点操作 API 可用
- **完成标准**：
  - 加载接口返回完整 nodes + edges 数据
  - 添加节点自动设为中间工作节点（is_start=0, is_end=0）
  - 更新节点时区分软/硬修改
  - 开始/结束节点不可修改和删除（返回 40307）
  - 删除节点级联删除关联连线
- **预计修改文件**：app/api/designer.py、app/schemas/designer.py、app/services/designer_service.py
- **Git Commit**：`feat(designer): 实现设计器节点 CRUD 后端接口`
- **状态**：Todo


---

#### Task038: 设计器后端 API（添加连线/删除连线）

- **目标**：实现设计器连线操作后端接口
- **范围**：POST /templates/{id}/edges（添加连线，含校验）、DELETE /templates/{id}/edges/{eid}（删除连线）
- **依赖**：Task037
- **输入**：TemplateEdge 模型
- **输出**：连线操作 API 可用
- **完成标准**：
  - 添加连线校验：source != target（禁止自环）、不重复、开始不可作 target、结束不可作 source
  - UNIQUE(source_node_id, target_node_id) 约束
  - 支持 fork（一源多目标）和 join（多源一目标）
- **预计修改文件**：app/api/designer.py、app/schemas/designer.py、app/services/designer_service.py
- **Git Commit**：`feat(designer): 实现设计器连线 CRUD 后端接口`
- **状态**：Todo


---

#### Task039: 设计器节点配置面板

- **目标**：开发选中节点后的属性配置面板
- **范围**：右侧属性面板组件、选中节点显示配置表单（名称/描述/负责人/校验人/审批人/时限/文件要求/可选节点）、未配置节点橙色虚线边框+红色圆点标记、开始/结束节点显示"系统默认节点"
- **依赖**：Task033、Task037
- **输入**：节点属性数据模型
- **输出**：属性面板可配置中间工作节点全部属性
- **完成标准**：
  - 选中中间节点 → 面板显示完整配置表单
  - 选中开始/结束节点 → 面板显示"系统默认节点，无需配置"
  - 未选中 → 面板显示"请选择节点进行配置"
  - 负责人/校验人/审批人使用 UserSelector 组件
  - 属性修改即时生效（前端本地状态）
  - 必填字段未填时红色边框提示
- **预计修改文件**：src/views/flows/designer/PropertyPanel.vue、src/views/flows/designer/components/NodeConfigForm.vue
- **Git Commit**：`feat(designer): 开发节点属性配置面板`
- **状态**：Todo


---

#### Task040: 节点视觉状态（配置完整/未配置/信息展示）

- **目标**：实现节点在画布上的视觉状态区分
- **范围**：配置完整节点（实线边框，显示名称/负责人/时限/审批人）、未配置节点（橙色虚线边框+红色圆点+未配置文字）、校验人和审批人显示上限2人+超出+N、Tooltip 显示完整信息
- **依赖**：Task033、Task039
- **输入**：节点配置数据
- **输出**：节点状态一目了然
- **完成标准**：
  - 配置完整节点正常显示四行信息
  - 未配置节点橙色虚线 + 红色圆点
  - 校验人/审批人超出2人显示"+N"
  - 鼠标悬停弹出 Tooltip 显示完整信息
- **预计修改文件**：src/views/flows/designer/nodes/WorkNode.ts、src/views/flows/designer/nodes/WorkNode.vue
- **Git Commit**：`feat(designer): 实现节点视觉状态区分与信息展示`
- **状态**：Todo


---

## Milestone 3.3: 流程设计器增强

### Epic 3.3.1: 属性面板与批量保存

#### Task041: 批量保存设计器内容 API

- **目标**：实现一次提交全部设计器内容的批量保存接口
- **范围**：PUT /templates/{id}/design，接收完整 nodes + edges 数组，自动判断新增/更新/删除（id 为已有则更新，id 为 null 则新增，列表中不存在的已有 ID 则删除），同一事务执行
- **依赖**：Task037、Task038
- **输入**：完整设计器数据
- **输出**：批量保存接口原子保存全部变更
- **完成标准**：
  - 一个请求完成全部节点的增删改
  - 一个请求完成全部连线的增删改
  - 所有操作在同一数据库事务中
  - 返回成功/失败及错误详情
- **预计修改文件**：app/api/designer.py、app/services/designer_service.py、app/schemas/designer.py
- **Git Commit**：`feat(designer): 实现批量保存设计器内容 API`
- **状态**：Todo


---

#### Task042: 设计器保存草稿功能

- **目标**：实现设计器保存草稿的前端交互
- **范围**：保存按钮、保存时调用批量保存 API、不做发布校验、保存成功提示
- **依赖**：Task041
- **输入**：批量保存 API
- **输出**：保存草稿功能可用
- **完成标准**：
  - 点击"保存"调用 PUT /templates/{id}/design
  - 不做完整性校验，直接保存
  - 保存成功绿色 Toast
  - 保存失败红色 Toast 显示原因
- **预计修改文件**：src/views/flows/designer/FlowDesigner.vue、src/views/flows/designer/DesignerToolbar.vue、src/api/designer.ts
- **Git Commit**：`feat(designer): 实现设计器保存草稿功能`
- **状态**：Todo


---

#### Task043: 节点列表视图（表格辅助视图）

- **目标**：开发画布下方的表格辅助视图
- **范围**：Tab 切换（画布/节点列表）、节点列表表格（序号/名称/负责人/校验人/审批人/时限/必传文件/可选）、点击行定位画布节点、未配置字段红色提示、开始/结束节点灰色背景
- **依赖**：Task039
- **输入**：节点配置数据
- **输出**：节点列表视图可辅助快速核对配置
- **完成标准**：
  - Tab 切换流畅
  - 表格列完整展示节点配置
  - 点击行 → 画布选中对应节点
  - 未配置字段红色文字"⚠ 未配置"
  - 开始/结束节点行灰色背景
- **预计修改文件**：src/views/flows/designer/FlowDesigner.vue、src/views/flows/designer/NodeListView.vue
- **Git Commit**：`feat(designer): 开发节点列表表格辅助视图`
- **状态**：Todo


---

### Epic 3.3.2: 发布校验与版本快照

#### Task044: 发布校验前端实现（校验按钮 + 错误面板）

- **目标**：实现发布按钮和校验不通过时的错误展示
- **范围**：发布按钮、发布前调用校验逻辑、校验失败弹窗列出所有错误项（含节点定位）、校验通过调用发布 API
- **依赖**：Task030、Task042
- **输入**：发布 API、校验规则
- **输出**：发布流程完整可用
- **完成标准**：
  - 点击"发布"→ 调用发布 API
  - 校验失败弹窗列出 error 列表，点击节点名定位画布
  - 校验通过显示"发布成功，当前版本 V{n}"
  - 发布中按钮 loading 禁止重复点击
- **预计修改文件**：src/views/flows/designer/DesignerToolbar.vue、src/views/flows/designer/components/PublishDialog.vue、src/api/template.ts
- **Git Commit**：`feat(designer): 实现发布校验前端与错误展示面板`
- **状态**：Todo


---

#### Task045: 发布校验后端 - 连通性 BFS 算法

- **目标**：实现发布时的连通性校验算法
- **范围**：从开始节点 BFS 遍历，检查所有非开始/结束节点是否可达、所有路径是否可达结束节点、分叉/汇合连线合法性、孤立节点检测
- **依赖**：Task030
- **输入**：模板节点和连线数据
- **输出**：连通性校验逻辑完成
- **完成标准**：
  - 孤立中间节点被检测到
  - 无法到达结束节点的路径被检测到
  - 分叉（一课多目标）合法
  - 汇合（多源一目标）合法
  - 禁止自环检测
- **预计修改文件**：app/services/validation_service.py
- **Git Commit**：`feat(designer): 实现发布校验连通性 BFS 算法`
- **状态**：Todo


---

#### Task046: 版本快照生成与服务

- **目标**：实现发布时生成完整版本快照的服务层
- **范围**：nodes_snapshot JSON 生成（节点全量配置）、edges_snapshot JSON 生成（连线关系，使用 template_node_id 引用）、published 状态版本管理
- **依赖**：Task030、Task045
- **输入**：发布时的节点和连线
- **输出**：flow_versions 记录含完整快照
- **完成标准**：
  - nodes_snapshot 含每个节点的完整配置（名称/描述/assignee_id/time_limit/approvers/checkers/require_file/is_optional/sort_order）
  - edges_snapshot 含 source_template_node_id 和 target_template_node_id
  - 快照一旦生成不可修改
  - 快照作为后续发起实例的基准数据
- **预计修改文件**：app/services/version_service.py、app/services/template_service.py
- **Git Commit**：`feat(designer): 实现版本快照生成服务`
- **状态**：Todo


---


# Phase 4: 流程实例

> 发起实例（配置快照+软配置合并）、实例列表、详情页、终止流程、优先级修改、紧急换人。本阶段共 10 个 Task。

## Milestone 4.1: 实例管理

### Epic 4.1.1: 发起流程实例

#### Task047: 发起实例后端 API（快照复制 + 配置合并 + 节点初始化）

- **目标**：实现发起流程实例的完整后端逻辑
- **范围**：POST /instances、从 flow_versions 快照复制生成 instance_nodes 和 instance_edges、应用 node_overrides（覆盖 assignee_id/deadline/checkers/approvers/is_skipped）、处理跳过节点（is_skipped=1 → status=skipped）、计算 incoming_count、开始节点自动 finished、推进到第一个工作节点、实例状态变 running、生成 Task、计算 deadline、记录操作日志
- **依赖**：Task010、Task030、Task046
- **输入**：模板快照数据、node_overrides 配置
- **输出**：发起 API 完成全部初始化逻辑
- **完成标准**：
  - instance_nodes 正确从快照复制
  - node_overrides 正确覆盖配置
  - 跳过节点 status=skipped，不生成 Task
  - incoming_count 按 instance_edges 正确计算
  - 开始节点自动 finished
  - 第一个工作节点 running，Task pending
  - 实例 status=running
  - 操作日志已记录
- **预计修改文件**：app/api/instances.py、app/schemas/instance.py、app/services/instance_service.py、app/engine/flow_engine.py
- **Git Commit**：`feat(instance): 实现发起流程实例后端完整逻辑`
- **状态**：Todo


---

#### Task048: 发起流程实例前端页面

- **目标**：开发发起流程实例的前端交互页面
- **范围**：模板选择列表、实例名称/描述表单、优先级选择、节点配置可展开面板（逐节点调整负责人/校验人/审批人/截止日期/跳过可选节点）、确认发起按钮
- **依赖**：Task047
- **输入**：发起实例 API、模板详情 API
- **输出**：发起流程实例前端页面完整可用
- **完成标准**：
  - 选择已发布模板后展示节点配置调整面板
  - 默认使用模板配置，可逐节点展开调整
  - 可选节点显示"跳过此节点"开关
  - 优先级默认 normal，可选 urgent/high/normal/low
  - 截止日期默认 = 发起日期 + 模板天数
  - 确认发起后跳转实例详情页
- **预计修改文件**：src/views/flows/StartInstance.vue、src/views/flows/components/NodeOverridePanel.vue、src/api/instance.ts
- **Git Commit**：`feat(instance): 开发发起流程实例前端页面`
- **状态**：Todo


---

#### Task049: 实例名称唯一性提示与表单校验

- **目标**：对发起实例时的表单进行前端校验
- **范围**：实例名称 2-100 字符、名称建议唯一提示、节点配置覆盖校验（审批人/校验人至少1人）、可选节点跳过校验（仅 is_optional=1 可跳过）
- **依赖**：Task048
- **输入**：发起实例前端页面
- **输出**：完整前端校验逻辑
- **完成标准**：
  - 实例名称为空时红色边框提示
  - 实例名称超 100 字符截断提示
  - 覆盖后审批人或校验人为空则不提交
  - 不可跳过的节点无跳过开关
- **预计修改文件**：src/views/flows/StartInstance.vue、src/views/flows/components/NodeOverridePanel.vue
- **Git Commit**：`feat(instance): 实现发起实例表单校验`
- **状态**：Todo


---

### Epic 4.1.2: 实例列表与详情

#### Task050: 实例列表后端 API（组织级/全局 + 筛选）

- **目标**：实现流程实例列表接口
- **范围**：GET /instances（支持 organization_id/status/priority/keyword 筛选 + 分页）、返回含 current_assignee_name/current_node_index/total_nodes
- **依赖**：Task047
- **输入**：FlowInstance 模型
- **输出**：实例列表 API 可用
- **完成标准**：
  - 传入 organization_id 返回该组织实例
  - 不传 organization_id 返回全部实例
  - status 筛选支持多选：running/completed/terminated
  - priority 筛选
  - keyword 模糊搜索实例名称
  - current_node_index/total_nodes 正确计算
- **预计修改文件**：app/api/instances.py、app/schemas/instance.py、app/services/instance_service.py
- **Git Commit**：`feat(instance): 实现实例列表后端 API`
- **状态**：Todo


---

#### Task051: 实例详情后端 API（节点卡+文件+审批+日志聚合）

- **目标**：实现流程实例详情的完整数据聚合接口
- **范围**：GET /instances/{id}、聚合节点信息（文件/校验/审批/日志每个节点的子列表）、进度信息、操作日志分页
- **依赖**：Task010、Task047
- **输入**：FlowInstance、InstanceNode、Task、Approval、File、OperationLog 模型
- **输出**：实例详情 API 返回完整聚合数据
- **完成标准**：
  - 返回完整节点列表（每个节点含状态/轮次/文件/校验进度/审批进度/操作记录）
  - 进度信息正确（当前节点序号/总节点数）
  - 审批人和校验人状态正确计算
  - 文件按节点分组
- **预计修改文件**：app/api/instances.py、app/schemas/instance.py、app/services/instance_service.py
- **Git Commit**：`feat(instance): 实现实例详情聚合查询 API`
- **状态**：Todo


---

#### Task052: 实例详情前端页面（单页滚动+节点卡片折叠）

- **目标**：开发流程实例详情页面
- **范围**：基本信息区（名称/模板/组织/发起人/优先级/时间）、流程进度条、节点卡片折叠布局（当前节点默认展开、已完成折叠、未开始折叠）、每张卡片含文件/校验/审批/操作记录区域、全流程操作日志时间线
- **依赖**：Task051
- **输入**：实例详情 API
- **输出**：实例详情页面完整展示
- **完成标准**：
  - 基本信息 + 进度条固定在顶部
  - 节点卡片按流程顺序排列
  - 当前节点默认展开显示全部详情
  - 已完成节点折叠显示摘要
  - 右上角操作按钮（终止流程/补交文件/修改优先级）
  - 操作日志时间线按时间倒序
- **预计修改文件**：src/views/flows/InstanceDetail.vue、src/views/flows/components/InstanceInfo.vue、src/views/flows/components/NodeCard.vue、src/views/flows/components/ProgressBar.vue、src/views/flows/components/OperationTimeline.vue、src/api/instance.ts
- **Git Commit**：`feat(instance): 开发实例详情前端页面`
- **状态**：Todo


---

## Milestone 4.2: 实例控制

### Epic 4.2.1: 终止流程

#### Task053: 终止流程后端 API

- **目标**：实现流程终止的完整后端逻辑
- **范围**：POST /instances/{id}/terminate、校验权限（仅发起人）、校验流程未 terminated、更新实例状态为 terminated、关闭非终态 node/task/check/approval 为 terminated、物理删除实例全部文件及目录和 files 记录、记录操作日志
- **依赖**：Task047
- **输入**：终止原因（必填，<=500字符）
- **输出**：终止接口完成全部清理逻辑
- **完成标准**：
  - 仅发起人可终止
  - 任意未 terminated 状态均可终止（含 completed）
  - reason 必填
  - 非终态 node → terminated
  - 非终态 task → terminated
  - pending check → terminated
  - pending approval → terminated
  - 文件物理删除 + files 记录删除
  - 操作日志已记录
  - 不可撤销
- **预计修改文件**：app/api/instances.py、app/services/instance_service.py、app/engine/flow_engine.py
- **Git Commit**：`feat(instance): 实现终止流程后端完整逻辑`
- **状态**：Todo


---

#### Task054: 终止流程前端确认弹窗

- **目标**：开发终止流程的前端交互
- **范围**：终止按钮（任意状态可见）、二次确认弹窗（显示流程名称/当前节点/终止原因输入/警告提示）、确认后调用终止 API、终止成功刷新详情页、已终止流程显示只读状态
- **依赖**：Task052、Task053
- **输入**：终止 API
- **输出**：终止流程前端交互完整
- **完成标准**：
  - 终止按钮在发起人可见
  - 弹窗包含流程名称/当前节点展示
  - 终止原因必填，<=500字符
  - 警告"终止后不可恢复，文件将被永久删除"
  - 确认按钮 loading 状态
  - 终止后详情页状态更新
- **预计修改文件**：src/views/flows/InstanceDetail.vue、src/views/flows/components/TerminateDialog.vue、src/api/instance.ts
- **Git Commit**：`feat(instance): 开发终止流程前端确认弹窗`
- **状态**：Todo


---

### Epic 4.2.2: 紧急换人与优先级

#### Task055: 紧急换人后端 API（含校验/审批记录更新）

- **目标**：实现运行中实例节点人员更换的完整后端逻辑
- **范围**：PUT /instances/{id}/nodes/{nid}/personnel、校验节点未完成、更新 instance_nodes 的 assignee_id/checkers/approvers、不在新列表的 pending CheckRecord/Approval → terminated、新人员生成 CheckRecord/Approval、若 running 仅换负责人则更新 Task.assignee_id、记录操作日志（变更详情）
- **依赖**：Task047
- **输入**：新 assignee_id/checkers/approvers
- **输出**：紧急换人接口完成全部更新逻辑
- **完成标准**：
  - 仅发起人可操作
  - 仅未完成节点可修改
  - pending 校验/审批不在新列表 → terminated
  - passed/approved 记录保留不动
  - 新人员生成对应记录
  - 操作日志记录变更详情
- **预计修改文件**：app/api/instances.py、app/schemas/instance.py、app/services/instance_service.py
- **Git Commit**：`feat(instance): 实现紧急换人后端完整逻辑`
- **状态**：Todo


---

#### Task056: 优先级修改 API + 前端交互

- **目标**：实现运行中实例优先级修改功能
- **范围**：PUT /instances/{id}/priority API、前端在实例详情页顶部修改优先级下拉框、仅发起人可见、仅 running 状态可修改、记录操作日志
- **依赖**：Task047、Task052
- **输入**：新 priority 值
- **输出**：优先级修改前后端完整可用
- **完成标准**：
  - 仅发起人可修改
  - 仅 running 状态可修改
  - 前端下拉框即时更新
  - 操作日志记录变更详情
  - 修改成功绿色 Toast
- **预计修改文件**：app/api/instances.py、app/services/instance_service.py、src/views/flows/InstanceDetail.vue、src/views/flows/components/PrioritySelector.vue
- **Git Commit**：`feat(instance): 实现优先级修改功能`
- **状态**：Todo


---

# Phase 5: 任务与校验

> 待办列表、文件上传、PDF 同步转换（LibreOffice+Pillow）、节点提交、校验列表、校验通过/退回。本阶段共 12 个 Task。

## Milestone 5.1: 任务处理

### Epic 5.1.1: 待办列表与详情

#### Task057: 我的待办列表后端 API

- **目标**：实现当前用户的待办任务列表接口
- **范围**：GET /tasks、按 assignee_id 查询、支持 status/keyword 筛选、按 deadline 升序排序、返回逾期标记和剩余天数
- **依赖**：Task010、Task014
- **输入**：当前用户 ID
- **输出**：待办列表 API 可用
- **完成标准**：
  - 仅返回当前用户的任务
  - 支持 status 筛选（pending/processing）
  - keyword 模糊搜索实例名称
  - 按 deadline 升序
  - is_overdue 和 days_remaining 正确计算
  - 逾期任务红色高亮标记
- **预计修改文件**：app/api/tasks.py、app/schemas/task.py、app/services/task_service.py
- **Git Commit**：`feat(task): 实现我的待办列表后端 API`
- **状态**：Todo


---

#### Task058: 任务详情后端 API（含文件/校验/审批进度）

- **目标**：实现任务详情数据聚合接口
- **范围**：GET /tasks/{id}、返回任务信息+节点信息+当前文件+历史文件+校验进度+审批进度、首次打开时 pending → processing
- **依赖**：Task057
- **输入**：Task 模型数据
- **输出**：任务详情 API 返回完整聚合数据
- **完成标准**：
  - 返回当前和历史文件（按节点分组）
  - 返回校验进度（各校验人状态）
  - 返回审批人列表
  - pending 状态首次请求自动变 processing
  - 仅任务负责人可访问
- **预计修改文件**：app/api/tasks.py、app/schemas/task.py、app/services/task_service.py
- **Git Commit**：`feat(task): 实现任务详情聚合查询 API`
- **状态**：Todo


---

#### Task059: 任务处理前端页面（我的待办列表+任务处理页）

- **目标**：开发待办列表和任务处理页面
- **范围**：待办列表表格（实例名称/节点/模板/发起人/截止时间/状态）、状态筛选、逾期红色高亮、任务处理页面布局（流程进度条+流程信息+节点说明+文件区
- **依赖**：Task057、Task058
- **输入**：待办列表和任务详情 API
- **输出**：待办列表和任务处理页面完整可用
- **完成标准**：
  - 待办列表展示完整字段和逾期标记
  - 点击"处理"进入任务处理页
  - 任务处理页含进度条/流程信息/节点说明/文件上传区
  - 历史文件折叠展示
- **预计修改文件**：src/views/profile/TaskList.vue、src/views/profile/TaskDetail.vue、src/views/profile/components/FileUploader.vue、src/views/profile/components/TaskProgress.vue、src/api/task.ts
- **Git Commit**：`feat(task): 开发待办列表和任务处理前端页面`
- **状态**：Todo


---

### Epic 5.1.2: 文件上传与 PDF 转换

#### Task060: 文件上传后端 API（上传/删除/存储目录）

- **目标**：实现文件上传和删除接口
- **范围**：POST /tasks/{id}/files（multipart 上传，校验大小和类型）、DELETE /tasks/{id}/files/{fid}（仅未提交可删）、文件存储到 storage/archive/{实例名称}/、文件名 UUID 防冲突、files 记录创建
- **依赖**：Task057
- **输入**：multipart file
- **输出**：文件上传/删除 API 可用
- **完成标准**：
  - 校验文件大小 <= 50MB
  - 校验文件类型在白名单
  - 存储路径正确：storage/archive/{实例名称}/
  - 文件名 UUID 防冲突
  - 仅 pending/processing 状态可上传
  - 仅未提交文件的 can_delete=true 可删除
- **预计修改文件**：app/api/files.py、app/services/file_service.py、app/schemas/file.py
- **Git Commit**：`feat(task): 实现文件上传/删除后端 API`
- **状态**：Todo


---

#### Task061: PDF 转换服务（LibreOffice 无头模式 + Pillow 图片转 PDF）

- **目标**：实现非 PDF 文件自动转换的完整服务
- **范围**：LibreOffice 无头模式（Word/Excel → PDF）、Pillow（图片 → PDF）、asyncio.Semaphore 限流 2 并发、超时 60 秒、失败重试 1 次、转换成功后删除源文件保留 PDF、转换失败清理临时产物
- **依赖**：Task060
- **输入**：上传的非 PDF 文件路径
- **输出**：PDF 转换服务可用，限流生效
- **完成标准**：
  - doc/docx → PDF（LibreOffice）
  - xls/xlsx → PDF（LibreOffice）
  - png/jpg/jpeg → PDF（Pillow）
  - pdf → 跳过转换
  - Semaphore(2) 限流生效
  - 超时 60 秒 + 重试 1 次
  - 转换成功删除源文件
  - 转换失败清理临时文件
- **预计修改文件**：app/services/pdf_converter.py、app/core/config.py
- **Git Commit**：`feat(task): 实现 PDF 转换服务（LibreOffice+Pillow）`
- **状态**：Todo


---

#### Task062: 前端文件上传组件（拖拽+进度条+类型预览）

- **目标**：开发可复用的文件上传组件
- **范围**：点击上传 + 拖拽上传、多文件同时上传、上传进度条、文件类型图标预览、上传中禁止关闭页面提示、上传失败重试按钮
- **依赖**：Task060
- **输入**：文件上传 API
- **输出**：文件上传组件可复用
- **完成标准**：
  - 支持点击和拖拽上传
  - 多文件同时上传
  - 进度条实时展示
  - 文件类型图标（Word/Excel/图片/PDF）
  - 超过 50MB 提示（前端预检）
  - 类型不在白名单提示
- **预计修改文件**：src/components/common/FileUploader.vue、src/components/common/FileItem.vue
- **Git Commit**：`feat(task): 开发文件上传组件（拖拽+进度条+类型预览）`
- **状态**：Todo


---

### Epic 5.1.3: 节点提交

#### Task063: 提交节点后端 API（文件转换+校验人通知）

- **目标**：实现节点提交的完整后端逻辑
- **范围**：POST /tasks/{id}/submit、前置校验（require_file 检查）、按 Semaphore(2) 限流完成所有 PDF 转换、全部成功后原子事务：Task → waiting_check、instance_node → waiting_check、按 checkers 创建 CheckRecord(pending)、记录日志、转换失败清理且不创建 CheckRecord
- **依赖**：Task057、Task061
- **输入**：assignee_note（可选）
- **输出**：提交接口完成全部转换和状态更新
- **完成标准**：
  - require_file=true 且无文件 → 拒绝提交
  - 全部转换成功后进入 waiting_check
  - 任一转换失败 → 保持 processing，不创建 CheckRecord
  - 事务原子性保证
  - CheckRecord 按当前 task_id + round 创建
  - 操作日志记录提交和转换
- **预计修改文件**：app/api/tasks.py、app/services/task_service.py、app/engine/flow_engine.py
- **Git Commit**：`feat(task): 实现节点提交后端完整逻辑`
- **状态**：Todo


---

#### Task064: 前端提交节点交互（保存草稿+提交+PDF转换状态）

- **目标**：开发节点提交的前端交互
- **范围**：保存草稿按钮（更新备注保持 processing）、提交按钮（前置校验+调用提交 API+等待 PDF 转换）、提交中 loading 状态、提交成功/失败提示
- **依赖**：Task059、Task063
- **输入**：任务提交 API
- **输出**：前端提交交互完整可用
- **完成标准**：
  - 保存草稿仅更新备注，不触发表单提交
  - 提交按钮显示 loading 态
  - require_file 未满足时红色提示
  - 提交成功跳回待办列表
  - 转换失败显示错误信息
- **预计修改文件**：src/views/profile/TaskDetail.vue、src/api/task.ts
- **Git Commit**：`feat(task): 开发前端提交节点交互`
- **状态**：Todo


---

## Milestone 5.2: 校验处理

### Epic 5.2.1: 校验列表与详情

#### Task065: 我的校验列表后端 API + 前端页面

- **目标**：实现校验人的待校验列表功能
- **范围**：GET /checks（按 checker_id 查询，status/keyword 筛选，按 created_at 升序）、前端校验列表表格（实例名称/节点/提交人/提交时间/状态）
- **依赖**：Task063
- **输入**：当前用户 ID
- **输出**：校验列表 API 和前端页面可用
- **完成标准**：
  - 仅返回当前用户的校验记录
  - 默认筛选 pending 状态
  - keyword 模糊搜索实例名称
  - 前端列表显示完整字段
- **预计修改文件**：app/api/checks.py、app/schemas/check.py、app/services/check_service.py、src/views/profile/CheckList.vue、src/api/check.ts
- **Git Commit**：`feat(check): 实现我的校验列表功能`
- **状态**：Todo


---

#### Task066: 校验详情前端页面（文件查看+校验进度+操作按钮）

- **目标**：开发校验处理的详情页面
- **范围**：校验详情页布局（流程进度条/流程信息/文件列表/负责人备注/校验进度/校验意见输入/通过+退回按钮）
- **依赖**：Task065
- **输入**：GET /checks/{id} API
- **输出**：校验详情页完整可用
- **完成标准**：
  - 显示节点文件列表（可下载）
  - 显示负责人备注
  - 显示校验进度（各校验人状态）
  - 校验意见输入框（通过时可空，退回时必填）
  - 通过/退回按钮
- **预计修改文件**：src/views/profile/CheckDetail.vue、src/views/profile/components/CheckProgress.vue
- **Git Commit**：`feat(check): 开发校验详情前端页面`
- **状态**：Todo


---

### Epic 5.2.2: 校验通过与退回

#### Task067: 校验通过后端 API（全部通过时触发审批生成）

- **目标**：实现校验通过的完整后端逻辑
- **范围**：POST /checks/{id}/pass、更新 CheckRecord → passed、记录日志、检查当前 task_id+round 全部 CheckRecord 是否 passed：全部 passed → instance_node → waiting_approval + Task → waiting_approval + 按 approvers 创建 Approval
- **依赖**：Task065
- **输入**：opinion（可选，<=500字符）
- **输出**：校验通过 API 完成全部联动逻辑
- **完成标准**：
  - 仅 pending 状态可操作
  - opinion 可选
  - 全部 passed 时自动创建 Approval
  - 未全部 passed 仅更新自身状态
  - 操作日志已记录
- **预计修改文件**：app/api/checks.py、app/services/check_service.py、app/engine/flow_engine.py
- **Git Commit**：`feat(check): 实现校验通过与审批生成联动逻辑`
- **状态**：Todo


---

#### Task068: 校验退回后端 API（退回当前负责人+文件删除）

- **目标**：实现校验退回的完整后端逻辑
- **范围**：POST /checks/{id}/return、更新 CheckRecord → returned、其余 pending CheckRecord → terminated、删除当前 task_id+round 全部文件+files 记录、Task → processing、instance_node → running、记录日志
- **依赖**：Task067
- **输入**：opinion（必填，<=500字符）
- **输出**：校验退回 API 完成全部清理和状态回退
- **完成标准**：
  - 仅 pending 状态可操作
  - opinion 必填
  - 其余 pending 校验记录 → terminated
  - 当前轮文件物理删除 + files 记录删除
  - Task 回到 processing（不生成新 Task）
  - Node 回到 running
  - 操作日志已记录
- **预计修改文件**：app/api/checks.py、app/services/check_service.py、app/engine/flow_engine.py
- **Git Commit**：`feat(check): 实现校验退回完整逻辑`
- **状态**：Todo


---

## Milestone 5.3: 审批处理

### Epic 5.3.1: 审批列表与详情

#### Task069: 我的审批列表后端 API + 前端页面

- **目标**：实现待审批记录列表查询与展示
- **范围**：GET /approvals（支持 status/instance_id/date_from/date_to 筛选及分页）、前端审批列表页面（表格展示：流程名称、节点、发起人、截止时间、状态标签）
- **依赖**：Task047（实例已发起）、Task067（校验全部通过后生成审批）
- **输入**：JWT 用户身份
- **输出**：待审批列表 API + 前端页面
- **完成标准**：
  - 支持 pending/approved/rejected/terminated 状态筛选
  - 分页正常
  - 前端状态标签颜色正确（待审批=橙、已通过=绿、已驳回=红）
  - 点击记录跳转审批详情页
- **预计修改文件**：app/api/approvals.py、app/services/approval_service.py、src/views/profile/ApprovalList.vue、src/api/approval.ts
- **Git Commit**：`feat(approval): 实现待审批列表 API 与前端页面`
- **状态**：Todo


---

#### Task070: 审批详情前端页面

- **目标**：实现审批处理页面，展示文件、流程进度、审批意见输入
- **范围**：审批详情页组件（包含：实例信息卡片、当前节点信息、全部节点文件查看、审批意见输入框、通过/退回按钮、审批进度时间线）
- **依赖**：Task058（任务详情后端）、Task069（审批列表）
- **输入**：路由参数 approval_id
- **输出**：审批处理前端页面
- **完成标准**：
  - 可查看当前节点全部已提交文件
  - 可展开查看历史节点文件
  - 审批意见输入框（通过可选、退回必填）
  - 区分中间节点审批与结束节点终审（按钮文案和交互不同）
  - 流程进度条展示整体进度
- **预计修改文件**：src/views/profile/ApprovalDetail.vue、src/api/approval.ts、src/components/approval/ApprovalActions.vue
- **Git Commit**：`feat(approval): 实现审批详情前端页面`
- **状态**：Todo


---

### Epic 5.3.2: 审批通过

#### Task071: 审批通过后端 API（含签名上 PDF）

- **目标**：实现审批通过完整后端逻辑，包含签名自动插入 PDF
- **范围**：POST /approvals/{id}/approve、更新 Approval → approved、pypdf 签名插入、检查全部通过后推进流程、操作日志
- **依赖**：Task063（提交已完成 PDF 转换）、用户签名图片已上传
- **输入**：opinion（可选，<=500 字符）
- **输出**：审批通过 API + 签名 PDF
- **完成标准**：
  - 仅 pending 状态可操作
  - 若用户已上传签名，pypdf 将签名插入节点 PDF 固定坐标
  - 未上传签名的用户正常通过，跳过签名步骤
  - 多审批人签名按审批顺序排列，不覆盖
  - 全部审批人通过后触发流程推进（FlowEngine）
  - 操作日志含签名状态
- **预计修改文件**：app/api/approvals.py、app/services/approval_service.py、app/services/signature_service.py、app/engine/flow_engine.py
- **Git Commit**：`feat(approval): 实现审批通过 API 含签名上 PDF`
- **状态**：Todo


---

#### Task072: 签名图片上传与管理

- **目标**：用户可在个人设置中上传和管理审批签名图片
- **范围**：用户签名上传 API（PUT /profile/signature）、前端上传组件（裁剪为 200×60px PNG 透明底、<500KB 校验）、个人中心展示当前签名
- **依赖**：Task018（用户管理基础）
- **输入**：PNG 图片文件
- **输出**：签名上传与管理功能
- **完成标准**：
  - 上传时校验尺寸和格式
  - 裁剪为 200×60px
  - 文件大小 < 500KB
  - 支持重新上传覆盖
  - 预览展示
- **预计修改文件**：app/api/profile.py、app/services/user_service.py、src/views/profile/SignatureUpload.vue
- **Git Commit**：`feat(profile): 实现用户签名图片上传`
- **状态**：Todo


---

### Epic 5.3.3: 审批退回

#### Task073: 中间节点审批退回后端 API

- **目标**：实现中间节点审批退回，固定返回当前负责人
- **范围**：POST /approvals/{id}/reject（target_node_id=NULL）、Approval → rejected、其余 pending Approval/CheckRecord → terminated、当前轮文件删除、Task → processing、Node → running、日志
- **依赖**：Task071（审批通过）
- **输入**：opinion（必填）、target_node_id（必须为 null）
- **输出**：中间节点审批退回 API
- **完成标准**：
  - target_node_id 非空时返回 400
  - 当前轮全部文件及 files 记录删除
  - 其余本轮 pending Approval → terminated
  - Task 回到 processing（不生成新 Task）
  - Node 回到 running
  - 记录日志（含退回原因）
- **预计修改文件**：app/api/approvals.py、app/services/approval_service.py、app/engine/flow_engine.py
- **Git Commit**：`feat(approval): 实现中间节点审批退回`
- **状态**：Todo


---

#### Task074: 结束节点终审总驳回后端 API

- **目标**：实现结束节点发起人终审总驳回，可选任意已执行中间工作节点
- **范围**：POST /approvals/{id}/reject（target_node_id 必填）、校验目标为已执行中间工作节点（非首尾/未执行/跳过）、目标节点文件立即删除、受影响下游回退 waiting、目标节点重新激活（round+1 生成新 Task）、受影响下游重新执行时删除旧文件、并行分支级联处理
- **依赖**：Task073（中间审批退回）
- **输入**：opinion（必填）、target_node_id（必填，已执行中间工作节点）
- **输出**：终审总驳回 API
- **完成标准**：
  - 仅结束节点审批可带 target_node_id
  - 目标必须是已执行普通中间工作节点
  - 开始/结束/未执行/跳过节点不可选，返回 400
  - 目标节点文件立即物理删除 + files 记录删除
  - 目标 round+1，生成新 Task
  - 受影响下游节点回退为 waiting
  - 驳回在分叉点之前：所有分支回退
  - 驳回在分支内：仅该分支及下游回退
  - 未受影响并行分支继续运行
  - 记录总驳回日志
- **预计修改文件**：app/api/approvals.py、app/services/approval_service.py、app/engine/flow_engine.py、app/engine/reject_handler.py
- **Git Commit**：`feat(approval): 实现结束节点终审总驳回`
- **状态**：Todo


---

#### Task075: 驳回目标选择器前端组件

- **目标**：终审驳回时弹窗选择已执行中间工作节点
- **范围**：节点选择弹窗组件（列出已执行中间工作节点、单选、显示节点名称/负责人/审批人/状态、已跳过/首尾/未执行节点灰显不可选、确认按钮标注目标名称）
- **依赖**：Task070（审批详情页）、Task074（总驳回 API）
- **输入**：实例节点列表数据
- **输出**：驳回目标选择器组件
- **完成标准**：
  - 仅结束节点审批时弹出
  - 已执行中间工作节点可选
  - 开始/结束/未执行/跳过节点灰显不可选
  - 单选，不默认选中
  - 确认按钮明确标注目标节点名称
- **预计修改文件**：src/components/approval/RejectTargetSelector.vue、src/views/profile/ApprovalDetail.vue
- **Git Commit**：`feat(approval): 实现驳回目标选择器`
- **状态**：Todo


---

# Phase 6: FlowEngine 流程引擎

## Milestone 6.1: 引擎核心

### Epic 6.1.1: FlowEngine 类与节点推进

#### Task076: FlowEngine 核心类设计与实现

- **目标**：实现流程引擎核心类，封装所有流程状态推进逻辑
- **范围**：FlowEngine 类（初始化、节点推进、汇合控制、跳过传播、终止、并发锁）、在 API 层统一调用
- **依赖**：Task012（ORM 模型完成）
- **输入**：instance_id 或 node_id
- **输出**：FlowEngine 类
- **完成标准**：
  - 封装所有流程状态变更逻辑
  - 所有数据库操作在事务内完成
  - SELECT ... FOR UPDATE 行锁防并发
  - 操作日志在事务内同步写入
  - 提供清晰的公共方法接口
- **预计修改文件**：app/engine/__init__.py、app/engine/flow_engine.py
- **Git Commit**：`feat(engine): 实现 FlowEngine 核心类`
- **状态**：Todo


---

#### Task077: 串行节点推进逻辑

- **目标**：实现串联流程中当前节点完成后激活下一节点
- **范围**：当前节点完成 → finished → 查询 direct 下游 → 激活 downstream 节点（running + 生成 Task + 计算 deadline）
- **依赖**：Task076
- **输入**：完成的 node_id
- **输出**：下游节点激活
- **完成标准**：
  - 通过 instance_edges 查找直接下游
  - 下游 incoming_count=1 时直接激活
  - 下游为结束节点时创建 Approval 而非 Task
  - 下游为工作节点时创建 Task
- **预计修改文件**：app/engine/flow_engine.py
- **Git Commit**：`feat(engine): 实现串行节点推进`
- **状态**：Todo


---

#### Task078: 并行汇合控制（incoming_count / arrived_count）

- **目标**：实现 fork/join 并行流程的汇合控制
- **范围**：上游节点完成时仅增加直接下游 arrived_count、arrived_count == incoming_count 时激活、arrived_count > incoming_count 时事务回滚报警、开始节点自身不增加
- **依赖**：Task077
- **输入**：完成的 node_id
- **输出**：并行汇合正确激活
- **完成标准**：
  - 仅直接下游 arrived_count + 1
  - 当前完成节点自身 arrived_count 不增加
  - 使用原子 UPDATE 防并发重复计数
  - arrived_count == incoming_count 激活下游
  - arrived_count > incoming_count 回滚并报警
  - 开始节点 incoming_count=0、arrived_count=0
- **预计修改文件**：app/engine/flow_engine.py、app/engine/convergence.py
- **Git Commit**：`feat(engine): 实现并行汇合控制`
- **状态**：Todo


---

#### Task079: 可选节点跳过与信号传播

- **目标**：实现发起时可跳过可选节点，信号沿原边传播
- **范围**：发起时对 selected_skip_node_ids 的节点置 skipped、skipped 节点向每个直接下游传播一次到达信号、连续 skipped 递归传播、不改 instance_edges
- **依赖**：Task078
- **输入**：实例初始化时的跳过节点列表
- **输出**：跳过节点自动传播到达信号
- **完成标准**：
  - skipped 节点不生成 Task/CheckRecord/Approval
  - 跳过节点向每个直接下游发送到达信号
  - 连续多个可选节点递归穿透
  - fork 分支全跳过时 join 正常汇合
  - 至少保留一个实际执行工作节点
  - 进度显示跳过节点单独标记
- **预计修改文件**：app/engine/flow_engine.py、app/services/instance_service.py
- **Git Commit**：`feat(engine): 实现可选节点跳过信号传播`
- **状态**：Todo


---

### Epic 6.1.2: 终止与驳回引擎

#### Task080: 终止流程引擎事务

- **目标**：实现终止流程的完整引擎事务
- **范围**：校验 can_terminate（发起人 + 未终止状态）、实例→terminated、所有非终态 node→terminated、所有非终态 task→terminated、所有 pending check→terminated、所有 pending approval→terminated、删除全部物理文件+files 记录、写日志、同一事务
- **依赖**：Task076
- **输入**：instance_id、reason
- **输出**：终止流程完整事务
- **完成标准**：
  - 仅发起人可终止
  - 已 terminated 实例返回 409
  - completed 含已归档实例可终止
  - 所有非终态记录全部关闭
  - 全部物理文件删除、files 记录删除
  - 日志和实例元数据保留
  - 全在同一数据库事务
- **预计修改文件**：app/engine/flow_engine.py、app/services/instance_service.py
- **Git Commit**：`feat(engine): 实现终止流程事务`
- **状态**：Todo


---

#### Task081: 驳回级联回退引擎

- **目标**：实现总驳回的级联回退逻辑（依赖 Task074 的前置校验结果）
- **范围**：按 instance_edges 拓扑计算受影响下游节点集合、目标 round+1 生成新 Task、受影响下游回退 waiting、并行分支边界判定（分叉点之前 vs 分支内）、未受影响分支保持
- **依赖**：Task078、Task074
- **输入**：reject_target_node_id、当前 approval 所属 node_id
- **输出**：目标及受影响下游正确回退
- **完成标准**：
  - 按图可达关系计算受影响节点（不依赖 sort_order）
  - 分叉前驳回：所有分支回退
  - 分支内驳回：仅该分支及下游回退
  - 目标节点 round+1
  - 受影响下游节点重新执行时删除旧文件
  - 未受影响并行分支不动
- **预计修改文件**：app/engine/flow_engine.py、app/engine/reject_handler.py
- **Git Commit**：`feat(engine): 实现驳回级联回退`
- **状态**：Todo


---

# Phase 7: 文件与日志

## Milestone 7.1: 文件管理

### Epic 7.1.1: 文件服务

#### Task082: 文件存储目录管理与清理

- **目标**：实现文件存储目录的创建、管理和清理
- **范围**：storage/archive/{实例名称}/ 目录自动创建、UUID 文件名防冲突、终止/驳回清理函数、转换临时文件清理
- **依赖**：Task009（数据库建表）
- **输入**：instance_id
- **输出**：文件存储目录管理服务
- **完成标准**：
  - 发起实例时自动创建目录
  - UUID 文件名保证唯一
  - 清理函数可按 instance/node/round 精确删除
  - 转换临时文件在成功/失败后均清理
- **预计修改文件**：app/services/file_storage.py、app/utils/file_utils.py
- **Git Commit**：`feat(file): 实现文件存储目录管理`
- **状态**：Todo


---

#### Task083: 文件下载鉴权接口

- **目标**：实现文件下载，通过接口鉴权而非直接暴露 URL
- **范围**：GET /files/{file_id}/download、校验用户对该实例有查看权限、返回文件流（Content-Disposition 下载）、仅下载最终 PDF
- **依赖**：Task060（文件上传）
- **输入**：file_id
- **输出**：文件下载 API
- **完成标准**：
  - 通过 JWT 鉴权
  - 仅能下载有权限查看的实例文件
  - 返回正确 MIME 类型和文件名
  - 文件不存在时返回 404
- **预计修改文件**：app/api/files.py、app/services/file_service.py
- **Git Commit**：`feat(file): 实现文件下载鉴权接口`
- **状态**：Todo


---

#### Task084: 补交文件 API + 前端页面

- **目标**：实现补交文件功能
- **范围**：POST /instances/{id}/files/supplement、权限校验（running: 发起人+当前负责人、completed: 发起人+对应节点历史负责人、terminated 禁止）、补交文件转 PDF、记录 upload_type=supplement、不影响流程状态、前端补交按钮与弹窗
- **依赖**：Task060、Task063
- **输入**：file、node_id（必填选定归属节点）
- **输出**：补交文件功能
- **完成标准**：
  - 权限校验严格按阶段
  - 补交文件归属正确 node_id/round
  - upload_type=supplement 标记
  - 转换成功后仅保留 PDF
  - 不影响流程状态和节点推进
  - 终止实例隐藏补交按钮
  - 操作日志记录
- **预计修改文件**：app/api/instances.py、app/services/file_service.py、src/components/file/SupplementUpload.vue
- **Git Commit**：`feat(file): 实现补交文件功能`
- **状态**：Todo


---

## Milestone 7.2: 操作日志

### Epic 7.2.1: 日志记录系统

#### Task085: 日志记录工具函数与操作类型枚举

- **目标**：实现统一的日志记录工具，定义全系统操作类型枚举
- **范围**：操作类型枚举（create_template→archive_instance，含 pass_check/return_check/update_node_personnel/update_instance_priority/delete_file/convert_file）、log_operation() 工具函数（自动判断 operator_type=user/system、支持 triggered_by）、日志写入不抛异常阻塞业务
- **依赖**：Task009（operation_logs 表）
- **输入**：instance_id、operation_type、operator_id（可空）、detail 等
- **输出**：日志记录工具
- **完成标准**：
  - 枚举覆盖所有 20+ 操作类型
  - operator_type=system 时 operator_id=NULL
  - 自动操作可通过 triggered_by 追溯触发人
  - 日志写入失败不抛异常阻塞主业务
  - 统一函数签名，所有模块复用
- **预计修改文件**：app/utils/logger.py、app/utils/operation_types.py
- **Git Commit**：`feat(log): 实现日志记录工具与操作类型枚举`
- **状态**：Todo


---

#### Task086: 全局操作日志查询 API + 前端页面

- **目标**：实现管理员全局日志查询
- **范围**：GET /logs（ADMIN 权限）、支持 instance_id/node_id/round/operation_type/operator_id/date_from/date_to 筛选及分页、前端日志页面（表格+筛选）、日志不可修改不可删除
- **依赖**：Task085
- **输入**：查询参数
- **输出**：全局日志查询功能
- **完成标准**：
  - 仅 ADMIN 可访问
  - 全部筛选参数可用
  - 响应含 operator_type/operator_id/triggered_by/node_id/round
  - 按 created_at DESC 排序
  - 无 DELETE/UPDATE 端点
  - 前端表格分页正常
- **预计修改文件**：app/api/logs.py、app/services/log_service.py、src/views/admin/OperationLogs.vue
- **Git Commit**：`feat(log): 实现全局日志查询`
- **状态**：Todo


---

#### Task087: 实例日志 API（含 node_id/round 筛选）

- **目标**：实现实例级操作日志查询，支持按节点和轮次筛选
- **范围**：GET /instances/{id}/logs（ALL 权限）、支持 node_id/round/operation_type 筛选、响应含完整字段、前端实例详情页节点卡片日志嵌入
- **依赖**：Task085、Task051（实例详情）
- **输入**：instance_id、可选筛选参数
- **输出**：实例日志 API + 前端节点日志展示
- **完成标准**：
  - 返回 node_id/node_name 稳定关联
  - node_id 筛选命中对应节点所有轮次
  - round 筛选命中对应轮次
  - 前端节点卡片可独立请求本节点日志
  - 实例详情页底部有全流程日志时间线
- **预计修改文件**：app/api/instances.py、app/services/log_service.py、src/views/instance/InstanceDetail.vue
- **Git Commit**：`feat(log): 实现实例日志 API 含节点/轮次筛选`
- **状态**：Todo


---

# Phase 8: 展示与分析

## Milestone 8.1: Dashboard

### Epic 8.1.1: 首页看板

#### Task088: Dashboard 统计 API

- **目标**：实现首页看板全部统计接口
- **范围**：14.1 stats（running_instances/overdue_tasks/total_instances/archived_total/archived_this_month）、14.2 任务状态分布饼图（含 waiting_check 五类）、14.3 个人待办概览、14.4 逾期预警（remaining_days/risk_level）、14.5 各所流程概览（组织实例列表而非模板汇总）
- **依赖**：Task047+（实例和任务 API 就绪）
- **输入**：JWT 用户身份
- **输出**：Dashboard 全部统计 API
- **完成标准**：
  - stats 返回全部指标
  - 任务分布含五类状态（pending/processing/waiting_check/waiting_approval/completed）
  - 逾期预警区分 overdue/today/upcoming
  - 各所概览返回运行中实例列表
  - 归档统计按 archive_status=archived
  - 总实例数正确
- **预计修改文件**：app/api/dashboard.py、app/services/dashboard_service.py
- **Git Commit**：`feat(dashboard): 实现 Dashboard 统计 API`
- **状态**：Todo


---

#### Task089: Dashboard 前端页面

- **目标**：实现首页看板前端展示
- **范围**：统计卡片行（运行中/已逾期/全部流程/已归档）、任务状态饼图（点击扇区跳转对应列表）、个人待办列表（快速入口）、卡点追踪表格、逾期预警列表、各所流程概览（卡片布局）
- **依赖**：Task088
- **输入**：Dashboard API 数据
- **输出**：Dashboard 前端页面
- **完成标准**：
  - 所有卡片数据正确
  - 饼图五色分区、点击跳转正确
  - 逾期预警区分颜色（红/橙/蓝）
  - 卡点追踪显示节点完整状态
  - 各所流程概览卡片按组织展示
  - 响应式布局
- **预计修改文件**：src/views/dashboard/Dashboard.vue、src/components/dashboard/StatsCards.vue、src/components/dashboard/TaskPieChart.vue、src/components/dashboard/OverdueList.vue、src/components/dashboard/OrgOverview.vue
- **Git Commit**：`feat(dashboard): 实现首页看板前端页面`
- **状态**：Todo


---

## Milestone 8.2: 个人中心

### Epic 8.2.1: 个人业务中心

#### Task090: 个人中心布局与导航

- **目标**：实现个人中心整体布局（卡片分区、一页展示）
- **范围**：个人中心入口（仅 manager/user 可见）、卡片分区布局（我的待办/我的校验/我的审批/我发起的流程/流程记录）、右上角下拉菜单（个人信息/修改密码）
- **依赖**：Task016（登录页面）
- **输入**：用户角色信息
- **输出**：个人中心布局框架
- **完成标准**：
  - system_admin 不显示个人中心菜单
  - 卡片分区布局合理
  - 右上角下拉菜单含个人信息和修改密码入口
  - 各卡片有对应数据列表入口
- **预计修改文件**：src/views/profile/ProfileLayout.vue、src/layout/HeaderDropdown.vue、src/router/profile.ts
- **Git Commit**：`feat(profile): 实现个人中心布局与导航`
- **状态**：Todo


---

#### Task091: 我的任务/校验/审批列表聚合

- **目标**：在个人中心聚合展示个人所有待办
- **范围**：个人中心首页卡片数据聚合（我的待办数、待校验数、待审批数）、各卡片点击进入对应列表页、列表页复用已有组件
- **依赖**：Task057（待办）、Task065（校验）、Task069（审批）
- **输入**：JWT 用户身份
- **输出**：个人中心聚合页面
- **完成标准**：
  - 每个卡片显示待处理数量
  - 点击卡片跳转对应列表
  - 列表页支持筛选和分页
  - 空状态友好提示
- **预计修改文件**：src/views/profile/ProfileLayout.vue、src/views/profile/MyTasks.vue、src/views/profile/MyChecks.vue、src/views/profile/MyApprovals.vue、src/views/profile/MyInstances.vue
- **Git Commit**：`feat(profile): 实现个人中心任务聚合`
- **状态**：Todo


---

#### Task092: 个人信息与密码修改

- **目标**：实现个人信息查看和密码修改功能
- **范围**：GET/PUT /profile（查看/更新个人信息）、PUT /profile/password（修改密码，需旧密码验证）、前端信息展示弹窗和密码修改表单
- **依赖**：Task018（用户管理）
- **输入**：用户信息、密码
- **输出**：个人信息与密码修改功能
- **完成标准**：
  - 个人信息页面展示姓名/用户名/组织/角色
  - 修改密码需旧密码验证
  - 新密码需确认一致
  - 修改成功提示并更新 token
- **预计修改文件**：app/api/profile.py、app/services/user_service.py、src/views/profile/ProfileInfo.vue、src/views/profile/ChangePassword.vue
- **Git Commit**：`feat(profile): 实现个人信息与密码修改`
- **状态**：Todo


---

# Phase 9: 集成测试与部署

## Milestone 9.1: 集成测试

### Epic 9.1.1: 核心流程测试

#### Task093: 全流程串联 E2E 测试

- **目标**：验证从模板创建到实例归档的完整串联流程
- **范围**：创建模板 → 设计器画节点连线 → 发布 → 发起实例 → 负责人执行上传 → 校验通过 → 审批通过 → 下一节点 → 终审通过归档
- **依赖**：全部业务 API 完成
- **输入**：测试数据（模板、用户、文件）
- **输出**：E2E 测试用例及通过报告
- **完成标准**：
  - 3 节点串联流程从头到尾跑通
  - 文件转换成功
  - 校验全部通过后进入审批
  - 审批全部通过后进入下一节点
  - 终审通过后实例 completed + archive_status=archived
  - 所有文件为 PDF 格式
- **预计修改文件**：tests/e2e/test_full_flow.py、tests/conftest.py、tests/fixtures/
- **Git Commit**：`test(e2e): 实现全流程串联测试`
- **状态**：Todo


---

#### Task094: 并行流程（fork/join）E2E 测试

- **目标**：验证 fork/join 并行流程的汇合正确性
- **范围**：A 分叉 → B1/B2 并行 → C 汇合、各分支独立执行节奏、汇合点计数正确、全部到达后激活下游
- **依赖**：Task078、Task093
- **输入**：并行流程模板
- **输出**：并行流程测试通过
- **完成标准**：
  - 两个并行分支独立推进互不影响
  - arrived_count 正确累加
  - 全部完成时正确激活汇合节点
  - 一个分支完成另一个未完成时汇合等待
  - 并发审批不出现重复计数
- **预计修改文件**：tests/e2e/test_parallel_flow.py
- **Git Commit**：`test(e2e): 实现并行流程测试`
- **状态**：Todo


---

#### Task095: 三类退回 E2E 测试

- **目标**：验证校验退回、中间审批退回、终审总驳回三类场景
- **范围**：
  - 校验退回：退回后 Task 回 processing、文件删除、重新提交再次校验
  - 中间审批退回：固定当前负责人、文件删除、Task 回 processing
  - 终审总驳回：选择已执行节点、目标 round+1、下游回退 waiting、重新执行
- **依赖**：Task068、Task073、Task074
- **输入**：各类退回场景数据
- **输出**：三类退回测试通过
- **完成标准**：
  - 校验退回不跳节点、Task 不变、文件已删
  - 中间审批退回不跨节点、文件已删
  - 终审总驳回目标正确、级联回退正确
  - 退回后重启流转正常
  - 日志记录正确
- **预计修改文件**：tests/e2e/test_reject_flows.py
- **Git Commit**：`test(e2e): 实现三类退回测试`
- **状态**：Todo


---

#### Task096: 终止流程 E2E 测试

- **目标**：验证终止流程在不同阶段的正确性
- **范围**：Created 终止、Running 终止、Completed 终止、终止后文件全部删除、files 记录删除、日志保留、不可恢复
- **依赖**：Task080
- **输入**：不同状态的实例
- **输出**：终止流程测试通过
- **完成标准**：
  - 各类状态均可终止
  - 文件物理删除 + files 记录删除
  - 日志和实例元数据保留
  - 不可重复终止（409）
  - 终止后补交被拒绝
- **预计修改文件**：tests/e2e/test_terminate.py
- **Git Commit**：`test(e2e): 实现终止流程测试`
- **状态**：Todo


---

### Epic 9.1.2: 边界与异常测试

#### Task097: 权限边界测试

- **目标**：验证各角色权限边界
- **范围**：system_admin 不能访问业务模块、manager/user 不能访问系统管理、非发起人不能终止/修改优先级/紧急换人、校验人/审批人不能补交、非 assigned 不能提交
- **依赖**：全部 API 完成
- **输入**：不同角色 JWT token
- **输出**：权限测试通过
- **完成标准**：
  - 所有越权请求返回 403
  - 前端隐藏按钮 + 后端校验双重保障
  - 覆盖所有角色和关键操作
- **预计修改文件**：tests/api/test_permissions.py
- **Git Commit**：`test(api): 实现权限边界测试`
- **状态**：Todo


---

#### Task098: 文件转换异常测试

- **目标**：验证 PDF 转换失败时的处理逻辑
- **范围**：上传损坏文件、LibreOffice 转换超时、Semaphore 限流满、转换失败后 Task 保持 processing、不创建 CheckRecord、临时文件清理
- **依赖**：Task061、Task063
- **输入**：异常文件（损坏、超大、不支持格式）
- **输出**：异常处理测试通过
- **完成标准**：
  - 损坏文件转换失败 Task 保持 processing
  - 不创建 CheckRecord
  - 返回友好错误提示
  - 临时文件清理干净
  - 转换超时后重试一次
- **预计修改文件**：tests/unit/test_pdf_conversion.py
- **Git Commit**：`test(unit): 实现 PDF 转换异常测试`
- **状态**：Todo


---

#### Task099: 并发审批测试

- **目标**：验证多人并行审批时的数据一致性
- **范围**：两个审批人同时 approve、SELECT FOR UPDATE 行锁、arrived_count 不重复计数、签名不互相覆盖
- **依赖**：Task071、Task078
- **输入**：多审批人并发请求
- **输出**：并发审批测试通过
- **完成标准**：
  - 同时审批不导致状态错乱
  - arrived_count 只增一次
  - 签名按审批顺序排列不覆盖
  - 全部通过后正确推进
  - 无死锁或数据不一致
- **预计修改文件**：tests/stress/test_concurrent_approval.py
- **Git Commit**：`test(stress): 实现并发审批测试`
- **状态**：Todo


---

#### Task100: 性能基准测试

- **目标**：验证大规模实例下的查询和推进性能
- **范围**：1000 实例列表分页查询 < 500ms、100 节点复杂流程推进 < 2s、文件转换限流不超 2 并发、Dashboard 聚合 < 1s
- **依赖**：全部核心功能完成
- **输入**：大量测试数据
- **输出**：性能基准报告
- **完成标准**：
  - 列表分页 < 500ms
  - 复杂流程推进 < 2s
  - PDF 转换并发 ≤ 2
  - Dashboard < 1s
- **预计修改文件**：tests/performance/test_benchmarks.py
- **Git Commit**：`test(perf): 实现性能基准测试`
- **状态**：Todo


---

## Milestone 9.2: 部署

### Epic 9.2.1: 生产环境部署

#### Task101: 生产环境配置管理

- **目标**：实现多环境配置管理
- **范围**：.env 配置（数据库/SECRET_KEY/LibreOffice 路径/文件存储路径/CORS 白名单）、配置加载模块、敏感信息不入库
- **依赖**：Task004（后端脚手架）
- **输入**：生产环境参数
- **输出**：多环境配置模块
- **完成标准**：
  - .env.example 含完整说明
  - 开发/测试/生产环境分离
  - 敏感配置不硬编码
  - 启动时校验必填配置
- **预计修改文件**：app/core/config.py、.env.example、docker-compose.yml
- **Git Commit**：`feat(deploy): 实现多环境配置管理`
- **状态**：Todo


---

#### Task102: MySQL 8.0 部署与初始化

- **目标**：编写数据库部署和初始化文档
- **范围**：MySQL 8.0 安装配置、建库建表脚本执行、分区表初始化（预建未来分区）、初始数据导入、备份策略
- **依赖**：Task009、Task011
- **输入**：完整 DDL SQL、种子数据
- **输出**：数据库部署文档和脚本
- **完成标准**：
  - 一键建库脚本
  - 分区表按年创建未来分区
  - 初始角色和系统管理员可用
  - 备份脚本
- **预计修改文件**：scripts/init_db.sql、scripts/seed_data.sql、scripts/backup.sh、docs/deployment.md
- **Git Commit**：`feat(deploy): 实现 MySQL 部署初始化脚本`
- **状态**：Todo


---

#### Task103: LibreOffice + Nginx 部署

- **目标**：编写服务端软件部署文档
- **范围**：LibreOffice 无头模式安装、字体安装（防 PDF 乱码）、Nginx 反向代理配置（含 /api/v1 代理和前端静态文件）、文件上传大小限制、Gunicorn/Uvicorn 生产启动
- **依赖**：Task061（PDF 转换）、Task004（后端）
- **输入**：服务器环境
- **输出**：部署文档与配置模板
- **完成标准**：
  - LibreOffice 命令行可用
  - 无头模式转换正常
  - Nginx 反向代理 + 静态文件服务
  - 文件上传 50MB 限制
  - 后端 Gunicorn + Uvicorn workers
- **预计修改文件**：nginx.conf、scripts/setup.sh、docs/deployment.md、gunicorn.conf.py
- **Git Commit**：`feat(deploy): 实现服务端软件部署配置`
- **状态**：Todo


---

#### Task104: 项目部署文档

- **目标**：编写完整的项目部署手册
- **范围**：系统要求、依赖安装步骤、数据库初始化、应用部署（后端+前端）、验证清单、常见问题排查
- **依赖**：Task101-103
- **输入**：全部部署配置
- **输出**：部署文档
- **完成标准**：
  - 覆盖从零到可用的完整步骤
  - 含验证检查点
  - 常见问题排查指南
  - 供运维人员直接使用
- **预计修改文件**：docs/deployment.md、README.md
- **Git Commit**：`docs: 编写项目部署文档`
- **状态**：Todo


---

# 附录 A: Task 依赖关系图

```
Phase 1 ─────────────────────────────────────────────────────────────────
Task001 → Task002 → Task003          (前端)
Task004 → Task005 → Task006          (后端)
Task007 + Task008                    (工具链)
Task009 → Task010                    (数据库)
Task011 + Task012                    (种子数据+迁移)

Phase 2 ─────────────────────────────────────────────────────────────────
Task013 → Task014 → Task015 → Task016 → Task017  (认证)
Task018 → Task019 + Task020                       (用户管理)
Task021 → Task022                                 (组织管理)
Task023                                           (角色管理)
Task024 → Task025                                 (系统配置)

Phase 3 ─────────────────────────────────────────────────────────────────
Task026 → Task027 + Task028 + Task029              (模板 CRUD)
Task030 → Task031 + Task032                        (版本发布)
Task033 → Task034 → Task035 → Task036              (设计器画布)
Task037 + Task038 → Task039 → Task040              (节点边操作)
Task041 + Task042 + Task043                        (批量保存)
Task044 + Task045 → Task046                        (发布校验+快照)

Phase 4 ─────────────────────────────────────────────────────────────────
Task047 → Task048 + Task049                        (发起实例)
Task050 → Task051 → Task052                        (实例列表+详情)
Task053 → Task054                                  (终止流程)
Task055 + Task056                                  (紧急换人+优先级)

Phase 5 ─────────────────────────────────────────────────────────────────
Task057 → Task058 → Task059                        (任务列表+详情)
Task060 → Task061 → Task062                        (文件上传+转换)
Task063 → Task064                                  (节点提交)
Task065 → Task066                                  (校验列表+详情)
Task067 → Task068                                  (校验通过+退回)

Phase 6 ─────────────────────────────────────────────────────────────────
Task069 → Task070                                  (审批列表+详情)
Task071 → Task072                                  (审批通过+签名)
Task073 → Task074 → Task075                        (审批退回+总驳回)

Phase 7 ─────────────────────────────────────────────────────────────────
Task076 → Task077 → Task078 → Task079              (FlowEngine 核心)
         Task080 + Task081                         (终止+驳回引擎)

Phase 8 ─────────────────────────────────────────────────────────────────
Task082 → Task083 → Task084                        (文件管理)
Task085 → Task086 → Task087                        (操作日志)

Phase 9 ─────────────────────────────────────────────────────────────────
Task088 → Task089                                  (Dashboard)
Task090 → Task091 → Task092                        (个人中心)

Phase 10 ────────────────────────────────────────────────────────────────
Task093 → Task094 + Task095 + Task096              (核心 E2E)
Task097 + Task098 + Task099 + Task100              (边界+性能)
Task101 → Task102 + Task103 → Task104              (部署)
```

---

> **文档版本**：1.0
> **创建日期**：2026-07-13
> **基于**：00_Project_Blueprint.md + 01_PRD.md + 02_Database_Design.md + 03_API_Design.md
> **总 Task 数**：104
> **状态**：全部 Todo，待开发启动
