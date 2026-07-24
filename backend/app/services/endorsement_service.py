"""批准服务 —— 难度4级时的最终审核环节

批准人在所有审批人通过后操作，单人审核 → 签字 → 节点完成。
驳回时节点回到运行状态，负责人重新处理。
"""
import logging
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Endorsement, FlowInstance, FlowTemplate, InstanceNode, Task,
    EndorsementStatus, InstanceNodeStatus, TaskStatus, ApprovalStatus,
    InstanceStatus, Signature, OperationLog,
)
from app.core.exceptions import AppException, ErrorCode
from app.engine.flow_engine import propagate_from_node

logger = logging.getLogger(__name__)


async def list_endorsements(
    db: AsyncSession,
    current_user_id: int,
    type_filter: str = "project",
) -> list[dict]:
    """我的批准列表 —— 查询当前用户作为批准人的待处理/已处理记录"""
    # 查找 endorser_id 匹配且实例未终止的记录
    query = (
        select(Endorsement)
        .where(Endorsement.endorser_id == current_user_id)
        .order_by(
            (Endorsement.status == EndorsementStatus.PENDING).desc(),
            Endorsement.created_at.desc(),
        )
    )
    result = await db.execute(query)
    endorsements = result.scalars().all()

    items = []
    for e in endorsements:
        # 查询关联实例信息
        inst = (await db.execute(
            select(FlowInstance).where(FlowInstance.id == e.instance_id)
        )).scalar_one_or_none()
        if inst is None:
            continue

        # 方案/项目类型过滤
        tpl = (await db.execute(
            select(FlowTemplate).where(FlowTemplate.id == inst.template_id)
        )).scalar_one_or_none()
        tpl_type = tpl.type if tpl else "project"
        if type_filter and tpl_type != type_filter:
            continue

        # 查询节点名称 + 是否结束节点
        node = (await db.execute(
            select(InstanceNode).where(InstanceNode.id == e.node_id)
        )).scalar_one_or_none()

        items.append({
            "id": e.id,
            "instance_id": e.instance_id,
            "instance_name": inst.name,
            "node_id": e.node_id,
            "node_name": node.name if node else "",
            "task_id": e.task_id,
            "endorser_id": e.endorser_id,
            "status": e.status,
            "is_end_node": node.is_end if node else False,
            "round": e.round,
            "created_at": e.created_at,
        })

    return items


async def get_endorsement_detail(
    db: AsyncSession,
    endorsement_id: int,
    current_user_id: int,
) -> dict:
    """批准详情 —— 含文件、校验/审批进度、签名配置"""
    e = (await db.execute(
        select(Endorsement).where(Endorsement.id == endorsement_id)
    )).scalar_one_or_none()
    if e is None:
        raise AppException(ErrorCode.NOT_FOUND, "批准记录不存在")
    if e.endorser_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "无权查看此批准记录")

    # 查询关联实例
    inst = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == e.instance_id)
    )).scalar_one_or_none()
    if inst is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联项目不存在")

    # 查询节点
    node = (await db.execute(
        select(InstanceNode).where(InstanceNode.id == e.node_id)
    )).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    # 查询 Task
    task = None
    if e.task_id:
        task = (await db.execute(
            select(Task).where(Task.id == e.task_id)
        )).scalar_one_or_none()

    # 查询当前轮次文件
    from app.models import File
    files_result = await db.execute(
        select(File).where(
            File.instance_id == e.instance_id,
            File.node_id == e.node_id,
            File.round == node.round,
        )
    )
    files = files_result.scalars().all()

    # 查询校验/审批记录
    from app.models import CheckRecord, Approval
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

    # 查询节点列表（进度链）
    nodes_result = await db.execute(
        select(InstanceNode).where(
            InstanceNode.instance_id == e.instance_id
        ).order_by(InstanceNode.sort_order)
    )
    all_nodes = nodes_result.scalars().all()

    # 查询用户姓名
    from app.models import User
    endorser_user = (await db.execute(
        select(User).where(User.id == e.endorser_id)
    )).scalar_one_or_none()
    initiator_user = (await db.execute(
        select(User).where(User.id == inst.initiator_id)
    )).scalar_one_or_none()

    # 查询批准人签名图片
    current_signature_url = None
    if endorser_user and endorser_user.signature_path:
        current_signature_url = f"/api/v1/auth/users/{endorser_user.id}/signature-image"

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
        "task_id": e.task_id,
        "endorser_id": e.endorser_id,
        "endorser_name": endorser_user.real_name if endorser_user else "",
        "status": e.status,
        "opinion": e.opinion,
        "round": e.round,
        "require_endorser_signature": node.require_endorser_signature,
        "signature_x": node.signature_x,
        "signature_y": node.signature_y,
        "signature_page": node.signature_page,
        "current_signature_url": current_signature_url,
        "current_node_index": next(
            (i + 1 for i, n in enumerate(all_nodes) if n.id == e.node_id), 0
        ),
        "total_nodes": len(all_nodes),
        "nodes": [{"id": n.id, "name": n.name, "status": n.status, "is_start": n.is_start, "is_end": n.is_end}
                   for n in all_nodes],
        "files": [{"id": f.id, "original_name": f.original_name, "file_size": f.file_size,
                    "round": f.round} for f in files],
        "checks": [{"id": c.id, "checker_id": c.checker_id, "status": c.status,
                     "opinion": c.opinion, "decided_at": c.decided_at} for c in checks],
        "approvals": [{"id": a.id, "approver_id": a.approver_id, "status": a.status,
                       "opinion": a.opinion, "signature_applied": a.signature_applied,
                       "decided_at": a.decided_at} for a in approvals],
        "decided_at": e.decided_at,
        "created_at": e.created_at,
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
    from app.services.notification_service import clear_related
    await clear_related(
        db, user_id=current_user_id, types=["endorsement_assigned"],
    )
    # 保存签名位置（旧版兼容）
    if signature_x is not None:
        e.signature_x = signature_x
    if signature_y is not None:
        e.signature_y = signature_y
    if signature_page is not None:
        e.signature_page = signature_page

    # 4. 保存签名记录
    sig_ids = []
    if signatures:
        for sig in signatures:
            s = Signature(
                file_id=sig.get("file_id"),
                node_id=e.node_id,
                role_type="endorser",
                source_id=e.id,
                user_id=current_user_id,
                signature_x=sig.get("signature_x", 400),
                signature_y=sig.get("signature_y", 100),
                signature_page=sig.get("signature_page", -1),
            )
            db.add(s)
            await db.flush()
            sig_ids.append(s.id)
    elif signature_x is not None:  # 旧版单签名兼容
        s = Signature(
            file_id=None,
            node_id=e.node_id,
            role_type="endorser",
            source_id=e.id,
            user_id=current_user_id,
            signature_x=signature_x,
            signature_y=signature_y or 100,
            signature_page=signature_page or -1,
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

    # 7. 签名上PDF
    if node.require_endorser_signature and sig_ids:
        from app.services.pdf_signature import apply_signatures_to_files
        await apply_signatures_to_files(db, sig_ids)

    e.signature_applied = True

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
        return {"message": "批准通过，项目已完成"}

    # 10. 普通节点 → finished → 传播到下游
    node.status = InstanceNodeStatus.FINISHED
    node.completed_at = now
    await db.flush()

    await propagate_from_node(db, e.instance_id, node.id)
    return {"message": "批准通过，流程已推进到下一节点"}


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
    from app.services.notification_service import clear_related
    await clear_related(
        db, user_id=current_user_id, types=["endorsement_assigned"],
    )

    # 4. 查询节点
    node = await _get_node(db, e.node_id)
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    # 5. 驳回：当前轮次待处理的审批 + 校验 + 批准全部终止
    from app.models import CheckRecord, Approval

    # 终止当前轮次 pending 的 Approval
    await db.execute(
        update(Approval)
        .where(Approval.node_id == e.node_id, Approval.status == ApprovalStatus.PENDING)
        .values(status=ApprovalStatus.TERMINATED)
    )

    # 终止当前轮次 pending 的 CheckRecord
    await db.execute(
        update(CheckRecord)
        .where(CheckRecord.node_id == e.node_id, CheckRecord.status == "pending")
        .values(status="terminated")
    )

    # 6. 删除当前轮文件（DB + 物理文件）
    from app.models import File
    import os
    from app.core.config import settings

    files_result = await db.execute(
        select(File).where(
            File.instance_id == e.instance_id,
            File.node_id == e.node_id,
            File.round == node.round,
        )
    )
    old_files = files_result.scalars().all()
    for f in old_files:
        await db.delete(f)
    await db.flush()
    # 物理文件删除
    for f in old_files:
        try:
            if f.storage_path and os.path.exists(f.storage_path):
                os.remove(f.storage_path)
        except Exception as exc:
            logger.warning("删除旧文件失败: %s", exc)

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
    from app.services.notification_service import create_notification
    if task_for_notify and task_for_notify.assignee_id:
        await create_notification(
            db, user_id=task_for_notify.assignee_id, type="endorsement_rejected",
            title="批准驳回",
            content=f"节点「{node.name}」批准驳回：{opinion}",
            link=f"/profile/task/{task_for_notify.id}",
        )

    return {"message": "已驳回，负责人需重新处理"}


async def _get_node(db: AsyncSession, node_id: int) -> InstanceNode | None:
    """获取节点（内部辅助）"""
    result = await db.execute(
        select(InstanceNode).where(InstanceNode.id == node_id)
    )
    return result.scalar_one_or_none()
