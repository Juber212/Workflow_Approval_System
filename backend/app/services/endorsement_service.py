"""批准服务 —— 难度4级时的最终审核环节

批准人在所有审批人通过后操作，单人审核 → 签字 → 节点完成。
驳回时节点回到运行状态，负责人重新处理。
"""
import logging
from datetime import datetime
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Endorsement, FlowInstance, FlowTemplate, InstanceNode, Task,
    EndorsementStatus, InstanceNodeStatus, TaskStatus, ApprovalStatus,
    InstanceStatus, Signature, OperationLog,
    File, CheckRecord, Approval,
)
from app.core.exceptions import AppException, ErrorCode
from app.engine.flow_engine import propagate_from_node
from app.services.notification_service import create_notification, clear_related, clear_related_for_users
from app.services.pdf_signature import get_role_signature_defaults, create_signature_records
from app.services.file_service import batch_delete_files_with_physical
from app.services.instance._helpers import compute_deadline_info
from app.services.detail_helpers import (
    fetch_users_map, user_name, load_instance_files, serialize_files,
    node_signature_position, signature_image_url,
)

logger = logging.getLogger(__name__)


async def list_endorsements(
    db: AsyncSession,
    current_user_id: int,
    *,
    type_filter: str = "project",
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """我的批准列表 —— 分页 + 关键词搜索"""
    # 基础查询（JOIN 获取实例和节点名，避免 N+1）
    base_stmt = (
        select(Endorsement, FlowInstance.name.label("instance_name"),
               FlowInstance.template_type.label("instance_type"),
               InstanceNode.name.label("node_name"),
               InstanceNode.is_end.label("is_end_node"),
               InstanceNode.deadline.label("node_deadline"))
        .join(FlowInstance, Endorsement.instance_id == FlowInstance.id)
        .join(InstanceNode, Endorsement.node_id == InstanceNode.id)
        .where(Endorsement.endorser_id == current_user_id)
    )

    # 类型过滤：直接用 FlowInstance.template_type
    if type_filter:
        base_stmt = base_stmt.where(FlowInstance.template_type == type_filter)

    if status:
        base_stmt = base_stmt.where(Endorsement.status == status)
    else:
        # 默认只显示待处理的批准记录（与审批列表行为一致）
        base_stmt = base_stmt.where(Endorsement.status == EndorsementStatus.PENDING)

    if keyword:
        base_stmt = base_stmt.where(FlowInstance.name.like(f"%{keyword}%"))

    # 总数
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 排序 + 分页
    base_stmt = base_stmt.order_by(
        (Endorsement.status == EndorsementStatus.PENDING).desc(),
        Endorsement.created_at.desc(),
    )
    base_stmt = base_stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(base_stmt)
    rows = result.all()

    items = [
        {
            "id": row.Endorsement.id,
            "instance_id": row.Endorsement.instance_id,
            "instance_name": row.instance_name,
            "node_id": row.Endorsement.node_id,
            "node_name": row.node_name or "",
            "task_id": row.Endorsement.task_id,
            "endorser_id": row.Endorsement.endorser_id,
            "status": row.Endorsement.status,
            "is_end_node": row.is_end_node if row.is_end_node is not None else False,
            "round": row.Endorsement.round,
            "deadline": row.node_deadline.isoformat() if row.node_deadline else None,
            "is_overdue": compute_deadline_info(row.node_deadline)[0],
            "days_remaining": compute_deadline_info(row.node_deadline)[1],
            "created_at": row.Endorsement.created_at,
        }
        for row in rows
    ]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_endorsement_detail(
    db: AsyncSession,
    endorsement_id: int,
    current_user_id: int,
) -> dict:
    """批准详情 —— 含文件、校验/审批进度、签名配置

    查询优化：Endorsement + FlowInstance + InstanceNode 合并为一次 JOIN 查询（3→1）
    """
    # 合并查询：Endorsement + FlowInstance + InstanceNode（一次 JOIN 替代 3 次独立查询）
    row = (await db.execute(
        select(Endorsement, FlowInstance, InstanceNode)
        .join(FlowInstance, Endorsement.instance_id == FlowInstance.id)
        .join(InstanceNode, Endorsement.node_id == InstanceNode.id)
        .where(Endorsement.id == endorsement_id)
    )).first()
    if row is None:
        raise AppException(ErrorCode.NOT_FOUND, "批准记录不存在")
    e, inst, node = row.Endorsement, row.FlowInstance, row.InstanceNode
    if e.endorser_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "无权查看此批准记录")

    # 查询 Task（独立结果集，保持单独查询）
    task = None
    if e.task_id:
        task = (await db.execute(
            select(Task).where(Task.id == e.task_id)
        )).scalar_one_or_none()

    # 查询实例全部文件 + 所属节点名称映射（批准人需查看完整上下文，含之前所有节点文件）
    files, file_node_names = await load_instance_files(db, e.instance_id)

    # 查询校验/审批记录
    checks_result = await db.execute(
        select(CheckRecord).where(
            CheckRecord.node_id == e.node_id,
            CheckRecord.round == node.round,
        )
    )
    checks = checks_result.scalars().all()

    approvals_result = await db.execute(
        select(Approval).where(
            Approval.node_id == e.node_id,
            Approval.round == node.round,
        )
    )
    approvals = approvals_result.scalars().all()

    # 批量查询校验人和审批人的真实姓名（与 approval_service 保持一致）
    checker_ids = list(set(c.checker_id for c in checks))
    approver_ids = list(set(a.approver_id for a in approvals))
    name_users_map = await fetch_users_map(db, set(checker_ids + approver_ids))

    # 查询节点列表（进度链）
    nodes_result = await db.execute(
        select(InstanceNode).where(
            InstanceNode.instance_id == e.instance_id
        ).order_by(InstanceNode.sort_order)
    )
    all_nodes = nodes_result.scalars().all()

    # 批量查询相关用户（一次 IN 查询替代 2 次独立查询）
    users_map = await fetch_users_map(db, {e.endorser_id, inst.initiator_id})
    endorser_user = users_map.get(e.endorser_id)
    initiator_user = users_map.get(inst.initiator_id)

    # 查询批准人签名图片
    current_signature_url = signature_image_url(endorser_user)

    return {
        "id": e.id,
        "instance_id": e.instance_id,
        "instance_name": inst.name,
        "instance_status": inst.status,
        "initiator_id": inst.initiator_id,
        "initiator_name": initiator_user.real_name if initiator_user else "",
        "priority": inst.priority,
        "difficulty": inst.difficulty,
        "node_id": e.node_id,
        "node_name": node.name,
        "node_status": node.status,
        "node_description": node.description,  # 节点说明
        "time_limit_days": node.time_limit_days,  # 完成时限（工作日）
        "deadline": node.deadline.isoformat() if node.deadline else None,  # 截止时间
        "task_id": e.task_id,
        "endorser_id": e.endorser_id,
        "endorser_name": endorser_user.real_name if endorser_user else "",
        "status": e.status,
        "opinion": e.opinion,
        "round": e.round,
        "require_endorser_signature": node.require_endorser_signature,
        **node_signature_position(node),
        "current_signature_url": current_signature_url,
        "current_node_index": next(
            (i + 1 for i, n in enumerate(all_nodes) if n.id == e.node_id), 0
        ),
        "total_nodes": len(all_nodes),
        "nodes": [{"id": n.id, "name": n.name, "status": n.status, "is_start": n.is_start, "is_end": n.is_end}
                   for n in all_nodes],
        "files": serialize_files(files, file_node_names),
        # 仅本节点文件（签批预览用，后端过滤，不可信前端）
        "node_files": serialize_files(files, file_node_names, node_id=node.id),
        "checks": [{"id": c.id, "checker_id": c.checker_id,
                     "checker_name": user_name(name_users_map, c.checker_id),
                     "status": c.status, "opinion": c.opinion,
                     "decided_at": c.decided_at} for c in checks],
        "approvals": [{"id": a.id, "approver_id": a.approver_id,
                       "approver_name": user_name(name_users_map, a.approver_id),
                       "status": a.status, "opinion": a.opinion,
                       "signature_applied": a.signature_applied,
                       "decided_at": a.decided_at} for a in approvals],
        "decided_at": e.decided_at,
        "created_at": e.created_at,
        "role_signature": await get_role_signature_defaults(db, "endorser"),
    }


async def endorse(
    db: AsyncSession,
    endorsement_id: int,
    current_user_id: int,
    opinion: str | None,
    signatures: list[dict] | None = None,
    signature_x: float | None = None,
    signature_y: float | None = None,
    signature_page: int | None = None,
) -> dict:
    """批准通过 —— 锁定记录 → 校验权限 → 签字上PDF → 推进流程"""
    now = datetime.now()

    # 1. 并发锁定目标 Endorsement 行
    e = (await db.execute(
        select(Endorsement).where(Endorsement.id == endorsement_id).with_for_update()
    )).scalar_one_or_none()
    if e is None:
        raise AppException(ErrorCode.NOT_FOUND, "批准记录不存在")

    # 2. 权限校验（在锁之后，防止 TOCTOU）
    if e.endorser_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "您不是此节点的批准人")
    if e.status != EndorsementStatus.PENDING:
        raise AppException(ErrorCode.VALIDATION_ERROR, "该批准记录已处理，不能重复操作")

    # 3. 更新状态
    e.status = EndorsementStatus.APPROVED
    e.opinion = opinion
    e.decided_at = now

    # ---- 通知清除：批准完成后删除该批准人的待批准通知 (#11) ----

    await clear_related(
        db, user_id=current_user_id, types=["endorsement_assigned"],
        instance_id=e.instance_id,
    )
    # 保存签名位置（旧版兼容）
    if signature_x is not None:
        e.signature_x = signature_x
    if signature_y is not None:
        e.signature_y = signature_y
    if signature_page is not None:
        e.signature_page = signature_page

    # 4. 保存签名记录
    sig_ids: list[int] = []
    if signatures:
        # 设置 signer_id 后再调用统一 helper
        for sig in signatures:
            sig["signer_id"] = current_user_id
        sig_ids = await create_signature_records(
            db,
            role_type="endorser",
            source_id=e.id,
            node_id=e.node_id,
            signatures=signatures,
        )
    elif signature_x is not None:  # 旧版单签名兼容（P1-13：补 file_id 到当前轮次首 PDF）
        # 对齐 approve 旧版兼容分支：默认签在节点当前轮次第一个 PDF 上，
        # 找不到 PDF 则不创建签名（避免 file_id=None 坏记录，签名永不落盘）
        sig_node = (await db.execute(
            select(InstanceNode).where(InstanceNode.id == e.node_id)
        )).scalar_one_or_none()
        if sig_node is None:
            raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")
        pdf_files = (await db.execute(
            select(File).where(
                File.node_id == e.node_id,
                File.round == sig_node.round,
            ).limit(1)
        )).scalars().all()
        if pdf_files:
            s = Signature(
                file_id=pdf_files[0].id,
                node_id=e.node_id,
                role_type="endorser",
                source_id=e.id,
                signer_id=current_user_id,
                signature_x=signature_x,
                signature_y=signature_y or 100,
                signature_page=signature_page or -1,
                applied=False,
                sort_order=0,
            )
            db.add(s)
            await db.flush()
            sig_ids.append(s.id)

    # 5. 操作日志
    log = OperationLog(
        instance_id=e.instance_id,
        node_id=e.node_id,
        operator_type="user",
        operator_id=current_user_id,
        operation_type="endorse",
        round=e.round,
        description="批准通过" + ("（已签名）" if sig_ids else ""),
    )
    db.add(log)
    await db.flush()

    # 6. 查询节点和实例信息
    node = await _get_node(db, e.node_id)
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    inst = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == e.instance_id)
    )).scalar_one_or_none()
    if inst is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联项目不存在")

    # 7. 收集签名 ID（由 API 层在 commit 后统一写入 PDF）
    _pending_signature_ids = sig_ids if (node.require_endorser_signature and sig_ids) else []

    # P1-13：signature_applied 按实际落盘结果标记——仅当存在待写入 PDF 的签名时才算已签名，
    # 避免「无签名/无需签名却显示已签名」的假状态
    e.signature_applied = bool(_pending_signature_ids)

    # 8. 标记 Task 为 completed
    if e.task_id:
        await db.execute(
            update(Task)
            .where(Task.id == e.task_id)
            .values(status=TaskStatus.COMPLETED, completed_at=now)
        )

    # 9. 判断结束节点 or 方案 → 实例完成
    from app.models import FlowTemplate
    is_proposal = False
    if not node.is_end:
        tpl = (await db.execute(
            select(FlowTemplate).where(FlowTemplate.id == inst.template_id)
        )).scalar_one_or_none()
        is_proposal = tpl is not None and tpl.type == "proposal"

    if node.is_end or is_proposal:
        node.status = InstanceNodeStatus.FINISHED
        node.completed_at = now
        inst.status = InstanceStatus.COMPLETED
        inst.completed_at = now
        return {"message": "批准通过，项目已完成", "_pending_sig_ids": _pending_signature_ids}

    # 10. 普通节点 → finished → 传播到下游
    node.status = InstanceNodeStatus.FINISHED
    node.completed_at = now
    await db.flush()

    logger.info(
        "endorse: 节点 #%d「%s」→ FINISHED，调用 propagate_from_node(instance=%d, node=%d)",
        node.id, node.name, e.instance_id, node.id,
    )
    await propagate_from_node(db, e.instance_id, node.id)
    return {"message": "批准通过，流程已推进到下一节点", "_pending_sig_ids": _pending_signature_ids}


async def endorse_reject(
    db: AsyncSession,
    endorsement_id: int,
    current_user_id: int,
    opinion: str,
) -> dict:
    """批准驳回 —— 节点回到运行状态，负责人重新处理"""
    now = datetime.now()

    if not opinion or not opinion.strip():
        raise AppException(ErrorCode.VALIDATION_ERROR, "驳回时必须填写意见")

    # 1. 并发锁定
    e = (await db.execute(
        select(Endorsement).where(Endorsement.id == endorsement_id).with_for_update()
    )).scalar_one_or_none()
    if e is None:
        raise AppException(ErrorCode.NOT_FOUND, "批准记录不存在")

    # 2. 权限校验
    if e.endorser_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "您不是此节点的批准人")
    if e.status != EndorsementStatus.PENDING:
        raise AppException(ErrorCode.VALIDATION_ERROR, "该批准记录已处理")

    # 3. 当前 Endorsement → rejected
    e.status = EndorsementStatus.REJECTED
    e.opinion = opinion
    e.decided_at = now

    # ---- 通知清除：批准驳回后删除该批准人的待批准通知 (#11) ----

    await clear_related(
        db, user_id=current_user_id, types=["endorsement_assigned"],
        instance_id=e.instance_id,
    )

    # 4. 查询节点
    node = await _get_node(db, e.node_id)
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    # 5. 驳回：当前轮次待处理的审批 + 校验 + 批准全部终止
    from app.models import CheckRecord, Approval

    # 终止当前轮次 pending 的 Approval（加 round 过滤防止误杀其他轮次）
    # P1-12：先收集被终止审批人，再终止并清除其待办通知
    terminated_approvers = (await db.execute(
        select(Approval.approver_id).where(
            Approval.node_id == e.node_id, Approval.status == ApprovalStatus.PENDING,
            Approval.round == e.round)
    )).scalars().all()
    await db.execute(
        update(Approval)
        .where(Approval.node_id == e.node_id, Approval.status == ApprovalStatus.PENDING,
               Approval.round == e.round)
        .values(status=ApprovalStatus.TERMINATED)
    )
    await clear_related_for_users(db, set(terminated_approvers), "approval_assigned", e.instance_id)

    # 终止当前轮次 pending 的 CheckRecord（加 round 过滤防止误杀其他轮次）
    terminated_checkers = (await db.execute(
        select(CheckRecord.checker_id).where(
            CheckRecord.node_id == e.node_id, CheckRecord.status == "pending",
            CheckRecord.round == e.round)
    )).scalars().all()
    await db.execute(
        update(CheckRecord)
        .where(CheckRecord.node_id == e.node_id, CheckRecord.status == "pending",
               CheckRecord.round == e.round)
        .values(status="terminated")
    )
    await clear_related_for_users(db, set(terminated_checkers), "check_assigned", e.instance_id)

    # 6. 删除当前轮文件（DB + 物理文件）
    files_result = await db.execute(
        select(File).where(
            File.instance_id == e.instance_id,
            File.node_id == e.node_id,
            File.round == node.round,
        )
    )
    old_files = files_result.scalars().all()
    if old_files:
        await batch_delete_files_with_physical(db, list(old_files))

    # 7. 节点回到运行状态，round+1
    node.status = InstanceNodeStatus.RUNNING
    node.round += 1

    # 8. Task → processing
    task_for_notify = None
    if e.task_id:
        await db.execute(
            update(Task)
            .where(Task.id == e.task_id)
            .values(status=TaskStatus.PROCESSING, submitted_at=None)
        )
        # 查询 task 用于通知
        task_for_notify = (await db.execute(
            select(Task).where(Task.id == e.task_id)
        )).scalar_one_or_none()

    # 9. 操作日志
    log = OperationLog(
        instance_id=e.instance_id,
        node_id=e.node_id,
        operator_type="user",
        operator_id=current_user_id,
        operation_type="endorse_reject",
        round=node.round,
        description=f"批准驳回：{opinion}",
    )
    db.add(log)

    # ---- 通知：负责人，批准驳回需重新处理 (#10) ----

    if task_for_notify and task_for_notify.assignee_id:
        await create_notification(
            db, user_id=task_for_notify.assignee_id, type="endorsement_rejected",
            title="批准驳回",
            content=f"节点「{node.name}」批准驳回：{opinion}",
            link=f"/profile/task/{task_for_notify.id}",
            instance_id=node.instance_id,
        )

    return {"message": "已驳回，负责人需重新处理"}


async def _get_node(db: AsyncSession, node_id: int) -> InstanceNode | None:
    """获取节点（内部辅助）"""
    result = await db.execute(
        select(InstanceNode).where(InstanceNode.id == node_id)
    )
    return result.scalar_one_or_none()
