"""流程引擎 —— 节点激活、实例状态推进

负责实例节点间的流转逻辑：
- 节点完成时，传播到达信号到下游
- 汇合节点等待所有上游到达后才激活
- 开始/结束节点的特殊处理
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InstanceNode, InstanceEdge, Task, FlowInstance, Approval
from app.models.enums import InstanceNodeStatus, ApprovalStatus, TaskStatus
# NOTE: engine 层直接依赖 services 层，形成隐式双向耦合（多个 Service 也 import engine）
# 这是当前架构的已知权衡——通知创建与节点传播紧密耦合，强行解耦会增加不必要的抽象
# 若未来引入循环引用，可考虑用事件回调或延迟导入重构
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


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
    start_node.status = InstanceNodeStatus.FINISHED
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
        logger.warning(
            "propagate_from_node: 节点 #%d（实例 #%d）无下游边，传播终止",
            finished_node_id, instance_id,
        )
        return []

    # 收集直接下游节点 ID（单层传播，V1 仅处理源节点的直接下游）
    target_ids = [edge.target_node_id for edge in downstream_edges]

    activated_ids: list[int] = []
    _tasks_for_notify: list[tuple] = []  # 收集创建的 Task（工作节点）用于通知
    _end_approvals: list[tuple] = []  # 收集终审审批记录（结束节点）用于通知：([user_id], instance_name)

    for node_id in target_ids:
        # ===== Fork-Join 防竞态（三步原子操作）=====
        # 1. SELECT ... FOR UPDATE 锁定目标行，序列化并发访问
        await db.execute(
            select(InstanceNode).where(InstanceNode.id == node_id).with_for_update()
        )
        # 2. 持有行锁时原子递增 arrived_count
        await db.execute(
            update(InstanceNode)
            .where(InstanceNode.id == node_id)
            .values(arrived_count=InstanceNode.arrived_count + 1)
        )
        # 3. 读取最新值（仍在行锁保护下，无竞态窗口）
        node = (
            await db.execute(
                select(InstanceNode).where(InstanceNode.id == node_id)
            )
        ).scalar_one_or_none()
        if node is None:
            logger.warning("propagate_from_node: 目标节点 #%d 不存在（可能已被并发删除），跳过", node_id)
            continue

        # 检查是否所有上游分支均已到达
        if node.arrived_count < node.incoming_count:
            logger.info(
                "propagate_from_node: 节点 #%d「%s」arrived=%d/%d，等待其他上游完成",
                node.id, node.name, node.arrived_count, node.incoming_count,
            )
            continue  # 还有上游未完成，继续等待

        # 重入守卫：非 WAITING 状态的节点不应被重复激活（防止环形边/并发导致无限循环）
        if node.status != InstanceNodeStatus.WAITING:
            logger.warning(
                "propagate_from_node: 节点 #%d「%s」当前状态=%s（非 WAITING），跳过激活以防环形边重复触发",
                node.id, node.name, node.status,
            )
            continue

        # === 所有上游已到达，按节点类型处理 ===

        if node.is_end:
            # 结束节点：进入 waiting_approval，按 approvers 创建审批记录，不生成 Task
            logger.info(
                "propagate_from_node: 结束节点 #%d「%s」激活 → WAITING_APPROVAL",
                node.id, node.name,
            )
            node.status = InstanceNodeStatus.WAITING_APPROVAL
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
                        status=ApprovalStatus.PENDING,
                        round=node.round,  # 记录当前节点轮次
                    ))
                    # 收集终审审批人用于后续通知
                    _end_approvals.append((approver_id, node.id))

            activated_ids.append(node.id)

        else:
            # 普通工作节点：激活为 running，生成 Task
            # 守卫：无负责人时拒绝激活，避免节点 RUNNING 但无 Task 导致永久死锁
            if not node.assignee_id:
                logger.error(
                    "propagate_from_node: 节点 #%d「%s」无负责人（assignee_id 为空），"
                    "无法激活，流程卡死！请管理员在实例详情中紧急换人",
                    node.id, node.name,
                )
                continue

            now = datetime.now()
            node.status = InstanceNodeStatus.RUNNING
            node.started_at = now
            logger.info(
                "propagate_from_node: 工作节点 #%d「%s」激活 → RUNNING（assignee_id=%s）",
                node.id, node.name, node.assignee_id,
            )

            # 兜底：若发起时未预计算 deadline，则按自然日估算（不跳过节假日）
            # 正常流程在 create_instance 中已用 add_workdays 预计算，此处不应触发
            if node.time_limit_days and not node.deadline:
                node.deadline = now + timedelta(days=node.time_limit_days)

            # 创建 Task（状态 pending，等待负责人处理）
            created_task = Task(
                instance_id=instance_id,
                node_id=node.id,
                assignee_id=node.assignee_id,
                status=TaskStatus.PENDING,
            )
            db.add(created_task)
            # 收集创建的 Task 用于后续通知
            _tasks_for_notify.append((node, created_task))

            activated_ids.append(node.id)

    await db.flush()

    # ---- 通知：下游节点负责人有新任务 (#5 / #1) ----
    notif_tasks = [
        create_notification(
            db, user_id=_node.assignee_id, type="task_assigned",
            title="新的待办任务",
            content=f"节点「{_node.name}」已激活，等待你处理",
            link=f"/profile/task/{_task.id}",
            instance_id=instance_id,
        )
        for _node, _task in _tasks_for_notify
        if _task.id and _node.assignee_id
    ]
    if notif_tasks:
        await asyncio.gather(*notif_tasks)

    # ---- 终审通知：通知发起人进行终审 ----
    if _end_approvals:
        inst = (await db.execute(
            select(FlowInstance).where(FlowInstance.id == instance_id)
        )).scalar_one_or_none()
        if inst:
            # 查询刚创建的终审 Approval 记录获取审批 ID 用于链接
            for _approver_id, _e_node_id in _end_approvals:
                end_approval = (await db.execute(
                    select(Approval).where(
                        Approval.node_id == _e_node_id,
                        Approval.approver_id == _approver_id,
                        Approval.status == ApprovalStatus.PENDING,
                    ).order_by(Approval.id.desc()).limit(1)
                )).scalar_one_or_none()
                link = f"/profile/approval/{end_approval.id}" if end_approval else None
                await create_notification(
                    db, user_id=_approver_id, type="approval_assigned",
                    title="待终审",
                    content=f"「{inst.name}」已到达终审环节，请审核全部文件",
                    link=link,
                    instance_id=instance_id,
                )

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
