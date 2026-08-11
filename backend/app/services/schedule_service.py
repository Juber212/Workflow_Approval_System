"""排产服务 —— 实例发起时按流程节点自动生成排产计划（自然日顺排 + 资源冲突避免）

排产独立于流程执行：工序 = 工作节点（排除开始/结束），
从发起日按 time_limit_days 自然日顺排，为每道工序分配一个当前空闲的负责人。
首期资源规则：每人同时只能做一个任务（时间窗口不重叠），候选 = 节点配置人员，
优先级负责人 > 校验人 > 审批人 > 批准人；候选全忙时顺延到最早空闲者。
"""

from datetime import date, timedelta

from sqlalchemy import select, delete

from app.models import ScheduleItem, FlowInstance, InstanceNode, User
from app.services.validation_service import extract_person_ids
from app.schemas.schedule import ScheduleItemOut


def _node_candidates(node: InstanceNode) -> list[int]:
    """节点候选人员，按优先级排序（负责人 > 校验人 > 审批人 > 批准人），去重保序"""
    cands: list[int] = []
    if node.assignee_id:
        cands.append(node.assignee_id)
    cands.extend(sorted(extract_person_ids(node.checkers)))
    cands.extend(sorted(extract_person_ids(node.approvers)))
    if node.endorser_id:
        cands.append(node.endorser_id)
    seen: set[int] = set()
    result: list[int] = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


async def _pick_available(
    db, candidates: list[int], plan_start: date, plan_end: date,
) -> int | None:
    """在 [plan_start, plan_end] 窗口内找空闲候选（该用户无其他排产任务与之重叠）"""
    if not candidates:
        return None
    rows = (await db.execute(
        select(ScheduleItem).where(
            ScheduleItem.assignee_id.in_(candidates),
            ScheduleItem.plan_start_date <= plan_end,
            ScheduleItem.plan_end_date >= plan_start,
        )
    )).scalars().all()
    busy = {r.assignee_id for r in rows}
    for c in candidates:
        if c not in busy:
            return c
    return None


async def _pick_earliest_free(db, candidates: list[int]) -> tuple[int, date]:
    """候选全忙时：算每人最早空闲日（其已有排产最晚结束 + 1 天），选最早的并顺延"""
    rows = (await db.execute(
        select(ScheduleItem).where(ScheduleItem.assignee_id.in_(candidates))
    )).scalars().all()
    latest_end: dict[int, date] = {}
    for r in rows:
        if r.assignee_id not in latest_end or r.plan_end_date > latest_end[r.assignee_id]:
            latest_end[r.assignee_id] = r.plan_end_date
    best: int | None = None
    best_free: date | None = None
    for c in candidates:
        free = latest_end.get(c)
        free_day = free + timedelta(days=1) if free else date.today()
        if best is None or free_day < best_free:
            best = c
            best_free = free_day
    assert best is not None and best_free is not None
    return best, best_free


async def schedule_instance(db, instance_id: int) -> None:
    """发起后生成排产计划（幂等：先删旧排产再生成，供重排复用）

    逐节点自然日顺排：首节点从发起日，后续节点衔接上一节点结束次日。
    """
    # 取实例工作节点（排除开始/结束）
    nodes = (await db.execute(
        select(InstanceNode).where(
            InstanceNode.instance_id == instance_id,
            InstanceNode.is_start == False,
            InstanceNode.is_end == False,
        ).order_by(InstanceNode.sort_order)
    )).scalars().all()
    if not nodes:
        return

    inst = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == instance_id)
    )).scalar_one_or_none()
    if inst is None:
        return
    # 排产起点 = 发起日（固定发起日口径，自然日）
    start_date = inst.created_at.date() if inst.created_at else date.today()

    # 幂等：清掉该实例已有排产
    await db.execute(delete(ScheduleItem).where(ScheduleItem.instance_id == instance_id))

    cursor_date = start_date  # 当前节点可用的最早开始日
    for node in nodes:
        duration = max(node.time_limit_days or 1, 1)
        plan_start = cursor_date
        plan_end = plan_start + timedelta(days=duration - 1)

        # 资源分配：候选空闲优先，全忙则顺延到最早空闲者
        candidates = _node_candidates(node)
        assignee = await _pick_available(db, candidates, plan_start, plan_end)
        if assignee is None and candidates:
            assignee, earliest_free = await _pick_earliest_free(db, candidates)
            plan_start = earliest_free
            plan_end = plan_start + timedelta(days=duration - 1)

        db.add(ScheduleItem(
            instance_id=instance_id,
            node_id=node.id,
            assignee_id=assignee,
            plan_start_date=plan_start,
            plan_end_date=plan_end,
            duration_days=duration,
            sort_order=node.sort_order,
        ))
        # flush 让后续节点资源分配能看到已分配的排产
        await db.flush()
        # 后续节点从本节点结束次日开始
        cursor_date = plan_end + timedelta(days=1)


async def get_instance_schedule(db, instance_id: int) -> list[ScheduleItemOut]:
    """返回实例排产列表（含节点名/分配人名），按 sort_order 排序"""
    items = (await db.execute(
        select(ScheduleItem).where(ScheduleItem.instance_id == instance_id)
        .order_by(ScheduleItem.sort_order)
    )).scalars().all()
    if not items:
        return []

    node_ids = {i.node_id for i in items}
    user_ids = {i.assignee_id for i in items}
    node_map = {
        n.id: n for n in (await db.execute(
            select(InstanceNode).where(InstanceNode.id.in_(node_ids))
        )).scalars().all()
    }
    user_map = {
        u.id: u for u in (await db.execute(
            select(User).where(User.id.in_(user_ids))
        )).scalars().all()
    }
    return [
        ScheduleItemOut(
            node_id=i.node_id,
            node_name=node_map[i.node_id].name if i.node_id in node_map else "",
            assignee_id=i.assignee_id,
            assignee_name=user_map[i.assignee_id].real_name if i.assignee_id in user_map else "",
            plan_start=i.plan_start_date.isoformat(),
            plan_end=i.plan_end_date.isoformat(),
            duration=i.duration_days,
            sort_order=i.sort_order,
        )
        for i in items
    ]
