"""审批服务 —— 审批列表、详情、通过（含签名）、退回、终审总驳回"""
import logging
from datetime import datetime

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.services.notification_service import create_notification, clear_related, clear_related_for_users
from app.services.pdf_signature import get_role_signature_defaults, create_signature_records
from app.services.instance._helpers import compute_progress, compute_deadline_info
from app.services.detail_helpers import (
    fetch_users_map, user_name, load_instance_files, serialize_files,
    node_signature_position, signature_image_url,
)
from app.services.file_service import batch_delete_files_with_physical
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
    Endorsement,
)
from app.models.enums import (
    ApprovalStatus,
    TaskStatus,
    InstanceNodeStatus,
    InstanceStatus,
    CheckStatus,
    EndorsementStatus,
    OperatorType,
)
from app.schemas.common import PaginatedData
from app.schemas.approval import ApprovalListItem, ApprovalDetail
from app.engine.flow_engine import propagate_from_node

logger = logging.getLogger(__name__)


async def _get_downstream_nodes_by_edges(
    db: AsyncSession,
    instance_id: int,
    start_node_id: int,
    stop_node_id: int,
) -> list:
    """基于边 BFS 查找 start_node 到 stop_node 之间的下游节点（含 stop_node）

    优化：一次性加载实例所有边到内存，BFS 纯内存遍历，避免 N+1 查询。
    替换 sort_order 区间过滤：修复 fork/join DAG 拓扑中 sort_order 线性排序
    无法正确表达偏序关系导致的死节点问题。
    """
    from collections import deque, defaultdict

    # 一次性加载实例所有边，构建邻接表（源节点 → [目标节点, ...]）
    all_edges = (await db.execute(
        select(InstanceEdge).where(InstanceEdge.instance_id == instance_id)
    )).scalars().all()
    adjacency: dict[int, list[int]] = defaultdict(list)
    for edge in all_edges:
        adjacency[edge.source_node_id].append(edge.target_node_id)

    downstream: list = []
    visited: set[int] = {start_node_id}
    queue: deque[int] = deque()

    # 从 start_node 的直接下游开始
    for target_id in adjacency.get(start_node_id, []):
        if target_id not in visited:
            visited.add(target_id)
            queue.append(target_id)

    while queue:
        nid = queue.popleft()
        if nid == stop_node_id:
            downstream.append(nid)
            continue  # 到达停止节点，不再继续向下遍历

        downstream.append(nid)

        # 继续沿边向下遍历（内存查找，无 DB 调用）
        for target_id in adjacency.get(nid, []):
            if target_id not in visited:
                visited.add(target_id)
                queue.append(target_id)

    return downstream


async def _preserved_upstream_count(
    db: AsyncSession,
    instance_id: int,
    dn: InstanceNode,
    redo_ids: set[int],
) -> int:
    """P0-5：驳回重跑时计算节点应保留的上游到达数

    fork/join 驳回到分支内节点时，兄弟分支不在重做路径、保持 FINISHED 不会重新传播，
    汇合点 arrived_count 若清零则永远等不到兄弟分支信号 → 流程永久悬挂。
    此函数将「非重做路径中已 FINISHED 的直接上游分支」计为已到达。
    非汇合点（incoming_count <= 1）直接返回 0，行为与原来一致。
    """
    if dn.incoming_count <= 1:
        return 0
    upstream_ids = (await db.execute(
        select(InstanceEdge.source_node_id).where(
            InstanceEdge.instance_id == instance_id,
            InstanceEdge.target_node_id == dn.id,
        )
    )).scalars().all()
    if not upstream_ids:
        return 0
    rows = (await db.execute(
        select(InstanceNode.id, InstanceNode.status).where(
            InstanceNode.id.in_(list(upstream_ids))
        )
    )).all()
    return sum(
        1 for rid, st in rows
        if st == InstanceNodeStatus.FINISHED and rid not in redo_ids
    )


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
            select(FlowInstance.id).where(FlowInstance.template_type == instance_type)
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
        node_deadline = node.deadline if node else None
        is_overdue, days_remaining = compute_deadline_info(node_deadline)
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
            deadline=node_deadline.isoformat() if node_deadline else None,
            is_overdue=is_overdue,
            days_remaining=days_remaining,
            created_at=a.created_at,
        ))

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def get_approval_detail(db: AsyncSession, approval_id: int, current_user_id: int) -> dict:
    """审批详情 —— 含文件、校验/审批进度、驳回目标候选

    查询优化：Approval + InstanceNode + FlowInstance 合并为一次 JOIN（3→1）
    """
    # 合并查询：Approval + InstanceNode + FlowInstance（一次 JOIN 替代 3 次独立查询）
    row = (await db.execute(
        select(Approval, InstanceNode, FlowInstance)
        .join(InstanceNode, Approval.node_id == InstanceNode.id)
        .join(FlowInstance, Approval.instance_id == FlowInstance.id)
        .where(Approval.id == approval_id)
    )).first()
    if row is None:
        raise AppException(ErrorCode.NOT_FOUND, "审批记录不存在")
    a, node, inst = row.Approval, row.InstanceNode, row.FlowInstance
    if a.approver_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅审批人可查看")

    # 批量查询相关用户（一次 IN 查询替代 2 次独立查询）
    users_map = await fetch_users_map(db, {a.approver_id, inst.initiator_id})
    approver_user = users_map.get(a.approver_id)
    initiator = users_map.get(inst.initiator_id)

    # 查询实例所有节点（供 ProgressBar 流程进度条使用）
    total_nodes, current_node_index, all_nodes = await compute_progress(db, a.instance_id)

    # 文件 —— 查实例全部文件 + 所属节点名称映射（审批人需了解完整上下文）
    files, file_node_names = await load_instance_files(db, a.instance_id)

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
                "checker_name": user_name(checker_users, c.checker_id),
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
            "approver_name": user_name(approver_users, ap.approver_id),
            "status": ap.status, "opinion": ap.opinion,
            "signature_applied": ap.signature_applied,
            "round": ap.round or 1,
            "decided_at": ap.decided_at.isoformat() if ap.decided_at else None,
        }
        for ap in all_apprs
    ]

    # 驳回目标候选（列出可驳回的历史已完成节点）
    # 终审节点：所有非首尾已执行节点；中间节点：当前节点之前已完成的历史节点
    reject_target_nodes = []
    if node.is_end:
        # 终审：列出所有已执行的非首尾节点
        exec_nodes_result = await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == a.instance_id,
                InstanceNode.is_start == False,
                InstanceNode.is_end == False,
                InstanceNode.status.notin_(["waiting", "terminated"]),
            ).order_by(InstanceNode.sort_order)
        )
    else:
        # 中间节点：列出当前节点之前已完成的工作节点（供审批人选择驳回目标）
        exec_nodes_result = await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == a.instance_id,
                InstanceNode.is_start == False,
                InstanceNode.is_end == False,
                InstanceNode.sort_order < node.sort_order,
                InstanceNode.status == InstanceNodeStatus.FINISHED,
            ).order_by(InstanceNode.sort_order)
        )
    if exec_nodes_result:
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
        difficulty=(inst.difficulty or "1"),  # 难度等级
        node_id=a.node_id,
        node_name=node.name,
        node_description=node.description,
        task_id=a.task_id,
        approver_id=a.approver_id,
        approver_name=approver_user.real_name if approver_user else "",
        status=a.status,
        opinion=a.opinion,
        is_end_node=node.is_end,
        time_limit_days=node.time_limit_days,  # 完成时限
        deadline=node.deadline,  # 截止时间
        round=node.round,  # 当前轮次
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
        files=serialize_files(files, file_node_names, with_upload_meta=True),
        # 仅本节点文件（签批预览用，后端过滤）
        node_files=serialize_files(files, file_node_names, node_id=a.node_id),
        check_progress=check_progress,
        approval_progress=approval_progress,
        reject_target_nodes=reject_target_nodes,
        signature_applied=a.signature_applied,
        # 节点签批配置（三个独立开关 + 默认位置）
        require_assignee_signature=node.require_assignee_signature,
        require_checker_signature=node.require_checker_signature,
        require_approver_signature=node.require_approver_signature,
        **node_signature_position(node),
        # 当前审批人的签名图片 URL
        current_signature_url=signature_image_url(approver_user),
        # 角色维度签名默认配置
        role_signature=await get_role_signature_defaults(db, "approver"),
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

    # ---- 通知清除：审批完成后删除该审批人的待审批通知 (#11) ----

    await clear_related(
        db, user_id=current_user_id, types=["approval_assigned"],
        instance_id=a.instance_id,
    )

    # 兼容旧版：单签名位置参数（直接存 Approval 旧字段）
    if signature_x is not None:
        a.signature_x = signature_x
    if signature_y is not None:
        a.signature_y = signature_y
    if signature_page is not None:
        a.signature_page = signature_page

    # 新版：多签名存入 signatures 表（暂不写 PDF，由 API 层 commit 后统一写入）
    sig_ids: list[int] = []
    _pending_signature_ids: list[int] = []  # post-commit hook 需要用到的签名 ID
    if signatures:
        # 设置 signer_id 后再调用统一 helper
        for sig in signatures:
            sig["signer_id"] = current_user_id
        sig_ids = await create_signature_records(
            db,
            role_type="approver",
            source_id=approval_id,
            node_id=a.node_id,
            signatures=signatures,
        )
    # 兼容旧版：无 signatures 但有单签名位置参数 → 自动生成一条签名记录
    elif signature_x is not None or signature_y is not None or signature_page is not None:
        # 获取审批人的签名位置（旧版模式下，默认签在节点第一个 PDF 上）
        node = (await db.execute(select(InstanceNode).where(InstanceNode.id == a.node_id))).scalar_one_or_none()
        if node is None:
            raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")
        pdf_files = (await db.execute(
            select(File).where(File.node_id == a.node_id, File.round == node.round).limit(1)  # 限定当前轮次
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
        round=a.round,
        description="审批通过" + ("（已签名）" if sig_ids else ""),
    )
    db.add(log)
    await db.flush()

    # 查询节点（审批策略判断需要）
    # P1-19：FOR UPDATE 锁 node 行 —— 与 change_personnel（紧急换人）操作同一 node 时串行化，
    # 消除「换人读旧状态 vs 审批推进节点」的 TOCTOU 竞态窗口。
    node = (await db.execute(
        select(InstanceNode).where(InstanceNode.id == a.node_id).with_for_update()
    )).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    # 审批策略分支：all_approve（默认）等待全部审批；single_approve 一人通过即推进
    if getattr(node, 'approval_strategy', 'all_approve') == 'single_approve':
        # 单人审批通过 → 终止其他 PENDING 审批，直接推进
        # P1-12：先收集被终止审批人，再终止并清除其待办通知
        terminated_approvers = (await db.execute(
            select(Approval.approver_id).where(
                Approval.node_id == a.node_id,
                Approval.task_id == a.task_id,  # 限定当前任务轮次
                Approval.status == ApprovalStatus.PENDING,
                Approval.id != approval_id,
            )
        )).scalars().all()
        await db.execute(
            update(Approval)
            .where(
                Approval.node_id == a.node_id,
                Approval.task_id == a.task_id,  # 限定当前任务轮次
                Approval.status == ApprovalStatus.PENDING,
                Approval.id != approval_id,
            )
            .values(status=ApprovalStatus.TERMINATED, decided_at=now)
        )
        await clear_related_for_users(db, set(terminated_approvers), "approval_assigned", a.instance_id)
    else:
        # 全部通过策略：检查是否还有待审批人员
        # P1-11：限定当前任务（task_id），与 single_approve 分支对齐——
        # 避免跨轮次/跨任务残留的 PENDING 审批被误计入，导致全部已通过仍"等待其他审批人"
        pending_apprs = await db.execute(
            select(Approval).where(
                Approval.node_id == a.node_id,
                Approval.task_id == a.task_id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )
        remaining = pending_apprs.scalars().all()
        if remaining:
            return {"all_approved": False, "message": "审批通过，等待其他审批人", "_pending_sig_ids": _pending_signature_ids}

    # 全部审批通过 → 标记当前节点的 Task 为 completed
    if a.task_id:
        await db.execute(
            update(Task)
            .where(Task.id == a.task_id)
            .values(status=TaskStatus.COMPLETED, completed_at=now)
        )

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
            # 收集签名 ID，由 API 层在 commit 后统一写入 PDF（post-commit hook）
            # 避免 PDF 文件修改在 DB 事务内 → 回滚后 PDF 与 DB 状态不一致
            _pending_signature_ids = [s.id for s in pending_sigs]

        # 兼容旧版：标记 Approval 的旧签名字段
        # P1-11：限定当前任务（task_id），只标当前轮次已通过审批的签名状态，
        # 避免多轮次重跑时把历史轮次的 APPROVED 记录也误标
        # M13 修复：signature_applied 按实际签名记录判定——审批人未上传签名（规则 10 允许跳过）
        # 时不得误标「已签名」，否则界面显示与 PDF 实际状态不符
        await db.execute(
            update(Approval)
            .where(
                Approval.node_id == node.id,
                Approval.task_id == a.task_id,
                Approval.status == ApprovalStatus.APPROVED,
            )
            .values(signature_applied=bool(_pending_signature_ids))
        )
        await db.flush()

    from app.models import FlowTemplate

    # 查询实例，判断是否为方案（方案工作节点审批通过后直接完成，跳过结束节点）
    # M23：完成分支对实例行加锁并校验未终止——防止 terminate 与审批并发时把已终止实例改写为已完成
    inst = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == a.instance_id).with_for_update()
    )).scalar_one_or_none()
    if inst is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联流程实例不存在")
    if (inst.status or "").lower() == "terminated":
        raise AppException(ErrorCode.INSTANCE_ALREADY_TERMINATED, "流程已终止，不可继续操作")
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
        # M12 修复：方案工作节点审批通过直接完成（跳过结束节点）时同样带回待盖章签名 ID，
        # 否则 API 层 post-commit 取空列表 → 审批人签名永不写入 PDF
        return {"all_approved": True, "instance_completed": True, "message": "流程已完成", "_pending_sig_ids": _pending_signature_ids}

    # 难度4 + 有批准人 → 进入批准环节（审核→签字→节点完成）
    if inst.difficulty == "4" and node.endorser_id:
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

        # ---- 通知：批准人有新的待批准任务 (#4) ----

        await create_notification(
            db, user_id=node.endorser_id, type="endorsement_assigned",
            title="新的待批准任务",
            content=f"节点「{node.name}」全部审批通过，等待你批准",
            link=f"/profile/endorse/{endorsement.id}",
            instance_id=a.instance_id,
        )

        return {"all_approved": True, "waiting_endorsement": True, "message": "全部审批通过，等待批准人审核", "_pending_sig_ids": _pending_signature_ids}

    # 普通节点 → finished → 传播到下游
    node.status = InstanceNodeStatus.FINISHED
    node.completed_at = now
    await db.flush()

    # 推进下游节点
    await propagate_from_node(db, a.instance_id, node.id)
    return {"all_approved": True, "message": "全部审批通过，流程已推进到下一节点", "_pending_sig_ids": _pending_signature_ids}


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

    # P1-19：FOR UPDATE 锁 node 行（reject 与 change_personnel 并发时串行化，防 TOCTOU）
    node = (await db.execute(
        select(InstanceNode).where(InstanceNode.id == a.node_id).with_for_update()
    )).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")
    now = datetime.now()

    # ---- 通知清除：审批退回后删除该审批人的待审批通知 (#11) ----

    await clear_related(
        db, user_id=current_user_id, types=["approval_assigned"],
        instance_id=a.instance_id,
    )

    if node.is_end:
        # 结束节点终审总驳回
        if target_node_id is None:
            raise AppException(ErrorCode.BAD_REQUEST, "终审驳回必须指定目标节点")

        target_node = (await db.execute(
            select(InstanceNode).where(InstanceNode.id == target_node_id, InstanceNode.instance_id == a.instance_id)
            .with_for_update()  # 加锁防并发驳回覆盖
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
        target_files_result = await db.execute(
            select(File).where(File.node_id == target_node_id)
        )
        target_files = target_files_result.scalars().all()
        if target_files:
            await batch_delete_files_with_physical(db, list(target_files))

        # 生成新 Task
        if target_node.assignee_id:
            new_task = Task(
                instance_id=a.instance_id,
                node_id=target_node_id,
                assignee_id=target_node.assignee_id,
                status=TaskStatus.PENDING,
            )
            db.add(new_task)

        # 基于边 BFS 查找目标节点到终审节点之间的下游节点
        downstream_node_ids = await _get_downstream_nodes_by_edges(
            db, a.instance_id, target_node_id, node.id,
        )
        if downstream_node_ids:
            downstream_result = await db.execute(
                select(InstanceNode).where(InstanceNode.id.in_(downstream_node_ids))
            )
        else:
            downstream_result = await db.execute(select(InstanceNode).where(False))
        # 批量收集所有下游节点文件 + 终止 Task（一次遍历）
        final_downstream_nodes = list(downstream_result.scalars().all())
        # P0-5：重做集合 = 目标节点 + 其下游（兄弟分支不在此集合，保持已完成计数）
        redo_ids = {target_node.id} | {d.id for d in final_downstream_nodes}
        final_downstream_files: list = []
        for dn in final_downstream_nodes:
            dn_files_result = await db.execute(select(File).where(File.node_id == dn.id))
            dn_files = dn_files_result.scalars().all()
            final_downstream_files.extend(dn_files)
        if final_downstream_files:
            await batch_delete_files_with_physical(db, final_downstream_files)
        for dn in final_downstream_nodes:
            # 终止下游节点未完成的 Task
            await db.execute(
                update(Task).where(
                    Task.node_id == dn.id,
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.WAITING_CHECK, TaskStatus.WAITING_APPROVAL, TaskStatus.WAITING_ENDORSEMENT]),
                ).values(status=TaskStatus.TERMINATED)
            )
            # 重置节点状态（轮次 +1，表示又一次经过此节点）
            dn.round += 1
            dn.status = InstanceNodeStatus.WAITING
            dn.started_at = None
            dn.completed_at = None
            # P0-5：汇合点保留非重做已完成的兄弟分支计数，防驳回后永久卡死
            dn.arrived_count = await _preserved_upstream_count(db, a.instance_id, dn, redo_ids)

        # 终止终审节点其余待审批记录
        # P1-12：先收集被终止审批人，再终止并清除其待办通知
        terminated_approvers = (await db.execute(
            select(Approval.approver_id).where(
                Approval.node_id == a.node_id, Approval.status == ApprovalStatus.PENDING)
        )).scalars().all()
        await db.execute(
            update(Approval)
            .where(Approval.node_id == a.node_id, Approval.status == ApprovalStatus.PENDING)
            .values(status=ApprovalStatus.TERMINATED, decided_at=now)
        )
        await clear_related_for_users(db, set(terminated_approvers), "approval_assigned", a.instance_id)

        # 记录日志
        log = OperationLog(
            instance_id=a.instance_id,
            node_id=a.node_id,
            operator_type=OperatorType.USER,
            operator_id=current_user_id,
            operation_type="final_reject",
            round=a.round,
            description=f"终审总驳回 → {target_node.name}：{opinion}",
        )
        db.add(log)
        await db.flush()

        # ---- 通知：目标节点负责人，终审总驳回需重新处理 (#9) ----

        new_task_id = getattr(new_task, 'id', None) if target_node.assignee_id else None
        if new_task_id:
            await create_notification(
                db, user_id=target_node.assignee_id, type="final_rejected",
                title="终审总驳回",
                content=f"发起人将流程驳回至节点「{target_node.name}」：{opinion}",
                link=f"/profile/task/{new_task_id}",
                instance_id=a.instance_id,
            )

        return {"message": f"已驳回至「{target_node.name}」节点"}

    else:
        # ── 中间节点审批退回 ──
        # 有 target_node_id → 驳回到历史已完成节点
        # 无 target_node_id → 固定退回当前节点负责人（兼容旧行为）
        if target_node_id is not None:
            # ── 驳回到指定历史节点 ──
            target_node = (await db.execute(
                select(InstanceNode).where(
                    InstanceNode.id == target_node_id,
                    InstanceNode.instance_id == a.instance_id,
                ).with_for_update()  # 加锁防并发驳回覆盖
            )).scalar_one_or_none()
            if target_node is None:
                raise AppException(ErrorCode.NOT_FOUND, "目标节点不存在")
            if target_node.is_start or target_node.is_end:
                raise AppException(ErrorCode.BAD_REQUEST, "不可驳回至开始或结束节点")
            if target_node.sort_order >= node.sort_order:
                raise AppException(ErrorCode.BAD_REQUEST, "只能驳回至当前节点之前的历史节点")

            a.status = ApprovalStatus.REJECTED
            a.opinion = opinion
            a.decided_at = now
            a.reject_target_node_id = target_node_id

            # 终止当前节点其他 pending 审批
            # P1-12：先收集被终止人员，再终止并清除其待办通知
            terminated_approvers = (await db.execute(
                select(Approval.approver_id).where(
                    Approval.node_id == a.node_id, Approval.task_id == a.task_id,
                    Approval.status == ApprovalStatus.PENDING)
            )).scalars().all()
            await db.execute(
                update(Approval)
                .where(Approval.node_id == a.node_id, Approval.task_id == a.task_id, Approval.status == ApprovalStatus.PENDING)  # task_id 限定当前轮次
                .values(status=ApprovalStatus.TERMINATED, decided_at=now)
            )
            await clear_related_for_users(db, set(terminated_approvers), "approval_assigned", a.instance_id)
            # 终止当前节点 pending 校验
            terminated_checkers = (await db.execute(
                select(CheckRecord.checker_id).where(
                    CheckRecord.task_id == a.task_id, CheckRecord.status == CheckStatus.PENDING)
            )).scalars().all()
            await db.execute(
                update(CheckRecord)
                .where(CheckRecord.task_id == a.task_id, CheckRecord.status == CheckStatus.PENDING)
                .values(status=CheckStatus.TERMINATED, decided_at=now)
            )
            await clear_related_for_users(db, set(terminated_checkers), "check_assigned", a.instance_id)
            # 终止当前节点 pending 批准（难度4兜底）
            terminated_endorsers = (await db.execute(
                select(Endorsement.endorser_id).where(
                    Endorsement.node_id == a.node_id, Endorsement.status == EndorsementStatus.PENDING)
            )).scalars().all()
            await db.execute(
                update(Endorsement)
                .where(Endorsement.node_id == a.node_id, Endorsement.status == EndorsementStatus.PENDING)
                .values(status=EndorsementStatus.TERMINATED, decided_at=now)
            )
            await clear_related_for_users(db, set(terminated_endorsers), "endorsement_assigned", a.instance_id)
            # 批量删除当前节点当前轮文件（一次 flush，避免 N 次 DB 操作）
            curr_files_result = await db.execute(
                select(File).where(File.node_id == a.node_id, File.round == node.round)
            )
            curr_files = curr_files_result.scalars().all()
            if curr_files:
                await batch_delete_files_with_physical(db, list(curr_files))

            # 重新激活目标节点
            target_node.round += 1
            target_node.status = InstanceNodeStatus.RUNNING
            target_node.started_at = now
            target_node.arrived_count = 0

            # 批量删除目标节点文件
            target_files_result = await db.execute(select(File).where(File.node_id == target_node_id))
            target_files = target_files_result.scalars().all()
            if target_files:
                await batch_delete_files_with_physical(db, list(target_files))

            # 生成新 Task
            new_task = None
            if target_node.assignee_id:
                new_task = Task(
                    instance_id=a.instance_id,
                    node_id=target_node_id,
                    assignee_id=target_node.assignee_id,
                    status=TaskStatus.PENDING,
                )
                db.add(new_task)
                await db.flush()

            # 基于边 BFS 查找目标节点到当前节点之间的下游节点
            downstream_node_ids = await _get_downstream_nodes_by_edges(
                db, a.instance_id, target_node_id, node.id,
            )
            if downstream_node_ids:
                downstream_result = await db.execute(
                    select(InstanceNode).where(InstanceNode.id.in_(downstream_node_ids))
                )
            else:
                downstream_result = await db.execute(select(InstanceNode).where(False))
            # 批量收集所有下游节点 → 一次性删除文件 + 终止 Task
            downstream_nodes = list(downstream_result.scalars().all())
            # P0-5：重做集合 = 目标节点 + 其下游（兄弟分支不在此集合，保持已完成计数）
            redo_ids = {target_node.id} | {d.id for d in downstream_nodes}
            all_downstream_files: list = []
            for dn in downstream_nodes:
                dn_files = (await db.execute(select(File).where(File.node_id == dn.id))).scalars().all()
                all_downstream_files.extend(dn_files)
            if all_downstream_files:
                await batch_delete_files_with_physical(db, all_downstream_files)
            for dn in downstream_nodes:
                await db.execute(
                    update(Task).where(
                        Task.node_id == dn.id,
                        Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.WAITING_CHECK, TaskStatus.WAITING_APPROVAL, TaskStatus.WAITING_ENDORSEMENT]),
                    ).values(status=TaskStatus.TERMINATED)
                )
                dn.round += 1
                dn.status = InstanceNodeStatus.WAITING
                dn.started_at = None
                dn.completed_at = None
                # P0-5：汇合点保留非重做已完成的兄弟分支计数，防驳回后永久卡死
                dn.arrived_count = await _preserved_upstream_count(db, a.instance_id, dn, redo_ids)

            # 日志
            log = OperationLog(
                instance_id=a.instance_id,
                node_id=a.node_id,
                operator_type=OperatorType.USER,
                operator_id=current_user_id,
                operation_type="reject_to_history",
                round=a.round,
                description=f"审批驳回到历史节点「{target_node.name}」：{opinion}",
            )
            db.add(log)
            await db.flush()

            # 通知目标节点负责人
            if target_node.assignee_id and new_task:
                await create_notification(
                    db, user_id=target_node.assignee_id, type="approval_rejected",
                    title="审批驳回",
                    content=f"节点「{node.name}」审批驳回到「{target_node.name}」：{opinion}",
                    link=f"/profile/task/{new_task.id}",
                    instance_id=a.instance_id,
                )

            return {"message": f"已驳回至历史节点「{target_node.name}」"}

        # ── 无目标节点：退回当前节点负责人（原有逻辑）──
        a.status = ApprovalStatus.REJECTED
        a.opinion = opinion
        a.decided_at = now

        # 其余 pending Approval → terminated
        # P1-12：先收集被终止人员，再终止并清除其待办通知
        terminated_approvers = (await db.execute(
            select(Approval.approver_id).where(
                Approval.node_id == a.node_id, Approval.task_id == a.task_id,
                Approval.status == ApprovalStatus.PENDING)
        )).scalars().all()
        await db.execute(
            update(Approval)
            .where(Approval.node_id == a.node_id, Approval.task_id == a.task_id, Approval.status == ApprovalStatus.PENDING)  # task_id 限定当前轮次
            .values(status=ApprovalStatus.TERMINATED, decided_at=now)
        )
        await clear_related_for_users(db, set(terminated_approvers), "approval_assigned", a.instance_id)

        # 终止当前轮次待校验记录（保留历史轮次已决记录）
        terminated_checkers = (await db.execute(
            select(CheckRecord.checker_id).where(
                CheckRecord.task_id == a.task_id, CheckRecord.status == CheckStatus.PENDING)
        )).scalars().all()
        await db.execute(
            update(CheckRecord)
            .where(
                CheckRecord.task_id == a.task_id,
                CheckRecord.status == CheckStatus.PENDING,
            )
            .values(status=CheckStatus.TERMINATED, decided_at=now)
        )
        await clear_related_for_users(db, set(terminated_checkers), "check_assigned", a.instance_id)

        # 终止当前节点 pending 的批准记录（难度4场景，安全兜底）
        terminated_endorsers = (await db.execute(
            select(Endorsement.endorser_id).where(
                Endorsement.node_id == a.node_id,
                Endorsement.status == EndorsementStatus.PENDING,
            )
        )).scalars().all()
        await db.execute(
            update(Endorsement)
            .where(
                Endorsement.node_id == a.node_id,
                Endorsement.status == EndorsementStatus.PENDING,
            )
            .values(status=EndorsementStatus.TERMINATED, decided_at=now)
        )
        await clear_related_for_users(db, set(terminated_endorsers), "endorsement_assigned", a.instance_id)

        # 删除当前轮文件（先DB后物理文件）
        curr_files_result = await db.execute(
            select(File).where(File.node_id == a.node_id, File.round == node.round)
        )
        curr_files = curr_files_result.scalars().all()
        if curr_files:
            await batch_delete_files_with_physical(db, list(curr_files))

        # Node → running, Task → processing，轮次 +1
        task: Task | None = None
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
            round=a.round,
            description=f"审批退回：{opinion}",
        )
        db.add(log)
        await db.flush()

        # ---- 通知：负责人，审批退回需重新处理 (#8) ----

        if task and task.assignee_id:
            await create_notification(
                db, user_id=task.assignee_id, type="approval_rejected",
                title="审批驳回",
                content=f"节点「{node.name}」审批驳回：{opinion}",
                link=f"/profile/task/{task.id}",
                instance_id=a.instance_id,
            )

        return {"message": "已退回，负责人可重新处理"}
