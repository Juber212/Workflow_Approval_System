# 企业流程审批系统 — 全栈代码审查报告

- **日期**：2026-08-03
- **方式**：10 个子代理并行分模块扫描 + 主对话逐条对抗验证
- **范围**：后端 `backend/app` 全部（117 py）+ 前端 `frontend/src` 全部（~95 vue/ts）+ 测试 + 部署配置
- **维度**：隐藏 Bug / 架构合理性 / 代码风格可维护性 / 安全性能 / 业务规则一致性 / 前后端契约 / 测试质量 / 部署安全

---

## 一、总体结论

**结论：当前状态「可运行、不可直接上线」。** 架构骨架、鉴权基础设施、并发防护思路、前后端契约对齐度都属上乘，正常路径的业务正确性高；但存在 **7 个 Critical 级问题**（3 个写/篡改/伪造漏洞、1 个并发死锁、1 个流程卡死、1 个死循环、1 个构建阻断），以及一批并发/数据一致性隐患。多轮审计宣称的「0 bug」与测试真实性不成立（见第五节）。

> **内网部署校准（2026-08-03 用户确认）**：本项目部署于公司内网，产品确认「项目实例详情、全系统待办/超期」**全员可见**——数据可见性非漏洞。本次校准：原 C1（实例详情无鉴权）移出 Critical，改为产品确认项（见下方标注）；越权「写/篡改/伪造」类（C2 模板下载接口无归属校验、C3 穿越写盘、C4 签名伪造）**保留为必须修复**——「看得见」不等于「改得动/盖得了章/绕过入口下载」。

**亮点（做得好的）**：
- 统一异常体系（AppException + ErrorCode + 全局处理器），HTTP 状态与业务码映射一致
- fork/join 传播的 `FOR UPDATE` 三步原子操作、READ COMMITTED 隔离级别、savepoint 隔离通知
- 文件删除「先 DB 后物理文件」、补交 DB 失败清理物理文件、PDF post-commit 写入 + 原子替换
- 批量查询普遍避免 N+1；列表/详情接口字段对齐度高，无 camelCase 蒙混
- 前端路由守卫、拦截器去重、生命周期清理大体到位；中文注释有业务价值，整体「像人写的」

---

## 二、基线更正（本次审查最重要的前置发现）

| 项目 | 声称 | 实测 | 说明 |
|------|------|------|------|
| 后端测试 | 190 条 0 bug | ✅ **192 passed** | 含本次会话新增 2 条；但有 7 个 SAWarning（non-checked-in connection，集成测试资源泄漏） |
| 前端类型检查 | vue-tsc 0 errors | ❌ **57 个 TS 错误** | 根因：`tsconfig.json` 为 references-only，`vue-tsc --noEmit` 不检查任何文件（假阳性）；`npm run build`（`vue-tsc -b`）**当前必失败** |
| 测试可信度 | 全链路端到端 | ❌ **核心链路被 mock / 手工改状态** | 见第五节 |

> 教训：`vue-tsc --noEmit` 在此项目无效，须用 `vue-tsc -b`（或 `npm run build`）验证类型。

---

## 三、Critical（上线前必须修复）

### 产品确认项（原 C1）— 实例详情全员可见
- **位置**：`backend/app/api/instances.py:196-207` → `backend/app/services/instance/detail.py:25-54`
- **结论**：2026-08-03 用户确认此为**产品需求**（公司内网部署，全员可看）。`get_instance_detail` 无组织/角色校验属有意设计，**不再修复**，但建议在 API 文档标注「实例详情全员可见」以免后续误当漏洞处理。

### C1. 模板 ZIP 下载接口无归属校验 — 前端入口受限 ≠ 后端安全
- **位置**：`backend/app/api/templates.py:463-505` → `backend/app/services/category_service.py:258-320`
- **问题**：前端「文件模板下载」入口在任务处理界面（负责人可见），但后端 `GET /templates/{template_id}/download-zip` 接口本身**零校验**——任何登录用户直接构造 URL 即可下载任意所模板并填充任意实例数据，UI 限制是软限制不是安全边界。
- **产品预期**：用户确认模板「仅在任务处理界面可见/下载」（限参与者）——与修复方向一致，需后端落实。
- **验证**：✅ 已读源码确认。对比 `tasks.py:244` 的 `download_file` 有同组织校验。

### C2. `folder_name` 路径穿越 → 任意文件写入
- **位置**：`backend/app/services/file_service.py:102-105`（入口 `api/tasks.py:221`）
- **问题**：`folder_name` 来自前端参数，**既未清洗、也未校验是否属于节点 `file_folders` 配置**，直接拼入存储路径。`os.path.join` 不归一化 `..`，`_unique_stored_name` 只清洗文件名不覆盖目录段。传 `folder_name="../../.."` 可把文件写到 `STORAGE_ROOT` 之外任意位置。
- **影响**：认证用户可覆盖配置文件、制造 webshell，属高危写漏洞。
- **验证**：✅ 已读源码确认（B4 与 S10 双代理独立确认）。`supplement.py` 补交上传不受影响（uuid 存储名 + folder_name 不拼路径）。

### C3. 签名 `file_id` 未校验归属 → 跨实例 PDF 篡改
- **位置**：`backend/app/services/task_service.py:420-436`、`check_service.py:293-303`、`approval_service.py:429-439`、`endorsement_service.py:297-307`
- **问题**：`data.signatures[].file_id` 直接透传给 `create_signature_records`，不校验该 file 是否属于当前 task/node/instance/round。攻击者可枚举 file_id 把自己的签名盖到其他实例/其他组织的 PDF 上。
- **影响**：破坏归档文件真实性（防伪依赖签名）。
- **验证**：✅ 已读源码确认。

### C4. 双审批人同时通过 → InnoDB ABBA 死锁
- **位置**：`backend/app/services/approval_service.py:388-405`（`approve()`），同模式在 `check_service.py:267-283`、`endorsement_service.py:266`
- **问题**：先 `FOR UPDATE` 锁自己的审批行，再锁节点其他 PENDING 行。两个审批人并发时 TxA 持 A1 等 A2、TxB 持 A2 等 A1 → 死锁，InnoDB 随机回滚一方 → 用户见 500。
- **关键**：**READ COMMITTED 不能解决此问题**——它只防脏读，锁序不一致仍是死锁源。
- **验证**：✅ 已读源码确认（B3 与 B4 双代理独立确认）。
- **处置（2026-08-03）**：**已撤销修复**。用户确认前端已改为单选（单审批人/校验人），多人并发场景在实际业务中不可达，死锁不会触发；代码与相关测试已回滚，保留原「先锁自己+锁其他」逻辑。

### C5. fork/join + 驳回 → 汇合节点永久卡死
- **位置**：`backend/app/services/approval_service.py:681-713`（终审总驳回）、`:823-851`（中间节点驳回）
- **问题**：驳回到**分支内**节点时，`_get_downstream_nodes_by_edges`（`:44-90`，全路径 BFS）不会包含兄弟分支节点——兄弟分支保持 FINISHED 不再传播；汇合节点 `arrived_count` 被重置为 0，目标分支重跑只加 1，永远达不到 `incoming_count` → 流程悬挂，无看门狗。
- **验证**：✅ 已读 BFS 实现与驳回逻辑确认场景成立。

### C6. must_change_password 用户无限重定向死循环
- **位置**：`frontend/src/router/guards.ts:45-46` 与 `:73-75`
- **问题**：守卫第 2 步把「已登录访问 /login」弹回 `/dashboard`；第 4.5 步又把 must_change_password 用户从受保护页弹回 `/login`。刷新场景：`/login → /dashboard → /login → …` 无限循环，Vue Router 报 "Infinite redirect" 并中断导航，该用户应用完全不可用。
- **验证**：✅ 已读源码确认死循环路径成立。

### C7. 前端构建阻断：57 个 TS 类型错误
- **位置**：全前端，主要集中 `views/flows/FlowDesigner.vue`（graphData 类型 unknown）、4 个详情页（`DetailNodeInfo[]` 类型不匹配）、`FlowManagement.vue`/`OrgHome.vue`/`ProposalManagement.vue`（`UserSearchItem` 缺 `user_id`）、`AppLayout.vue:238`（访问不存在的 `signature_image`）、大量未使用变量
- **问题**：`npm run build` = `vue-tsc -b && vite build`，`vue-tsc -b` 报 57 个错误 → **构建必然失败**，无法产出生产包。
- **验证**：✅ 亲自运行 `npx vue-tsc -b --force` 实测 57 个 error。
- **附带**：`AppLayout.vue:238` 的类型错误同时暴露了逻辑 bug——store 里根本没有 `signature_image`，`has_signature` 恒为 false（签名状态展示错误）。

---

## 四、Important（建议尽快修复）

### 4.1 越权 / 数据暴露（后端）
| ID | 问题 | 位置 |
|----|------|------|
| I01 | 设计器单节点 CRUD 未校验节点归属模板，manager 可跨模板改他人节点 | `designer_service.py:281-311`（`update_node`/`delete_node` 只按 node_id 查）✅已确认 |
| I02 | 任务维度模板下载不校验 doc/category 归属，可跨组织下载 | `api/tasks.py:401-505` |
| I03 | `/notifications/overdue` 与 `/dashboard` 全系统待办/超期全员可见 —— **已确认为产品需求（内网部署），无需修复**，建议在 API 文档标注 | `api/notifications.py:71-78`、`api/dashboard.py` |
| I04 | 模板文件模板列表接口无组织隔离 | `api/templates.py:215-328` |
| I05 | WebSocket 鉴权不完整：不查黑名单/is_active，登出/禁用后连接存活 | `api/ws.py:54-65` ✅已确认 |
| I06 | JWT 内嵌 roles 无条件信任，角色降级/升级不生效至过期（8h） | `api/deps.py:67-76` ✅已确认 |
| I07 | 改密/重置密码不吊销既有 token | `api/auth.py:117-148`、`user_service.py:218-227` |

### 4.2 流程状态 / 数据一致性（后端）
| ID | 问题 | 位置 |
|----|------|------|
| I08 | `clear_related` 跨实例误删通知（无 instance_id 维度） | `notification_service.py:227-247` |
| I09 | 换负责人不覆盖 `waiting_*` 阶段 Task，驳回后退回旧负责人 | `instance/change.py:195-206` |
| I10 | 校验阶段加校验人 → 生成 `task_id=None` 坏 CheckRecord | `instance/change.py:108-115` |
| I11 | 优先级排序的 deadline 子查询恒为 NULL，「最近截止优先」失效 | `instance/list.py:91-101` |
| I12 | 补交文件未强制文件夹必填/数量/白名单校验 | `instance/supplement.py:36,154` ✅已确认 |
| I13 | 无负责人节点激活失败后「紧急换人」不触发重新激活，永久卡死 | `flow_engine.py:166-172` + `change.py` |
| I14 | deadline 设为 00:00，截止日当天 00:01 起即显逾期、剩余天数 -1 | `instance/create.py:241-244`、`_helpers.py:26-29` |
| I15 | 难度4 未强制配置批准人，未配时静默跳过批准环节 | `approval_service.py:563` ✅已确认 |
| I16 | all_approve 聚合与 `signature_applied` 批量更新未按 task_id/round 限定 | `approval_service.py:500-507,536-538` |
| I17 | 被 TERMINATED 的校验/审批/批准人残留待办通知（未 clear_related） | `check_service.py:470-477`、`approval_service.py:489-498,772-777,882-887` |
| I18 | endorse 旧兼容分支 `file_id=None` 签名永不写入 PDF | `endorsement_service.py:308-321` |
| I19 | 「多审批人自动偏移」仅在死代码 `apply_signatures_to_node_pdfs` 实现，活跃路径同坐标会互相覆盖 | `pdf_signature.py:170-317` vs `382-408` |
| I20 | `convert_all_files_job` 无限自重新入队无重试上限 | `pdf_queue.py:163-171` |

### 4.3 模型 / Schema / 配置（后端）
| ID | 问题 | 位置 |
|----|------|------|
| I21 | 模型层零索引声明 + `UserRole` 缺外键 → Schema 漂移；`autogenerate` 会误生成 DROP；测试库与生产库不一致 | `models/*.py`、`user_role.py` |
| I22 | `create_instance` 响应缺 `difficulty`，恒返回 "1" | `instance/create.py:272-288` ✅已确认 |
| I23 | 不校验审批人/校验人/负责人 ID 存在 → 脏 ID 触发 FK 500 | `instance/create.py:118-190`、`validation_service.py:44-55` |
| I24 | bcrypt 72 字节截断 + 登录密码无最大长度 | `core/security.py:18-25`、`schemas/auth.py` |
| I25 | 缺失 Authorization 头返回 422 而非 401 | `api/deps.py:38` ✅已确认 |
| I26 | 无条件信任 X-Forwarded-For，可绕过登录限流 + 滑动窗口无 key 上限（内存 DoS） | `core/rate_limit.py:120-127` ✅已确认 |
| I27 | 黑名单 Redis 客户端无 socket 超时，Redis 故障时请求挂死 | `core/redis.py:61-65` ✅已确认 |
| I28 | DB 密码未 URL 编码，含特殊字符破坏连接串 | `core/config.py:101-105` ✅已确认 |
| I29 | 中间件注册顺序与注释不符（限流被包在内侧），且 must_change_password 逐请求查库 | `main.py:88-94`、`auth_middleware.py:66-79` ✅已确认 |
| I30 | 连接池 40/进程 × 多 worker 超 MySQL max_connections | `core/database.py:10-18` |

### 4.4 测试质量（专项，详见第五节）
- I31 假全链路测试 / 核心逻辑被 mock / 关键路径零覆盖 / 3 个永远通过的测试 / 测试凭据硬编码入库 / 测试数量文档漂移

### 4.5 前端
| ID | 问题 | 位置 |
|----|------|------|
| I32 | WebSocket 卸载后 onclose 异步重连 → 孤儿连接 + 无限重连循环 | `api/notification.ts:180-197`（F7/F6 双确认） |
| I33 | 方案「发起人」搜索失效：`searchUsers` 传对象当 keyword + option 用不存在的 `user_id` | `proposals/ProposalManagement.vue:56-59,292`（TS 错误已实证） |
| I34 | 四详情页「前往上传签名」跳转 `tab=signature` 无人监听 → 死链 | `TaskDetail.vue:553` 等 + `profile/index.vue` |
| I35 | Dashboard「我的待办」总数虚标（后端每组最多 8 条，真实计数字段未用） | `dashboard/index.vue:121-122`、`dashboard_service.py:570` |
| I36 | 超期预警页汇总全系统数据，点开他人记录 → 详情 403 + 误导性空态 | `overdue/OverdueWarning.vue:43-47` + 详情页 |
| I37 | 错误处理反模式：拦截器不携带 `.response`，全站 `err?.response?.data?.message`（30+ 处）恒命中通用文案 + 双重弹窗；`TaskDetail.vue:539,648` 任何失败都误报「网络连接异常」 | `api/request.ts:66-92` 等（F6/F7 双确认） |
| I38 | axios 实例类型未增强，`res.data` 实为 any，契约「注释级」非「编译级」 | `api/request.ts:61-65` |
| I39 | api 层返回值约定不统一（`return res` vs `return res.data`） | `task.ts:135` 等 |
| I40 | UserSelector 带预填值时「本所成员浏览」失效 | `components/UserSelector.vue:87-107` ✅已确认（F8/F7 双确认） |
| I41 | 截止日期前后端语义不一致（off-by-one）+ 级联不跳节假日 | `designer/PropertyPanel.vue:651-728` vs `api/utils.py:83` |
| I42 | 发起弹窗模板初始勾选依赖 `category.documents` 可选字段，可能缺分类内模板 | `FlowDesigner.vue:381-401` |
| I43 | OrgHome/OrgProposalHome 未 watch `route.params.orgId`，跨组织切换不刷新 | `OrgHome.vue` 等 |

---

## 五、测试质量专项（S10）

**结论：测试「数量」真实但「可信度」被显著高估。** CLAUDE.md 的「190 条测试、0 业务逻辑 bug」对以下区域不成立。

### 5.1 结构性失真
- **T1 假全链路**：`tests/mysql/test_full_flow.py:170-280` 名为「全链路端到端」，实际手工设状态 + 断言自己（注释自述「改为直接在 DB 层面模拟」），`submit_task`/`pass_check`/`approve` 均未调用。✅已确认
- **T2 核心逻辑被 mock**：`tests/mysql/test_service_flows.py:31-54` 统一 mock 了 `propagate_from_node`（return `[]`）、`apply_signatures_to_files`、通知、甚至 `os.path.exists`。fork/join 传播、PDF 签名写入、终止删文件**均无真实断言**。✅已确认
- **T3 永远通过的测试**：`test_edge_cases.py:159-170`（`except IntegrityError: pass`）、`test_service_flows.py:394-439`（`if result["all_approved"]:` 包裹断言）。✅已确认

### 5.2 覆盖缺口（零测试）
fork/join 真实汇合、terminate/reject 物理文件删除、换人成功路径、补交文件、JWT 黑名单 + must_change_password 中间件、超期预警口径 `compute_deadline_info`。

### 5.3 其他
- **T4** 测试库密码硬编码入库：`tests/mysql/conftest.py:17` `root:REDACTED`（已泄露进 git）✅已确认
- **T5** 集成测试全 mock DB + `sqlite_session`/`mock_db_factory` 死 fixture（从未被使用）
- **T6** 文档漂移：实测 145 unit + 28 integration + 19 mysql，CLAUDE.md 写 158+10+19
- **T7** SAWarning（non-checked-in connection）：基线运行实测出现（test_notification_api），集成测试资源释放缺陷

---

## 六、Minor 与代码风格问题（P2 处理）

### 6.1 死代码（建议清理）
- `frontend/src/views/flows/components/NodeOverridePanel.vue` — 整文件 400 行，全局无 import，未挂载
- `FlowDesigner.vue:527` `systemNodeDbIds` 只赋值从不读取；`FlowCanvas.vue:68` `workNodeCounter` 未使用
- 后端 `pdf_signature.py:170-317` `apply_signatures_to_node_pdfs` 无调用点（且注释承诺的自动偏移只在此实现）
- 后端 `instance_service.py` 与 `instance/__init__.py` 内容完全相同（兼容 shim）
- `rate_limit.py:109-110` `if payload is None` 死代码（payload 已非 None）

### 6.2 重复代码（约 600+ 行可收敛）
- 4 个详情页（TaskDetail 831 行等）：摘要条、节点信息 8 字段网格、文件行渲染、历史文件分组、PDF 列表、签批检查整套 SCSS 逐字重复 → 建议抽共享组件/composable
- `OrgHome.vue` / `FlowManagement.vue` 表格约 200 行重复 → 抽 `InstanceTable` 组件
- `PropertyPanel.vue:198-305` 与 `PresetEditor.vue:73-139` 文件夹卡片编辑器 → 抽 `FolderConfigEditor.vue`
- `FlowDesigner.vue:856-880` 与 `918-942` handleSave/handleLaunch 序列化逻辑 → 抽 `buildDesignPayload(lf)`
- `deadlineRowClass` 在 4 处重复定义，`utils/format.ts:23` 已有工具函数
- 后端四详情接口（task/check/approval/endorsement）文件列表/用户查询/进度/签名默认值大面积拷贝

### 6.3 一致性小问题（节选）
- 枚举字符串在服务层部分硬编码（`dashboard_service.py:59-119` 等），建议统一枚举引用
- `Signature.role_type` 注释缺 `endorser`；JSON 字段类型标注 dict vs list 不一致
- 响应 schema 大量 `list[dict]` 裸类型（无契约可读性）
- `roleLabel` 文案「管理员」vs「系统管理员」不一致
- 前端 3 套 URL 拼接来源并存（硬编码 /api/v1、VITE_API_BASE_URL、API_BASE）
- `PriorityEditDialog` newPriority 不随 prop 刷新；`TerminateDialog` reason 关闭后不清空
- `SignaturePreviewDialog.vue` 遗留 5 处 console.log 调试日志 + 过期注释
- 签名图片接口 `GET /users/{id}/signature-image` 任意用户可枚举下载
- 配置校验 `configs.py:46-55` 拒绝 `-1`（最后页），与 `config.py:58` 默认 -1 矛盾
- `get_task_detail` GET 打开详情即改 PENDING→PROCESSING（GET 带写副作用）
- 超期口径依赖服务器本地时区

---

## 七、代码风格评估（像不像人写）

**整体非常像有经验的工程师维护的真实项目，而非 AI 样板。** 证据：
- 有历史包袱的自然痕迹（`get_db` 注释里自我承认的「双重 commit」、兼容 shim、legacy 数据兜底、注释与实现的微小漂移）
- 中文注释能表达业务意图（「先 DB 后物理文件，避免回滚后文件丢失」「兼容历史多选数据」），非机械翻译
- 防御性细节真实合理（FOR UPDATE 锁、savepoint、uuid 存储名、魔数校验、is_safe_path）
- 命名语义化（`showErrorOnce`、`_isRedirecting`、`refreshNotifyCounts`），无无意义变量

**但存在 AI 批量生成的残留痕迹**：
- 前端 4 详情页、后端 4 详情接口的复制粘贴式重复（AI 加速期的典型产物）
- 死代码未清理（NodeOverridePanel 整组件、无调用点的签名偏移函数）
- 注释与实现漂移（中间件顺序注释、`folderNameConflict` 注释、ZIP 下载 category_id 注释）

---

## 八、修复计划索引

详见 `2026-08-03-fix-plan.md`。分三档：
- **P0（上线阻断）**：C1-C8 + 直接相关的越权/流程卡死项
- **P1（尽快）**：越权收敛、状态一致性、测试补真、前端功能 bug
- **P2（重构/清理）**：重复代码、死代码、模型对账、文档同步
