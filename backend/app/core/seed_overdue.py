"""超期预警测试数据脚本 —— 造「已逾期 / 即将逾期」记录，覆盖待办/校验/审批/批准 4 类跳转

运行方式（在 backend 目录下执行）：
  python -m app.core.seed_overdue                # 造 4 条已逾期（3 天前到期）
  python -m app.core.seed_overdue --near         # 造 4 条即将逾期（1 天后到期，独立前缀）
  python -m app.core.seed_overdue --clean        # 清理本脚本造的全部数据（两个前缀）

用途：手动测试「超期预警」页面跳转详情页及「已逾期/即将逾期」标签展示。
所有当事人固定为 manager1，用 manager1 登录即可查看全部 4 类并正常跳转（详情页校验仅当事人可查看）。
"""

import asyncio
import sys
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models import (
    User, Organization,
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge,
)
from app.core.seed_test_data import (
    _make_task, _make_check, _make_approval, _make_endorsement,
)

# 前缀：与 seed_test_data 的 [测试] 区分开，清理时互不影响。
# 已逾期与即将逾期用不同前缀，可各自独立增删。
PREFIX_OVERDUE = "[测试超期]"   # 已逾期（deadline 过去）
PREFIX_NEAR = "[测试临期]"      # 即将逾期（deadline 未来 1 天）
ALL_PREFIXES = (PREFIX_OVERDUE, PREFIX_NEAR)
MANAGER_USERNAME = "manager1"  # 当事人：同一账号承担负责人/校验人/审批人/批准人
OVERDUE_DAYS = 3               # 已逾期：deadline 设为 3 天前
NEAR_DAYS = 1                  # 即将逾期：deadline 设为 1 天后
NOW = datetime.now()


# ════════════════════════════════════════════
# 清理（按前缀清理本脚本造的数据）
# ════════════════════════════════════════════
async def cleanup(session: AsyncSession, prefixes: tuple = ALL_PREFIXES) -> None:
    """按前缀清理实例与模板（仿 seed_test_data.cleanup_test_data）。

    遍历所有前缀收集实例/模板 ID（避免只清理第一个前缀导致残留）。
    """
    inst_ids: list[int] = []
    tpl_ids: list[int] = []
    for prefix in prefixes:
        result = await session.execute(
            select(FlowInstance.id).where(FlowInstance.name.like(f"{prefix}%"))
        )
        inst_ids.extend(r[0] for r in result.fetchall())
        result = await session.execute(
            select(FlowTemplate.id).where(FlowTemplate.name.like(f"{prefix}%"))
        )
        tpl_ids.extend(r[0] for r in result.fetchall())
    inst_ids = list(set(inst_ids))
    tpl_ids = list(set(tpl_ids))

    if not inst_ids and not tpl_ids:
        print("  无数据，无需清理")
        return

    await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    try:
        for table, col, ids in [
            ("endorsements", "instance_id", inst_ids),
            ("approvals", "instance_id", inst_ids),
            ("check_records", "instance_id", inst_ids),
            ("tasks", "instance_id", inst_ids),
            ("files", "instance_id", inst_ids),
            ("operation_logs", "instance_id", inst_ids),
            ("notifications", "instance_id", inst_ids),  # P1-19 补：先清通知，防残留跳转已删任务 404
            ("instance_edges", "instance_id", inst_ids),
            ("instance_nodes", "instance_id", inst_ids),
            ("flow_instances", "id", inst_ids),
            ("template_edges", "template_id", tpl_ids),
            ("template_nodes", "template_id", tpl_ids),
            ("flow_templates", "id", tpl_ids),
        ]:
            if not ids:
                continue
            placeholders = ",".join(str(int(i)) for i in ids)
            await session.execute(text(
                f"DELETE FROM {table} WHERE {col} IN ({placeholders})"
            ))
    finally:
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    print(f"  已清理 {len(inst_ids)} 个实例、{len(tpl_ids)} 个模板")


# ════════════════════════════════════════════
# 模板构建
# ════════════════════════════════════════════
async def create_template(session: AsyncSession, *, name: str, org_id: int,
                          created_by: int, person_name: str,
                          with_endorser: bool) -> int:
    """创建 3 节点模板（开始-工作-结束），返回模板 ID。

    with_endorser=True 时工作节点配置批准人（manager1），供难度4实例使用。
    """
    tpl = FlowTemplate(
        name=name, description="超期预警测试模板", type="project",
        organization_id=org_id, created_by=created_by,
    )
    session.add(tpl)
    await session.flush()

    # 3 个模板节点
    def _tpl_node(node_name, is_start=False, is_end=False, sort=0):
        return TemplateNode(
            template_id=tpl.id, name=node_name, is_start=is_start, is_end=is_end,
            assignee_id=None if is_start or is_end else created_by,
            time_limit_days=None if is_start or is_end else 7,
            require_file=not is_start and not is_end,
            checkers=[{"id": created_by, "name": person_name}] if not is_start and not is_end else None,
            approvers=[{"id": created_by, "name": person_name}] if not is_start and not is_end else None,
            approval_strategy="all_approve",
            endorser_id=created_by if (with_endorser and not is_start and not is_end) else None,
            require_assignee_signature=False,
            require_checker_signature=False,
            require_approver_signature=False,
            require_endorser_signature=bool(with_endorser and not is_start and not is_end),
            sort_order=sort,
            position_x=100 + sort * 200, position_y=300,
        )

    nodes = [_tpl_node("开始", is_start=True, sort=0),
             _tpl_node("工作节点", sort=1),
             _tpl_node("结束", is_end=True, sort=2)]
    for n in nodes:
        session.add(n)
    await session.flush()

    # 连线 开始→工作→结束
    for s, t in [(0, 1), (1, 2)]:
        session.add(TemplateEdge(
            template_id=tpl.id,
            source_node_id=nodes[s].id,
            target_node_id=nodes[t].id,
        ))
    await session.flush()
    return tpl.id


# ════════════════════════════════════════════
# 实例构建
# ════════════════════════════════════════════
async def create_instance(session: AsyncSession, *, name: str, tpl_id: int,
                          tpl_name: str, org_id: int, initiator_id: int,
                          difficulty: str, priority: str, scenario: str,
                          deadline_days: int) -> None:
    """创建一个运行中的超期/临期实例，按场景造出对应的待办/校验/审批/批准记录

    deadline_days: 工作节点相对今天的到期天数。负数为已逾期，正数为即将逾期。
    """
    inst = FlowInstance(
        name=name, description=f"超期预警测试：{scenario}",
        template_id=tpl_id, template_name=tpl_name, template_type="project",
        organization_id=org_id, initiator_id=initiator_id,
        priority=priority, difficulty=difficulty,
        status="running", initiated_at=NOW - timedelta(days=5),
    )
    session.add(inst)
    await session.flush()

    # 实例节点：从模板复制（工作节点 deadline 按 deadline_days 计算）
    tpl_nodes = (await session.execute(
        select(TemplateNode).where(TemplateNode.template_id == tpl_id).order_by(TemplateNode.sort_order)
    )).scalars().all()

    inst_nodes = []
    for t in tpl_nodes:
        deadline = None
        if not t.is_start and not t.is_end:
            deadline = NOW + timedelta(days=deadline_days)  # 正数=即将逾期，负数=已逾期
        n = InstanceNode(
            instance_id=inst.id, name=t.name, is_start=t.is_start, is_end=t.is_end,
            assignee_id=initiator_id if not t.is_start and not t.is_end else None,
            time_limit_days=t.time_limit_days, deadline=deadline,
            require_file=t.require_file, checkers=t.checkers, approvers=t.approvers,
            approval_strategy=t.approval_strategy, endorser_id=t.endorser_id,
            require_assignee_signature=t.require_assignee_signature,
            require_checker_signature=t.require_checker_signature,
            require_approver_signature=t.require_approver_signature,
            require_endorser_signature=t.require_endorser_signature,
            status="waiting", sort_order=t.sort_order, round=1,
        )
        session.add(n)
        inst_nodes.append(n)
    await session.flush()

    # 连线
    tpl_edges = (await session.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == tpl_id)
    )).scalars().all()
    id_map = {t.id: n.id for t, n in zip(tpl_nodes, inst_nodes)}
    for e in tpl_edges:
        session.add(InstanceEdge(
            instance_id=inst.id,
            source_node_id=id_map[e.source_node_id],
            target_node_id=id_map[e.target_node_id],
        ))

    # 场景：设置节点状态 + 任务/校验/审批/批准记录
    start = next(n for n in inst_nodes if n.is_start)
    work = next(n for n in inst_nodes if not n.is_start and not n.is_end)
    start.status = "finished"
    start.completed_at = NOW - timedelta(days=4)

    uid = initiator_id
    if scenario == "task":            # 处理中 → 超期待办
        work.status = "running"
        work.started_at = NOW - timedelta(days=2)
        await _make_task(session, inst.id, work.id, uid, "processing", 1,
                         NOW - timedelta(days=2), None, "超期测试：任务处理中")
    elif scenario == "check":         # 待校验 → 超期校验
        work.status = "waiting_check"
        work.started_at = NOW - timedelta(days=2)
        task = await _make_task(session, inst.id, work.id, uid, "waiting_check", 1,
                                NOW - timedelta(days=2), NOW - timedelta(days=1), "已提交，等待校验")
        _make_check(session, inst.id, work.id, task.id, uid, "pending", 1)
    elif scenario == "approval":      # 待审批 → 超期审批
        work.status = "waiting_approval"
        work.started_at = NOW - timedelta(days=2)
        task = await _make_task(session, inst.id, work.id, uid, "waiting_approval", 1,
                                NOW - timedelta(days=2), NOW - timedelta(days=1), "已提交，校验通过")
        _make_check(session, inst.id, work.id, task.id, uid, "passed", 1, "校验通过")
        _make_approval(session, inst.id, work.id, task.id, uid, "pending", 1)
    elif scenario == "endorsement":   # 待批准(难度4) → 超期批准
        work.status = "waiting_endorsement"
        work.started_at = NOW - timedelta(days=2)
        task = await _make_task(session, inst.id, work.id, uid, "waiting_endorsement", 1,
                                NOW - timedelta(days=2), NOW - timedelta(days=1), "已提交，等待批准")
        _make_check(session, inst.id, work.id, task.id, uid, "passed", 1, "校验通过")
        _make_approval(session, inst.id, work.id, task.id, uid, "approved", 1, "审批通过")
        _make_endorsement(session, inst.id, work.id, task.id, uid, "pending", 1)

    await session.flush()
    print(f"  + 实例: {name} [{scenario}]")


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════
async def seed(near: bool = False) -> None:
    """near=False 造已逾期（3 天前）；near=True 造即将逾期（1 天后）"""
    # 按模式选择前缀 / 实例名后缀 / 到期天数
    prefix = PREFIX_NEAR if near else PREFIX_OVERDUE
    suffix = "临期" if near else "超期"
    deadline_days = NEAR_DAYS if near else -OVERDUE_DAYS
    mode_label = "即将逾期（1 天后到期）" if near else "已逾期（3 天前到期）"

    print("=" * 56)
    print(f"  超期预警测试数据脚本 —— {mode_label}")
    print("=" * 56)

    async with async_session_factory() as session:
        # 0. 找当事人账号 manager1
        manager = (await session.execute(
            select(User).where(User.username == MANAGER_USERNAME)
        )).scalar_one_or_none()
        if manager is None:
            print(f"  错误: 用户 {MANAGER_USERNAME} 不存在")
            return
        org = (await session.execute(
            select(Organization).where(Organization.id == manager.organization_id)
        )).scalar_one_or_none()
        org_id = org.id if org else 1
        print(f"  当事人: {manager.real_name} (id={manager.id}) org_id={org_id}")

        # 1. 清理本模式前缀的旧数据
        print("\n[1/3] 清理旧数据…")
        await cleanup(session, prefixes=(prefix,))
        await session.commit()

        # 2. 模板
        print("\n[2/3] 创建模板…")
        tpl_normal = await create_template(session, name=f"{prefix}普通流程", org_id=org_id,
                                           created_by=manager.id, person_name=manager.real_name,
                                           with_endorser=False)
        tpl_end = await create_template(session, name=f"{prefix}难度4流程", org_id=org_id,
                                        created_by=manager.id, person_name=manager.real_name,
                                        with_endorser=True)
        tpl_names = {tpl_normal: f"{prefix}普通流程", tpl_end: f"{prefix}难度4流程"}
        await session.commit()

        # 3. 4 个实例（待办/校验/审批/批准各一）
        print("\n[3/3] 创建 4 个实例…")
        await create_instance(session, name=f"{prefix}待办{suffix}", tpl_id=tpl_normal,
                              tpl_name=tpl_names[tpl_normal], org_id=org_id,
                              initiator_id=manager.id, difficulty="1", priority="urgent",
                              scenario="task", deadline_days=deadline_days)
        await create_instance(session, name=f"{prefix}校验{suffix}", tpl_id=tpl_normal,
                              tpl_name=tpl_names[tpl_normal], org_id=org_id,
                              initiator_id=manager.id, difficulty="1", priority="high",
                              scenario="check", deadline_days=deadline_days)
        await create_instance(session, name=f"{prefix}审批{suffix}", tpl_id=tpl_normal,
                              tpl_name=tpl_names[tpl_normal], org_id=org_id,
                              initiator_id=manager.id, difficulty="1", priority="normal",
                              scenario="approval", deadline_days=deadline_days)
        await create_instance(session, name=f"{prefix}批准{suffix}", tpl_id=tpl_end,
                              tpl_name=tpl_names[tpl_end], org_id=org_id,
                              initiator_id=manager.id, difficulty="4", priority="low",
                              scenario="endorsement", deadline_days=deadline_days)
        await session.commit()

    print("\n" + "=" * 56)
    print(f"  数据写入完成（{mode_label}）")
    print("  用 manager1 登录 → 首页 → 超期预警，可看到对应类别的标签")
    print("  清理全部: python -m app.core.seed_overdue --clean")
    print("=" * 56)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        async def clean_only():
            async with async_session_factory() as session:
                await cleanup(session, prefixes=ALL_PREFIXES)
                await session.commit()
            print("清理完成")
        asyncio.run(clean_only())
    else:
        asyncio.run(seed(near="--near" in sys.argv))
