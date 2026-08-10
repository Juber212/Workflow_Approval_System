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
    BottleneckItem,
    OrgOverview,
    TrendPoint,
    TrendData,
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

    # M15：项目/方案区分改用实例快照 template_type（不依赖模板是否仍存在）——
    # 方案模板被删除后，已完成/已终止的方案实例若按 template_id 集合判断会被误算为项目，
    # 与列表页「template_type 快照」口径统一
    project_filter = FlowInstance.template_type == "project"
    proposal_filter = FlowInstance.template_type == "proposal"

    # ─── 1. 项目四大统计卡片 ───

    running_count = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "running", project_filter
        )
    )).scalar() or 0

    archived_count = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed", project_filter
        )
    )).scalar() or 0

    archived_this_month = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed",
            FlowInstance.completed_at >= month_start,
            project_filter,
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
            project_filter,
        )
    )).scalar() or 0

    stats = {
        "running_instances": running_count,
        "archived_total": archived_count,
        "archived_this_month": archived_this_month,
        "overdue_warnings": overdue_count,
    }

    # ─── 1b. 方案四大统计卡片 ───

    prop_total = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(proposal_filter)
    )).scalar() or 0

    prop_running = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "running", proposal_filter
        )
    )).scalar() or 0

    prop_completed = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed", proposal_filter
        )
    )).scalar() or 0

    prop_this_month = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(
            FlowInstance.status == "completed",
            FlowInstance.completed_at >= month_start,
            proposal_filter,
        )
    )).scalar() or 0

    proposal_stats = DashboardStats(
        running_instances=prop_running,
        archived_total=prop_completed,
        archived_this_month=prop_this_month,
        overdue_warnings=0,  # 方案暂不做超期预警
        total=prop_total,    # 方案总数
    )

    # ─── 2. 流程卡点追踪（项目 + 方案分开；列表取前 N 条 + 真实总数，防运行中实例量级拖慢首页） ───
    bottleneck, bottleneck_total = await _get_bottleneck_tracking(db, now, template_type="project")
    proposal_bottleneck, proposal_bottleneck_total = await _get_bottleneck_tracking(db, now, template_type="proposal")

    # ─── 3. 各所流程概览（项目 + 方案分开，前端 tab 切换） ───
    org_overview = await _get_org_overview(db, template_type="project")
    proposal_org_overview = await _get_org_overview(db, template_type="proposal")

    # ─── 4. 我的待办（个人列表，P1-33 已 Top 8 + 真实计数） ───
    if user_id:
        pending_items = await _get_my_pending_items(db, user_id)
    else:
        pending_items = {"project": [], "project_total": 0, "proposal": [], "proposal_total": 0}

    return DashboardData(
        stats=DashboardStats(**stats),
        proposal_stats=proposal_stats,
        bottleneck=bottleneck,
        bottleneck_total=bottleneck_total,
        proposal_bottleneck=proposal_bottleneck,
        proposal_bottleneck_total=proposal_bottleneck_total,
        org_overview=org_overview,
        proposal_org_overview=proposal_org_overview,
        my_pending=pending_items["project"],
        my_pending_total=pending_items["project_total"],
        proposal_my_pending=pending_items["proposal"],
        proposal_my_pending_total=pending_items["proposal_total"],
    )


async def _get_bottleneck_tracking(
    db: AsyncSession,
    now: datetime,
    template_type: str | None = None,
) -> tuple[list[BottleneckItem], int]:
    """流程卡点追踪 —— 运行中实例的节点进度链（PRD §4.5）

    Args:
        template_type: "project" | "proposal"（M15：改用实例快照 template_type 口径）

    Returns:
        (items, total)：items 仅取前 _BOTTLENECK_LIMIT 条（按优先级 + 发起时间排序），
        total 为该视图真实运行中实例总数（供前端展示「共 N 条」）。
    """
    # 构建过滤条件
    conditions = [FlowInstance.status == "running"]
    if template_type:
        conditions.append(FlowInstance.template_type == template_type)

    # 真实运行中实例总数（独立 count 走 idx_status 索引，避免全量拉取实例再 len）
    total = (await db.execute(
        select(func.count()).select_from(FlowInstance).where(*conditions)
    )).scalar() or 0

    # 查询运行中实例（SQL 层 limit：看板一屏展示，防运行中实例量级拖慢首页）
    instances_result = await db.execute(
        select(FlowInstance).where(*conditions).order_by(
            case(
                (FlowInstance.priority == "urgent", 0),
                (FlowInstance.priority == "high", 1),
                (FlowInstance.priority == "normal", 2),
                else_=3,
            ),
            FlowInstance.initiated_at.asc(),
        ).limit(_BOTTLENECK_LIMIT)
    )
    instances = instances_result.scalars().all()

    if not instances:
        return [], total

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

    return items, total


async def _get_org_overview(
    db: AsyncSession,
    template_type: str | None = None,
) -> list[OrgOverview]:
    """各所流程概览 —— 按组织统计项目/方案数（PRD §4.7）

    Args:
        template_type: "project" | "proposal"（M15：改用实例快照 template_type 口径）

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
    if template_type:
        conditions.append(FlowInstance.template_type == template_type)

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

    # 完成数按粒度统计（日/月/年）——柱状图「已完成」可切换粒度查看（产品口径 2026-08-10）。
    # 单次 SUM(CASE) 查询同时返回今日/本月/本年完成数，避免三次查询。
    now = datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)  # 今日 0 点
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # 本月 1 日
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)  # 本年 1 月 1 日
    comp_stmt = (
        select(
            FlowInstance.organization_id,
            func.sum(case((FlowInstance.completed_at >= day_start, 1), else_=0)).label("day"),
            func.sum(case((FlowInstance.completed_at >= month_start, 1), else_=0)).label("month"),
            func.sum(case((FlowInstance.completed_at >= year_start, 1), else_=0)).label("year"),
        )
        .where(
            *conditions,
            FlowInstance.status == "completed",
            FlowInstance.completed_at >= year_start,  # 只需统计今年内的完成记录
        )
        .group_by(FlowInstance.organization_id)
    )
    comp_rows = (await db.execute(comp_stmt)).all()
    comp_map: dict[int, tuple[int, int, int]] = {
        org_id: (int(day or 0), int(month or 0), int(year or 0))
        for org_id, day, month, year in comp_rows
    }

    result = []
    for org in orgs:
        sc = org_stats.get(org.id, {})
        running = sc.get("running", 0)
        day_c, month_c, year_c = comp_map.get(org.id, (0, 0, 0))
        terminated = sc.get("terminated", 0)
        total = sum(sc.values())

        result.append(OrgOverview(
            org_id=org.id,
            org_name=org.name,
            total_count=total,
            running_count=running,
            completed_count=month_c,  # 本月已完成（兼容保留，柱状图默认粒度）
            terminated_count=terminated,
            day_completed_count=day_c,
            month_completed_count=month_c,
            year_completed_count=year_c,
        ))

    return result


# ─── 优先级排序键映射 ───
_PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
# ─── 类型标签映射 ───
_TYPE_LABEL: dict[str, str] = {"task": "待办", "check": "校验", "approval": "审批"}
# ─── 列表最大条数 ───
_MAX_PENDING_ITEMS = 8
# ─── 卡点追踪最大条数（看板一屏展示，防运行中实例量级拖慢首页） ───
_BOTTLENECK_LIMIT = 100


async def _get_my_pending_items(db: AsyncSession, user_id: int) -> dict:
    """
    查询当前用户待办/校验/审批列表，合并排序后按项目/方案分组。

    三张表（Task / CheckRecord / Approval）各查一次，
    在 Python 层合并 → 按优先级 + 截止时间排序 → 按 template_type 分组。

    返回 {"project": [...], "project_total": N, "proposal": [...], "proposal_total": M}，
    每组最多 8 条（_MAX_PENDING_ITEMS），project_total / proposal_total 为该组真实全量条数（P1-33）
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
    # P1-33：分组时同时统计每组真实全量条数（不截断），供前端「共 N 条」真实展示
    projects: list[dict] = []
    proposals: list[dict] = []
    project_total = 0
    proposal_total = 0
    for it in all_items:
        t = it.pop("_tpl_type")
        if t == "project":
            project_total += 1
            if len(projects) < _MAX_PENDING_ITEMS:
                projects.append(it)
        else:
            proposal_total += 1
            if len(proposals) < _MAX_PENDING_ITEMS:
                proposals.append(it)
    return {
        "project": projects,
        "project_total": project_total,
        "proposal": proposals,
        "proposal_total": proposal_total,
    }


# ─── 发起/归档趋势图相关 ───
_GRAN_MONTH = "%Y-%m"   # 月度分组格式（MySQL DATE_FORMAT）
_GRAN_YEAR = "%Y"       # 年度分组格式
_DEFAULT_MONTH_SPAN = 12  # 月度默认展示近 12 个月


def _shift_months(dt: datetime, n: int) -> datetime:
    """时间往前/后平移 n 个月，返回该月 1 日（跨年安全）"""
    total = dt.year * 12 + (dt.month - 1) - n
    return datetime(total // 12, total % 12 + 1, 1)


def _iter_months(start: datetime, end: datetime):
    """迭代 start 到 end（含）之间的每个 (year, month)，含首尾"""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            m = 1
            y += 1


async def get_flow_trends(
    db: AsyncSession,
    granularity: str,
    category: str,
    year: int | None = None,
) -> TrendData:
    """发起/归档趋势 —— 按 月/年 粒度统计发起量与归档量（首页趋势卡片）

    Args:
        granularity: "month" | "year"
        category: "project" | "proposal"（口径与 get_dashboard_stats 完全一致）
        year: 仅 month 粒度使用；省略 = 近 12 个月，指定 = 该年 12 个月

    实现要点：
    - 发起量按 initiated_at 分组、归档量按 completed_at 分组，各一次聚合查询
    - 项目/方案过滤沿用 proposal_tpl_ids 集合口径（与统计卡片数字对得上）
    - Python 层生成连续时间段并补零，保证折线图不中断
    """
    now = datetime.now()

    # ── 1. 项目/方案口径（M15：改用实例快照 template_type，与统计卡片一致，不依赖模板存在性） ──
    inst_filter = FlowInstance.template_type == category

    # ── 2. 时间范围（仅 month 粒度需要下限；year 全历史） ──
    gran = _GRAN_YEAR if granularity == "year" else _GRAN_MONTH
    if granularity == "year":
        start = end = None  # 全历史
    elif year:
        start = datetime(year, 1, 1)      # 指定年份：该年 1 月 1 日起
        end = datetime(year + 1, 1, 1)    # 次年 1 月 1 日截止（不含）
    else:
        # 近 12 个月：当前月首日往前推 11 个月
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = _shift_months(month_start, _DEFAULT_MONTH_SPAN - 1)
        end = None  # 无上限（同当前月）

    def _range(column) -> list:
        """按粒度构造时间范围条件（两时间列都排除 NULL——发起量理论非空，防御脏数据防 int(None) 500）"""
        conds = []
        if column in (FlowInstance.initiated_at, FlowInstance.completed_at):
            conds.append(column.isnot(None))
        if start is not None:
            conds.append(column >= start)
        if end is not None:
            conds.append(column < end)
        return conds

    # ── 3. 发起量 / 归档量两次聚合（各一次 GROUP BY，避免逐时间段查询） ──
    initiated_expr = func.date_format(FlowInstance.initiated_at, gran)
    completed_expr = func.date_format(FlowInstance.completed_at, gran)
    initiated_rows = dict((await db.execute(
        select(initiated_expr.label("m"), func.count(FlowInstance.id))
        .where(inst_filter, *_range(FlowInstance.initiated_at))
        .group_by(initiated_expr)
    )).all())
    completed_rows = dict((await db.execute(
        select(completed_expr.label("m"), func.count(FlowInstance.id))
        .where(inst_filter, *_range(FlowInstance.completed_at))
        .group_by(completed_expr)
    )).all())

    # ── 4. 生成连续时间段 + 补零合并（保证折线不中断） ──
    all_keys = set(initiated_rows) | set(completed_rows)
    if granularity == "year":
        if not all_keys:
            return TrendData(granularity=granularity, periods=[])
        # 年度：最早数据年份 → 当前年（当年暂无数据也补 0）
        year_min = int(min(all_keys))
        year_max = max(int(max(all_keys)), now.year)
        periods_iter = ((y, 0) for y in range(year_min, year_max + 1))
    else:
        # 月度：连续月份序列（近 12 个月 或 指定年份 12 个月）
        m_start = start if not year else datetime(year, 1, 1)
        m_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) if not year else datetime(year, 12, 1)
        periods_iter = _iter_months(m_start, m_end)

    periods: list[TrendPoint] = []
    for y, m in periods_iter:
        key = str(y) if granularity == "year" else f"{y:04d}-{m:02d}"
        label = f"{y}年" if granularity == "year" else f"{y}年{m}月"
        periods.append(TrendPoint(
            period=key,
            label=label,
            initiated=initiated_rows.get(key, 0),
            completed=completed_rows.get(key, 0),
        ))

    return TrendData(granularity=granularity, periods=periods)
