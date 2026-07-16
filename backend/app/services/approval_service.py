"""审批服务 —— 审批列表、详情、通过（含签名）、退回、终审总驳回"""
import os
from datetime import datetime

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    Approval,
    Task,
    InstanceNode,
    InstanceEdge,
    FlowInstance,
    User,
    File,
    CheckRecord,
    OperationLog,
)
from app.models.enums import (
    ApprovalStatus,
    TaskStatus,
    InstanceNodeStatus,
    InstanceStatus,
    CheckStatus,
    OperatorType,
)
from app.engine.flow_engine import propagate_from_node


async def list_approvals(
    db: AsyncSession,
    *,
    approver_id: int,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """我的审批列表 —— 默认 pending"""
    conditions = [Approval.approver_id == approver_id]
    if status:
        conditions.append(Approval.status == status)
    else:
        conditions.append(Approval.status == ApprovalStatus.PENDING)

    if keyword:
        inst_ids_sub = select(FlowInstance.id).where(FlowInstance.name.like(f"%{keyword}%"))
        conditions.append(Approval.instance_id.in_(inst_ids_sub))

    base_stmt = select(Approval).where(*conditions)

    count_stmt = select(func.count()).select_from(Approval).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base_stmt.order_by(Approval.created_at.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    approvals = result.scalars().all()

    if not approvals:
        return {"items": [], "total": total, "page": page, "page_size": page_size}

    # 批量查关联数据
    node_ids = list(set(a.node_id for a in approvals))
    nodes_result = await db.execute(select(InstanceNode).where(InstanceNode.id.in_(node_ids)))
    nodes_map = {n.id: n for n in nodes_result.scalars().all()}

    inst_ids = list(set(a.instance_id for a in approvals))
    insts_result = await db.execute(select(FlowInstance).where(FlowInstance.id.in_(inst_ids)))
    insts_map = {i.id: i for i in insts_result.scalars().all()}

    items = []
    for a in approvals:
        node = nodes_map.get(a.node_id)
        inst = insts_map.get(a.instance_id)
        items.append({
            "id": a.id,
            "instance_id": a.instance_id,
            "instance_name": inst.name if inst else "",
            "node_id": a.node_id,
            "node_name": node.name if node else "",
            "task_id": a.task_id,
            "approver_id": a.approver_id,
            "status": a.status,
            "is_end_node": node.is_end if node else False,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_approval_detail(db: AsyncSession, approval_id: int, current_user_id: int) -> dict:
    """审批详情 —— 含文件、校验/审批进度、驳回目标候选"""
    a = (await db.execute(select(Approval).where(Approval.id == approval_id))).scalar_one_or_none()
    if a is None:
        raise AppException(ErrorCode.NOT_FOUND, "审批记录不存在")
    if a.approver_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅审批人可查看")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one()
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == a.instance_id))).scalar_one()
    approver_user = (await db.execute(select(User).where(User.id == a.approver_id))).scalar_one_or_none()
    # 查发起人
    initiator = (await db.execute(select(User).where(User.id == inst.initiator_id))).scalar_one_or_none()

    # 查询实例所有节点（供 ProgressBar 流程进度条使用）
    all_nodes_result = await db.execute(
        select(InstanceNode)
        .where(InstanceNode.instance_id == a.instance_id)
        .order_by(InstanceNode.sort_order)
    )
    all_nodes = all_nodes_result.scalars().all()
    total_nodes = len(all_nodes)
    current_node_index = sum(
        1 for n in all_nodes
        if (n.status or "").lower() == "finished"
    )

    # 文件（终审节点查看流程全部文件，普通节点只看本节点文件）
    if node.is_end:
        files_result = await db.execute(
            select(File).where(File.instance_id == a.instance_id).order_by(File.id.desc())
        )
    else:
        files_result = await db.execute(
            select(File).where(File.node_id == a.node_id).order_by(File.id.desc())
        )
    files = files_result.scalars().all()

    # 批量查询文件所属节点名称
    file_node_ids = [f.node_id for f in files if f.node_id]
    file_node_names: dict[int, str] = {}
    if file_node_ids:
        fn_result = await db.execute(
            select(InstanceNode.id, InstanceNode.name).where(InstanceNode.id.in_(file_node_ids))
        )
        file_node_names = {row[0]: row[1] for row in fn_result.all()}

    # 校验进度
    if a.task_id:
        checks_result = await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == a.task_id).order_by(CheckRecord.id)
        )
        checks = checks_result.scalars().all()
        checker_ids = [c.checker_id for c in checks]
        checker_users = {}
        if checker_ids:
            cu = await db.execute(select(User).where(User.id.in_(checker_ids)))
            checker_users = {u.id: u for u in cu.scalars().all()}
        check_progress = [
            {
                "id": c.id, "checker_id": c.checker_id,
                "checker_name": checker_users.get(c.checker_id).real_name if checker_users.get(c.checker_id) else "",
                "status": c.status, "opinion": c.opinion,
                "decided_at": c.decided_at.isoformat() if c.decided_at else None,
            }
            for c in checks
        ]
    else:
        check_progress = []

    # 审批进度
    all_apprs_result = await db.execute(
        select(Approval).where(Approval.node_id == a.node_id).order_by(Approval.id)
    )
    all_apprs = all_apprs_result.scalars().all()
    approver_ids = [ap.approver_id for ap in all_apprs]
    approver_users = {}
    if approver_ids:
        au = await db.execute(select(User).where(User.id.in_(approver_ids)))
        approver_users = {u.id: u for u in au.scalars().all()}
    approval_progress = [
        {
            "id": ap.id, "approver_id": ap.approver_id,
            "approver_name": approver_users.get(ap.approver_id).real_name if approver_users.get(ap.approver_id) else "",
            "status": ap.status, "opinion": ap.opinion,
            "signature_applied": ap.signature_applied,
            "decided_at": ap.decided_at.isoformat() if ap.decided_at else None,
        }
        for ap in all_apprs
    ]

    # 驳回目标候选（仅结束节点审批，列出已执行的中间工作节点）
    reject_target_nodes = []
    if node.is_end:
        exec_nodes_result = await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == a.instance_id,
                InstanceNode.is_start == False,
                InstanceNode.is_end == False,
                InstanceNode.status.notin_(["waiting", "terminated"]),
            ).order_by(InstanceNode.sort_order)
        )
        reject_target_nodes = [
            {"id": n.id, "name": n.name, "sort_order": n.sort_order, "status": n.status}
            for n in exec_nodes_result.scalars().all()
        ]

    return {
        "id": a.id,
        "instance_id": a.instance_id,
        "instance_name": inst.name,
        "instance_status": inst.status,
        "initiator_id": inst.initiator_id,
        "initiator_name": initiator.real_name if initiator else "",
        "priority": (inst.priority or "normal").lower(),
        "node_id": a.node_id,
        "node_name": node.name,
        "node_description": node.description,
        "task_id": a.task_id,
        "approver_id": a.approver_id,
        "approver_name": approver_user.real_name if approver_user else "",
        "status": a.status,
        "opinion": a.opinion,
        "is_end_node": node.is_end,
        "total_nodes": total_nodes,
        "current_node_index": current_node_index,
        "nodes": [
            {
                "id": n.id, "name": n.name,
                "is_start": n.is_start, "is_end": n.is_end,
                "status": (n.status or "waiting").lower(),
                "sort_order": n.sort_order,
            }
            for n in all_nodes
        ],
        "files": [
            {
                "id": f.id, "original_name": f.original_name,
                "file_size": f.file_size,
                "node_id": f.node_id,
                "node_name": file_node_names.get(f.node_id, "") if f.node_id else "",
                "uploader_name": "", "upload_type": f.upload_type,
                "round": f.round,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ],
        "check_progress": check_progress,
        "approval_progress": approval_progress,
        "reject_target_nodes": reject_target_nodes,
        "signature_applied": a.signature_applied,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


async def approve(db: AsyncSession, approval_id: int, current_user_id: int, opinion: str | None) -> dict:
    """审批通过 —— 含签名处理 + 流程推进"""
    a = (await db.execute(select(Approval).where(Approval.id == approval_id))).scalar_one_or_none()
    if a is None:
        raise AppException(ErrorCode.NOT_FOUND, "审批记录不存在")
    if a.approver_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅审批人可操作")
    if a.status != ApprovalStatus.PENDING:
        raise AppException(ErrorCode.FORBIDDEN, "仅待审批状态可操作")

    now = datetime.now()
    a.status = ApprovalStatus.APPROVED
    a.opinion = opinion
    a.decided_at = now

    # 操作日志
    log = OperationLog(
        instance_id=a.instance_id,
        node_id=a.node_id,
        operator_type=OperatorType.USER,
        operator_id=current_user_id,
        operation_type="approve",
        round=a.task_id or 0,
        description="审批通过" + (f"（已签名）" if a.signature_applied else ""),
    )
    db.add(log)
    await db.flush()

    # 检查当前 node 的全部 Approval 是否都已 approved
    pending_apprs = await db.execute(
        select(Approval).where(
            Approval.node_id == a.node_id,
            Approval.status == ApprovalStatus.PENDING,
        )
    )
    if pending_apprs.scalars().all():
        return {"all_approved": False, "message": "审批通过，等待其他审批人"}

    # 全部审批通过 → 标记当前节点的 Task 为 completed
    if a.task_id:
        await db.execute(
            update(Task)
            .where(Task.id == a.task_id)
            .values(status=TaskStatus.COMPLETED, completed_at=now)
        )

    # 全部审批通过 → 签名上 PDF → 推进流程
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one()

    # 实际签名插入：将审批人签名图片写入节点 PDF 文件
    from app.services.pdf_signature import apply_signatures_to_node_pdfs
    signed_count = await apply_signatures_to_node_pdfs(db, node.id)
    if signed_count > 0:
        # 标记签名已应用
        await db.execute(
            update(Approval)
            .where(Approval.node_id == node.id, Approval.status == ApprovalStatus.APPROVED)
            .values(signature_applied=True)
        )
    await db.flush()

    if node.is_end:
        # 结束节点 → 流程完成，同步归档（V1 完成即归档）
        node.status = InstanceNodeStatus.FINISHED
        node.completed_at = now
        inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == a.instance_id))).scalar_one()
        inst.status = InstanceStatus.COMPLETED
        inst.completed_at = now
        inst.archive_status = "archived"
        inst.archived_at = now
        return {"all_approved": True, "instance_completed": True, "message": "流程已完成"}

    # 普通节点 → finished → 传播到下游
    node.status = InstanceNodeStatus.FINISHED
    node.completed_at = now
    await db.flush()

    # 推进下游节点
    await propagate_from_node(db, a.instance_id, node.id)
    return {"all_approved": True, "message": "全部审批通过，流程已推进到下一节点"}


async def reject(
    db: AsyncSession,
    approval_id: int,
    current_user_id: int,
    opinion: str,
    target_node_id: int | None = None,
) -> dict:
    """审批退回 —— 中间节点固定退回负责人，结束节点总驳回可指定目标"""
    if not opinion:
        raise AppException(ErrorCode.BAD_REQUEST, "退回必须填写审批意见")

    a = (await db.execute(select(Approval).where(Approval.id == approval_id))).scalar_one_or_none()
    if a is None:
        raise AppException(ErrorCode.NOT_FOUND, "审批记录不存在")
    if a.approver_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅审批人可操作")
    if a.status != ApprovalStatus.PENDING:
        raise AppException(ErrorCode.FORBIDDEN, "仅待审批状态可操作")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one()
    now = datetime.now()

    if node.is_end:
        # 结束节点终审总驳回
        if target_node_id is None:
            raise AppException(ErrorCode.BAD_REQUEST, "终审驳回必须指定目标节点")

        target_node = (await db.execute(
            select(InstanceNode).where(InstanceNode.id == target_node_id, InstanceNode.instance_id == a.instance_id)
        )).scalar_one_or_none()
        if target_node is None:
            raise AppException(ErrorCode.NOT_FOUND, "目标节点不存在")
        if target_node.is_start or target_node.is_end:
            raise AppException(ErrorCode.BAD_REQUEST, "不可驳回至开始或结束节点")

        a.status = ApprovalStatus.REJECTED
        a.opinion = opinion
        a.decided_at = now
        a.reject_target_node_id = target_node_id

        # 目标节点重新激活（round + 1）
        target_node.round += 1
        target_node.status = InstanceNodeStatus.RUNNING
        target_node.started_at = now
        target_node.arrived_count = 0

        # 删除目标节点当前文件
        target_files = await db.execute(
            select(File).where(File.node_id == target_node_id)
        )
        for f in target_files.scalars().all():
            abs_path = os.path.join(settings.STORAGE_ROOT, f.file_path) if not os.path.isabs(f.file_path) else f.file_path
            if os.path.exists(abs_path):
                os.remove(abs_path)
            await db.delete(f)

        # 生成新 Task
        if target_node.assignee_id:
            new_task = Task(
                instance_id=a.instance_id,
                node_id=target_node_id,
                assignee_id=target_node.assignee_id,
                status=TaskStatus.PENDING,
            )
            db.add(new_task)

        # 记录日志
        log = OperationLog(
            instance_id=a.instance_id,
            node_id=a.node_id,
            operator_type=OperatorType.USER,
            operator_id=current_user_id,
            operation_type="final_reject",
            round=0,
            description=f"终审总驳回 → {target_node.name}：{opinion}",
        )
        db.add(log)
        await db.flush()
        return {"message": f"已驳回至「{target_node.name}」节点"}

    else:
        # 中间节点审批退回：固定退回当前负责人
        a.status = ApprovalStatus.REJECTED
        a.opinion = opinion
        a.decided_at = now

        # 其余 pending Approval → terminated
        await db.execute(
            update(Approval)
            .where(Approval.node_id == a.node_id, Approval.status == ApprovalStatus.PENDING)
            .values(status=ApprovalStatus.TERMINATED, decided_at=now)
        )

        # 终止全部校验记录（新轮次重新生成）
        await db.execute(
            update(CheckRecord)
            .where(CheckRecord.task_id == a.task_id)
            .values(status=CheckStatus.TERMINATED, decided_at=now)
        )

        # 删除当前轮文件
        curr_files = await db.execute(
            select(File).where(File.node_id == a.node_id, File.round == node.round)
        )
        for f in curr_files.scalars().all():
            abs_path = os.path.join(settings.STORAGE_ROOT, f.file_path) if not os.path.isabs(f.file_path) else f.file_path
            if os.path.exists(abs_path):
                os.remove(abs_path)
            await db.delete(f)

        # Node → running, Task → processing，轮次 +1
        node.status = InstanceNodeStatus.RUNNING
        node.round += 1
        if a.task_id:
            task = (await db.execute(select(Task).where(Task.id == a.task_id))).scalar_one_or_none()
            if task:
                task.status = TaskStatus.PROCESSING
                task.submitted_at = None  # 清除提交时间，标记为退回重做

        log = OperationLog(
            instance_id=a.instance_id,
            node_id=a.node_id,
            operator_type=OperatorType.USER,
            operator_id=current_user_id,
            operation_type="reject",
            round=a.task_id or 0,
            description=f"审批退回：{opinion}",
        )
        db.add(log)
        await db.flush()
        return {"message": "已退回，负责人可重新处理"}
