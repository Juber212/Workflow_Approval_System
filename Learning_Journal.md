# 学习日志

> 每次 Task 完成后记录经验总结、问题和解决方案。

---

## 2026-07-13 — Task001: 前端脚手架创建

- **无问题**：`npm create vite@latest` 开箱即用，创建过程顺利
- **经验**：vue-tsc 启用后可直接用 `npx vite build` 验证项目可用性，无需启动 dev server

---

## 2026-07-13 — Task002: Element Plus 安装与主题配置

- **Bug**：构建报 "Preprocessor dependency sass-embedded not found"。原因是 Vite 8 内置 `rolldown` 替代了 `esbuild`，SCSS 预处理改用 `sass-embedded` 而非传统的 `sass`
- **解决**：`npm install -D sass-embedded`
- **经验**：Element Plus 的 SCSS 主题覆盖需用 `@forward` 语法（不可用 `@use`），通过 vite.config.ts 的 `css.preprocessorOptions.scss.additionalData` 全局注入

---

## 2026-07-13 — Task003: 前端公共模块搭建

- **无问题**：vue-router + pinia + axios 安装配置顺利
- **经验**：Vue SFC 懒加载使用 `() => import()` 即可，Vite 自动分包。@ 路径别名需同时在 vite.config.ts 和 tsconfig.app.json 中配置。

---

## 2026-07-13 — Task004: FastAPI 后端脚手架创建

- **无问题**：FastAPI + Uvicorn 开箱即用
- **经验**：TimedRotatingFileHandler 的 when="midnight" 适合生产日志按日归档。Windows 上 8000 端口可能被系统保留，用 18000+ 端口避开。

---

## 2026-07-13 — Task005: 数据库连接配置

- **注意**：aiomysql 在 asyncio.run() 环境清理时可能抛 RuntimeError（Event loop is closed），这是 Windows ProactorEventLoop 的已知行为，uvicorn 正常运行时不出现
- **经验**：MySQL 9.6 与 aiomysql 0.3.2 兼容

---

## 2026-07-13 — Task006: 统一响应与异常处理

- **无问题**：Pydantic + FastAPI 异常处理器注册简洁
- **经验**：业务异常返回 HTTP 200 + 错误码 code 字段，避免前端 HTTP 层和业务层双重错误处理；RequestValidationError 路径用 `.join()` 拼接便于前端定位字段`@` 路径别名需同时在 vite.config.ts（resolve.alias）和 tsconfig.app.json（paths）中配置，否则 vue-tsc 类型检查会报找不到模块。

---

## 2026-07-13 — Task007+Task008: 代码规范工具

- **无问题**：ESLint flat config + vue plugin 兼容正常
- **注意**：pyproject.toml 需放在 backend/ 目录下，Black/isort/mypy 自动读取

---

## 2026-07-13 — Task009: 数据库建表

- **无问题**：MySQL 9.6 执行 MySQL 8.0 DDL 完全兼容
- **经验**：建表 SQL 直接从设计文档提取，无需维护独立脚本

---

## 2026-07-13 — Task010: ORM 模型定义

- **无问题**：SQLAlchemy 2.0 Mapped 语法简洁，17 个模型导入无循环引用
- **经验**：operation_logs 分区表需把 created_at 加入 primary_key=True 才能注册到 Base.metadata

---

## 2026-07-13 — Task011: 种子数据

- **Bug**：passlib 1.7.4 与 bcrypt 5.0+ 不兼容（__about__ 属性移除 + detect_wrap_bug 边界检查失败）
- **解决**：改用 bcrypt 直接调用 bcrypt.hashpw() / bcrypt.gensalt()
- **经验**：幂等种子脚本用 SELECT 先查后插，适合多次执行

---

## 2026-07-13 — Task012: Alembic 迁移

- **Bug**：alembic.ini 中文注释导致 configparser UnicodeDecodeError（GBK）
- **解决**：改用英文注释
- 经验：Windows 下 configparser 默认读取编码为 locale（GBK），不要在 .ini 中放中文

---

## 2026-07-13 — Task013: 登录 API

- **Bug**：aiomysql 0.3.2 pool_pre_ping=True 导致 ping() 参数错误
- **解决**：pool_pre_ping=False
- **经验**：JWT payload 含 roles 和 org_id 方便后续权限判断，无需每次查库


### Task015 学习笔记
- /auth/me 使用 `get_current_active_user` 依赖注入，既校验 JWT 又校验账号 is_active
- has_signature 用 `signature_image IS NOT NULL` 判断，不需要额外查询
- V1 不做 Token 黑名单/logout 只是占位，后续需要时可加 Redis 黑名单

### Task016 学习笔记
- TypeScript 7.0 废弃了 `baseUrl`，需加 `ignoreDeprecations: "6.0"` 兼容 Vite/Vue 的 `@/` 路径别名
- element-plus 中文 locale 的 .mjs 导入无类型声明，需手动声明模块
- 前端 UserInfo.id 用后端 user_id 映射，保持前端命名风格统一
- 登录成功后 token 和 userInfo 同时设置，避免 AppLayout header 在路由跳转前闪现"未登录"

### Task017 学习笔记
- JWT 三个部分用 `.` 分隔：header.payload.signature，payload 是 base64url 编码的 JSON
- 前端解析 exp 只需 `atob(token.split('.')[1])` 不解码签名（安全性由服务端保证）
- 路由守卫中如果用 `useUserStore()`，必须在 `setupRouterGuards` 函数内部调用，否则在 pinia 初始化前调用会报错
- vue-router 的 RouteMeta 扩展通过 `declare module 'vue-router'` 实现，IDE 可获得类型提示
- 菜单角色控制与路由守卫是两层防护：守卫阻止路由进入，菜单只是 UI 层面的辅助控制

### Task018 学习笔记
- SQLAlchemy 2.0 async 中 `await session.delete(instance)` 在某些 ORM 实例上不稳定，用 `delete(Table).where(...)` 语句更可靠
- 用户列表的角色查询必须批量进行（`WHERE user_id IN (...)` + `GROUP BY`），N+1 在 100 条数据时就是 100 次额外查询
- 业务校验（组织存在/角色存在/用户名唯一）放在 service 层而非 API 层，保持 API 层简洁
- 编辑用户时角色替换用"先删后增"模式比计算 diff 再增删更简单可靠
- Python 3.10+ 的 `X | None` 类型语法比 `Optional[X]` 更简洁，Pydantic 2 原生支持

### Task019 学习笔记
- Vue 3 中 `defineProps` 返回的类型是运行时值，不能用 `Component['$props']` 语法获取类型，需要手动定义 interface
- 表格列宽度设计：ID=60, 用户名=120, 姓名=100, 角色=120, 组织=120, 状态=80, 创建时间=170, 操作=240，总计约 1010px，适合 1080p 以上屏幕
- 下拉框选项应该从后端动态加载，即使当前只用于表单，因为后续组织/角色管理会增删改，硬编码会导致数据不同步
- admin 页面用 Tab 容器而非独立路由，UI 更简洁，切换时不需要重新加载整个布局

### Task020 学习笔记
- el-select 的 `remote` + `remote-method` 属性启用远程搜索，配合 `filterable` 可自定义搜索逻辑
- 远程搜索需要防抖（300ms），避免每次按键都发请求
- 组件库中的 `v-model` 在 Vue 3 中展开为 `modelValue` + `update:modelValue`，用 `defineEmits` 声明
- 后端搜索接口应该与完整列表接口分开：搜索返回精简字段（id+name+org），不返回 password_hash 等敏感字段
- 搜索接口限制 limit 上限防止全表扫描

### Task021 学习笔记
- 计算字段（user_count/manager_name）应在 SQL 层面批量计算，不能在 Python 循环中逐条查询
- 组织名称唯一性校验时，编辑接口需要排除自身（`WHERE name = ? AND id != ?`）
- API 端点去重：/organizations/options 移到 organizations.py，从 users.py 删除避免路由冲突
- 组织启停而非删除：保留历史数据完整性，V1 策略

### Task022 学习笔记
- 前端 getOrgOptions 复用 /organizations/options 端点，避免在组件内过滤列表数据
- 编辑时用 `find(o => o.name === editingOrg.value!.name)` 反查 ID，依赖名称短期内不变（编辑接口 name 可改但会刷新列表）

### Task023 学习笔记
- V1 预置角色不可修改，减少权限管理复杂度
- 角色 user_count 批量 GROUP BY 替代 N+1

### Task024 学习笔记
- 配置缓存可避免每次请求都查库，5 项配置的代价不高但模式正确
- ConfigService 更新方法先写 DB 再刷新缓存（而非反过来），保证 DB 写入失败不影响缓存

### Task025 学习笔记
- 行内编辑比弹窗编辑更直观，适合 key-value 表格场景
- reactive Record<number, string> 适合编辑时的临时状态存储
- Phase 2 完成：前后端认证+基础数据 CRUD 完整可用
