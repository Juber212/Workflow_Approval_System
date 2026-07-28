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
- **经验**：MySQL 8.0 与 aiomysql 0.3.2 兼容

---

## 2026-07-13 — Task006: 统一响应与异常处理

- **无问题**：Pydantic + FastAPI 异常处理器注册简洁
- **经验**：业务异常返回 HTTP 200 + 错误码 code 字段，避免前端 HTTP 层和业务层双重错误处理；RequestValidationError 路径用 `.join()` 拼接便于前端定位字段
- **经验**：`@` 路径别名需同时在 vite.config.ts（resolve.alias）和 tsconfig.app.json（paths）中配置，否则 vue-tsc 类型检查会报找不到模块。

---

## 2026-07-13 — Task007+Task008: 代码规范工具

- **无问题**：ESLint flat config + vue plugin 兼容正常
- **注意**：pyproject.toml 需放在 backend/ 目录下，Black/isort/mypy 自动读取

---

## 2026-07-13 — Task009: 数据库建表

- **无问题**：MySQL 8.0 DDL 执行完全兼容
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

---
## Phase 3 — 流程模板与设计器

### Task026 学习笔记
- MySQL ENUM 与 SQLAlchemy Enum 大小写冲突是常见陷阱。MySQL ENUM 存入时区分大小写但 SQLAlchemy Enum 的 `.value` 返回定义时的值。如果两者不一致，查询能查出但更新会报 LookupError。**根本解决**：全部状态字段改用 `String(20)`。
- 模板列表的权限标识（can_edit/can_publish/can_start）应在 SQL 层面预先计算，避免前端逐个判断。

### Task030 学习笔记
- BFS 连通性校验是最核心的发布校验：从开始节点正向 BFS + 从结束节点反向 BFS，两者取交集确保每个工作节点都能"从开始到达"且"能到达结束"。
- AppException 扩展 data 字段后，全局异常处理器需同步修改，将 data 透传给前端。

### Task032-033 学习笔记（LogicFlow 设计器）
- LogicFlow 2.x 内部使用 Preact 渲染，非 Vue。类型定义文件（.d.ts）与 Vue 无关。
- 自定义节点通过 `lf.register(type, { model, view })` 注册，model 负责数据（尺寸/样式/属性），view 负责渲染。
- `getNodeStyle()` 替代 1.x 的 `getShape()` 用于节点边框/填充样式。
- `guards.beforeDelete` 可在删除前拦截，返回 false 阻止删除。
- CSS 路径：LogicFlow 2.2.4 的 CSS 在 `@logicflow/core/dist/index.css`（非 1.x 的 style/index.css）。
- 事件名：画布变换事件用 `graph:transform`（非 1.x 的 `transform:change`）。
- `history.maxSize` 限制撤销/重做步数上限。

### Task037 学习笔记（设计器后端）
- 批量保存的"系统节点自动映射"是关键设计：前端可能提交错误的开始/结束节点 ID（或 null），后端自动匹配已有系统节点，既保证完整性又不产生重复。
- 临时 ID 映射：新增节点时，前端传递临时 client ID，后端返回真实 DB ID，连线中的 source/target 引用需从临时 ID 映射到真实 ID。
- `is_hard_modified` 标志必须在调用 `hard_modify_template` **之前**捕获，因为该函数会将状态从 published 改为 draft。

### Task038 学习笔记（连线 API）
- 连线校验必须同时考虑 fork（一源多目标）和 join（多源一目标），V1 不做条件分支但允许并行分叉/汇合。
- DB 层的 UNIQUE(source_node_id, target_node_id) 约束是最后防线，应用层校验（查库判重）提供更友好的错误提示。

### Task040 学习笔记（HtmlNode 工作节点）
- LogicFlow 2.x 的 HtmlNode 通过 SVG `<foreignObject>` 注入 HTML，实现富文本渲染。这比纯 SVG text 元素灵活得多。
- `setHtml(rootEl)` 的参数是 SVGForeignObjectElement，可像普通 DOM 操作一样 innerHTML。
- `shouldUpdate()` 的返回值控制是否重新渲染，对比 properties JSON 字符串可避免坐标变化导致的无效重渲染。
- foreignObject 内的 CSS 需要单独管理（WorkNode.css），Vue scoped styles 无法穿透 SVG 边界。
- 用户名需要缓存到节点属性中（assignee_name 等），否则 HtmlNode 只能显示 ID。

### Task044 学习笔记（发布校验前端）
- 校验错误字符串的格式约定（`节点「名称」缺少XXX`）使得前端可以正则解析出节点名，转为可点击链接定位画布。
- `lf.focusOn({ coordinate: { x, y } })` 可将画布居中到指定节点。
- 发布流程应先保存（确保最新画布数据已提交），再调用发布 API。

### Task045 学习笔记（BFS 连通性）
- 开始节点必须有出边、结束节点必须有入边，这是基本的流程完整性检查。
- 可选节点在连通性校验中与普通节点相同待遇——仍需可达且能到达结束——"可选"只影响运行时行为。

### Task046 学习笔记（版本快照）
- 快照在发布时一次性生成、永久不可变，是后续发起实例的唯一依据。
- 软配置覆盖层（soft_config_overrides）独立于快照存储，发布后修改不破坏快照不可变性。
- 版本详情 API 返回完整快照数据，前端版本历史可进一步扩展为"查看快照内容"功能。

---
## 🎉 Phase 3 完成！

---

## Phase 4 — 流程实例

### Task047 学习笔记（发起流程实例）
- **快照复制模式**：版本快照是实例的唯一数据源。创建实例时不依赖当前模板节点表，完全从 `flow_versions.nodes_snapshot`/`edges_snapshot`（JSON）复制。这保证了实例与模板的完全解耦。
- **配置三层合并**：快照默认值 → 软覆盖(soft_config_overrides) → 发起覆盖(node_overrides)。优先级递增，后层覆盖前层。这种设计使得模板软修改（不改版本号）和发起时的个性化调整（逐节点覆盖）可以共存。
- **BFS 信号传播**：节点激活使用 BFS 队列而非递归。当节点完成/跳过时，仅直接下游节点的 `arrived_count + 1`。汇合节点（fork/join）需要所有上游都到达（`arrived_count == incoming_count`）才激活。这是经典的 DAG 拓扑传播算法。
- **跳过节点链式传播**：跳过节点不创建 Task，但必须沿原图继续传播信号。BFS 队列天然支持这种链式传播——跳过节点标记 `skipped` 后，其下游入队继续处理。
- **MySQL ENUM→VARCHAR 迁移教训**：这是 Phase 3 已发现的 ENUM 大小写冲突在实例模型上的延续。解决方案一致：全部状态字段改用 `String(20)`。但已建表需要 `ALTER TABLE ... MODIFY COLUMN ... VARCHAR(20)` 手动迁移，SQLAlchemy 不会自动同步 DDL。
- **实例初始状态设计**：实例先以 `status=created` 创建，完成所有节点/连线/配置初始化后再切换为 `running`。中间如果失败则整个事务回滚，不会留下半初始化实例。
- **FlowEngine 职责边界**：flow_engine 仅负责节点激活与信号传播的纯逻辑，不关心配置合并、权限校验等业务规则。instance_service 负责编排整个创建流程。

---

### 前端风格统一 学习笔记

- **参考设计 ≠ 照搬代码**：pages/ 原型是用纯 HTML+内联 style 写的，不能直接复制到 Vue。关键是提取**设计模式**（卡片分区、面包屑导航、页面头布局），用 Vue + Element Plus 重新表达。
- **CSS 工具类 vs 组件内样式**：`common.scss` 中的全局 class（`.page-breadcrumb`、`.card` 等）适合跨页面复用，但**页面特有的样式应该写 scoped**，避免全局污染。本次找到了这个平衡点。
- **Element Plus 原生能力要优先使用**：能用 el-menu/el-card/el-tag 的地方不用自定义 CSS，保持一致性。参考设计的卡片、状态标签都可以映射到 Element Plus 组件 + 自定义 class。

---

### Task050 学习笔记（实例列表 API）

- **SQLAlchemy `aliased()` 踩坑**：同一个查询中多次 JOIN `users` 表（initiator + assignee）时必须用 `aliased(User)`，否则 SQLAlchemy 无法区分两个同名表引用。
- **MySQL `func.if_()` 做条件聚合**：`func.sum(func.if_(condition, 1, 0))` 是 SQLAlchemy 中做条件 COUNT 的标准方式，需配合 `func.lower()` 处理大小写不一致。
- **列表 API 的性能权衡**：每条实例都额外查 node stats + current_assignee 是 N+1 查询。当前数据量小（<100条）可接受，但数据量大后应改用 window function 或 JOIN 子查询一次完成。已在注释中标注"后续可优化为批量查询"。

### Task051 学习笔记（实例详情 API）

- **批量查询比 ORM relationship 更适合聚合场景**：获取节点的人员姓名时，先收集所有 user_id → `WHERE id IN (...)` 一次查完 → Python dict 映射，比逐个访问 relationship 快一个数量级。
- **JSON 字段格式不统一是常态**：`checkers`/`approvers` 在快照中存的是 `[{"user_id": 1}]`（dict 列表），但部分测试数据存的是 `[1, 2]`（int 列表）。由于 MySQL JSON 字段没有 schema 约束，必须在服务层做格式标准化（`_normalize_personnel()`）。
- **大小写处理要一致**：MySQL VARCHAR 列与 Python Enum 迁移后，旧数据可能保留大写值。所有字符串比较都应使用 `.lower()` 或 `func.lower()` 统一处理，不假设任何格式。
- **日志文件污染 Git**：运行中生成的 `logs/app.log.2026-07-13`（8403 行 SQL 日志）被 `git add -A` 误提交。教训：`.gitignore` 必须在首次运行前配置好，且提交前要 `git diff --cached` 检查。

### Task052 学习笔记（实例详情前端页面）

- **参考设计 ≠ 复制代码**：P17 参考页使用纯 HTML + 内联 CSS + onclick，需要转为 Vue 组件化思维。关键是提取**设计模式**（sticky head + base-grid + node-card 折叠 + timeline），用 Vue + Element Plus + common.scss 重新表达。
- **状态驱动的 CSS 优于条件渲染**：节点卡片的 `is-active`/`is-wait`/`is-done` 全由 `node.status` 计算属性驱动，CSS 负责视觉呈现，模板不写任何条件类判断逻辑。这比 `v-if`/`v-else` 切换 DOM 更流畅。
- **ProgressBar 的连接线颜色**：连接线颜色由**前驱节点**状态决定（前驱完成→蓝线，否则灰线），而非当前节点。这个细节容易写反——当前节点进行中不代表进入它的线应该蓝。
- **NodeCard 折叠默认态**：当前节点和已完成节点默认展开（用户想看详情），未开始节点默认折叠（减少视觉噪音）。开始/结束节点也默认展开（节点数少时直接看到全貌）。
- **粘性定位的 z-index 层级**：sticky head 需要 `z-index: 10` 确保滚动时不被节点卡片遮挡，但需要低于顶部导航栏的 z-index（通常 100+）。
- **el-timeline 是 Element Plus 原生组件**：比手写 CSS timeline 简单得多，自动处理竖线、圆点、时间戳布局。只需自定义颜色和内容格式。
- **实例列表的 Tab 懒加载**：用 `watch(activeTab)` 而非 `tab-change` 事件更可靠——v-model 已经处理了状态变更，watch 确保在状态更新后才触发加载逻辑。

### Task053 学习笔记（终止流程后端 API）

- **级联更新的顺序很重要**：先删除文件（物理+记录），再关闭 node → task → check → approval，最后更新 instance。这个顺序确保即使中途出错回滚，也不会有已删除文件但记录还在的不一致状态——因为整个操作在一个事务中。
- **`os.remove()` 需要 try/except**：物理文件可能已在之前的操作中被删除，或磁盘故障导致无法访问。用 except OSError 吞掉错误是合理的——终止流程的核心目标是把业务状态转为 terminated，文件删除是辅助操作。
- **SQLAlchemy `sql_update().values()` vs ORM 对象赋值**：对于批量更新（如关闭同 instance 的所有 node），SQL UPDATE 语句比逐个 ORM 对象赋值的 N+1 模式高效得多。但对于单个 FlowInstance 的更新，直接修改 ORM 对象属性更简洁。
- **终态判断要精准**：node 的终态是 finished/terminated/skipped（3个），task 的终态是 completed/terminated（2个），check/approval 只关闭 pending 状态。这些判断条件不能一刀切用同一个列表——不同模型有不同的生命周期。
- **内联 import 是不良实践**：最初在函数内写了 `from sqlalchemy import delete as sql_delete` 和 `import os`，代码审查时发现并移到了文件顶部。函数内 import 虽然功能正常，但让依赖关系不透明，且每次调用都会重新 import（虽然 Python 有缓存）。
- **操作日志的 detail 字段设计**：除了 description 外，detail JSON 字段存储结构化数据（如 `{"reason": "...", "instance_name": "..."}`）。这为后续的审计查询（如"按终止原因统计"）提供了 SQL 可查的结构化字段。

### Task054 学习笔记（终止流程前端确认弹窗）

- **el-dialog 的安全配置**：`close-on-click-modal: false` + `close-on-press-escape: false` 确保危险操作不会被误触关闭。这是 D06 参考设计中"点击遮罩不可关闭"的 Element Plus 实现方式。
- **v-model 双向绑定弹窗可见性**：`computed({ get, set })` 将 `modelValue` prop 转为双向绑定，父组件通过 `v-model="showDialog"` 控制，子组件内部关闭也通过 `visible.value = false` 触发。这保持了 Vue 3 的 v-model 惯用模式。
- **terminated 事件优于直接在弹窗内刷新**：弹窗 emit `terminated` 事件，由父组件 InstanceDetail 决定如何响应（调用 `fetchDetail()` 刷新）。这保持了"数据流向下、事件流向上"的单向数据流原则。
- **`v-if` vs `v-show` 在弹窗场景**：用 `v-if="detail"` 确保弹窗仅在数据就绪后挂载，避免空 instanceId 传入导致的无效 API 调用。`v-show` 会提前渲染 DOM，不适合依赖异步数据的弹窗。

### Task055 学习笔记（紧急换人后端 API）

- **集合差集算法是最优解**：对比新旧人员列表用 `set` 差集（`old - new = removed`, `new - old = added`），时间复杂度 O(n)。避免了"全删重建"的粗暴模式，也避免了逐条比对的高复杂度。
- **"仅操作差集"原则**：已通过(passed/approved)的记录完全不动，只终止被移除的 pending 记录、创建新增的 pending 记录。这保证了已完成的校验/审批不受换人影响。
- **assignee 变更与 Task 联动**：当节点处于 running/arrived 状态时，换负责人必须同步更新 Task.assignee_id，否则任务列表会指向旧负责人。这个联动很容易遗漏——在代码 review 时才补上的。
- **所有字段选填的设计**：`ChangePersonnelRequest` 的三个字段全是 optional，因为换人可能只换其中一个角色。空 body 不算错误（返回"无需变更"），但也不会产生副作用。

### Task056 学习笔记（优先级修改）

- **Pydantic pattern 校验比手动 if-else 更可靠**：`Field(pattern="^(urgent|high|normal|low)$")` 在请求体解析阶段就拦截非法值，不需要在 service 层再写校验逻辑。
- **PriorityEditDialog 的 v-model 同步**：用 `computed({ get, set })` 将父组件的 `modelValue` prop 转为双向绑定，保持 Vue 3 惯用模式的同时确保弹窗内部也能关闭自己。
- **优先级变更不需要幂等保护**：与终止不同（不可逆），优先级可以反复修改。后端只需校验 running 状态和发起人权限，不检查新旧值是否相同——如果相同也不报错，只是不记录有意义的变化。
- **Phase 4 完成总结**：10 个 Task 覆盖了流程实例的完整生命周期——创建（047/048/049）、查询（050/051/052）、终止（053/054）、应急管理（055/056）。数据流模式已经稳定：FastAPI endpoint → service 函数（事务内完成全部 DB 操作） → commit → 返回。

---

## 后续功能说明

Task056 之后的开发未按 Task 逐条记录学习笔记，完整功能变更见 [`CHANGELOG.md`](CHANGELOG.md)。关键里程碑：

- **Redis + arq 任务队列**：PDF 转换异步化，arq 比 Celery 更轻量（零额外 Broker 依赖）
- **WebSocket + Redis Pub/Sub**：`ws_bridge.py` 实现多 Worker 进程间广播，解决单进程 WebSocket 限制
- **方案（Proposal）**：第二模板类型，工作节点审批后直接完成（跳过终审）
- **补交文件**：已完成实例支持追加文件，不影响流程状态
- **超期预警**：独立页面展示所有超期的任务/校验/审批/批准项
- **全量审计**：38 项问题修复（6 严重 + 9 高 + 14 中 + 9 低），详见 `AUDIT_FIX_LOG.md`
