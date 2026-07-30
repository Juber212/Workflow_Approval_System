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
from app.services.instance._helpers import compute_deadline_info
from app.schemas.dashboard import (
    DashboardData,
    DashboardStats,
    TaskDistItem,
    BottleneckItem,
    OverdueItem,
    OrgOverview,
    MyTaskCounts,
    MyPendingItem,
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

    # ─── 3. 流程卡点追踪（项目 + 方案分开） ───
    bottleneck = await _get_bottleneck_tracking(db, now, exclude_proposal_tpl_ids=proposal_tpl_ids)
    proposal_bottleneck = await _get_bottleneck_tracking(db, now, proposal_only_tpl_ids=proposal_tpl_ids)

    # ─── 4. 超期预警列表 ───
    overdue_list = await _get_overdue_list(db, now)

    # ─── 5. 各所流程概览（项目 + 方案分开，前端 tab 切换） ───
    org_overview = await _get_org_overview(db, exclude_proposal_tpl_ids=proposal_tpl_ids)
    proposal_org_overview = await _get_org_overview(db, proposal_only_tpl_ids=proposal_tpl_ids)

    # ─── 6. 我的待办（个人统计 + 列表） ───
    if user_id:
        pending_items = await _get_my_pending_items(db, user_id)
        my_task_counts = await _get_my_task_counts(db, user_id)
    else:
        pending_items = {"project": [], "proposal": []}
        my_task_counts = MyTaskCounts()

    return DashboardData(
        stats=DashboardStats(**stats),
        proposal_stats=proposal_stats,
        task_distribution=task_dist,
        bottleneck=bottleneck,
        proposal_bottleneck=proposal_bottleneck,
        overdue_list=overdue_list,
        org_overview=org_overview,
        proposal_org_overview=proposal_org_overview,
        my_task_counts=my_task_counts,
        my_pending=pending_items["project"],
        proposal_my_pending=pending_items["proposal"],
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


async def _get_bottleneck_tracking(
    db: AsyncSession,
    now: datetime,
    exclude_proposal_tpl_ids: set = frozenset(),
    proposal_only_tpl_ids: set = frozenset(),
) -> list[BottleneckItem]:
    """流程卡点追踪 —— 运行中实例的节点进度链（PRD §4.5）

    Args:
        exclude_proposal_tpl_ids: 排除这些模板 ID（用于项目）
        proposal_only_tpl_ids: 仅统计这些模板 ID（用于方案）
    """
    # 构建过滤条件
    conditions = [FlowInstance.status == "running"]
    if exclude_proposal_tpl_ids:
        conditions.append(FlowInstance.template_id.notin_(exclude_proposal_tpl_ids))
    elif proposal_only_tpl_ids:
        conditions.append(FlowInstance.template_id.in_(proposal_only_tpl_ids))

    # 查询运行中实例
    instances_result = await db.execute(
        select(FlowInstance).where(*conditions).order_by(
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

    # 批量查节点（不再排除 is_end：终审时结束节点为活跃状态，需显示）
    nodes_result = await db.execute(
        select(InstanceNode).where(
            InstanceNode.instance_id.in_(inst_ids),
            InstanceNode.is_start == False,
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

    # 批量查所有人员姓名（负责人 + 校验人 + 审批人 + 批准人）
    all_personnel_ids: set[int] = set()
    for n in all_nodes:
        if n.assignee_id:
            all_personnel_ids.add(n.assignee_id)
        if n.endorser_id:
            all_personnel_ids.add(n.endorser_id)
        if n.checkers:
            for c in n.checkers:
                uid = c.get("user_id") if isinstance(c, dict) else c
                if uid:
                    all_personnel_ids.add(uid)
        if n.approvers:
            for a in n.approvers:
                uid = a.get("user_id") if isinstance(a, dict) else a
                if uid:
                    all_personnel_ids.add(uid)
    users_map: dict[int, str] = {}
    if all_personnel_ids:
        users_result = await db.execute(
            select(User.id, User.real_name).where(User.id.in_(list(all_personnel_ids)))
        )
        users_map = {uid: name for uid, name in users_result.all()}

    # 辅助函数：根据节点状态计算当前处理人
    def _calc_handlers(node: InstanceNode) -> str:
        status = (node.status or "").lower()
        if status in ("running", "pending", "processing"):
            name = users_map.get(node.assignee_id, "") if node.assignee_id else ""
            return name or "—"
        if status == "waiting_check":
            cids = []
            if node.checkers:
                for c in node.checkers:
                    uid = c.get("user_id") if isinstance(c, dict) else c
                    if uid:
                        cids.append(uid)
            if not cids:
                return "—"
            if len(cids) == 1:
                return users_map.get(cids[0], "") or "—"
            first_name = users_map.get(cids[0], "") or "?"
            return f"{first_name}等{len(cids)}人"
        if status == "waiting_approval":
            aids = []
            if node.approvers:
                for a in node.approvers:
                    uid = a.get("user_id") if isinstance(a, dict) else a
                    if uid:
                        aids.append(uid)
            if not aids:
                return "—"
            if len(aids) == 1:
                return users_map.get(aids[0], "") or "—"
            first_name = users_map.get(aids[0], "") or "?"
            return f"{first_name}等{len(aids)}人"
        if status == "waiting_endorsement":
            name = users_map.get(node.endorser_id, "") if node.endorser_id else ""
            return name or "—"
        return "—"

    items = []
    for inst in instances:
        nodes = nodes_by_inst.get(inst.id, [])
        if not nodes:
            continue

        # 构建节点进度链
        progress_chain = []
        current_node_name = ""
        current_handlers = "—"
        all_finished = True
        has_overdue = False
        has_near_overdue = False
        near_future = now + timedelta(days=2)

        for node in nodes:
            status_icon = "waiting"  # 待开始
            if node.status == "finished":
                status_icon = "done"
            elif node.status in ("running", "waiting_check", "waiting_approval", "waiting_endorsement"):
                status_icon = "active"
                all_finished = False
                current_node_name = node.name
                current_handlers = _calc_handlers(node)
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
            current_handlers=current_handlers,
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


async def _get_org_overview(
    db: AsyncSession,
    exclude_proposal_tpl_ids: set = frozenset(),
    proposal_only_tpl_ids: set = frozenset(),
) -> list[OrgOverview]:
    """各所流程概览 —— 按组织统计项目/方案数（PRD §4.7）

    Args:
        exclude_proposal_tpl_ids: 排除这些模板 ID（用于项目概览）
        proposal_only_tpl_ids: 仅统计这些模板 ID（用于方案概览）
        两个参数互斥，同时只传一个。

    返回每个组织的：全部、运行中、已完成 三组数据，
    供前端柱状图和饼图渲染。
    """
    orgs_result = await db.execute(
        select(Organization).where(Organization.is_active == True)
    )
    orgs = orgs_result.scalars().all()
    if not orgs:
        return []

    org_ids = [o.id for o in orgs]

    # 构建过滤条件
    conditions = [FlowInstance.organization_id.in_(org_ids)]
    if exclude_proposal_tpl_ids:
        conditions.append(FlowInstance.template_id.notin_(exclude_proposal_tpl_ids))
    elif proposal_only_tpl_ids:
        conditions.append(FlowInstance.template_id.in_(proposal_only_tpl_ids))

    # 一次性按组织 + 状态分组统计（单个 SQL，避免 N+1）
    from sqlalchemy import func
    stats_stmt = (
        select(
            FlowInstance.organization_id,
            FlowInstance.status,
            func.count(FlowInstance.id),
        )
        .where(*conditions)
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
        terminated = sc.get("terminated", 0)
        total = sum(sc.values())

        result.append(OrgOverview(
            org_id=org.id,
            org_name=org.name,
            total_count=total,
            running_count=running,
            completed_count=completed,
            terminated_count=terminated,
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


# ─── 优先级排序键映射 ───
_PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
# ─── 类型标签映射 ───
_TYPE_LABEL: dict[str, str] = {"task": "待办", "check": "校验", "approval": "审批"}
# ─── 列表最大条数 ───
_MAX_PENDING_ITEMS = 8


async def _get_my_pending_items(db: AsyncSession, user_id: int) -> dict:
    """
    查询当前用户待办/校验/审批列表，合并排序后按项目/方案分组。

    三张表（Task / CheckRecord / Approval）各查一次，
    在 Python 层合并 → 按优先级 + 截止时间排序 → 按 template_type 分组。

    返回 {"project": [...], "proposal": [...]}，每组最多 8 条
    """
    from datetime import datetime as dt

    # 构建 SELECT 列的工厂函数 —— 三表查询列完全相同
    def _cols(id_col, record_type: str):
        return (
            id_col.label("rid"),
            InstanceNode.name.label("node_name"),
            InstanceNode.deadline.label("deadline"),
            FlowInstance.name.label("instance_name"),
            FlowInstance.priority.label("priority"),
            FlowInstance.template_type.label("template_type"),
            FlowInstance.id.label("instance_id"),
        )

    # ── 1. 待办任务 ──
    task_rows = (await db.execute(
        select(*_cols(Task.id, "task"))
        .join(InstanceNode, Task.node_id == InstanceNode.id)
        .join(FlowInstance, Task.instance_id == FlowInstance.id)
        .where(
            Task.assignee_id == user_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING]),
        )
    )).all()

    # ── 2. 待校验 ──
    check_rows = (await db.execute(
        select(*_cols(CheckRecord.id, "check"))
        .join(InstanceNode, CheckRecord.node_id == InstanceNode.id)
        .join(FlowInstance, CheckRecord.instance_id == FlowInstance.id)
        .where(
            CheckRecord.checker_id == user_id,
            CheckRecord.status == CheckStatus.PENDING,
        )
    )).all()

    # ── 3. 待审批 ──
    approval_rows = (await db.execute(
        select(*_cols(Approval.id, "approval"))
        .join(InstanceNode, Approval.node_id == InstanceNode.id)
        .join(FlowInstance, Approval.instance_id == FlowInstance.id)
        .where(
            Approval.approver_id == user_id,
            Approval.status == ApprovalStatus.PENDING,
        )
    )).all()

    # ── 4. 合并 → Python 排序 ──
    all_items: list[dict] = []
    for record_type, rows in [("task", task_rows), ("check", check_rows), ("approval", approval_rows)]:
        for row in rows:
            tpl_type = row.template_type or "project"
            d = row.deadline
            is_overdue, days_remaining = compute_deadline_info(d)
            all_items.append({
                "type": record_type,
                "type_label": _TYPE_LABEL[record_type],
                "id": row.rid,
                "instance_id": row.instance_id,
                "instance_name": row.instance_name,
                "node_name": row.node_name or "",
                "priority": row.priority or "normal",
                "deadline": d.isoformat() if d else None,
                "is_overdue": is_overdue,
                "days_remaining": days_remaining,
                "_tpl_type": tpl_type,  # 内部用于分组，不暴露给前端
            })

    # 排序：优先级降序 → 截止时间升序（无截止排最后）
    all_items.sort(key=lambda x: (
        _PRIORITY_ORDER.get(x["priority"], 9),
        x["deadline"] is None,
        x["deadline"] or "",
    ))

    # ── 5. 按 template_type 分组 + Top N ──
    projects: list[dict] = []
    proposals: list[dict] = []
    for it in all_items:
        t = it.pop("_tpl_type")
        if t == "project":
            if len(projects) < _MAX_PENDING_ITEMS:
                projects.append(it)
        else:
            if len(proposals) < _MAX_PENDING_ITEMS:
                proposals.append(it)
    return {"project": projects, "proposal": proposals}
