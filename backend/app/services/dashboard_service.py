"""Dashboard 服务 —— 全局统计数据聚合（PRD §4）"""
from datetime import datetime, timedelta

from sqlalchemy import select, func, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FlowInstance,
    InstanceNode,
    Task,
    Organization,
    User,
)


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """
    Dashboard 全局统计数据（PRD §4.3-4.7）

    返回：
    - stats: 4 个统计卡片（进行中、已归档、本月归档、超期预警）
    - task_distribution: 任务状态分布（饼图数据）
    - bottleneck: 流程卡点追踪
    - overdue_tasks: 超期预警列表
    - org_overview: 各所流程概览
    """
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ─── 1. 四大统计卡片（全局） ───

    # 进行中实例
    running_count = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(FlowInstance.status == "running")
    )).scalar() or 0

    # 已归档实例
    archived_count = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(FlowInstance.archive_status == "archived")
    )).scalar() or 0

    # 本月归档
    archived_this_month = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.archive_status == "archived",
            FlowInstance.archived_at >= month_start,
        )
    )).scalar() or 0

    # 超期预警：已逾期 + 即将逾期（2天内）的 Task
    near_future = now + timedelta(days=2)
    overdue_count = (await db.execute(
        select(func.count()).select_from(Task).join(
            InstanceNode, Task.node_id == InstanceNode.id
        ).where(
            Task.status.notin_(["completed", "terminated"]),
            InstanceNode.deadline.isnot(None),
            InstanceNode.deadline < near_future,
        )
    )).scalar() or 0

    stats = {
        "running_instances": running_count,
        "archived_total": archived_count,
        "archived_this_month": archived_this_month,
        "overdue_warnings": overdue_count,
    }

    # ─── 2. 任务状态分布 ───
    task_dist = await _get_task_distribution(db, now)

    # ─── 3. 流程卡点追踪 ───
    bottleneck = await _get_bottleneck_tracking(db, now)

    # ─── 4. 超期预警列表 ───
    overdue_list = await _get_overdue_list(db, now)

    # ─── 5. 各所流程概览 ───
    org_overview = await _get_org_overview(db)

    return {
        "stats": stats,
        "task_distribution": task_dist,
        "bottleneck": bottleneck,
        "overdue_list": overdue_list,
        "org_overview": org_overview,
    }


async def _get_task_distribution(db: AsyncSession, now: datetime) -> list[dict]:
    """任务状态分布 —— 全局统计（PRD §4.4）"""
    thirty_days_ago = now - timedelta(days=30)

    statuses = ["pending", "processing", "waiting_check", "waiting_approval", "completed"]
    labels = {
        "pending": "待处理", "processing": "处理中",
        "waiting_check": "待校验", "waiting_approval": "待审批",
        "completed": "近30天已完成",
    }
    colors = {
        "pending": "#E6A23C", "processing": "#409EFF",
        "waiting_check": "#00B5AD", "waiting_approval": "#9B59B6",
        "completed": "#67C23A",
    }

    result = []
    for status in statuses:
        conditions = [Task.status == status]
        if status == "completed":
            conditions.append(Task.completed_at >= thirty_days_ago)

        count = (await db.execute(
            select(func.count()).select_from(Task).where(*conditions)
        )).scalar() or 0

        result.append({
            "status": status,
            "label": labels.get(status, status),
            "color": colors.get(status, "#909399"),
            "count": count,
        })

    return result


async def _get_bottleneck_tracking(db: AsyncSession, now: datetime) -> list[dict]:
    """流程卡点追踪 —— 运行中实例的节点进度链（PRD §4.5）"""
    # 查询所有运行中实例
    instances_result = await db.execute(
        select(FlowInstance).where(FlowInstance.status == "running").order_by(
            case(
                (FlowInstance.priority == "urgent", 0),
                (FlowInstance.priority == "high", 1),
                (FlowInstance.priority == "normal", 2),
                else_=3,
            ),
            FlowInstance.initiated_at.asc(),
        )
    )
    instances = instances_result.scalars().all()

    if not instances:
        return []

    inst_ids = [i.id for i in instances]

    # 批量查节点
    nodes_result = await db.execute(
        select(InstanceNode).where(
            InstanceNode.instance_id.in_(inst_ids),
            InstanceNode.is_start == False,
            InstanceNode.is_end == False,
        ).order_by(InstanceNode.instance_id, InstanceNode.sort_order)
    )
    all_nodes = nodes_result.scalars().all()
    nodes_by_inst: dict[int, list] = {}
    for n in all_nodes:
        nodes_by_inst.setdefault(n.instance_id, []).append(n)

    # 批量查组织
    org_ids = list(set(i.organization_id for i in instances))
    orgs = {}
    if org_ids:
        orgs_result = await db.execute(select(Organization).where(Organization.id.in_(org_ids)))
        orgs = {o.id: o.name for o in orgs_result.scalars().all()}

    # 批量查当前负责人
    assignee_ids = list(set(n.assignee_id for n in all_nodes if n.assignee_id))
    users_map = {}
    if assignee_ids:
        users_result = await db.execute(select(User).where(User.id.in_(assignee_ids)))
        users_map = {u.id: u.real_name for u in users_result.scalars().all()}

    items = []
    for inst in instances:
        nodes = nodes_by_inst.get(inst.id, [])
        if not nodes:
            continue

        # 构建节点进度链
        progress_chain = []
        current_node_name = ""
        current_assignee_name = ""
        all_finished = True
        has_overdue = False
        has_near_overdue = False
        near_future = now + timedelta(days=2)

        for node in nodes:
            status_icon = "⚪"  # 待开始
            if node.status == "finished":
                status_icon = "✅"
            elif node.status in ("running", "waiting_check", "waiting_approval"):
                status_icon = "🔵"
                all_finished = False
                current_node_name = node.name
                current_assignee_name = users_map.get(node.assignee_id, "") if node.assignee_id else ""
                if node.deadline:
                    if node.deadline < now:
                        has_overdue = True
                    elif node.deadline < near_future:
                        has_near_overdue = True
            elif node.status == "waiting":
                all_finished = False

            assignee_label = ""
            if node.assignee_id and status_icon in ("🔵", "✅"):
                assignee_label = f" {users_map.get(node.assignee_id, '')}"

            progress_chain.append(f"{status_icon}{node.name}{assignee_label}")

        # 逾期判定
        if has_overdue:
            overdue_status = "已逾期"
        elif has_near_overdue:
            overdue_status = "即将逾期"
        else:
            overdue_status = "正常"

        # 已耗时天数
        days_elapsed = (now - (inst.initiated_at or inst.created_at)).days

        items.append({
            "instance_id": inst.id,
            "instance_name": inst.name,
            "organization_name": orgs.get(inst.organization_id, ""),
            "progress_chain": progress_chain,
            "current_node_name": current_node_name,
            "current_assignee_name": current_assignee_name,
            "priority": inst.priority,
            "days_elapsed": days_elapsed,
            "overdue_status": overdue_status,
            "all_finished": all_finished,
        })

    return items


async def _get_overdue_list(db: AsyncSession, now: datetime) -> list[dict]:
    """超期预警列表 —— 已逾期 + 即将逾期任务（PRD §4.6）"""
    near_future = now + timedelta(days=2)

    # JOIN tasks + instance_nodes 获取 deadline
    tasks_result = await db.execute(
        select(Task, InstanceNode).join(
            InstanceNode, Task.node_id == InstanceNode.id
        ).where(
            Task.status.notin_(["completed", "terminated"]),
            InstanceNode.deadline.isnot(None),
            InstanceNode.deadline < near_future,
        )
    )
    rows = tasks_result.all()

    if not rows:
        return []

    inst_ids = list(set(t.instance_id for t, _ in rows))
    insts = {}
    if inst_ids:
        insts_result = await db.execute(select(FlowInstance).where(FlowInstance.id.in_(inst_ids)))
        insts = {i.id: i for i in insts_result.scalars().all()}

    assignee_ids = list(set(t.assignee_id for t, _ in rows))
    users_map = {}
    if assignee_ids:
        users_result = await db.execute(select(User).where(User.id.in_(assignee_ids)))
        users_map = {u.id: u for u in users_result.scalars().all()}

    items = []
    for task, node in rows:
        inst = insts.get(task.instance_id)
        assignee = users_map.get(task.assignee_id)
        dl = node.deadline

        if dl:
            delta = (dl - now).days
            if delta < 0:
                days_label = f"🔴已逾期 {-delta}天"
            else:
                days_label = f"还剩 {delta}天"
        else:
            days_label = "—"

        items.append({
            "task_id": task.id,
            "instance_id": task.instance_id,
            "instance_name": inst.name if inst else "",
            "node_name": node.name,
            "assignee_name": assignee.real_name if assignee else "",
            "deadline": dl.isoformat() if dl else None,
            "days_label": days_label,
            "organization_name": "",  # 通过实例获取
            "is_overdue": dl is not None and dl < now,
        })

    # 排序：逾期从多到少，然后剩余从少到多
    items.sort(key=lambda x: (
        not x["is_overdue"],
        -(abs((datetime.fromisoformat(x["deadline"]) - now).days) if x["deadline"] else 0) if x["is_overdue"] else 999,
        abs((datetime.fromisoformat(x["deadline"]) - now).days) if x["deadline"] and not x["is_overdue"] else 999,
    ))

    return items


async def _get_org_overview(db: AsyncSession) -> list[dict]:
    """各所流程概览 —— 按组织分组运行中实例（PRD §4.7）"""
    orgs_result = await db.execute(
        select(Organization).where(Organization.is_active == True)
    )
    orgs = orgs_result.scalars().all()

    if not orgs:
        return []

    org_ids = [o.id for o in orgs]

    # 每个组织下运行中实例
    instances_result = await db.execute(
        select(FlowInstance).where(
            FlowInstance.organization_id.in_(org_ids),
            FlowInstance.status == "running",
        ).order_by(FlowInstance.priority.asc(), FlowInstance.initiated_at.asc())
    )
    instances = instances_result.scalars().all()
    insts_by_org: dict[int, list] = {}
    for i in instances:
        insts_by_org.setdefault(i.organization_id, []).append(i)

    # 批量获取当前节点信息
    all_inst_ids = [i.id for i in instances]
    current_nodes = {}
    if all_inst_ids:
        node_result = await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id.in_(all_inst_ids),
                InstanceNode.status.in_(["running", "waiting_check", "waiting_approval"]),
            ).order_by(InstanceNode.sort_order).limit(len(all_inst_ids))
        )
        for n in node_result.scalars().all():
            if n.instance_id not in current_nodes:
                current_nodes[n.instance_id] = n

    # 批量获取当前负责人姓名
    assignee_ids = list(set(n.assignee_id for n in current_nodes.values() if n.assignee_id))
    users_map = {}
    if assignee_ids:
        users_result = await db.execute(select(User).where(User.id.in_(assignee_ids)))
        users_map = {u.id: u.real_name for u in users_result.scalars().all()}

    result = []
    for org in orgs:
        org_insts = insts_by_org.get(org.id, [])
        items = []
        for inst in org_insts:
            cn = current_nodes.get(inst.id)
            items.append({
                "id": inst.id,
                "name": inst.name,
                "priority": inst.priority,
                "current_node_name": cn.name if cn else "—",
                "current_assignee_name": users_map.get(cn.assignee_id, "") if cn and cn.assignee_id else "",
                "status": inst.status,
            })
        result.append({
            "org_id": org.id,
            "org_name": org.name,
            "running_count": len(items),
            "instances": items,
        })

    return result
