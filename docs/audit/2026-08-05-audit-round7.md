# 第七轮全栈审查报告（2026-08-05）

> 方式：7 代理并行扫描 230+ 文件（后端 130 py + 前端 100 vue/ts），维度：正确性/安全/性能/可用性/死代码
> 结果：**0 致命 / 2 高危 / 34 中危 / 35 低危**（跨代理去重后）
> 状态：报告已确认，按严重度修复中
>
> **产品口径确认（2026-08-05）**：项目/方案列表与详情**全员可见**（所有登录用户可查看任意组织数据，与组织卡片页列出全部组织一致，同待办/超期规则 19）。据此 H2 非越权漏洞（改为统一口径）、M1 确认非漏洞。

---

## 一、高危（2 项，优先修复）

### H1 发起模式把整份设计写回共享模板，破坏「快照解耦」；checker/approver 改动未进 node_overrides
- **文件**: `frontend/src/views/flows/FlowDesigner.vue:786`（handleLaunch 先 saveDesign 写回模板）、`:790-814`（override 只收集 deadline/assignee_id/endorser_id）
- **问题**: 发起实例时先把画布设计保存回模板，再创建实例。一次发起永久改动组织级共享模板，两个用户并发发起会互相覆盖；且校验人/审批人调整只能靠写回模板生效，与业务规则 3「发起后生成配置快照，与模板解耦」直接冲突。
- **修复**: handleLaunch 把 checkers/approvers 一并收集进 node_overrides（比对模板值有变化才传），去掉发起流程里的 saveDesign（或仅显式选择时保存）。

### H2 resolve_org_scope 默认限本组织，与产品「全员可见」规则矛盾（口径不一致）
- **文件**: `backend/app/api/deps.py:139-146`；调用点 `proposals.py:43` / `instances.py:99` / `templates.py:71`
- **问题**: 函数注释「非管理员不传 org_id 时默认限本组织」，但产品确认项目列表**全员可见**（组织卡片页列出全部组织，点卡片可看该所项目）。现状：非管理员默认只看到本所项目（与产品规则矛盾），显式传其他所 org_id 又能看到（绕过默认限制）。口径不一致。
- **修复**: `resolve_org_scope` 移除「默认限本组织」逻辑，`organization_id` 改为纯筛选参数（透传），同步更新函数注释；三个调用点不受影响。

---

## 二、中危（34 项，按主题分组）

### 安全/越权类（11 项）
| # | 问题 | 文件 |
|---|------|------|
| M1 | ~~实例详情接口无组织/角色鉴权~~ **产品确认全员可见，非漏洞**，仅补注释说明口径 | `api/instances.py:196-207`、`services/instance/detail.py:25-50` |
| M2 | WS 认证遗漏密码版本号校验，改密/重置后旧 token 仍可建立并维持 WS 连接（凭据吊销侧信道） | `api/ws.py:59-67`、`core/token_blacklist.py:128-129` |
| M3 | 签名图片上传「解压炸弹」：尺寸限制前全量解码，构造高分辨率小图可 OOM 拒服 | `api/auth.py:288-293` |
| M4 | 组织 ID 沿用 JWT 快照，改组织后旧权限最长保留至 token 过期（≤8h 跨所窗口） | `api/deps.py:131-146` |
| M5 | 模板包 ZIP 条目名未清洗原始文件名 → Zip Slip 路径穿越 | `services/category_service.py:314` |
| M6 | 两个上传端点先全量读入内存再校验大小 → 单请求 OOM（无请求体上限） | `api/templates.py:661`、`api/auth.py:253` |
| M7 | 实例文件下载仅同组织校验，跨所审批人/负责人被 403，与「跨所协作」规则冲突 | `api/tasks.py:259-264` |
| M8 | change_personnel 无新人员 ID 存在性校验 → 非法 ID 触发外键 500/脏数据 | `services/instance/change.py:158-245` |
| M9 | change_personnel 把审批人/校验人置空 → 节点永久卡死（waiting_approval/waiting_check） | `services/instance/change.py:159-245` |
| M10 | ensure_proposal_template 的 FOR UPDATE 在 READ COMMITTED 下无效，并发重复建方案默认模板 | `services/proposal_service.py:43-50` |
| M11 | create_proposal 无人员存在性校验 + approvers 可空 → 流程中途 FK 500 / 卡死 | `services/proposal_service.py:93-215` |

### 正确性/数据类（11 项）
| # | 问题 | 文件 |
|---|------|------|
| M12 | 方案工作节点审批通过路径丢签名 ID，审批人签名永不写入 PDF | `services/approval_service.py:577-584` |
| M13 | approve 无条件置 signature_applied=True，未签名也显示已签名（与批准侧不一致） | `services/approval_service.py:552-563` |
| M14 | 实例名称无唯一约束 + permanent_delete 对共享目录 rmtree → 同名实例误删文件 | `services/instance/delete.py:84-93` |
| M15 | dashboard 用 template_id 集合判方案，与列表 template_type 快照口径不一致，模板删除后方案误算为项目 | `services/dashboard_service.py:45-52` |
| M16 | 设计器单节点/连线 CRUD 不触发发布校验 → 可保存并据此发起非法模板卡死实例 | `services/designer_service.py:334-395` |
| M17 | 发起模式新增节点（db_id=null）截止日期覆盖丢失 + PropertyPanel 对 null 算 NaN | `FlowDesigner.vue:794`、`PropertyPanel.vue:545` |
| M18 | TemplateTable 每页条数选择器无效（只绑 @change 未绑 @size-change） | `flows/components/TemplateTable.vue:43-51` |
| M19 | 首页「本月归档」卡片跳转未做本月筛选（与已归档同路由） | `views/dashboard/index.vue:43-47` |
| M20 | OrgHome 发起项目弹窗模板搜索框只绑 v-model 无事件，搜索不生效 | `flows/OrgHome.vue:20` |
| M21 | 个人中心 9 个列表「搜索/筛选后不重置页码」，深页码下筛选空结果 | `views/profile/index.vue:394-402` |
| M22 | 3 个管理弹窗提交失败仍提前关闭 → 用户输入丢失 | `OrgFormDialog.vue:75`、`UserFormDialog.vue:179`、`ResetPasswordDialog.vue:46` |

### 并发/性能类（8 项）
| # | 问题 | 文件 |
|---|------|------|
| M23 | terminate 与 approve/endorse/pass_check 完成分支未在同一把实例行锁下，已终止实例可能被改写为已完成 | `terminate.py:40`、`approval_service.py:569-583` |
| M24 | pass_check/endorse 未对 InstanceNode 行加锁（P1-19 只覆盖 approve/reject），与紧急换人存在 TOCTOU | `check_service.py:293`、`endorsement_service.py:328` |
| M25 | 同一 PDF 并发签名临时文件碰撞（固定 .tmp 路径无锁）→ 丢签名/损坏 | `services/pdf_signature.py:283,581` |
| M26 | 模板 .doc 转换超时不杀子进程 → soffice 进程泄漏 | `api/templates.py:183-205`、`pdf_converter.py:103-108` |
| M27 | ARQ job_timeout=120s 与转换「重试2×60s+sleep」冲突，慢转换第二次重试被强杀 | `worker.py:35`、`pdf_converter.py:20` |
| M28 | 系统配置 3 个开关（max_file_size_mb/allowed_file_extensions/default_time_limit_days）无任何消费方，改了零效果 | `api/configs.py:74-80` |
| M29 | 详情页公共加载无并发保护，快速切换记录时旧响应覆盖新数据 | `composables/useDetailLoad.ts:25-48` |
| M30 | NotificationBell 双实例 → 每次进出 Dashboard 触发 WS 断连/重连 | `AppLayout.vue:26`、`views/dashboard/index.vue:10` |
| M31 | 跨组织切换列表请求竞态，旧组织响应覆盖新组织数据 | `proposals/OrgProposalHome.vue:185-194` |
| M32 | DocTemplateManagement 串行逐个加载包详情，包多时明显变慢 | `admin/DocTemplateManagement.vue:247-261` |

### 前端健壮性（2 项）
| # | 问题 | 文件 |
|---|------|------|
| M33 | 签名上传成功回调对 userInfoDetail 非空断言，存在空引用崩溃窗口 | `layouts/AppLayout.vue:311` |
| M34 | 设计器编辑模式缺前端角色守卫（依赖后端兜底，越权面暴露） | `views/flows/FlowDesigner.vue` |

---

## 三、低危（35 项，去重后约 30 项，摘要）

- **后端死代码/一致性**：`core/storage.py` 整模块 5 函数零引用（M 路径语义与实际不一致）；`rate_limit.py:150` 不可达死分支；`enums.py` 两个 REJECTED 枚举值未用 + `ACTIVE_NODE_STATUSES` 含 3 个无效状态；`pdf_signature_offset` 配置加载但从未使用（多签名 X 偏移缺失）；`pdf_converter` gif/webp 分支不可达；`dashboard_service` 未用导入 MyPendingItem
- **后端健壮性**：`DEFAULT_USER_PASSWORD` 无启动非空守卫（重置密码可置空密码锁死用户）；签名图片路径解析依赖进程 CWD（双前缀回退脆弱）；多 worker 部署限流按进程翻倍稀释；通知 WS 推送先于 DB 提交（回滚时幽灵通知）；`get_flow_trends` 年度对 NULL initiated_at 无防护会 500
- **后端性能**：reject 驳回下游节点文件逐节点查询 N+1
- **前端健壮性**：`clearToken` 动态 import 异步清空计数竞态；`decodeURIComponent(raw)` 非法 % 序列抛 URIError 下载静默中断；上传复用全局 30s 超时大文件慢网必失败；签名上传回调空值断言；`wsConnected` 返回值无消费方；SidebarNav 重复 clearAll；个人中心 onMounted 预拉 3 个隐藏 Tab 列表；角标计数被筛选 total 覆盖后周期性跳变；DocTemplate 上传后 fetchAll 未 await；OverdueWarning 裸用 request.get 绕过 API 层；`_AVAILABLE_VARIABLES` 漏列 2 个已支持变量；新建模板连续保存 DB ID 抖动；NodeCard 已完成节点末阶段显示为进行中；OperationTimeline 折叠状态不随 isProposal 重置；4 处下载逻辑重复未抽公共助手；多处过时/错位注释

---

## 四、已排除/无需修

- 各代理均确认：无 v-html/XSS 面、token 存储与 401 跳转闭环无死循环、路由守卫权限正确、WS 首条消息鉴权完整、模型索引与迁移逐一对账、schema 未暴露密码 hash、文件/签名/模板下载的历史 P0 修复（Zip Slip 主入口、签名 file_id 越权、folder_name 穿越）均已在位。

---

## 五、修复顺序建议

1. **H1/H2**（高危，先修）
2. **安全类 M1-M11**（越权/拒绝服务优先）
3. **正确性 M12-M22**（签名链路、卡死、数据口径）
4. **并发 M23-M32**（锁覆盖、竞态）
5. **低危按需**（死代码清理 + 健壮性补丁）

每项修复后跑全量测试（296 mock + 27 MySQL）回归。
