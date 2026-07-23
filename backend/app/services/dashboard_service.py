"""Dashboard 服务 —— 全局统计数据聚合（PRD §4）"""
from datetime import datetime, timedelta

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FlowInstance,
    FlowTemplate,
    InstanceNode,
    Task,
    Organization,
    User,
    CheckRecord,
    Approval,
)
from app.models.enums import TaskStatus, CheckStatus, ApprovalStatus
from app.schemas.dashboard import (
    DashboardData,
    DashboardStats,
    TaskDistItem,
    BottleneckItem,
    OverdueItem,
    OrgOverview,
    MyTaskCounts,
)


async def get_dashboard_stats(db: AsyncSession, user_id: int | None = None) -> dict:
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

    # 获取方案模板 ID 集合（用于区分项目/方案）
    proposal_tpl_ids = set(
        row[0] for row in (await db.execute(
            select(FlowTemplate.id).where(FlowTemplate.type == "proposal")
        )).all()
    )

    # 项目实例过滤条件：非方案模板
    not_proposal = FlowInstance.template_id.notin_(proposal_tpl_ids) if proposal_tpl_ids else True

    # ─── 1. 项目四大统计卡片 ───

    running_count = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "running", not_proposal
        )
    )).scalar() or 0

    archived_count = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed", not_proposal
        )
    )).scalar() or 0

    archived_this_month = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed",
            FlowInstance.completed_at >= month_start,
            not_proposal,
        )
    )).scalar() or 0

    near_future = now + timedelta(days=2)
    overdue_count = (await db.execute(
        select(func.count()).select_from(Task).join(
            InstanceNode, Task.node_id == InstanceNode.id
        ).join(
            FlowInstance, Task.instance_id == FlowInstance.id
        ).where(
            Task.status.notin_(["completed", "terminated"]),
            InstanceNode.deadline.isnot(None),
            InstanceNode.deadline < near_future,
            not_proposal,
        )
    )).scalar() or 0

    stats = {
        "running_instances": running_count,
        "archived_total": archived_count,
        "archived_this_month": archived_this_month,
        "overdue_warnings": overdue_count,
    }

    # ─── 1b. 方案四大统计卡片 ───
    is_proposal = FlowInstance.template_id.in_(proposal_tpl_ids) if proposal_tpl_ids else False

    prop_total = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(is_proposal)
    )).scalar() or 0

    prop_running = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "running", is_proposal
        )
    )).scalar() or 0

    prop_completed = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed", is_proposal
        )
    )).scalar() or 0

    prop_this_month = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed",
            FlowInstance.completed_at >= month_start,
            is_proposal,
        )
    )).scalar() or 0

    proposal_stats = DashboardStats(
        running_instances=prop_running,
        archived_total=prop_completed,
        archived_this_month=prop_this_month,
        overdue_warnings=0,  # 方案暂不做超期预警
        total=prop_total,    # 方案总数
    )

    # ─── 2. 任务状态分布 ───
    task_dist = await _get_task_distribution(db, now)

    # ─── 3. 流程卡点追踪 ───
    bottleneck = await _get_bottleneck_tracking(db, now)

    # ─── 4. 超期预警列表 ───
    overdue_list = await _get_overdue_list(db, now)

    # ─── 5. 各所流程概览 ───
    org_overview = await _get_org_overview(db)

    # ─── 6. 我的待办（个人统计） ───
    my_task_counts = await _get_my_task_counts(db, user_id) if user_id else MyTaskCounts()

    return DashboardData(
        stats=DashboardStats(**stats),
        proposal_stats=proposal_stats,
        task_distribution=task_dist,
        bottleneck=bottleneck,
        overdue_list=overdue_list,
        org_overview=org_overview,
        my_task_counts=my_task_counts,
    )


async def _get_task_distribution(db: AsyncSession, now: datetime) -> list[TaskDistItem]:
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

    result: list[TaskDistItem] = []
    for status in statuses:
        conditions = [Task.status == status]
        if status == "completed":
            conditions.append(Task.completed_at >= thirty_days_ago)

        count = (await db.execute(
            select(func.count()).select_from(Task).where(*conditions)
        )).scalar() or 0

        result.append(TaskDistItem(
            status=status,
            label=labels.get(status, status),
            color=colors.get(status, "#909399"),
            count=count,
        ))

    return result


async def _get_bottleneck_tracking(db: AsyncSession, now: datetime) -> list[BottleneckItem]:
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
            status_icon = "waiting"  # 待开始
            if node.status == "finished":
                status_icon = "done"
            elif node.status in ("running", "waiting_check", "waiting_approval"):
                status_icon = "active"
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
            if node.assignee_id and status_icon in ("active", "done"):
                assignee_label = f" {users_map.get(node.assignee_id, '')}"

            progress_chain.append(f"{status_icon}{node.name}{assignee_label}")

        # 逾期判定
        if has_overdue:
            overdue_status = "已逾期"
        elif has_near_overdue:
            overdue_status = "即将逾期"
        else:
            overdue_status = "正常"

        # 进度统计：已完成节点数 / 总工作节点数
        finished_count = sum(1 for n in nodes if n.status == "finished")
        total_nodes = len(nodes)

        items.append(BottleneckItem(
            instance_id=inst.id,
            instance_name=inst.name,
            organization_name=orgs.get(inst.organization_id, ""),
            progress_chain=progress_chain,
            current_node_name=current_node_name,
            current_assignee_name=current_assignee_name,
            priority=inst.priority,
            difficulty=inst.difficulty or "1",
            finished_count=finished_count,
            total_nodes=total_nodes,
            overdue_status=overdue_status,
            all_finished=all_finished,
        ))

    return items


async def _get_overdue_list(db: AsyncSession, now: datetime) -> list[OverdueItem]:
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
                days_label = f"已逾期 {-delta}天"
            else:
                days_label = f"还剩 {delta}天"
        else:
            days_label = "—"

        items.append(OverdueItem(
            task_id=task.id,
            instance_id=task.instance_id,
            instance_name=inst.name if inst else "",
            node_name=node.name,
            assignee_name=assignee.real_name if assignee else "",
            deadline=dl.isoformat() if dl else None,
            days_label=days_label,
            organization_name="",
            is_overdue=dl is not None and dl < now,
        ))

    # 排序：逾期从多到少，然后剩余从少到多
    items.sort(key=lambda x: (
        not x.is_overdue,
        -(abs((datetime.fromisoformat(x.deadline) - now).days) if x.deadline else 0) if x.is_overdue else 999,
        abs((datetime.fromisoformat(x.deadline) - now).days) if x.deadline and not x.is_overdue else 999,
    ))

    return items


async def _get_org_overview(db: AsyncSession) -> list[OrgOverview]:
    """各所流程概览 —— 按组织统计项目数（PRD §4.7）

    返回每个组织的：全部项目、运行中、已完成 三组数据，
    供前端柱状图和饼图渲染。
    """
    orgs_result = await db.execute(
        select(Organization).where(Organization.is_active == True)
    )
    orgs = orgs_result.scalars().all()
    if not orgs:
        return []

    org_ids = [o.id for o in orgs]

    # 一次性按组织 + 状态分组统计（单个 SQL，避免 N+1）
    from sqlalchemy import func
    stats_stmt = (
        select(
            FlowInstance.organization_id,
            FlowInstance.status,
            func.count(FlowInstance.id),
        )
        .where(FlowInstance.organization_id.in_(org_ids))
        .group_by(FlowInstance.organization_id, FlowInstance.status)
    )
    stats_rows = (await db.execute(stats_stmt)).all()

    # 组织 -> {status: count}
    org_stats: dict[int, dict[str, int]] = {}
    for org_id, status, count in stats_rows:
        org_stats.setdefault(org_id, {})[status] = count

    result = []
    for org in orgs:
        sc = org_stats.get(org.id, {})
        running = sc.get("running", 0)
        completed = sc.get("completed", 0)
        total = sum(sc.values())

        result.append(OrgOverview(
            org_id=org.id,
            org_name=org.name,
            total_count=total,
            running_count=running,
            completed_count=completed,
        ))

    return result


async def _get_my_task_counts(db: AsyncSession, user_id: int) -> MyTaskCounts:
    """
    当前用户的个人待办统计（PRD §4.8）

    分别统计三张表：
    - 待处理：tasks 表，assignee_id = 本人，status = 'pending'
    - 待校验：check_records 表，checker_id = 本人，status = 'pending'
    - 待审批：approvals 表，approver_id = 本人，status = 'pending'
    """
    # 待处理任务数（pending=刚分配未开始, processing=处理中，都算待处理）
    pending = (await db.execute(
        select(func.count()).select_from(Task).where(
            Task.assignee_id == user_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING]),
        )
    )).scalar() or 0

    # 待校验数
    checking = (await db.execute(
        select(func.count()).select_from(CheckRecord).where(
            CheckRecord.checker_id == user_id,
            CheckRecord.status == CheckStatus.PENDING,
        )
    )).scalar() or 0

    # 待审批数
    approval = (await db.execute(
        select(func.count()).select_from(Approval).where(
            Approval.approver_id == user_id,
            Approval.status == ApprovalStatus.PENDING,
        )
    )).scalar() or 0

    return MyTaskCounts(pending=pending, checking=checking, approval=approval)
