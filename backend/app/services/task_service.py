"""任务服务 —— 待办列表、任务详情、提交、草稿保存"""
from datetime import datetime

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import AppException
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
)
from app.models.enums import TaskStatus, InstanceNodeStatus, CheckStatus, ApprovalStatus
from app.schemas.common import PaginatedData
from app.schemas.task import TaskListItem, TaskDetail


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
        tpl_filter = FlowTemplate.type == instance_type
        conditions.append(Task.instance_id.in_(
            select(FlowInstance.id).where(
                FlowInstance.template_id.in_(
                    select(FlowTemplate.id).where(tpl_filter)
                )
            )
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
    """任务详情 —— 含文件/校验/审批进度聚合"""
    t = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if t is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")

    # 权限校验：仅任务负责人可查看
    if t.assignee_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可查看")

    # 首次打开：pending → processing
    if t.status == TaskStatus.PENDING:
        t.status = TaskStatus.PROCESSING
        await db.flush()

    # 查节点
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == t.node_id))).scalar_one()
    # 查实例
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == t.instance_id))).scalar_one()
    # 查负责人
    assignee = (await db.execute(select(User).where(User.id == t.assignee_id))).scalar_one_or_none()
    # 查发起人
    initiator = (await db.execute(select(User).where(User.id == inst.initiator_id))).scalar_one_or_none()

    # 查询实例所有节点（供 ProgressBar 流程进度条使用）
    all_nodes_result = await db.execute(
        select(InstanceNode)
        .where(InstanceNode.instance_id == t.instance_id)
        .order_by(InstanceNode.sort_order)
    )
    all_nodes = all_nodes_result.scalars().all()
    total_nodes = len(all_nodes)
    current_node_index = sum(
        1 for n in all_nodes
        if (n.status or "").lower() == "finished"
    )

    # 文件
    files_result = await db.execute(
        select(File).where(File.task_id == t.id, File.round == node.round).order_by(File.id.desc())
    )
    files = files_result.scalars().all()

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
        # 优先查审批退回
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

    return TaskDetail(
        id=t.id,
        instance_id=t.instance_id,
        instance_name=inst.name,
        instance_status=inst.status,
        initiator_id=inst.initiator_id,
        initiator_name=initiator.real_name if initiator else "",
        priority=(inst.priority or "normal").lower(),
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
                "mime_type": f.mime_type,  # 文件 MIME 类型（前端判断是否为 PDF）
                "file_size": f.file_size,
                "uploader_name": "",
                "upload_type": f.upload_type,
                "folder_name": f.folder_name,  # 所属文件夹名称
                "round": f.round,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
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
