"""终止项目服务"""

from datetime import datetime

from ._helpers import _get_type_label

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.services.notification_service import create_notification, clear_related
from app.services.file_service import batch_delete_files_with_physical
from app.models import (
    FlowInstance, InstanceNode,
    OperationLog,
    Task, CheckRecord, Approval, Endorsement, File,
)
from app.models.enums import ApprovalStatus, CheckStatus, EndorsementStatus
from app.api.deps import CurrentUser



async def terminate_instance(
    db: AsyncSession,
    instance_id: int,
    reason: str,
    current_user: CurrentUser,
) -> dict:
    """终止项目 —— 级联关闭所有关联记录并物理删除文件

    处理步骤：
    1. 校验实例存在 + 发起人权限 + 未已终止
    2. 物理删除磁盘文件 + 删除 files 记录
    3. 级联关闭：非终态 node/task → terminated, pending check/approval → terminated
    4. 更新实例状态为 terminated
    5. 记录操作日志
    """
    # ========== 1. 查询实例 ==========
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id).with_for_update()
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()

    if not instance:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")

    # ========== 2. 校验发起人权限 ==========
    if instance.initiator_id != current_user.id:
        type_label = await _get_type_label(db, instance.template_id)
        raise AppException(ErrorCode.NOT_INITIATOR, f"仅发起人可终止{type_label}")

    # ========== 3. 校验未已终止 ==========
    if (instance.status or "").lower() == "terminated":
        raise AppException(ErrorCode.INSTANCE_ALREADY_TERMINATED, "流程已终止，不可重复操作")

    now = datetime.now()

    # ========== 4. 先收集待通知人员（必须在状态 UPDATE 之前！） ==========
    # 如果先 UPDATE 再 SELECT，所有 pending 记录已变为 terminated，通知查询永远为空
    notified: set[int] = set()  # 已通知用户去重
    notify_users: list[tuple[int, str]] = []  # [(user_id, clear_type), ...]

    # 待处理 task 的负责人
    pre_pending_tasks = (await db.execute(
        select(Task).where(Task.instance_id == instance_id, Task.status.in_(["pending", "processing"]))
    )).scalars().all()
    for t in pre_pending_tasks:
        if t.assignee_id and t.assignee_id not in notified:
            notified.add(t.assignee_id)
            notify_users.append((t.assignee_id, "task_assigned"))

    # 待处理校验的校验人
    pre_pending_checks = (await db.execute(
        select(CheckRecord).where(CheckRecord.instance_id == instance_id, CheckRecord.status == "pending")
    )).scalars().all()
    for c in pre_pending_checks:
        if c.checker_id and c.checker_id not in notified:
            notified.add(c.checker_id)
            notify_users.append((c.checker_id, "check_assigned"))

    # 待处理审批的审批人
    pre_pending_approvals = (await db.execute(
        select(Approval).where(Approval.instance_id == instance_id, Approval.status == "pending")
    )).scalars().all()
    for a in pre_pending_approvals:
        if a.approver_id and a.approver_id not in notified:
            notified.add(a.approver_id)
            notify_users.append((a.approver_id, "approval_assigned"))

    # 待处理批准的批准人
    pre_pending_endorsements = (await db.execute(
        select(Endorsement).where(Endorsement.instance_id == instance_id, Endorsement.status == "pending")
    )).scalars().all()
    for e in pre_pending_endorsements:
        if e.endorser_id and e.endorser_id not in notified:
            notified.add(e.endorser_id)
            notify_users.append((e.endorser_id, "endorsement_assigned"))

    # ========== 5. 物理删除文件 + 删除 files 记录 ==========
    file_stmt = select(File).where(File.instance_id == instance_id)
    file_result = await db.execute(file_stmt)
    files = file_result.scalars().all()

    # 批量删除 DB 记录 + 物理文件（先 flush DB 再删磁盘，防止事务回滚后磁盘文件丢失）
    if files:
        await batch_delete_files_with_physical(db, list(files))

    # ========== 6. 关闭非终态 instance_nodes ==========
    non_terminal_statuses = ["finished", "terminated"]
    await db.execute(
        sql_update(InstanceNode)
        .where(
            InstanceNode.instance_id == instance_id,
            InstanceNode.status.notin_(non_terminal_statuses),
        )
        .values(status="terminated", completed_at=now)
    )

    # ========== 7. 关闭非终态 tasks ==========
    task_terminal = ["completed", "terminated"]
    await db.execute(
        sql_update(Task)
        .where(
            Task.instance_id == instance_id,
            Task.status.notin_(task_terminal),
        )
        .values(status="terminated", completed_at=now)
    )

    # ========== 8. 关闭 pending check_records ==========
    await db.execute(
        sql_update(CheckRecord)
        .where(
            CheckRecord.instance_id == instance_id,
            CheckRecord.status == CheckStatus.PENDING,
        )
        .values(status=CheckStatus.TERMINATED, decided_at=now)
    )

    # ========== 9. 关闭 pending approvals ==========
    await db.execute(
        sql_update(Approval)
        .where(
            Approval.instance_id == instance_id,
            Approval.status == ApprovalStatus.PENDING,
        )
        .values(status=ApprovalStatus.TERMINATED, decided_at=now)
    )

    # ========== 9b. 关闭 pending endorsements ==========
    await db.execute(
        sql_update(Endorsement)
        .where(
            Endorsement.instance_id == instance_id,
            Endorsement.status == EndorsementStatus.PENDING,
        )
        .values(status=EndorsementStatus.TERMINATED, decided_at=now)
    )

    # ========== 10. 更新实例状态 ==========
    instance.status = "terminated"
    instance.termination_reason = reason
    instance.terminated_at = now

    # ========== 11. 记录操作日志 ==========
    term_type_label = await _get_type_label(db, instance.template_id)
    log = OperationLog(
        instance_id=instance_id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="instance_terminated",
        description=f"终止{term_type_label}：「{instance.name}」，原因：{reason}",
        detail={"reason": reason, "instance_name": instance.name},
    )
    db.add(log)

    # ========== 12. 发送终止通知 + 清除待办（使用步骤4预先收集的用户列表） ==========
    for user_id, clear_type in notify_users:
        await clear_related(db, user_id=user_id, types=[clear_type])
        await create_notification(db, user_id=user_id, type="instance_terminated",
            title="项目已终止", content=f"「{instance.name}」已被发起人终止，原因：{reason}")

    return {
        "id": instance.id,
        "name": instance.name,
        "status": "terminated",
        "termination_reason": reason,
        "terminated_at": now,
    }



