"""通知服务 —— 创建/列表/已读/未读数 + WebSocket 实时推送

所有通知发送均用 try/except 包裹，失败不影响主流程。
"""

import logging
from datetime import datetime

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.schemas.notification import NotificationOut, UnreadCountOut
from app.schemas.common import PaginatedData
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    user_id: int,
    type: str,
    title: str,
    content: str,
    link: str | None = None,
) -> Notification | None:
    """创建通知 + WebSocket 实时推送（不阻塞主流程）"""
    try:
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            link=link,
            is_read=False,
        )
        db.add(notif)
        await db.flush()

        # WebSocket 实时推送（异步，不阻塞）
        try:
            await manager.send_to_user(user_id, {
                "type": "notification",
                "data": {
                    "id": notif.id,
                    "type": notif.type,
                    "title": notif.title,
                    "content": notif.content,
                    "link": notif.link,
                    "is_read": False,
                    "created_at": notif.created_at.isoformat() if notif.created_at else None,
                },
            })
        except Exception:  # 安全网：WebSocket 推送不可靠，失败不阻塞通知创建
            logger.debug(f"WebSocket 推送失败: user_id={user_id}", exc_info=True)

        return notif
    except Exception:  # 安全网：通知创建任何环节失败都不影响主业务流程
        logger.error(f"创建通知失败: user_id={user_id}, type={type}", exc_info=True)
        return None


async def list_notifications(
    db: AsyncSession,
    *,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """我的通知列表（按时间倒序）"""
    conditions = [Notification.user_id == user_id]

    count_stmt = select(func.count()).select_from(Notification).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = [NotificationOut.model_validate(n) for n in result.scalars().all()]

    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def get_unread_count(db: AsyncSession, *, user_id: int) -> UnreadCountOut:
    """获取当前用户未读通知数量"""
    stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id,
        Notification.is_read == False,
    )
    count = (await db.execute(stmt)).scalar() or 0
    return UnreadCountOut(count=count)


async def mark_read(db: AsyncSession, *, notification_id: int, user_id: int) -> None:
    """标记单条通知为已读（仅操作自己的通知）"""
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.flush()


async def mark_all_read(db: AsyncSession, *, user_id: int) -> None:
    """标记当前用户全部通知为已读"""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.flush()


async def get_summary(db: AsyncSession, *, user_id: int) -> dict:
    """获取待办/校验/审批/批准计数汇总 —— 一次请求获取所有红点数据

    使用 JOIN + GROUP BY 按实例类型分组计数，
    返回完整的 project/proposal 分类 breakdown，供前端侧边栏角标和个人中心 Tab 角标使用。
    """
    from app.models import Task, CheckRecord, Approval, Endorsement, FlowInstance

    # 1. 任务计数按实例类型分组
    task_counts = (await db.execute(
        select(FlowInstance.template_type, func.count(Task.id))
        .join(Task, Task.instance_id == FlowInstance.id)
        .where(
            Task.assignee_id == user_id,
            Task.status.notin_(["completed", "terminated"]),
            FlowInstance.template_type.in_(["project", "proposal"]),
        )
        .group_by(FlowInstance.template_type)
    )).all()
    task_map: dict[str, int] = {row[0]: row[1] for row in task_counts}
    project_tasks = task_map.get("project", 0)
    proposal_tasks = task_map.get("proposal", 0)

    # 2. 校验计数（pending 状态，只有项目有校验）
    check_count = (await db.execute(
        select(func.count(CheckRecord.id)).where(
            CheckRecord.checker_id == user_id,
            CheckRecord.status == "pending",
        )
    )).scalar() or 0

    # 3. 审批计数按实例类型分组
    approval_counts = (await db.execute(
        select(FlowInstance.template_type, func.count(Approval.id))
        .join(Approval, Approval.instance_id == FlowInstance.id)
        .where(
            Approval.approver_id == user_id,
            Approval.status == "pending",
            FlowInstance.template_type.in_(["project", "proposal"]),
        )
        .group_by(FlowInstance.template_type)
    )).all()
    approval_map: dict[str, int] = {row[0]: row[1] for row in approval_counts}
    project_approvals = approval_map.get("project", 0)
    proposal_approvals = approval_map.get("proposal", 0)

    # 4. 批准计数按实例类型分组（endorsement，难度4级专有）
    endorsement_counts = (await db.execute(
        select(FlowInstance.template_type, func.count(Endorsement.id))
        .join(Endorsement, Endorsement.instance_id == FlowInstance.id)
        .where(
            Endorsement.endorser_id == user_id,
            Endorsement.status == "pending",
            FlowInstance.template_type.in_(["project", "proposal"]),
        )
        .group_by(FlowInstance.template_type)
    )).all()
    endorsement_map: dict[str, int] = {row[0]: row[1] for row in endorsement_counts}
    project_endorsements = endorsement_map.get("project", 0)
    proposal_endorsements = endorsement_map.get("proposal", 0)

    task_total = project_tasks + proposal_tasks
    approval_total = project_approvals + proposal_approvals
    endorsement_total = project_endorsements + proposal_endorsements

    return {
        # 汇总（侧边栏角标用）
        "task_count": task_total,
        "check_count": check_count,
        "approval_count": approval_total,
        "endorsement_count": endorsement_total,
        "project_pending": project_tasks + check_count + project_approvals + project_endorsements,
        "proposal_pending": proposal_tasks + proposal_approvals + proposal_endorsements,
        # 分类 breakdown（个人中心 Tab 角标用）
        "project_task_count": project_tasks,
        "project_check_count": check_count,
        "project_approval_count": project_approvals,
        "project_endorsement_count": project_endorsements,
        "proposal_task_count": proposal_tasks,
        "proposal_approval_count": proposal_approvals,
        "proposal_endorsement_count": proposal_endorsements,
    }


async def clear_related(db: AsyncSession, *, user_id: int, types: list[str]) -> None:
    """操作完成后删除相关通知（纯 DB 操作，不发送 WS）

    WS 推送由 API 层在 db.commit() 后调用 send_refresh_signal() 完成，
    确保前端查询 summary 时数据已提交。
    """
    try:
        from sqlalchemy import delete
        await db.execute(
            delete(Notification).where(
                Notification.user_id == user_id,
                Notification.type.in_(types),
            )
        )
        await db.flush()
    except Exception:
        logger.debug(f"清除通知失败: user_id={user_id}, types={types}", exc_info=True)


async def send_refresh_signal(user_id: int) -> None:
    """向指定用户推送 refresh_count（在 DB commit 后调用，保证前端查询到最新数据）"""
    try:
        await manager.send_to_user(user_id, {"type": "refresh_count"})
    except Exception:
        logger.warning(f"WebSocket 推送 refresh_count 失败: user_id={user_id}", exc_info=True)


async def get_overdue_items(db: AsyncSession) -> dict:
    """查询系统全部超期项，按类型分组（任务/校验/审批/批准）

    全部用户可见，不区分组织。
    返回各类别超期项列表，含实例名、节点名、负责人、截止时间、优先级。
    """
    from datetime import datetime
    from app.models import Task, CheckRecord, Approval, Endorsement, FlowInstance, InstanceNode, User, Organization
    from sqlalchemy import and_

    now = datetime.now()
    result: dict[str, list[dict]] = {
        "tasks": [],
        "checks": [],
        "approvals": [],
        "endorsements": [],
    }

    # ── 1. 超期待办任务 ──
    overdue_tasks = (await db.execute(
        select(Task, InstanceNode, FlowInstance, User)
        .join(InstanceNode, Task.node_id == InstanceNode.id)
        .join(FlowInstance, Task.instance_id == FlowInstance.id)
        .join(User, Task.assignee_id == User.id)
        .where(
            Task.status.notin_(["completed", "terminated"]),
            InstanceNode.deadline.isnot(None),
            InstanceNode.deadline < now,
        )
        .order_by(InstanceNode.deadline.asc())
    )).all()

    # ── 2. 超期校验 ──
    overdue_checks = (await db.execute(
        select(CheckRecord, InstanceNode, FlowInstance, User)
        .join(InstanceNode, and_(CheckRecord.node_id == InstanceNode.id))
        .join(FlowInstance, CheckRecord.instance_id == FlowInstance.id)
        .join(User, CheckRecord.checker_id == User.id)
        .where(
            CheckRecord.status == "pending",
            InstanceNode.deadline.isnot(None),
            InstanceNode.deadline < now,
        )
        .order_by(InstanceNode.deadline.asc())
    )).all()

    # ── 3. 超期审批 ──
    overdue_approvals = (await db.execute(
        select(Approval, InstanceNode, FlowInstance, User)
        .join(InstanceNode, and_(Approval.node_id == InstanceNode.id))
        .join(FlowInstance, Approval.instance_id == FlowInstance.id)
        .join(User, Approval.approver_id == User.id)
        .where(
            Approval.status == "pending",
            InstanceNode.deadline.isnot(None),
            InstanceNode.deadline < now,
        )
        .order_by(InstanceNode.deadline.asc())
    )).all()

    # ── 4. 超期批准 ──
    overdue_endorsements = (await db.execute(
        select(Endorsement, InstanceNode, FlowInstance, User)
        .join(InstanceNode, and_(Endorsement.node_id == InstanceNode.id))
        .join(FlowInstance, Endorsement.instance_id == FlowInstance.id)
        .join(User, Endorsement.endorser_id == User.id)
        .where(
            Endorsement.status == "pending",
            InstanceNode.deadline.isnot(None),
            InstanceNode.deadline < now,
        )
        .order_by(InstanceNode.deadline.asc())
    )).all()

    # ── 批量获取组织名称（FlowInstance 只有 organization_id，需查 Organization 表）──
    all_org_ids: set[int] = set()
    for items in [overdue_tasks, overdue_checks, overdue_approvals, overdue_endorsements]:
        for row in items:
            inst = row[2]  # FlowInstance 在各查询中都是第3个元素
            if inst.organization_id:
                all_org_ids.add(inst.organization_id)
    org_name_map: dict[int, str] = {}
    if all_org_ids:
        org_rows = (await db.execute(
            select(Organization.id, Organization.name).where(Organization.id.in_(list(all_org_ids)))
        )).all()
        org_name_map = {oid: oname for oid, oname in org_rows}

    # ── 组装结果 ──
    for t, node, inst, user in overdue_tasks:
        result["tasks"].append({
            "id": t.id,
            "type": "task",
            "instance_id": inst.id,
            "instance_name": inst.name,
            "node_name": node.name,
            "person_name": user.real_name,
            "person_id": user.id,
            "deadline": node.deadline.isoformat() if node.deadline else None,
            "priority": inst.priority,
            "organization_name": org_name_map.get(inst.organization_id, "") if inst.organization_id else "",
        })

    for c, node, inst, user in overdue_checks:
        result["checks"].append({
            "id": c.id,
            "type": "check",
            "instance_id": inst.id,
            "instance_name": inst.name,
            "node_name": node.name,
            "person_name": user.real_name,
            "person_id": user.id,
            "deadline": node.deadline.isoformat() if node.deadline else None,
            "priority": inst.priority,
            "organization_name": org_name_map.get(inst.organization_id, "") if inst.organization_id else "",
        })

    for a, node, inst, user in overdue_approvals:
        result["approvals"].append({
            "id": a.id,
            "type": "approval",
            "instance_id": inst.id,
            "instance_name": inst.name,
            "node_name": node.name,
            "person_name": user.real_name,
            "person_id": user.id,
            "deadline": node.deadline.isoformat() if node.deadline else None,
            "priority": inst.priority,
            "organization_name": org_name_map.get(inst.organization_id, "") if inst.organization_id else "",
        })

    for e, node, inst, user in overdue_endorsements:
        result["endorsements"].append({
            "id": e.id,
            "type": "endorsement",
            "instance_id": inst.id,
            "instance_name": inst.name,
            "node_name": node.name,
            "person_name": user.real_name,
            "person_id": user.id,
            "deadline": node.deadline.isoformat() if node.deadline else None,
            "priority": inst.priority,
            "organization_name": org_name_map.get(inst.organization_id, "") if inst.organization_id else "",
        })

    return result
