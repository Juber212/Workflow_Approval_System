"""流程引擎 —— 节点激活、跳过传播、实例状态推进

负责实例节点间的流转逻辑：
- 节点完成/跳过时，传播到达信号到下游
- 汇合节点等待所有上游到达后才激活
- 跳过节点沿原图传播，不生成 Task
- 开始/结束节点的特殊处理
"""

from collections import deque
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InstanceNode, InstanceEdge, Task


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
    """节点完成/跳过时，传播到达信号到所有直接下游节点

    返回本轮新激活的节点 ID 列表（状态变为 running/waiting_approval 的工作节点）

    处理逻辑：
    1. 查询所有以 finished_node_id 为源的边
    2. 对每个目标节点 arrived_count + 1
    3. 如果 arrived_count == incoming_count（所有上游已到达）：
       - is_skipped → 标记 skipped，递归传播（并入队列）
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

        if node.is_skipped:
            # 跳过节点：标记 skipped，继续向下游传播
            now = datetime.now()
            node.status = "skipped"
            node.started_at = now
            node.completed_at = now

            # 找到跳过节点的所有下游，入队
            skip_edges = await db.execute(
                select(InstanceEdge).where(
                    InstanceEdge.source_node_id == node.id,
                    InstanceEdge.instance_id == instance_id,
                )
            )
            for se in skip_edges.scalars().all():
                queue.append(se.target_node_id)

        elif node.is_end:
            # 结束节点：进入 waiting_approval，等待发起人终审，不生成 Task
            node.status = "waiting_approval"
            node.started_at = datetime.now()
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

    发起实例时调用一次，后续不变。
    """
    # 查询所有节点
    nodes_result = await db.execute(
        select(InstanceNode).where(InstanceNode.instance_id == instance_id)
    )
    nodes = nodes_result.scalars().all()

    # 对每个节点统计入边
    for node in nodes:
        count_result = await db.execute(
            select(InstanceEdge).where(
                InstanceEdge.target_node_id == node.id,
                InstanceEdge.instance_id == instance_id,
            )
        )
        node.incoming_count = len(count_result.scalars().all())

    await db.flush()
