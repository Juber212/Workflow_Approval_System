"""无负责人 waiting 节点卡死场景测试数据脚本 —— 验证 P1-18 换人后自动激活

运行方式（在 backend 目录下执行）：
    python -m app.core.seed_no_assignee          # 造 1 条卡死实例
    python -m app.core.seed_no_assignee --clean  # 清理本脚本造的全部数据（前缀 [测试无负责人]）

用途：工作节点发起时未配负责人（assignee_id=None），propagate 激活被「无负责人守卫」
拒绝，节点停在 waiting（arrived_count 已满足激活条件）。验证 P1-18：
用 manager1 登录 → 项目列表点开该实例 → 工作节点「紧急换人」配负责人
→ 节点应自动激活为运行中并生成待办（修复前流程永久卡死，无解）。
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
from app.core.seed_overdue import create_template, cleanup

# 前缀：与 [测试]/[测试超期]/[测试临期]/[测试截止] 区分，清理互不影响
PREFIX = "[测试无负责人]"
MANAGER_USERNAME = "manager1"  # 发起人：用其登录后换人
NOW = datetime.now()


async def create_instance(session: AsyncSession, *, name: str, tpl_id: int,
                          tpl_name: str, org_id: int, initiator_id: int) -> None:
    """创建「无负责人 waiting 卡死」实例

    工作节点 assignee_id=None（模拟发起时未配负责人）+ status=waiting +
    arrived_count=1/incoming_count=1（上游开始节点已完成，激活条件已满足）
    —— 正是 propagate 被「无负责人守卫」拒绝后的卡死态。
    """
    inst = FlowInstance(
        name=name, description="P1-18 无负责人卡死场景测试",
        template_id=tpl_id, template_name=tpl_name, template_type="project",
        organization_id=org_id, initiator_id=initiator_id,
        priority="urgent", difficulty="1",
        status="running", initiated_at=NOW - timedelta(days=2),
    )
    session.add(inst)
    await session.flush()

    # 从模板复制实例节点（工作节点清空负责人 + 置为已满足激活条件的 waiting）
    tpl_nodes = (await session.execute(
        select(TemplateNode).where(TemplateNode.template_id == tpl_id).order_by(TemplateNode.sort_order)
    )).scalars().all()

    inst_nodes = []
    for t in tpl_nodes:
        n = InstanceNode(
            instance_id=inst.id, name=t.name, is_start=t.is_start, is_end=t.is_end,
            # P1-18 关键：工作节点无负责人（模板有负责人，此处清空模拟未配场景）
            assignee_id=None,
            time_limit_days=t.time_limit_days, deadline=None,
            require_file=t.require_file, checkers=t.checkers, approvers=t.approvers,
            approval_strategy=t.approval_strategy, endorser_id=t.endorser_id,
            require_assignee_signature=t.require_assignee_signature,
            require_checker_signature=t.require_checker_signature,
            require_approver_signature=t.require_approver_signature,
            require_endorser_signature=t.require_endorser_signature,
            status="waiting", sort_order=t.sort_order, round=1,
            # 激活条件已满足：arrived=1/incoming=1（上游开始节点已完成）
            arrived_count=1, incoming_count=1,
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

    # 开始节点已完成（模拟上游走完），工作节点保持 waiting + 无 Task
    start = next(n for n in inst_nodes if n.is_start)
    start.status = "finished"
    start.completed_at = NOW - timedelta(days=1)

    await session.flush()
    work = next(n for n in inst_nodes if not n.is_start and not n.is_end)
    print(f"  + 实例: {name}  工作节点[{work.name}] assignee_id={work.assignee_id} "
          f"status={work.status} arrived={work.arrived_count}/{work.incoming_count}")


async def seed() -> None:
    """造 1 条无负责人 waiting 卡死实例"""
    print("=" * 56)
    print("  P1-18 无负责人卡死场景测试数据脚本")
    print("=" * 56)

    async with async_session_factory() as session:
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

        # 1 个卡死实例
        print("\n[3/3] 创建 1 个卡死实例…")
        await create_instance(session, name=f"{PREFIX}卡死", tpl_id=tpl,
                              tpl_name=f"{PREFIX}流程", org_id=org_id,
                              initiator_id=manager.id)
        await session.commit()

    print("\n" + "=" * 56)
    print("  数据写入完成")
    print("  验证步骤：manager1 登录 → 项目列表点开该实例 → 工作节点「紧急换人」")
    print("  → 选负责人提交 → 期望节点变运行中、负责人收到待办（修复前永久卡死）")
    print("  清理: python -m app.core.seed_no_assignee --clean")
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
