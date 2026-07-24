# 审计修复日志

> 全量审计日期：2026-07-24
> 审计范围：后端 21 Service + 19 API + 中间件 + 前端关键路径
> 发现问题：38 项（严重 6 + 高 9 + 中 14 + 低 9），跳过 #4 IDOR，修复 37 项

---

## Phase 1 — 🔴 严重 Bug 修复（2026-07-24）

### #1: endorsement_service.py — signature_path → signature_image（BUG）
- **文件**: `backend/app/services/endorsement_service.py:171`
- **严重程度**: 🔴 严重
- **改前**: `endorser_user.signature_path`（User 模型无此字段）
- **改后**: `endorser_user.signature_image`
- **影响**: 批准详情页签名图片 URL 永远返回 None，签名预览功能不可用
- **验证**: pytest + 手动测试

### #2: endorsement_service.py — storage_path → file_path（BUG）
- **文件**: `backend/app/services/endorsement_service.py:432`
- **严重程度**: 🔴 严重
- **改前**: `f.storage_path`（File 模型无此字段）
- **改后**: `os.path.join(settings.STORAGE_ROOT, f.file_path)` + `isabs` 检查
- **影响**: 批准驳回时物理文件删除静默失败，产生孤儿文件
- **验证**: pytest + 手动测试

### #3: endorsement_service.py — user_id → signer_id（BUG）
- **文件**: `backend/app/services/endorsement_service.py:268,282`
- **严重程度**: 🔴 严重
- **改前**: `user_id=current_user_id`（Signature 模型字段是 signer_id）
- **改后**: `signer_id=current_user_id`
- **影响**: 签名记录创建失败（字段名不匹配）
- **验证**: pytest + 手动测试

### #5: 前端 EndorseDetail.vue — 导入/调用修复（BUG）
- **文件**: `frontend/src/views/profile/EndorseDetail.vue:145,226,249`
- **严重程度**: 🔴 严重
- **改前**: `import { ..., endorse, ... }`；调用 `endorse(id, {opinion, signatures})`；调用 `endorseReject(id, {opinion})`
- **改后**: `import { ..., endorseApprove, ... }`；调用 `endorseApprove(id, opinion, signatures)`；调用 `endorseReject(id, opinion)`
- **影响**: 批准功能完全不可用（运行时 ReferenceError）
- **验证**: vue-tsc --noEmit + 手动测试

### #6: JWT SECRET_KEY 启动校验
- **文件**: `backend/app/core/config.py:22` + `backend/app/main.py`
- **严重程度**: 🔴 严重
- **改前**: `SECRET_KEY: str = "change-me-in-production"`
- **改后**: `SECRET_KEY: str = ""`，启动时若为空则拒绝启动
- **影响**: 部署安全加固，防止使用默认弱密钥
- **验证**: 启动测试

---

## Phase 2 — 🟠 高优先级修复（2026-07-24）

### #8: 文件上传魔数校验
- **文件**: `backend/app/services/file_service.py:34-52`
- **严重程度**: 🟠 高
- **改前**: 仅校验客户端 Content-Type（可伪造）
- **改后**: 安装 `filetype` 库，读文件前 8KB 检测真实魔数；未知类型回退到扩展名白名单
- **影响**: 防止伪造 MIME type 上传恶意文件
- **验证**: pytest 57/57

### #9: 列表端点组织隔离
- **文件**: `backend/app/api/instances.py:92-94`, `proposals.py:42-45`, `templates.py:56-59,85-92`
- **严重程度**: 🟠 高
- **改前**: organization_id 可选，不传则跨所有组织查询
- **改后**: 非管理员默认过滤为 `current_user.organization_id`；模板详情增加组织校验
- **影响**: 普通用户不再能查看其他组织数据
- **验证**: pytest 57/57

### #10: 同步 I/O 改异步
- **文件**: `backend/app/services/file_service.py:75-77`, `pdf_signature.py:171,282`, 新增 `import asyncio`
- **严重程度**: 🟠 高
- **改前**: `open(file, "wb").write()` 同步阻塞事件循环；`_insert_signatures` 同步处理 PDF
- **改后**: `aiofiles.open()` 异步写入；`_insert_signatures` 用 `asyncio.to_thread()` 放到线程池
- **影响**: 大文件上传/PDF 签名不再阻塞事件循环
- **验证**: pytest 57/57

### #11: 用 FlowInstance.template_type 代替子查询
- **文件**: `backend/app/services/approval_service.py:52-58`, `task_service.py:46-53`
- **严重程度**: 🟠 高
- **改前**: `FlowInstance.id.in_(select(FlowTemplate.id).where(type==X))` 双层子查询
- **改后**: `FlowInstance.template_type == instance_type` 直接使用快照字段
- **影响**: 减少一次 JOIN 子查询，提升列表查询性能
- **验证**: pytest 57/57

### #12: approval_strategy 实现
- **文件**: `backend/app/services/approval_service.py:403-430`
- **严重程度**: 🟠 高
- **改前**: `approval_strategy` 字段存储但从未被读取，全审批逻辑硬编码为 all_approve
- **改后**: 在 `approve()` 中读取 `node.approval_strategy`；`single_approve` 一人通过即生效（终止其他 pending），`all_approve` 保持原逻辑
- **影响**: 单人审批模式现已可用
- **验证**: pytest 57/57（含更新后的测试 mock）

### #13: 连接池 pool_recycle
- **文件**: `backend/app/core/database.py:14`
- **严重程度**: 🟠 高
- **改前**: `pool_pre_ping=False` 且无 pool_recycle，长时间空闲后可能拿到 stale 连接
- **改后**: 添加 `pool_recycle=3600`（1 小时回收）
- **影响**: 防止 "MySQL server has gone away" 错误
- **验证**: 配置项无需单元测试

### #14: 文件路径解析统一
- **文件**: 新建 `backend/app/utils/file_utils.py` + 修改 `task_service.py`, `file_service.py`, `document_service.py`, `terminate.py`
- **严重程度**: 🟠 高
- **改前**: 4 处文件路径拼接不一致（部分缺少 `isabs` 检查），潜在路径错误
- **改后**: 创建 `resolve_file_path()` 统一函数；`is_safe_path()` 防路径遍历
- **影响**: 消除路径拼接不一致导致的潜在 Bug
- **验证**: pytest 57/57

### #7: seed.py 密码改用环境变量
- **文件**: `backend/app/core/seed.py`
- **严重程度**: 🔴 严重
- **改前**: 硬编码 `admin123` + `print()` 输出密码
- **改后**: 从 `DEFAULT_ADMIN_PASSWORD` 环境变量读取；删除 print 密码行
- **影响**: 防止硬编码密码泄露到日志/版本控制
- **验证**: 手动测试种子脚本

---

## Phase 2 — 🟠 高优先级（2026-07-24）

### #8: 文件上传魔数校验
- **文件**: `backend/app/services/file_service.py`
- **改前**: 仅校验客户端 Content-Type
- **改后**: `filetype` 库检测魔数，未知类型退回到扩展名白名单
- **验证**: pytest 57/57 ✅

### #9: 列表端点组织隔离
- **文件**: `instances.py`, `proposals.py`, `templates.py`
- **改前**: 非管理员可跨组织查看所有数据
- **改后**: 非管理员默认强制过滤为本组织
- **验证**: pytest 57/57 ✅

### #10: 同步 I/O 改异步
- **文件**: `file_service.py`, `pdf_signature.py`
- **改前**: `open().write()` 同步阻塞 + `_insert_signatures` 同步 PDF 处理
- **改后**: `aiofiles` 异步写入 + `asyncio.to_thread()` 线程池
- **验证**: pytest 57/57 ✅

### #11: FlowInstance.template_type 代替子查询
- **文件**: `approval_service.py`, `task_service.py`
- **改前**: 双层子查询 `FlowInstance → FlowTemplate`
- **改后**: 直接使用 `FlowInstance.template_type` 快照字段
- **验证**: pytest 57/57 ✅

### #12: approval_strategy 实现
- **文件**: `approval_service.py`
- **改前**: 字段存储但从未使用，硬编码 all_approve
- **改后**: `single_approve` 一人通过即推进，`all_approve` 保持原逻辑
- **验证**: pytest 57/57 ✅（含更新后的测试 mock）

### #13: 连接池 pool_recycle
- **文件**: `database.py`
- **改前**: `pool_pre_ping=False` 且无回收机制
- **改后**: `pool_recycle=3600`（1 小时回收）
- **验证**: 配置项无需单元测试

### #14: 文件路径解析统一
- **文件**: 新建 `utils/file_utils.py` + 修改 4 处不一致拼接
- **改前**: 4 种不同路径拼接实现
- **改后**: 统一 `resolve_file_path()` + `is_safe_path()`
- **验证**: pytest 57/57 ✅

---

## Phase 3 — 🟡 中优先级（2026-07-24）

### #15: 签名逐条 flush → 批量
- **文件**: `approval_service.py`, `check_service.py`, `endorsement_service.py`
- **改前**: 循环内逐条 `db.add()+flush()`
- **改后**: 循环收集后统一 `flush()`
- **验证**: pytest 57/57 ✅

### #16: BFS 循环保护
- **文件**: `engine/flow_engine.py`
- **改前**: 无循环保护（环形边可导致无限循环）
- **改后**: 最大迭代次数 = 节点总数 × 2
- **验证**: pytest 57/57 ✅

### #17: .env 加入 .gitignore
- **文件**: `.gitignore`
- **改前**: 未忽略 .env 和 storage/
- **改后**: 添加 `.env` 和 `storage/`

### #18: 401 拦截器不显示错误消息
- **文件**: `frontend/src/api/request.ts`
- **改前**: 401 跳转前显示错误消息
- **改后**: 静默跳转，不显示错误

### #19: check_service 冗余代码清理
- **文件**: `check_service.py:412-414`
- **改前**: 重复赋值 c.status/opinion/decided_at
- **改后**: 删除冗余代码

### #20: 死代码 "arrived" 状态移除
- **文件**: `instance/change.py:223`
- **改前**: `if node_status in ("arrived", "running")`
- **改后**: `if node_status in ("running", "pending", "processing")`

### 🔧 额外修复: dashboard_service.py select() + scalars() Bug
- **文件**: `dashboard_service.py:256`
- **bug**: `select(User.id, User.real_name).scalars().all()` 返回 int 列表
- **改后**: `.all()` 返回元组列表
- **影响**: Dashboard API 500 错误

---

## 🔧 紧急修复 — 429 限流误触发（2026-07-24）

### 问题: AppLayout 每次路由切换触发 7 次分页查询
- **文件**: `AppLayout.vue:113-134` → `notification_service.py` + `notifications.py` + `notification.ts`
- **bug**: `refreshNotifyCounts()` 在 `onMounted` + `watch(route.path)` 中并行发出 7 个分页请求（tasks × 3 + checks + approvals × 3），正常浏览一分钟可超 120 次/分钟限流阈值
- **改后**: 
  1. 后端新增 `GET /api/v1/notifications/summary` —— 用 COUNT + JOIN + GROUP BY 一次返回全部 5 个计数
  2. 前端 `fetchSummaryCounts()` 一次请求替代 7 次独立查询
  3. 移除 `watch(route.path)` —— WebSocket 已实时推送计数变更
  4. 限流阈值提升：DEFAULT 120→300/min，MEDIUM 30→60/min
- **验证**: pytest 57/57 ✅ | vue-tsc 0 errors ✅
