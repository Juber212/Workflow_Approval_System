"""校验服务 —— 校验列表、详情、通过、退回"""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    CheckRecord,
    Task,
    InstanceNode,
    FlowInstance,
    User,
    File,
    Approval,
    OperationLog,
)
from app.models.enums import CheckStatus, TaskStatus, InstanceNodeStatus, ApprovalStatus, OperatorType
from app.schemas.common import PaginatedData
from app.schemas.check import CheckListItem, CheckDetail


async def list_checks(
    db: AsyncSession,
    *,
    checker_id: int,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """我的校验列表 —— 默认 pending"""
    conditions = [CheckRecord.checker_id == checker_id]
    if status:
        conditions.append(CheckRecord.status == status)
    else:
        conditions.append(CheckRecord.status == CheckStatus.PENDING)

    if keyword:
        inst_ids_sub = select(FlowInstance.id).where(FlowInstance.name.like(f"%{keyword}%"))
        conditions.append(CheckRecord.instance_id.in_(inst_ids_sub))

    base_stmt = select(CheckRecord).where(*conditions)

    count_stmt = select(func.count()).select_from(CheckRecord).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base_stmt.order_by(CheckRecord.created_at.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    checks = result.scalars().all()

    if not checks:
        return PaginatedData(items=[], total=total, page=page, page_size=page_size)

    # 批量查 Task（获取负责人信息）
    task_ids = list(set(c.task_id for c in checks))
    tasks_result = await db.execute(select(Task).where(Task.id.in_(task_ids)))
    tasks_map = {t.id: t for t in tasks_result.scalars().all()}

    node_ids = [n.node_id for n in tasks_map.values()]
    nodes_result = await db.execute(select(InstanceNode).where(InstanceNode.id.in_(node_ids)))
    nodes_map = {n.id: n for n in nodes_result.scalars().all()}

    inst_ids = [n.instance_id for n in tasks_map.values()]
    insts_result = await db.execute(select(FlowInstance).where(FlowInstance.id.in_(inst_ids)))
    insts_map = {i.id: i for i in insts_result.scalars().all()}

    # 负责人
    assignee_ids = list(set(t.assignee_id for t in tasks_map.values()))
    users_result = await db.execute(select(User).where(User.id.in_(assignee_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    items: list[CheckListItem] = []
    for c in checks:
        task = tasks_map.get(c.task_id)
        node = nodes_map.get(task.node_id) if task else None
        inst = insts_map.get(c.instance_id)
        assignee = users_map.get(task.assignee_id) if task else None

        items.append(CheckListItem(
            id=c.id,
            instance_id=c.instance_id,
            instance_name=inst.name if inst else "",
            node_id=c.node_id,
            node_name=node.name if node else "",
            task_id=c.task_id,
            submitter_name=assignee.real_name if assignee else "",
            status=c.status,
            created_at=c.created_at,
        ))

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def get_check_detail(db: AsyncSession, check_id: int, current_user_id: int) -> dict:
    """校验详情 —— 含文件、负责人备注、并行校验进度"""
    c = (await db.execute(select(CheckRecord).where(CheckRecord.id == check_id))).scalar_one_or_none()
    if c is None:
        raise AppException(ErrorCode.NOT_FOUND, "校验记录不存在")
    if c.checker_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅校验人可查看详情")

    task = (await db.execute(select(Task).where(Task.id == c.task_id))).scalar_one()
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == c.node_id))).scalar_one()
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == c.instance_id))).scalar_one()
    checker_user = (await db.execute(select(User).where(User.id == c.checker_id))).scalar_one_or_none()
    # 查发起人 + 提交人（负责人）
    initiator = (await db.execute(select(User).where(User.id == inst.initiator_id))).scalar_one_or_none()
    submitter = (await db.execute(select(User).where(User.id == task.assignee_id))).scalar_one_or_none()

    # 查询实例所有节点（供 ProgressBar 流程进度条使用）
    all_nodes_result = await db.execute(
        select(InstanceNode)
        .where(InstanceNode.instance_id == c.instance_id)
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
        select(File).where(File.task_id == c.task_id, File.round == node.round).order_by(File.id.desc())
    )
    files = files_result.scalars().all()

    # 并行校验进度
    all_checks_result = await db.execute(
        select(CheckRecord).where(CheckRecord.task_id == c.task_id).order_by(CheckRecord.id)
    )
    all_checks = all_checks_result.scalars().all()
    checker_ids = [ac.checker_id for ac in all_checks]
    checker_users = {}
    if checker_ids:
        cu = await db.execute(select(User).where(User.id.in_(checker_ids)))
        checker_users = {u.id: u for u in cu.scalars().all()}

    return CheckDetail(
        id=c.id,
        instance_id=c.instance_id,
        instance_name=inst.name,
        instance_status=inst.status,
        initiator_id=inst.initiator_id,
        initiator_name=initiator.real_name if initiator else "",
        submitter_id=task.assignee_id,
        submitter_name=submitter.real_name if submitter else "",
        priority=(inst.priority or "normal").lower(),
        node_id=c.node_id,
        node_name=node.name,
        task_id=c.task_id,
        checker_id=c.checker_id,
        checker_name=checker_user.real_name if checker_user else "",
        status=c.status,
        opinion=c.opinion,
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
                "file_size": f.file_size,
                "uploader_name": "",
                "upload_type": f.upload_type,
                "round": f.round,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ],
        assignee_note=task.assignee_note,
        check_progress=[
            {
                "id": ac.id,
                "checker_id": ac.checker_id,
                "checker_name": checker_users.get(ac.checker_id).real_name if checker_users.get(ac.checker_id) else "",
                "status": ac.status,
                "opinion": ac.opinion,
                "decided_at": ac.decided_at.isoformat() if ac.decided_at else None,
            }
            for ac in all_checks
        ],
        decided_at=c.decided_at,
        created_at=c.created_at,
    )


async def pass_check(db: AsyncSession, check_id: int, current_user_id: int, opinion: str | None) -> dict:
    """校验通过 —— 检查全部通过后触发审批生成"""
    c = (await db.execute(select(CheckRecord).where(CheckRecord.id == check_id))).scalar_one_or_none()
    if c is None:
        raise AppException(ErrorCode.NOT_FOUND, "校验记录不存在")
    if c.checker_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅校验人可操作")
    if c.status != CheckStatus.PENDING:
        raise AppException(ErrorCode.FORBIDDEN, "仅待校验状态可操作")

    now = datetime.now()
    c.status = CheckStatus.PASSED
    c.opinion = opinion
    c.decided_at = now

    # 记录操作日志
    log = OperationLog(
        instance_id=c.instance_id,
        node_id=c.node_id,
        operator_type=OperatorType.USER,
        operator_id=current_user_id,
        operation_type="check_pass",
        round=c.task_id,
        description=f"校验通过",
    )
    db.add(log)
    await db.flush()

    # 检查当前 task 的全部 CheckRecord 是否都已 passed
    all_pending = await db.execute(
        select(CheckRecord).where(
            CheckRecord.task_id == c.task_id,
            CheckRecord.status == CheckStatus.PENDING,
        )
    )
    has_pending = all_pending.scalars().all()

    if not has_pending:
        # 全部校验通过 → 推进到审批阶段
        task = (await db.execute(select(Task).where(Task.id == c.task_id))).scalar_one()
        node = (await db.execute(select(InstanceNode).where(InstanceNode.id == c.node_id))).scalar_one()

        task.status = TaskStatus.WAITING_APPROVAL
        node.status = InstanceNodeStatus.WAITING_APPROVAL

        # 按 approvers 创建 Approval 记录
        approvers = node.approvers or []
        if approvers:
            for a in approvers:
                approval = Approval(
                    instance_id=c.instance_id,
                    node_id=c.node_id,
                    task_id=c.task_id,
                    approver_id=a.get("user_id") if isinstance(a, dict) else a,  # a 是 int 时即为 user_id
                    status=ApprovalStatus.PENDING,
                )
                db.add(approval)

        await db.flush()
        return {"all_passed": True, "message": "全部校验通过，已进入审批阶段"}

    return {"all_passed": False, "message": "校验通过，等待其他校验人"}


async def return_check(db: AsyncSession, check_id: int, current_user_id: int, opinion: str) -> dict:
    """校验退回 —— 退回当前负责人，删除当前轮文件"""
    if not opinion:
        raise AppException(ErrorCode.BAD_REQUEST, "退回必须填写校验意见")

    c = (await db.execute(select(CheckRecord).where(CheckRecord.id == check_id))).scalar_one_or_none()
    if c is None:
        raise AppException(ErrorCode.NOT_FOUND, "校验记录不存在")
    if c.checker_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅校验人可操作")
    if c.status != CheckStatus.PENDING:
        raise AppException(ErrorCode.FORBIDDEN, "仅待校验状态可操作")

    now = datetime.now()
    c.status = CheckStatus.RETURNED
    c.opinion = opinion
    c.decided_at = now

    # 终止当前 task 的全部校验记录（新轮次重新生成）
    await db.execute(
        update(CheckRecord)
        .where(CheckRecord.task_id == c.task_id)
        .values(status=CheckStatus.TERMINATED, decided_at=now)
    )
    # 当前这条保持 returned（不被覆盖）
    c.status = CheckStatus.RETURNED
    c.opinion = opinion
    c.decided_at = now

    # 删除当前轮文件
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == c.node_id))).scalar_one()
    files = (await db.execute(
        select(File).where(File.task_id == c.task_id, File.round == node.round)
    )).scalars().all()
    for f in files:
        await db.delete(f)

    # Task → processing，Node → running，轮次 +1
    task = (await db.execute(select(Task).where(Task.id == c.task_id))).scalar_one()
    task.status = TaskStatus.PROCESSING
    task.submitted_at = None  # 清除提交时间，标记为退回重做
    node.status = InstanceNodeStatus.RUNNING
    node.round += 1

    # 操作日志
    log = OperationLog(
        instance_id=c.instance_id,
        node_id=c.node_id,
        operator_type=OperatorType.USER,
        operator_id=current_user_id,
        operation_type="check_return",
        round=c.task_id,
        description=f"校验退回：{opinion}",
    )
    db.add(log)
    await db.flush()

    return {"message": "已退回，负责人可重新处理"}
