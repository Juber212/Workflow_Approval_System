"""流程引擎 —— 节点激活、实例状态推进

负责实例节点间的流转逻辑：
- 节点完成时，传播到达信号到下游
- 汇合节点等待所有上游到达后才激活
- 开始/结束节点的特殊处理
"""

from collections import deque
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InstanceNode, InstanceEdge, Task, FlowInstance, Approval


async def activate_start_node(db: AsyncSession, instance_id: int) -> None:
    """开始节点：发起后自动标记为 finished"""
    start_node = (
        await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == instance_id,
                InstanceNode.is_start == True,
            )
        )
    ).scalar_one_or_none()

    if start_node is None:
        return  # 不应该发生，但安全处理

    now = datetime.now()
    start_node.status = "finished"
    start_node.started_at = now
    start_node.completed_at = now
    await db.flush()


async def propagate_from_node(
    db: AsyncSession,
    instance_id: int,
    finished_node_id: int,
) -> list[int]:
    """节点完成时，传播到达信号到所有直接下游节点

    返回本轮新激活的节点 ID 列表（状态变为 running/waiting_approval 的工作节点）

    处理逻辑：
    1. 查询所有以 finished_node_id 为源的边
    2. 对每个目标节点 arrived_count + 1
    3. 如果 arrived_count == incoming_count（所有上游已到达）：
       - is_end → 标记 waiting_approval（等待发起人终审）
       - 普通工作节点 → 标记 running，创建 Task
    """
    # 找到所有下游边
    edges_result = await db.execute(
        select(InstanceEdge).where(
            InstanceEdge.source_node_id == finished_node_id,
            InstanceEdge.instance_id == instance_id,
        )
    )
    downstream_edges = edges_result.scalars().all()

    if not downstream_edges:
        return []

    # BFS 队列：(node_id) —— 每个到达条件满足的节点入队
    queue: deque[int] = deque()
    for edge in downstream_edges:
        queue.append(edge.target_node_id)

    activated_ids: list[int] = []

    while queue:
        node_id = queue.popleft()

        node = (
            await db.execute(
                select(InstanceNode).where(InstanceNode.id == node_id)
            )
        ).scalar_one()

        # 到达信号 +1
        node.arrived_count += 1

        # 检查是否所有上游分支均已到达
        if node.arrived_count < node.incoming_count:
            continue  # 还有上游未完成，继续等待

        # === 所有上游已到达，按节点类型处理 ===

        if node.is_end:
            # 结束节点：进入 waiting_approval，按 approvers 创建审批记录，不生成 Task
            node.status = "waiting_approval"
            node.started_at = datetime.now()

            # 为结束节点创建审批记录（发起人终审）
            approvers = node.approvers or []
            if not approvers:
                # 兜底：结束节点未配置审批人时，默认由发起人终审
                inst = (
                    await db.execute(
                        select(FlowInstance).where(FlowInstance.id == instance_id)
                    )
                ).scalar_one_or_none()
                if inst:
                    approvers = [{"user_id": inst.initiator_id}]

            if approvers:
                for approver in approvers:
                    approver_id = approver.get("user_id") if isinstance(approver, dict) else approver
                    db.add(Approval(
                        instance_id=instance_id,
                        node_id=node.id,
                        task_id=None,  # 结束节点无 Task
                        approver_id=approver_id,
                        status="pending",
                    ))

            activated_ids.append(node.id)

        else:
            # 普通工作节点：激活为 running，生成 Task
            now = datetime.now()
            node.status = "running"
            node.started_at = now

            # 计算 deadline（如果有 time_limit_days 且未手动指定 deadline）
            if node.time_limit_days and not node.deadline:
                node.deadline = now + timedelta(days=node.time_limit_days)

            # 创建 Task（状态 pending，等待负责人处理）
            if node.assignee_id:
                task = Task(
                    instance_id=instance_id,
                    node_id=node.id,
                    assignee_id=node.assignee_id,
                    status="pending",
                )
                db.add(task)

            activated_ids.append(node.id)

    await db.flush()
    return activated_ids


async def calculate_incoming_counts(db: AsyncSession, instance_id: int) -> None:
    """根据 instance_edges 批量计算每个节点的 incoming_count（上游连线数）

    发起实例时调用一次，后续不变。使用 GROUP BY 单次查询避免 N+1。
    """
    # 单次 GROUP BY 查询所有节点的入边数
    count_stmt = (
        select(
            InstanceEdge.target_node_id,
            func.count(InstanceEdge.id).label("cnt"),
        )
        .where(InstanceEdge.instance_id == instance_id)
        .group_by(InstanceEdge.target_node_id)
    )
    count_result = await db.execute(count_stmt)
    incoming_map = {row.target_node_id: row.cnt for row in count_result.all()}

    # 查询所有节点并赋值
    nodes_result = await db.execute(
        select(InstanceNode).where(InstanceNode.instance_id == instance_id)
    )
    nodes = nodes_result.scalars().all()

    for node in nodes:
        node.incoming_count = incoming_map.get(node.id, 0)

    await db.flush()
