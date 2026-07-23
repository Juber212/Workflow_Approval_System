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
    FlowTemplate,
    User,
    File,
    CheckRecord,
    OperationLog,
    Signature,
)
from app.models.enums import (
    ApprovalStatus,
    TaskStatus,
    InstanceNodeStatus,
    InstanceStatus,
    CheckStatus,
    OperatorType,
)
from app.schemas.common import PaginatedData
from app.schemas.approval import ApprovalListItem, ApprovalDetail
from app.engine.flow_engine import propagate_from_node


async def list_approvals(
    db: AsyncSession,
    *,
    approver_id: int,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    instance_type: str | None = None,  # "project" 或 "proposal"
) -> dict:
    """我的审批列表 —— 默认 pending"""
    conditions = [Approval.approver_id == approver_id]

    # 按实例类型过滤
    if instance_type:
        conditions.append(Approval.instance_id.in_(
            select(FlowInstance.id).where(
                FlowInstance.template_id.in_(
                    select(FlowTemplate.id).where(FlowTemplate.type == instance_type)
                )
            )
        ))
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
        return PaginatedData(items=[], total=total, page=page, page_size=page_size)

    # 批量查关联数据
    node_ids = list(set(a.node_id for a in approvals))
    nodes_result = await db.execute(select(InstanceNode).where(InstanceNode.id.in_(node_ids)))
    nodes_map = {n.id: n for n in nodes_result.scalars().all()}

    inst_ids = list(set(a.instance_id for a in approvals))
    insts_result = await db.execute(select(FlowInstance).where(FlowInstance.id.in_(inst_ids)))
    insts_map = {i.id: i for i in insts_result.scalars().all()}

    items: list[ApprovalListItem] = []
    for a in approvals:
        node = nodes_map.get(a.node_id)
        inst = insts_map.get(a.instance_id)
        items.append(ApprovalListItem(
            id=a.id,
            instance_id=a.instance_id,
            instance_name=inst.name if inst else "",
            node_id=a.node_id,
            node_name=node.name if node else "",
            task_id=a.task_id,
            approver_id=a.approver_id,
            status=a.status,
            is_end_node=node.is_end if node else False,
            round=a.round or 1,
            created_at=a.created_at,
        ))

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def get_approval_detail(db: AsyncSession, approval_id: int, current_user_id: int) -> dict:
    """审批详情 —— 含文件、校验/审批进度、驳回目标候选"""
    a = (await db.execute(select(Approval).where(Approval.id == approval_id))).scalar_one_or_none()
    if a is None:
        raise AppException(ErrorCode.NOT_FOUND, "审批记录不存在")
    if a.approver_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅审批人可查看")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == a.instance_id))).scalar_one_or_none()
    if inst is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联流程实例不存在")
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

    # 校验进度（排除被系统终止的记录）
    if a.task_id:
        checks_result = await db.execute(
            select(CheckRecord).where(
                CheckRecord.task_id == a.task_id,
                CheckRecord.status != CheckStatus.TERMINATED,
            ).order_by(CheckRecord.id)
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
                "round": c.round or 1,
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
            "round": ap.round or 1,
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

    return ApprovalDetail(
        id=a.id,
        instance_id=a.instance_id,
        instance_name=inst.name,
        instance_status=inst.status,
        initiator_id=inst.initiator_id,
        initiator_name=initiator.real_name if initiator else "",
        priority=(inst.priority or "normal").lower(),
        node_id=a.node_id,
        node_name=node.name,
        node_description=node.description,
        task_id=a.task_id,
        approver_id=a.approver_id,
        approver_name=approver_user.real_name if approver_user else "",
        status=a.status,
        opinion=a.opinion,
        is_end_node=node.is_end,
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
                "id": f.id, "original_name": f.original_name,
                "mime_type": f.mime_type,  # 文件 MIME 类型（前端判断是否为 PDF）
                "file_size": f.file_size,
                "node_id": f.node_id,
                "node_name": file_node_names.get(f.node_id, "") if f.node_id else "",
                "uploader_name": "", "upload_type": f.upload_type,
                "round": f.round,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ],
        check_progress=check_progress,
        approval_progress=approval_progress,
        reject_target_nodes=reject_target_nodes,
        signature_applied=a.signature_applied,
        # 节点签批配置（三个独立开关 + 默认位置）
        require_assignee_signature=node.require_assignee_signature,
        require_checker_signature=node.require_checker_signature,
        require_approver_signature=node.require_approver_signature,
        signature_x=node.signature_x,
        signature_y=node.signature_y,
        signature_page=node.signature_page,
        # 当前审批人的签名图片 URL
        current_signature_url=f"/api/v1/auth/users/{a.approver_id}/signature-image" if approver_user and approver_user.signature_image else None,
        # 本审批记录的签名明细（从 signatures 表获取）
        signatures=[
            {
                "id": s.id, "file_id": s.file_id,
                "signature_x": s.signature_x, "signature_y": s.signature_y,
                "signature_page": s.signature_page,
                "signature_width": s.signature_width, "signature_height": s.signature_height,
                "applied": s.applied,
            }
            for s in (await db.execute(
                select(Signature).where(
                    Signature.source_id == approval_id,
                    Signature.role_type == "approver",
                )
            )).scalars().all()
        ],
        decided_at=a.decided_at,
        created_at=a.created_at,
    )


async def approve(db: AsyncSession, approval_id: int, current_user_id: int, opinion: str | None, signatures: list[dict] | None = None, signature_x: float | None = None, signature_y: float | None = None, signature_page: int | None = None) -> dict:
    """审批通过 —— 含签名处理 + 流程推进

    并发安全：先锁定目标行再校验，消除 TOCTOU 窗口。
    """
    # 先锁定目标审批行（SELECT ... FOR UPDATE —— 校验和锁原子化）
    a = (await db.execute(
        select(Approval).where(Approval.id == approval_id).with_for_update()
    )).scalar_one_or_none()
    if a is None:
        raise AppException(ErrorCode.NOT_FOUND, "审批记录不存在")
    if a.approver_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅审批人可操作")
    if a.status != ApprovalStatus.PENDING:
        raise AppException(ErrorCode.FORBIDDEN, "仅待审批状态可操作")

    # 锁定本节点其他待审批行（防并发——确保只有一个事务能操作本节点的审批）
    await db.execute(
        select(Approval).where(
            Approval.node_id == a.node_id,
            Approval.status == ApprovalStatus.PENDING,
            Approval.id != approval_id,
        ).with_for_update()
    )

    now = datetime.now()
    a.status = ApprovalStatus.APPROVED
    a.opinion = opinion
    a.decided_at = now

    # 兼容旧版：单签名位置参数（直接存 Approval 旧字段）
    if signature_x is not None:
        a.signature_x = signature_x
    if signature_y is not None:
        a.signature_y = signature_y
    if signature_page is not None:
        a.signature_page = signature_page

    # 新版：多签名存入 signatures 表（暂不写 PDF，等全部审批通过后批量写入）
    sig_ids: list[int] = []
    if signatures:
        for idx, sig in enumerate(signatures):
            sig_record = Signature(
                file_id=sig["file_id"],
                signer_id=current_user_id,
                role_type="approver",
                source_id=approval_id,
                node_id=a.node_id,
                signature_x=sig.get("signature_x", 400),
                signature_y=sig.get("signature_y", 100),
                signature_page=sig.get("signature_page", -1),
                signature_width=sig.get("signature_width"),
                signature_height=sig.get("signature_height"),
                applied=False,
                sort_order=idx,
            )
            db.add(sig_record)
            await db.flush()
            sig_ids.append(sig_record.id)
    # 兼容旧版：无 signatures 但有单签名位置参数 → 自动生成一条签名记录
    elif signature_x is not None or signature_y is not None or signature_page is not None:
        # 获取审批人的签名位置（旧版模式下，默认签在节点第一个 PDF 上）
        node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one_or_none()
        if node is None:
            raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")
        pdf_files = (await db.execute(
            select(File).where(File.node_id == a.node_id).limit(1)
        )).scalars().all()
        if pdf_files:
            sig_record = Signature(
                file_id=pdf_files[0].id,
                signer_id=current_user_id,
                role_type="approver",
                source_id=approval_id,
                node_id=a.node_id,
                signature_x=signature_x if signature_x is not None else node.signature_x,
                signature_y=signature_y if signature_y is not None else node.signature_y,
                signature_page=signature_page if signature_page is not None else node.signature_page,
                signature_width=None,
                signature_height=None,
                applied=False,
                sort_order=0,
            )
            db.add(sig_record)
            await db.flush()
            sig_ids.append(sig_record.id)

    # 操作日志
    log = OperationLog(
        instance_id=a.instance_id,
        node_id=a.node_id,
        operator_type=OperatorType.USER,
        operator_id=current_user_id,
        operation_type="approve",
        round=a.task_id or 0,
        description="审批通过" + ("（已签名）" if sig_ids else ""),
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
    remaining = pending_apprs.scalars().all()
    if remaining:
        return {"all_approved": False, "message": "审批通过，等待其他审批人"}

    # 全部审批通过 → 标记当前节点的 Task 为 completed
    if a.task_id:
        await db.execute(
            update(Task)
            .where(Task.id == a.task_id)
            .values(status=TaskStatus.COMPLETED, completed_at=now)
        )

    # 全部审批通过 → 签名上 PDF → 推进流程
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    # 签批：终审节点跳过 PDF 盖章（终审只需确认文件齐全即可归档）
    if not node.is_end and node.require_approver_signature:
        pending_sigs_result = await db.execute(
            select(Signature).where(
                Signature.node_id == node.id,
                Signature.role_type == "approver",
                Signature.applied == False,
            )
        )
        pending_sigs = pending_sigs_result.scalars().all()
        if pending_sigs:
            from app.services.pdf_signature import apply_signatures_to_files
            await apply_signatures_to_files(db, [s.id for s in pending_sigs])

        # 兼容旧版：标记 Approval 的旧签名字段
        await db.execute(
            update(Approval)
            .where(Approval.node_id == node.id, Approval.status == ApprovalStatus.APPROVED)
            .values(signature_applied=True)
        )
        await db.flush()

    from app.models import FlowTemplate

    # 查询实例，判断是否为方案（方案工作节点审批通过后直接完成，跳过结束节点）
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == a.instance_id))).scalar_one_or_none()
    if inst is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联流程实例不存在")
    is_proposal = False
    if not node.is_end:
        tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == inst.template_id))).scalar_one_or_none()
        is_proposal = tpl is not None and tpl.type == "proposal"

    if node.is_end or is_proposal:
        # 结束节点 → 流程完成
        # 方案工作节点全部审批通过 → 直接完成（跳过结束节点终审）
        node.status = InstanceNodeStatus.FINISHED
        node.completed_at = now
        inst.status = InstanceStatus.COMPLETED
        inst.completed_at = now
        return {"all_approved": True, "instance_completed": True, "message": "流程已完成"}

    # 难度4 + 有批准人 → 进入批准环节（审核→签字→节点完成）
    if inst.difficulty == "4" and node.endorser_id:
        from app.models.endorsement import Endorsement
        from app.models.enums import EndorsementStatus
        endorsement = Endorsement(
            instance_id=a.instance_id,
            node_id=a.node_id,
            task_id=a.task_id,
            endorser_id=node.endorser_id,
            status=EndorsementStatus.PENDING,
            round=node.round,
        )
        db.add(endorsement)
        # 更新 Task 和 Node 状态为等待批准
        if a.task_id:
            await db.execute(
                update(Task)
                .where(Task.id == a.task_id)
                .values(status=TaskStatus.WAITING_ENDORSEMENT)
            )
        node.status = InstanceNodeStatus.WAITING_ENDORSEMENT
        return {"all_approved": True, "waiting_endorsement": True, "message": "全部审批通过，等待批准人审核"}

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
    """审批退回 —— 中间节点固定退回负责人，结束节点总驳回可指定目标

    并发安全：FOR UPDATE 锁定目标行，防止并发驳回导致状态混乱。
    """
    if not opinion:
        raise AppException(ErrorCode.BAD_REQUEST, "退回必须填写审批意见")

    a = (await db.execute(
        select(Approval).where(Approval.id == approval_id).with_for_update()
    )).scalar_one_or_none()
    if a is None:
        raise AppException(ErrorCode.NOT_FOUND, "审批记录不存在")
    if a.approver_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅审批人可操作")
    if a.status != ApprovalStatus.PENDING:
        raise AppException(ErrorCode.FORBIDDEN, "仅待审批状态可操作")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")
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

        # 删除目标节点当前文件（先DB后物理文件，避免事务回滚后物理文件丢失）
        target_files = await db.execute(
            select(File).where(File.node_id == target_node_id)
        )
        for f in target_files.scalars().all():
            abs_path = os.path.join(settings.STORAGE_ROOT, f.file_path) if not os.path.isabs(f.file_path) else f.file_path
            await db.delete(f)
            try:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except OSError as e:
                logger = __import__('logging').getLogger(__name__)
                logger.warning(f"[审批退回] 物理文件删除失败: {abs_path}, err={e}")

        # 生成新 Task
        if target_node.assignee_id:
            new_task = Task(
                instance_id=a.instance_id,
                node_id=target_node_id,
                assignee_id=target_node.assignee_id,
                status=TaskStatus.PENDING,
            )
            db.add(new_task)

        # 重置目标节点之后、终审节点（含）的所有下游节点为 waiting
        downstream_result = await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == a.instance_id,
                InstanceNode.sort_order > target_node.sort_order,
                InstanceNode.sort_order <= node.sort_order,
            ).order_by(InstanceNode.sort_order)
        )
        for dn in downstream_result.scalars().all():
            # 删除下游节点文件（先DB后物理文件）
            dn_files = await db.execute(select(File).where(File.node_id == dn.id))
            for f in dn_files.scalars().all():
                abs_path = os.path.join(settings.STORAGE_ROOT, f.file_path) if not os.path.isabs(f.file_path) else f.file_path
                await db.delete(f)
                try:
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                except OSError:
                    pass
            # 终止下游节点未完成的 Task
            await db.execute(
                update(Task).where(
                    Task.node_id == dn.id,
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.WAITING_CHECK, TaskStatus.WAITING_APPROVAL]),
                ).values(status=TaskStatus.TERMINATED)
            )
            # 重置节点状态（轮次 +1，表示又一次经过此节点）
            dn.round += 1
            dn.status = InstanceNodeStatus.WAITING
            dn.started_at = None
            dn.completed_at = None

        # 终止终审节点其余待审批记录
        await db.execute(
            update(Approval)
            .where(Approval.node_id == a.node_id, Approval.status == ApprovalStatus.PENDING)
            .values(status=ApprovalStatus.TERMINATED, decided_at=now)
        )

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

        # 终止当前轮次待校验记录（保留历史轮次已决记录）
        await db.execute(
            update(CheckRecord)
            .where(
                CheckRecord.task_id == a.task_id,
                CheckRecord.status == CheckStatus.PENDING,
            )
            .values(status=CheckStatus.TERMINATED, decided_at=now)
        )

        # 删除当前轮文件（先DB后物理文件）
        curr_files = await db.execute(
            select(File).where(File.node_id == a.node_id, File.round == node.round)
        )
        for f in curr_files.scalars().all():
            abs_path = os.path.join(settings.STORAGE_ROOT, f.file_path) if not os.path.isabs(f.file_path) else f.file_path
            await db.delete(f)
            try:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except OSError:
                pass

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
