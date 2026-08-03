"""紧急换人 + 修改优先级服务"""

from datetime import datetime

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.services.notification_service import create_notification, clear_related
from app.models import (
    FlowInstance, InstanceNode,
    OperationLog,
    Task, CheckRecord, Approval, Endorsement, User,
)
from app.schemas.instance import (
    ChangePersonnelRequest,
    ChangePriorityRequest,
)
from app.api.deps import CurrentUser


# 任务「非活跃」状态：已完成/已终止/已驳回 → 换人时不再处理。
# 其余状态（pending/processing/waiting_check/waiting_approval/waiting_endorsement）
# 均视为活跃任务，换人需覆盖（P1-8：修复 WAITING_* 状态下换人不生效）。
_INACTIVE_TASK_STATUSES = ["completed", "terminated", "rejected"]

# 各角色「工作已完成」的节点状态（按节点所处阶段判断）——已完成阶段的人员不可更换：
# 负责人：节点进入等待校验/审批/批准（已提交文件）后不可换
# 校验人：节点进入等待审批/批准（校验已通过）后不可换
# 审批人：节点进入等待批准（审批已通过）后不可换
_ASSIGNEE_DONE_STATUSES = {"waiting_check", "waiting_approval", "waiting_endorsement"}
_CHECKER_DONE_STATUSES = {"waiting_approval", "waiting_endorsement"}
_APPROVER_DONE_STATUSES = {"waiting_endorsement"}


async def _get_active_task(db: AsyncSession, node_id: int) -> Task | None:
    """查询节点当前活跃任务（含等待校验/审批/批准状态）

    P1-8：原只查 pending/processing，WAITING_* 状态的任务查不到，
    导致换校验人/审批人/批准人时新记录 task_id=None（坏记录）。
    """
    result = await db.execute(
        select(Task).where(
            Task.node_id == node_id,
            Task.status.notin_(_INACTIVE_TASK_STATUSES),
        )
    )
    return result.scalar_one_or_none()


async def change_personnel(
    db: AsyncSession,
    instance_id: int,
    node_id: int,
    body: ChangePersonnelRequest,
    current_user: CurrentUser,
) -> dict:
    """紧急换人 —— 更换运行中实例节点的负责人/校验人/审批人

    处理步骤：
    1. 校验实例存在 + 发起人权限
    2. 校验节点存在且未完成
    3. 对比新旧人员列表，决定增删
    4. pending 记录不在新列表 → terminated
    5. 新人员生成 CheckRecord/Approval
    6. 更新 instance_node 人员字段
    7. 若仅换负责人且节点 running → 更新 Task.assignee_id
    8. 记录操作日志
    """
    # ========== 辅助函数：从人员列表提取 user_id 集合 ==========
    def extract_user_ids(personnel: list | None) -> set[int]:
        if not personnel:
            return set()
        result = set()
        for item in personnel:
            if isinstance(item, dict):
                result.add(item.get("user_id", 0))
            elif isinstance(item, int):
                result.add(item)
        return result - {0}  # 排除无效 0

    # ========== 1. 校验实例（加锁防并发）==========
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id).with_for_update()
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    if not instance:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")
    if instance.initiator_id != current_user.id:
        raise AppException(ErrorCode.NOT_INITIATOR, "仅发起人可更换人员")

    # ========== 2. 校验节点（加锁防并发）==========
    node_stmt = select(InstanceNode).where(
        InstanceNode.id == node_id,
        InstanceNode.instance_id == instance_id,
    ).with_for_update()
    node_result = await db.execute(node_stmt)
    node = node_result.scalar_one_or_none()
    if not node:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")
    if node.status in ("finished", "terminated"):
        raise AppException(ErrorCode.NOT_RUNNING, "已完成/已终止的节点不可更换人员")

    now = datetime.now()
    changes: list[str] = []  # 记录变更描述

    # 捕获旧值，用于后续通知清除
    _old_assignee_id = node.assignee_id
    _old_endorser_id = node.endorser_id
    _removed_checkers: set[int] = set()
    _removed_approvers: set[int] = set()
    removed_users: set[int] = set()  # 被换掉的人员（旧负责人/被移除的校验人审批人/旧批准人），用于推送刷新

    # 收集本次变更涉及的全部用户 → 真实姓名映射（changes 文案用人名而非裸 ID）
    involved_ids: set[int] = set()
    if _old_assignee_id:
        involved_ids.add(_old_assignee_id)
    if body.assignee_id:
        involved_ids.add(body.assignee_id)
    if body.checkers is not None:
        involved_ids |= extract_user_ids(node.checkers)
        involved_ids |= extract_user_ids(body.checkers)
    if body.approvers is not None:
        involved_ids |= extract_user_ids(node.approvers)
        involved_ids |= extract_user_ids(body.approvers)
    if body.endorser_id:
        involved_ids.add(body.endorser_id)
    if _old_endorser_id:
        involved_ids.add(_old_endorser_id)
    id_name_map: dict[int, str] = {}
    if involved_ids:
        user_rows = (await db.execute(
            select(User).where(User.id.in_(involved_ids))
        )).scalars().all()
        id_name_map = {u.id: (u.real_name or u.username) for u in user_rows}

    # ========== 3. 处理校验人变更 ==========
    if body.checkers is not None:
        # 校验已通过（节点进入等待审批/批准）后校验人不可更换
        if (node.status or "").lower() in _CHECKER_DONE_STATUSES:
            raise AppException(ErrorCode.VALIDATION_ERROR, "校验已完成，不可更换校验人")

        old_ids = extract_user_ids(node.checkers)
        new_checkers = _normalize_list(body.checkers)
        new_ids = extract_user_ids(new_checkers)

        removed = old_ids - new_ids
        added = new_ids - old_ids
        _removed_checkers = removed  # 记录用于通知清除
        removed_users |= removed

        if removed or added:
            # 不在新列表的 pending CheckRecord → terminated
            await db.execute(
                sql_update(CheckRecord)
                .where(
                    CheckRecord.instance_id == instance_id,
                    CheckRecord.node_id == node_id,
                    CheckRecord.status == "pending",
                    CheckRecord.checker_id.in_(list(removed)),
                )
                .values(status="terminated", decided_at=now)
            )

            # 新校验人生成 CheckRecord（查询当前节点的活跃 Task 获取 task_id，含 WAITING_* 状态）
            active_task = await _get_active_task(db, node_id)
            task_id_for_check = active_task.id if active_task else None
            for uid in added:
                db.add(CheckRecord(
                    instance_id=instance_id,
                    node_id=node_id,
                    task_id=task_id_for_check,
                    checker_id=uid,
                    status="pending",
                    round=node.round,  # 记录当前节点轮次
                ))

            changes.append(f"校验人: {_describe_change(old_ids, new_ids, id_name_map)}")
            node.checkers = new_checkers

    # ========== 4. 处理审批人变更 ==========
    if body.approvers is not None:
        # 审批已通过（节点进入等待批准）后审批人不可更换
        if (node.status or "").lower() in _APPROVER_DONE_STATUSES:
            raise AppException(ErrorCode.VALIDATION_ERROR, "审批已完成，不可更换审批人")

        old_ids = extract_user_ids(node.approvers)
        new_approvers = _normalize_list(body.approvers)
        new_ids = extract_user_ids(new_approvers)

        removed = old_ids - new_ids
        added = new_ids - old_ids
        _removed_approvers = removed  # 记录用于通知清除
        removed_users |= removed

        if removed or added:
            # 不在新列表的 pending Approval → terminated
            await db.execute(
                sql_update(Approval)
                .where(
                    Approval.instance_id == instance_id,
                    Approval.node_id == node_id,
                    Approval.status == "pending",
                    Approval.approver_id.in_(list(removed)),
                )
                .values(status="terminated", decided_at=now)
            )

            # 新审批人生成 Approval（task_id 关联当前活跃任务，避免坏记录）
            active_task = await _get_active_task(db, node_id)
            for uid in added:
                db.add(Approval(
                    instance_id=instance_id,
                    node_id=node_id,
                    task_id=active_task.id if active_task else None,
                    approver_id=uid,
                    status="pending",
                    round=node.round,  # 记录当前节点轮次
                ))

            changes.append(f"审批人: {_describe_change(old_ids, new_ids, id_name_map)}")
            node.approvers = new_approvers

    # ========== 4b. 处理批准人变更（单人，直接更新） ==========
    if body.endorser_id is not None and body.endorser_id != node.endorser_id:
        # 终止旧批准人的 pending Endorsement
        if _old_endorser_id:
            await db.execute(
                sql_update(Endorsement)
                .where(Endorsement.node_id == node_id, Endorsement.endorser_id == _old_endorser_id,
                       Endorsement.status == "pending")
                .values(status="terminated", decided_at=now)
            )
        # 创建新批准人的 Endorsement（task_id 关联当前活跃任务，避免坏记录）
        if body.endorser_id:
            active_task = await _get_active_task(db, node_id)
            db.add(Endorsement(
                instance_id=instance_id,
                node_id=node_id,
                task_id=active_task.id if active_task else None,
                endorser_id=body.endorser_id,
                status="pending",
                round=node.round,
            ))
        node.endorser_id = body.endorser_id
        if _old_endorser_id:
            removed_users.add(_old_endorser_id)
        old_endorser_name = id_name_map.get(_old_endorser_id) if _old_endorser_id else None
        changes.append(f"批准人: {old_endorser_name or '无'} → {id_name_map.get(body.endorser_id) or f'ID:{body.endorser_id}'}")

    # ========== 5. 处理负责人变更 ==========
    if body.assignee_id is not None and body.assignee_id != node.assignee_id:
        node_status = (node.status or "").lower()
        # 负责人已提交（节点进入等待校验/审批/批准）后，禁止更换负责人：
        # 此时负责人的工作已完成，改负责人会造成任务记录与处理人不符
        if node_status in ("waiting_check", "waiting_approval", "waiting_endorsement"):
            raise AppException(ErrorCode.VALIDATION_ERROR, "负责人已提交文件，不可更换负责人")

        if _old_assignee_id:
            removed_users.add(_old_assignee_id)
        old_name = id_name_map.get(_old_assignee_id) if _old_assignee_id else "无"
        node.assignee_id = body.assignee_id
        changes.append(f"负责人: {old_name} → {id_name_map.get(body.assignee_id) or f'ID:{body.assignee_id}'}")

        # 更新 Task.assignee_id 到新负责人（此处节点必处于负责人处理阶段）
        await db.execute(
            sql_update(Task)
            .where(
                Task.instance_id == instance_id,
                Task.node_id == node_id,
                Task.status.notin_(_INACTIVE_TASK_STATUSES),
            )
            .values(assignee_id=body.assignee_id)
        )

    # ========== 6. 无变更时返回 ==========
    if not changes:
        return {"id": node_id, "message": "无需变更"}

    # ========== 7. 记录操作日志 ==========
    log = OperationLog(
        instance_id=instance_id,
        node_id=node_id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="personnel_changed",
        round=node.round,  # 记录当前节点轮次
        description=f"节点「{node.name}」人员变更：{'；'.join(changes)}",
        detail={
            "node_id": node_id,
            "node_name": node.name,
            "changes": changes,
        },
    )
    db.add(log)

    # ---- 通知：新人员 + 清除旧人员 ----


    # 清除被移除的校验人通知
    for uid in _removed_checkers:
        await clear_related(db, user_id=uid, types=["check_assigned"], instance_id=node.instance_id)
    # 清除被移除的审批人通知
    for uid in _removed_approvers:
        await clear_related(db, user_id=uid, types=["approval_assigned"], instance_id=node.instance_id)
    # 清除旧负责人通知
    if _old_assignee_id:
        await clear_related(db, user_id=_old_assignee_id, types=["task_assigned"], instance_id=node.instance_id)
    # 清除旧批准人通知
    if _old_endorser_id:
        await clear_related(db, user_id=_old_endorser_id, types=["endorsement_assigned"], instance_id=node.instance_id)

    # 查询当前节点所有 pending 的校验/审批记录（即刚分配给新人员的）
    new_checks = (await db.execute(
        select(CheckRecord).where(CheckRecord.node_id == node_id, CheckRecord.status == "pending")
    )).scalars().all()
    for nc in new_checks:
        await create_notification(
            db, user_id=nc.checker_id, type="check_assigned",
            title="新的待校验任务",
            content=f"节点「{node.name}」人员变更，你被分配为校验人",
            link=f"/profile/check/{nc.id}",
            instance_id=node.instance_id,
        )

    new_apprs = (await db.execute(
        select(Approval).where(Approval.node_id == node_id, Approval.status == "pending")
    )).scalars().all()
    for na in new_apprs:
        await create_notification(
            db, user_id=na.approver_id, type="approval_assigned",
            title="新的待审批任务",
            content=f"节点「{node.name}」人员变更，你被分配为审批人",
            link=f"/profile/approval/{na.id}",
            instance_id=node.instance_id,
        )

    # 负责人变更：通知新负责人（含 WAITING_* 状态的活跃任务）
    if body.assignee_id is not None:
        active_task = await _get_active_task(db, node_id)
        if active_task:
            await create_notification(
                db, user_id=body.assignee_id, type="task_assigned",
                title="新的待办任务",
                content=f"节点「{node.name}」人员变更，你被分配为负责人",
                link=f"/profile/task/{active_task.id}",
                instance_id=node.instance_id,
            )

    # 批准人变更：通知新批准人
    if body.endorser_id is not None and body.endorser_id != _old_endorser_id:
        if body.endorser_id:
            pending_e = (await db.execute(
                select(Endorsement).where(
                    Endorsement.node_id == node_id,
                    Endorsement.endorser_id == body.endorser_id,
                    Endorsement.status == "pending",
                ).order_by(Endorsement.id.desc()).limit(1)
            )).scalar_one_or_none()
            link = f"/profile/endorse/{pending_e.id}" if pending_e else None
            await create_notification(
                db, user_id=body.endorser_id, type="endorsement_assigned",
                title="新的待批准任务",
                content=f"节点「{node.name}」人员变更，你被分配为批准人",
                link=link,
                instance_id=node.instance_id,
            )

    return {
        "id": node_id,
        "node_name": node.name,
        "assignee_id": node.assignee_id,
        "checkers": node.checkers,
        "approvers": node.approvers,
        "endorser_id": node.endorser_id,
        "changes": changes,
        "removed_users": sorted(removed_users),  # 被换掉的人员，供 API 层推送实时刷新
    }


def _normalize_list(raw: list | None) -> list[dict] | None:
    """标准化人员列表：[1,2] → [{'user_id':1},{'user_id':2}]，已是 dict 则保持"""
    if raw is None:
        return None
    result = []
    for item in raw:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, int):
            result.append({"user_id": item})
    return result if result else None


def _describe_change(old_ids: set[int], new_ids: set[int], id_name_map: dict[int, str]) -> str:
    """将人员变更描述为可读字符串（用人名，缺省回退 ID）"""
    parts = []
    if old_ids - new_ids:
        parts.append(f"移除 {_ids_str(old_ids - new_ids, id_name_map)}")
    if new_ids - old_ids:
        parts.append(f"新增 {_ids_str(new_ids - old_ids, id_name_map)}")
    return "、".join(parts)


def _ids_str(ids: set[int], id_name_map: dict[int, str]) -> str:
    """人员 ID 列表 → 名字字符串（查不到名字时回退为 ID）"""
    return "、".join(id_name_map.get(i) or f"ID:{i}" for i in sorted(ids))


async def change_priority(
    db: AsyncSession,
    instance_id: int,
    priority: str,
    current_user: CurrentUser,
) -> dict:
    """修改项目优先级 —— 仅发起人 + running 状态可操作

    返回更新后的优先级和实例基本信息。
    """
    # 1. 查询实例（加锁防并发覆盖）
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id).with_for_update()
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    if not instance:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")

    # 2. 仅发起人
    if instance.initiator_id != current_user.id:
        raise AppException(ErrorCode.NOT_INITIATOR, "仅发起人可修改优先级")

    # 3. 仅 running 状态
    if (instance.status or "").lower() != "running":
        raise AppException(ErrorCode.PRIORITY_ONLY_RUNNING, "仅运行中的流程可修改优先级")

    old_priority = instance.priority
    instance.priority = priority

    # 4. 操作日志
    priority_names = {"urgent": "紧急", "high": "高", "normal": "普通", "low": "低"}
    old_label = priority_names.get(old_priority, old_priority)
    new_label = priority_names.get(priority, priority)

    log = OperationLog(
        instance_id=instance_id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="priority_changed",
        description=f"优先级变更：{old_label} → {new_label}",
        detail={"old_priority": old_priority, "new_priority": priority},
    )
    db.add(log)

    return {
        "id": instance.id,
        "priority": priority,
        "old_priority": old_priority,
    }



