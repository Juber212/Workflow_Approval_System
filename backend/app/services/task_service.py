"""任务服务 —— 待办列表、任务详情、提交、草稿保存"""
import asyncio
import logging
import os
from datetime import datetime

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.utils.file_utils import resolve_file_path
from app.core.exceptions import AppException
from app.services.notification_service import create_notification, clear_related
from app.services.pdf_signature import get_role_signature_defaults, create_signature_records
from app.services.instance._helpers import compute_progress
from app.core.error_codes import ErrorCode
from app.models import (
    Task,
    FlowInstance,
    FlowTemplate,
    InstanceNode,
    Organization,
    User,
    File,
    CheckRecord,
    Approval,
    OperationLog,
)
from app.models.enums import TaskStatus, InstanceNodeStatus, CheckStatus, ApprovalStatus
from app.engine.flow_engine import propagate_from_node
from app.schemas.common import PaginatedData
from app.schemas.task import TaskListItem, TaskDetail, TaskSubmit

logger = logging.getLogger(__name__)


async def list_tasks(
    db: AsyncSession,
    *,
    assignee_id: int,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    instance_type: str | None = None,  # "project" 或 "proposal"，用于区分项目/方案
) -> dict:
    """我的待办列表 —— 按 deadline 升序，逾期优先"""
    conditions = [Task.assignee_id == assignee_id]

    # 按实例类型过滤（项目/方案）
    if instance_type:
        conditions.append(Task.instance_id.in_(
            select(FlowInstance.id).where(FlowInstance.template_type == instance_type)
        ))
    if status:
        conditions.append(Task.status == status)
    else:
        # 默认排除已完成和已终止
        conditions.append(Task.status.notin_(["completed", "terminated"]))

    # 实例名模糊搜索
    if keyword:
        inst_ids_sub = select(FlowInstance.id).where(FlowInstance.name.like(f"%{keyword}%"))
        conditions.append(Task.instance_id.in_(inst_ids_sub))

    base_stmt = select(Task).where(*conditions)

    # 总数
    count_stmt = select(func.count()).select_from(Task).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页 + 逾期优先排序（deadline 在 InstanceNode 上，需 JOIN）
    now = datetime.now()
    stmt = (
        base_stmt
        .join(InstanceNode, Task.node_id == InstanceNode.id)
        .order_by(
            # 逾期排前面：无 deadline 视为不逾期，排在最后
            case((InstanceNode.deadline < now, 0), else_=1),
            # MySQL 不支持 NULLS LAST，用 CASE 模拟：NULL deadline 排后面
            case((InstanceNode.deadline.is_(None), 1), else_=0),
            InstanceNode.deadline.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    if not tasks:
        return PaginatedData(items=[], total=total, page=page, page_size=page_size)

    # 批量查询关联数据
    task_ids = [t.id for t in tasks]
    node_ids = list(set(t.node_id for t in tasks))
    inst_ids = list(set(t.instance_id for t in tasks))

    # 节点
    nodes_result = await db.execute(select(InstanceNode).where(InstanceNode.id.in_(node_ids)))
    nodes_map = {n.id: n for n in nodes_result.scalars().all()}

    # 实例
    insts_result = await db.execute(select(FlowInstance).where(FlowInstance.id.in_(inst_ids)))
    insts_map = {i.id: i for i in insts_result.scalars().all()}

    # 发起人
    initiator_ids = list(set(i.initiator_id for i in insts_map.values()))
    users_result = await db.execute(select(User).where(User.id.in_(initiator_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    items: list[TaskListItem] = []
    for t in tasks:
        node = nodes_map.get(t.node_id)
        inst = insts_map.get(t.instance_id)
        initiator = users_map.get(inst.initiator_id) if inst else None

        # deadline 来自关联节点
        dl = node.deadline if node else None
        is_overdue = dl is not None and dl < now
        days_remaining = None
        if dl:
            delta = (dl - now).days
            days_remaining = max(0, delta)

        items.append(TaskListItem(
            id=t.id,
            instance_id=t.instance_id,
            instance_name=inst.name if inst else "",
            node_id=t.node_id,
            node_name=node.name if node else "",
            initiator_name=initiator.real_name if initiator else "",
            status=t.status,
            deadline=dl,
            is_overdue=is_overdue,
            days_remaining=days_remaining,
            priority=inst.priority if inst else "normal",
            created_at=t.created_at,
        ))

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def get_task_detail(db: AsyncSession, task_id: int, current_user_id: int) -> dict:
    """任务详情 —— 含文件/校验/审批进度聚合

    查询优化：Task + InstanceNode + FlowInstance 合并为一次 JOIN（3→1）
    """
    # 合并查询：Task + InstanceNode + FlowInstance（一次 JOIN 替代 3 次独立查询）
    row = (await db.execute(
        select(Task, InstanceNode, FlowInstance)
        .join(InstanceNode, Task.node_id == InstanceNode.id)
        .join(FlowInstance, Task.instance_id == FlowInstance.id)
        .where(Task.id == task_id)
    )).first()
    if row is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    t, node, inst = row.Task, row.InstanceNode, row.FlowInstance

    # 权限校验：仅任务负责人可查看
    if t.assignee_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可查看")

    # 首次打开任务详情：自动标记为"处理中"（设计意图：无需单独的"开始"按钮，打开即开始）
    if t.status == TaskStatus.PENDING:
        t.status = TaskStatus.PROCESSING
        await db.flush()

    # 批量查询负责人 + 发起人（一次 IN 查询替代 2 次独立查询）
    user_ids_needed = {t.assignee_id, inst.initiator_id}
    user_ids_needed.discard(None)
    users_result = await db.execute(
        select(User).where(User.id.in_(user_ids_needed))
    )
    users_map: dict[int, User] = {u.id: u for u in users_result.scalars().all()}
    assignee = users_map.get(t.assignee_id)
    initiator = users_map.get(inst.initiator_id)

    # 查询实例所有节点（供 ProgressBar 流程进度条使用）
    total_nodes, current_node_index, all_nodes = await compute_progress(db, t.instance_id)

    # 文件 —— 查实例全部文件（负责人需了解完整上下文）
    files_result = await db.execute(
        select(File).where(File.instance_id == t.instance_id).order_by(File.node_id, File.id.desc())
    )
    files = files_result.scalars().all()

    # 批量查询文件所属节点名称
    file_node_ids = list(set(f.node_id for f in files if f.node_id))
    file_node_names: dict[int, str] = {}
    if file_node_ids:
        fn_result = await db.execute(
            select(InstanceNode.id, InstanceNode.name).where(InstanceNode.id.in_(file_node_ids))
        )
        file_node_names = {row[0]: row[1] for row in fn_result.all()}

    # 校验进度
    checks_result = await db.execute(
        select(CheckRecord).where(CheckRecord.task_id == t.id).order_by(CheckRecord.id)
    )
    checks = checks_result.scalars().all()
    checker_ids = [c.checker_id for c in checks]
    checker_users = {}
    if checker_ids:
        cu = await db.execute(select(User).where(User.id.in_(checker_ids)))
        checker_users = {u.id: u for u in cu.scalars().all()}

    # 审批进度
    apprs_result = await db.execute(
        select(Approval).where(Approval.task_id == t.id).order_by(Approval.id)
    )
    approvals = apprs_result.scalars().all()
    approver_ids = [a.approver_id for a in approvals]
    approver_users = {}
    if approver_ids:
        au = await db.execute(select(User).where(User.id.in_(approver_ids)))
        approver_users = {u.id: u for u in au.scalars().all()}

    # 退回信息：当 Task 被退回重做时，返回最近一次退回原因
    rejected_type: str | None = None
    rejected_reason: str | None = None
    if t.submitted_at is None and t.status == TaskStatus.PROCESSING:
        # 优先查审批退回（通过 task_id 关联的审批退回）
        rejected_appr = (
            await db.execute(
                select(Approval)
                .where(Approval.task_id == t.id, Approval.status == ApprovalStatus.REJECTED)
                .order_by(Approval.decided_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if rejected_appr:
            rejected_type = "approval"
            rejected_reason = rejected_appr.opinion
        else:
            # 查校验退回
            returned_check = (
                await db.execute(
                    select(CheckRecord)
                    .where(CheckRecord.task_id == t.id, CheckRecord.status == CheckStatus.RETURNED)
                    .order_by(CheckRecord.decided_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if returned_check:
                rejected_type = "check"
                rejected_reason = returned_check.opinion
            else:
                # 查终审驳回（终审审批 task_id=None，通过 reject_target_node_id 匹配）
                final_reject_appr = (
                    await db.execute(
                        select(Approval)
                        .where(
                            Approval.reject_target_node_id == t.node_id,
                            Approval.status == ApprovalStatus.REJECTED,
                        )
                        .order_by(Approval.decided_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if final_reject_appr:
                    rejected_type = "approval"  # 统一当审批驳回展示
                    rejected_reason = final_reject_appr.opinion

    return TaskDetail(
        id=t.id,
        instance_id=t.instance_id,
        instance_name=inst.name,
        instance_status=inst.status,
        initiator_id=inst.initiator_id,
        initiator_name=initiator.real_name if initiator else "",
        priority=(inst.priority or "normal").lower(),
        difficulty=(inst.difficulty or "1"),  # 难度等级
        node_id=t.node_id,
        node_name=node.name,
        node_description=node.description,
        node_status=node.status,
        assignee_id=t.assignee_id,
        assignee_name=assignee.real_name if assignee else "",
        status=t.status,
        assignee_note=t.assignee_note,
        require_file=node.require_file,
        file_folders=node.file_folders,  # 文件提交文件夹配置
        time_limit_days=node.time_limit_days,
        deadline=node.deadline,
        round=node.round,
        total_nodes=total_nodes,
        current_node_index=current_node_index,
        nodes=[
            {
                "id": n.id, "name": n.name,
                "is_start": n.is_start, "is_end": n.is_end,
                "status": (n.status or "waiting").lower(),
                "sort_order": n.sort_order,
            }
            for n in all_nodes
        ],
        files=[
            {
                "id": f.id,
                "original_name": f.original_name,
                "mime_type": f.mime_type,
                "file_size": f.file_size,
                "uploader_name": "",
                "upload_type": f.upload_type,
                "folder_name": f.folder_name,
                "round": f.round,
                "node_id": f.node_id,
                "node_name": file_node_names.get(f.node_id, "") if f.node_id else "",
                "conversion_status": f.conversion_status or "ready",  # PDF 转换状态（上传后待转换/转换中/失败）
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ],
        # 仅本节点文件（签批预览用，后端过滤）—— 字段与 files 保持一致，前端文件夹模式依赖 folder_name
        node_files=[
            {
                "id": f.id,
                "original_name": f.original_name,
                "mime_type": f.mime_type,
                "file_size": f.file_size,
                "uploader_name": "",
                "upload_type": f.upload_type,
                "folder_name": f.folder_name,
                "round": f.round,
                "node_id": f.node_id,
                "node_name": file_node_names.get(f.node_id, "") if f.node_id else "",
                "conversion_status": f.conversion_status or "ready",
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files if f.node_id == t.node_id
        ],
        checks=[
            {
                "id": c.id,
                "checker_id": c.checker_id,
                "checker_name": checker_users.get(c.checker_id, "").real_name if checker_users.get(c.checker_id) else "",
                "status": c.status,
                "opinion": c.opinion,
                "decided_at": c.decided_at.isoformat() if c.decided_at else None,
            }
            for c in checks
        ],
        approvals=[
            {
                "id": a.id,
                "approver_id": a.approver_id,
                "approver_name": approver_users.get(a.approver_id, "").real_name if approver_users.get(a.approver_id) else "",
                "status": a.status,
                "opinion": a.opinion,
                "signature_applied": a.signature_applied,
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
            }
            for a in approvals
        ],
        rejected_type=rejected_type,
        rejected_reason=rejected_reason,
        # 节点签批配置（三个独立开关 + 默认位置）
        require_assignee_signature=node.require_assignee_signature,
        require_checker_signature=node.require_checker_signature,
        require_approver_signature=node.require_approver_signature,
        signature_x=node.signature_x,
        signature_y=node.signature_y,
        signature_page=node.signature_page,
        # 当前负责人的签名图片 URL
        current_signature_url=f"/api/v1/auth/users/{t.assignee_id}/signature-image" if assignee and assignee.signature_image else None,
        # 角色维度签名默认配置
        role_signature=await get_role_signature_defaults(db, "assignee"),
        submitted_at=t.submitted_at,
        created_at=t.created_at,
    )


async def save_draft(db: AsyncSession, task_id: int, current_user_id: int, note: str | None) -> None:
    """保存草稿 —— 仅更新负责人备注"""
    t = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if t is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if t.assignee_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可操作")
    if t.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise AppException(ErrorCode.FORBIDDEN, "当前任务状态不可编辑")

    t.assignee_note = note
    await db.flush()


async def submit_task(db: AsyncSession, task_id: int, current_user_id: int, data: TaskSubmit) -> dict:
    """提交任务 —— 文件校验 + PDF 转换 + 签名存储 + 创建校验/审批记录

    从 api/tasks.py 迁入，保持原有逻辑不变。
    """
    task = (await db.execute(
        select(Task).where(Task.id == task_id).with_for_update()
    )).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可提交")
    if task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise AppException(ErrorCode.FORBIDDEN, "当前状态不可提交")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    # ========== 文件提交校验 ==========
    await _validate_file_submission(node, task_id, db)

    # ========== 更新备注和提交时间 ==========
    if data.assignee_note:
        task.assignee_note = data.assignee_note
    now = datetime.now()
    task.submitted_at = now

    # ========== PDF 转换（并发 + 限流） ==========
    await _convert_files_to_pdf(task_id, node.round, db)

    # ========== 负责人签批（由 API 层 commit 后统一写入 PDF）==========
    _sig_ids: list[int] = []
    _pending_sig_ids: list[int] = []  # post-commit hook 需要用到的签名 ID
    if data.signatures and node.require_assignee_signature:
        # 设置 signer_id 后再调用统一 helper
        for sig in data.signatures:
            sig["signer_id"] = current_user_id
        _sig_ids = await create_signature_records(
            db,
            role_type="assignee",
            source_id=task_id,
            node_id=task.node_id,
            signatures=data.signatures,
            default_signature_x=node.signature_x,
            default_signature_y=node.signature_y,
            default_signature_page=node.signature_page,
        )

        # 收集签名 ID，由 API 层在 commit 后统一写入 PDF（post-commit hook）
        _pending_sig_ids = list(_sig_ids) if _sig_ids else []

    # ========== 按 checkers 创建 CheckRecord ==========
    checkers = node.checkers or []
    created_checks: list[tuple[int, CheckRecord]] = []  # (checker_id, CheckRecord)
    created_approvals: list[tuple[int, Approval]] = []  # (approver_id, Approval)
    if checkers:
        task.status = TaskStatus.WAITING_CHECK
        node.status = InstanceNodeStatus.WAITING_CHECK
        for ch in checkers:
            checker_id = ch.get("user_id") if isinstance(ch, dict) else ch
            cr = CheckRecord(
                instance_id=task.instance_id,
                node_id=task.node_id,
                task_id=task_id,
                checker_id=checker_id,
                status=CheckStatus.PENDING,
                round=node.round,
            )
            db.add(cr)
            created_checks.append((checker_id, cr))
    else:
        # 无校验人（legacy 数据容错：已发布的老模板可能存在无校验人的节点）
        # 校验人和审批人在模板发布时都必须配置，此分支仅用于历史数据兼容
        approvers = node.approvers or []
        if approvers:
            # 有审批人 → 直接进入等待审批
            task.status = TaskStatus.WAITING_APPROVAL
            node.status = InstanceNodeStatus.WAITING_APPROVAL
            for a in approvers:
                approver_id = a.get("user_id") if isinstance(a, dict) else a
                ap = Approval(
                    instance_id=task.instance_id,
                    node_id=task.node_id,
                    task_id=task_id,
                    approver_id=approver_id,
                    status=ApprovalStatus.PENDING,
                    round=node.round,
                )
                db.add(ap)
                created_approvals.append((approver_id, ap))
        else:
            # 既无校验人也无审批人（legacy 极端情况）→ 直接完成节点，避免死锁
            task.status = TaskStatus.COMPLETED
            node.status = InstanceNodeStatus.FINISHED
            node.completed_at = datetime.now()
            logger.warning(
                "[submit_task] 节点 #%d 无校验人也无审批人（legacy数据容错）→ 直接完成",
                node.id,
            )

    # ========== 操作日志 ==========
    db.add(OperationLog(
        instance_id=task.instance_id,
        node_id=task.node_id,
        operator_type="user",
        operator_id=current_user_id,
        operation_type="task_submit",
        round=node.round,
        description=f"提交了节点「{node.name}」的任务",
        detail={"node_name": node.name, "round": node.round},
    ))

    await db.flush()

    # ---- legacy 兜底：无校验+无审批人时节点已完成，传播到下游 ----
    if task.status == TaskStatus.COMPLETED:
        await propagate_from_node(db, task.instance_id, task.node_id)

    # ---- 通知：校验人有新的待校验任务 (#2) ----
    notif_tasks = [
        create_notification(
            db, user_id=c_id, type="check_assigned",
            title="新的待校验任务",
            content=f"节点「{node.name}」负责人已提交，等待你校验",
            link=f"/profile/check/{cr.id}",
            instance_id=task.instance_id,
        )
        for c_id, cr in created_checks
    ]
    # ---- 通知：审批人有新的待审批任务（无校验人直通审批）(#3) ----
    notif_tasks += [
        create_notification(
            db, user_id=a_id, type="approval_assigned",
            title="新的待审批任务",
            content=f"节点「{node.name}」负责人已提交，等待你审批",
            link=f"/profile/approval/{ap.id}",
            instance_id=task.instance_id,
        )
        for a_id, ap in created_approvals
    ]
    if notif_tasks:
        try:
            await asyncio.gather(*notif_tasks)
        except Exception:
            logger.warning("[submit_task] 通知创建失败，不影响提交", exc_info=True)

    # ---- 通知清除：提交后删除该负责人的相关待办通知 (#11) ----
    # endorsement_rejected（批准驳回）与 check_returned/approval_rejected/final_rejected 同类，
    # 负责人重新提交文件时一并清除
    await clear_related(
        db, user_id=current_user_id,
        types=["task_assigned", "check_returned", "approval_rejected", "final_rejected", "endorsement_rejected"],
        instance_id=task.instance_id,
    )

    return {"message": "任务已提交，等待校验" if checkers else "任务已提交，等待审批", "_pending_sig_ids": _pending_sig_ids}


# ==================== 内部辅助函数 ====================

async def _validate_file_submission(node: InstanceNode, task_id: int, db: AsyncSession):
    """前置校验：文件提交规则（文件夹配置优先，否则沿用 require_file 布尔开关）"""
    folders_config = node.file_folders or []
    if folders_config:
        result = await db.execute(
            select(File).where(File.task_id == task_id, File.round == node.round)
        )
        current_files = result.scalars().all()

        folder_counts: dict[str, int] = {}
        for f in current_files:
            fn = f.folder_name or ""
            folder_counts[fn] = folder_counts.get(fn, 0) + 1

        errors: list[str] = []
        for folder in folders_config:
            name = (folder.get("name") or "").strip()
            if not name:
                continue
            required = folder.get("required", False)
            count = folder.get("file_count")
            actual = folder_counts.get(name, 0)

            if required and actual == 0:
                errors.append(f"文件夹「{name}」必须至少提交 1 个文件")
            elif required and count is not None and actual != count:
                errors.append(f"文件夹「{name}」需要提交 {count} 个文件，当前已提交 {actual} 个")

        if errors:
            raise AppException(ErrorCode.BAD_REQUEST, "；".join(errors))
    elif node.require_file:
        result = await db.execute(
            select(File).where(File.task_id == task_id, File.round == node.round)
        )
        files = result.scalars().all()
        if not files:
            raise AppException(ErrorCode.BAD_REQUEST, "该节点要求必须上传文件")


async def _convert_files_to_pdf(task_id: int, round_num: int, db: AsyncSession):
    """检查文件转换状态（50+ 优化：转换已由 ARQ Worker 后台完成）

    改造前：同步调用 convert_to_pdf 转换所有文件（阻塞 5-30 秒）。
    改造后：检查 File.conversion_status，确保所有文件已转换完成。
    若仍有 pending/converting，拒绝提交提示稍后重试。
    """
    task_files = (await db.execute(
        select(File).where(File.task_id == task_id, File.round == round_num)
    )).scalars().all()

    if not task_files:
        return

    for f in task_files:
        if f.conversion_status == "failed":
            raise AppException(
                ErrorCode.PDF_CONVERSION_FAILED,
                f"文件「{f.original_name}」转换失败: {f.conversion_error or '未知错误'}，请重新上传"
            )
        if f.conversion_status in ("pending", "converting"):
            raise AppException(
                ErrorCode.BAD_REQUEST,
                f"文件「{f.original_name}」仍在转换中，请稍后重试"
            )
        # ready 状态：确保 DB 路径已更新为 PDF 扩展名
        if f.conversion_status == "ready" and f.mime_type != "application/pdf":
            f.file_path = os.path.splitext(f.file_path)[0] + ".pdf"
            f.stored_name = os.path.splitext(f.stored_name)[0] + ".pdf"
            f.mime_type = "application/pdf"
