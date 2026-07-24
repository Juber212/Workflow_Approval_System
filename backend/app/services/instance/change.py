"""项目服务 —— 发起实例、配置合并、快照复制、列表查询、终止项目、补交文件"""

import os
import uuid

from fastapi import UploadFile
from datetime import datetime

from sqlalchemy import select, func, case, and_, delete as sql_delete, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge,
    OperationLog, User, Organization,
    Task, CheckRecord, Approval, Endorsement, File,
)
from app.models.enums import UploadType, InstanceStatus, InstanceNodeStatus, TaskStatus, ApprovalStatus, CheckStatus, EndorsementStatus
from app.schemas.common import PaginatedData
from app.schemas.instance import (
    CreateInstanceRequest,
    InstanceResponse,
    InstanceNodeBrief,
    InstanceListItem,
    InstanceDetailResponse,
    DetailNodeInfo,
    NodeFileBrief,
    CheckRecordBrief,
    ApprovalBrief,
    LogItemBrief,
    SupplementFileResponse,
    ChangePersonnelRequest,
    ChangePriorityRequest,
)
from app.api.deps import CurrentUser
from app.engine.flow_engine import (
    calculate_incoming_counts,
    activate_start_node,
    propagate_from_node,
)
from app.utils.workday import add_workdays
from datetime import date as date_type



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

    # ========== 1. 校验实例 ==========
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id)
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    if not instance:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")
    if instance.initiator_id != current_user.id:
        raise AppException(ErrorCode.NOT_INITIATOR, "仅发起人可更换人员")

    # ========== 2. 校验节点 ==========
    node_stmt = select(InstanceNode).where(
        InstanceNode.id == node_id,
        InstanceNode.instance_id == instance_id,
    )
    node_result = await db.execute(node_stmt)
    node = node_result.scalar_one_or_none()
    if not node:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")
    if node.status in ("finished", "terminated"):
        raise AppException(ErrorCode.NOT_RUNNING, "已完成/已终止的节点不可更换人员")

    now = datetime.now()
    changes: list[str] = []  # 记录变更描述

    # ========== 3. 处理校验人变更 ==========
    if body.checkers is not None:
        old_ids = extract_user_ids(node.checkers)
        new_checkers = _normalize_list(body.checkers)
        new_ids = extract_user_ids(new_checkers)

        removed = old_ids - new_ids
        added = new_ids - old_ids

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

            # 新校验人生成 CheckRecord（查询当前节点的活跃 Task 获取 task_id）
            active_task = (await db.execute(
                select(Task).where(
                    Task.node_id == node_id,
                    Task.status.in_(["pending", "processing"]),
                )
            )).scalar_one_or_none()
            task_id_for_check = active_task.id if active_task else 0
            for uid in added:
                db.add(CheckRecord(
                    instance_id=instance_id,
                    node_id=node_id,
                    task_id=task_id_for_check,
                    checker_id=uid,
                    status="pending",
                    round=node.round,  # 记录当前节点轮次
                ))

            changes.append(f"校验人: {_describe_change(old_ids, new_ids)}")
            node.checkers = new_checkers

    # ========== 4. 处理审批人变更 ==========
    if body.approvers is not None:
        old_ids = extract_user_ids(node.approvers)
        new_approvers = _normalize_list(body.approvers)
        new_ids = extract_user_ids(new_approvers)

        removed = old_ids - new_ids
        added = new_ids - old_ids

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

            # 新审批人生成 Approval
            for uid in added:
                db.add(Approval(
                    instance_id=instance_id,
                    node_id=node_id,
                    task_id=None,
                    approver_id=uid,
                    status="pending",
                    round=node.round,  # 记录当前节点轮次
                ))

            changes.append(f"审批人: {_describe_change(old_ids, new_ids)}")
            node.approvers = new_approvers

    # ========== 4b. 处理批准人变更（单人，直接更新） ==========
    if body.endorser_id is not None and body.endorser_id != node.endorser_id:
        old_name = f"ID:{node.endorser_id}" if node.endorser_id else "无"
        node.endorser_id = body.endorser_id
        changes.append(f"批准人: {old_name} → ID:{body.endorser_id}")

    # ========== 5. 处理负责人变更 ==========
    if body.assignee_id is not None and body.assignee_id != node.assignee_id:
        old_name = f"ID:{node.assignee_id}" if node.assignee_id else "无"
        node.assignee_id = body.assignee_id
        changes.append(f"负责人: {old_name} → ID:{body.assignee_id}")

        # 若节点正运行且只有负责人变更 → 更新 Task.assignee_id
        node_status = (node.status or "").lower()
        if node_status in ("arrived", "running"):
            await db.execute(
                sql_update(Task)
                .where(
                    Task.instance_id == instance_id,
                    Task.node_id == node_id,
                    Task.status.in_(["pending", "processing"]),
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
        description=f"节点「{node.name}」人员变更：{'；'.join(changes)}",
        detail={
            "node_id": node_id,
            "node_name": node.name,
            "changes": changes,
        },
    )
    db.add(log)

    # ---- 通知：新人员被分配到任务 (#6) ----
    from app.services.notification_service import create_notification
    # 查询当前节点所有 pending 的校验/审批记录（即刚分配给新人员的）
    new_checks = (await db.execute(
        select(CheckRecord).where(
            CheckRecord.node_id == node_id,
            CheckRecord.status == "pending",
        )
    )).scalars().all()
    for nc in new_checks:
        await create_notification(
            db, user_id=nc.checker_id, type="check_assigned",
            title="新的待校验任务",
            content=f"节点「{node.name}」人员变更，你被分配为校验人",
            link=f"/profile/check/{nc.id}",
        )

    new_apprs = (await db.execute(
        select(Approval).where(
            Approval.node_id == node_id,
            Approval.status == "pending",
        )
    )).scalars().all()
    for na in new_apprs:
        await create_notification(
            db, user_id=na.approver_id, type="approval_assigned",
            title="新的待审批任务",
            content=f"节点「{node.name}」人员变更，你被分配为审批人",
            link=f"/profile/approval/{na.id}",
        )

    # 负责人变更：查询当前活跃 task
    if body.assignee_id is not None:
        active_task = (await db.execute(
            select(Task).where(
                Task.node_id == node_id,
                Task.status.in_(["pending", "processing"]),
            )
        )).scalar_one_or_none()
        if active_task:
            await create_notification(
                db, user_id=body.assignee_id, type="task_assigned",
                title="新的待办任务",
                content=f"节点「{node.name}」人员变更，你被分配为负责人",
                link=f"/profile/task/{active_task.id}",
            )

    return {
        "id": node_id,
        "node_name": node.name,
        "assignee_id": node.assignee_id,
        "checkers": node.checkers,
        "approvers": node.approvers,
        "endorser_id": node.endorser_id,
        "changes": changes,
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


def _describe_change(old_ids: set[int], new_ids: set[int]) -> str:
    """将人员变更描述为可读字符串"""
    parts = []
    if old_ids - new_ids:
        parts.append(f"移除 {_ids_str(old_ids - new_ids)}")
    if new_ids - old_ids:
        parts.append(f"新增 {_ids_str(new_ids - old_ids)}")
    return "、".join(parts)


def _ids_str(ids: set[int]) -> str:
    return "ID:" + ",ID:".join(str(i) for i in sorted(ids))


async def change_priority(
    db: AsyncSession,
    instance_id: int,
    priority: str,
    current_user: CurrentUser,
) -> dict:
    """修改项目优先级 —— 仅发起人 + running 状态可操作

    返回更新后的优先级和实例基本信息。
    """
    # 1. 查询实例
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id)
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



