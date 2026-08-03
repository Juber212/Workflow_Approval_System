"""deadline 自然日口径测试数据脚本 —— 造「今天/昨天/明天截止」实例验证 P1-17

运行方式（在 backend 目录下执行）：
    python -m app.core.seed_deadline          # 造 3 条测试实例
    python -m app.core.seed_deadline --clean  # 清理本脚本造的全部数据（前缀 [测试截止]）

用途：手动验证 P1-17 逾期口径。deadline 存储形态为当日 00:00:00（与 create.py 一致），
自然日口径下：
  - 今天 00:00:00 截止 → 应显示「未逾期 / 剩余0天」（旧口径误报「已逾期1天」）
  - 昨天 00:00:00 截止 → 应显示「已逾期1天」
  - 明天 00:00:00 截止 → 应显示「剩余1天」
用 manager1 登录查看项目列表 / 首页超期即可。
"""

import asyncio
import sys
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models import (
    User, Organization,
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge,
)
from app.core.seed_test_data import _make_task
from app.core.seed_overdue import create_template, cleanup

# 前缀：与其他 seed 脚本的 [测试]/[测试超期]/[测试临期] 区分，清理互不影响
PREFIX = "[测试截止]"
MANAGER_USERNAME = "manager1"  # 当事人：发起人 + 负责人同一账号
NOW = datetime.now()


async def create_instance(session: AsyncSession, *, name: str, tpl_id: int,
                          tpl_name: str, org_id: int, initiator_id: int,
                          priority: str, deadline_days: int) -> None:
    """创建运行中实例：工作节点 deadline = (今天 + deadline_days) 的 00:00:00

    deadline_days: 0=今天截止, -1=昨天截止, 1=明天截止。
    自然日归零是关键——与 create.py 的存储形态（当日 00:00:00）一致，
    才能触发 P1-17 的「截止日当天误报逾期」场景（旧口径 deadline-now 得 -1 天）。
    """
    inst = FlowInstance(
        name=name, description="P1-17 截止日语义测试",
        template_id=tpl_id, template_name=tpl_name, template_type="project",
        organization_id=org_id, initiator_id=initiator_id,
        priority=priority, difficulty="1",
        status="running", initiated_at=NOW - timedelta(days=5),
    )
    session.add(inst)
    await session.flush()

    # 从模板复制实例节点
    tpl_nodes = (await session.execute(
        select(TemplateNode).where(TemplateNode.template_id == tpl_id).order_by(TemplateNode.sort_order)
    )).scalars().all()

    inst_nodes = []
    for t in tpl_nodes:
        deadline = None
        if not t.is_start and not t.is_end:
            # 自然日归零：deadline 存当日 00:00:00
            deadline = (NOW + timedelta(days=deadline_days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
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

    # 连线（模板边 → 实例边，节点 ID 映射）
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

    # task 场景：工作节点 running（负责人处理中），列表展示其 deadline 与逾期标记
    start = next(n for n in inst_nodes if n.is_start)
    work = next(n for n in inst_nodes if not n.is_start and not n.is_end)
    start.status = "finished"
    start.completed_at = NOW - timedelta(days=4)
    work.status = "running"
    work.started_at = NOW - timedelta(days=2)
    await _make_task(session, inst.id, work.id, initiator_id, "processing", 1,
                     NOW - timedelta(days=2), None, "P1-17 截止日测试")

    await session.flush()
    print(f"  + 实例: {name}  deadline={work.deadline}")


async def seed() -> None:
    """造 3 条截止日语义测试实例（今天/昨天/明天截止）"""
    print("=" * 56)
    print("  P1-17 截止日语义测试数据脚本")
    print("=" * 56)

    async with async_session_factory() as session:
        # 当事人 manager1
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

        # 清理前缀旧数据
        print("\n[1/3] 清理旧数据…")
        await cleanup(session, prefixes=(PREFIX,))
        await session.commit()

        # 模板（3 节点：开始-工作-结束）
        print("\n[2/3] 创建模板…")
        tpl = await create_template(session, name=f"{PREFIX}流程", org_id=org_id,
                                    created_by=manager.id, person_name=manager.real_name,
                                    with_endorser=False)
        await session.commit()

        # 3 个实例
        print("\n[3/3] 创建 3 个实例…")
        await create_instance(session, name=f"{PREFIX}今天截止", tpl_id=tpl,
                              tpl_name=f"{PREFIX}流程", org_id=org_id,
                              initiator_id=manager.id, priority="urgent", deadline_days=0)
        await create_instance(session, name=f"{PREFIX}昨天截止", tpl_id=tpl,
                              tpl_name=f"{PREFIX}流程", org_id=org_id,
                              initiator_id=manager.id, priority="high", deadline_days=-1)
        await create_instance(session, name=f"{PREFIX}明天截止", tpl_id=tpl,
                              tpl_name=f"{PREFIX}流程", org_id=org_id,
                              initiator_id=manager.id, priority="normal", deadline_days=1)
        await session.commit()

    print("\n" + "=" * 56)
    print("  数据写入完成")
    print("  预期: 今天截止=未逾期/剩余0天, 昨天截止=已逾期1天, 明天截止=剩余1天")
    print("  用 manager1 登录查看项目列表 / 首页超期")
    print("  清理: python -m app.core.seed_deadline --clean")
    print("=" * 56)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        async def clean_only() -> None:
            async with async_session_factory() as session:
                await cleanup(session, prefixes=(PREFIX,))
                await session.commit()
            print("清理完成")
        asyncio.run(clean_only())
    else:
        asyncio.run(seed())
