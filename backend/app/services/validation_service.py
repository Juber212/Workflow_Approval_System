"""模板发布校验服务 —— 7 项校验 + BFS 连通性"""
from collections import deque
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FlowTemplate, TemplateNode, TemplateEdge


async def validate_template_for_publish(db: AsyncSession, template_id: int) -> list[str]:
    """发布前校验，返回错误列表（空列表表示通过）"""
    errors: list[str] = []

    # 加载数据
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        return ["模板不存在"]

    nodes_result = await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == template_id).order_by(TemplateNode.sort_order)
    )
    nodes = nodes_result.scalars().all()

    edges_result = await db.execute(select(TemplateEdge).where(TemplateEdge.template_id == template_id))
    edges = edges_result.scalars().all()

    # 1. 模板名称
    if not tpl.name or not tpl.name.strip():
        errors.append("模板名称不能为空")

    # 2. 节点数 >= 3（开始+至少1个中间+结束）
    if len(nodes) < 3:
        errors.append("至少需要 3 个节点（开始 + 中间工作节点 + 结束）")

    # 3. 必须有开始节点和结束节点
    start_nodes = [n for n in nodes if n.is_start]
    end_nodes = [n for n in nodes if n.is_end]
    if not start_nodes:
        errors.append("缺少开始节点")
    if not end_nodes:
        errors.append("缺少结束节点")

    # 4. 工作节点配置完整性
    work_nodes = [n for n in nodes if not n.is_start and not n.is_end]
    for n in work_nodes:
        if not n.name or not n.name.strip():
            errors.append(f"节点 ID={n.id} 名称不能为空")
        if not n.assignee_id:
            errors.append(f"节点「{n.name}」缺少负责人")
        if not n.checkers or len(n.checkers) == 0:
            errors.append(f"节点「{n.name}」缺少校验人")
        if not n.approvers or len(n.approvers) == 0:
            errors.append(f"节点「{n.name}」缺少审批人")
        if not n.time_limit_days or n.time_limit_days < 1:
            errors.append(f"节点「{n.name}」时限未设置或小于1天")

    # 如果有基础错误，不再做连通性校验
    if errors:
        return errors

    # 5. BFS 连通性校验
    adjacency = _build_adjacency(edges)
    reverse_adj = _build_reverse_adjacency(edges)

    start_id = start_nodes[0].id
    end_id = end_nodes[0].id

    # 5a. 从开始节点出发可达的节点
    reachable_from_start = _bfs_reachable(start_id, adjacency)

    # 5b. 可以到达结束节点的节点
    can_reach_end = _bfs_reachable_reverse(end_id, reverse_adj)

    # 所有非开始/结束节点必须同时满足两个条件
    for n in work_nodes:
        if n.id not in reachable_from_start:
            errors.append(f"节点「{n.name}」无法从开始节点到达")
        if n.id not in can_reach_end:
            errors.append(f"节点「{n.name}」无法到达结束节点")

    # 6. 无自环
    for e in edges:
        if e.source_node_id == e.target_node_id:
            errors.append(f"节点「{_get_node_name(nodes, e.source_node_id)}」存在自环连线")

    # 7. 开始节点必须有出边
    for n in start_nodes:
        if n.id not in adjacency or len(adjacency[n.id]) == 0:
            errors.append(f"开始节点「{n.name}」没有出边，至少需要连接一个后续节点")

    # 8. 结束节点必须有入边
    for n in end_nodes:
        if n.id not in reverse_adj or len(reverse_adj[n.id]) == 0:
            errors.append(f"结束节点「{n.name}」没有入边，至少需要一个前驱节点连接到它")

    # 9. 可选节点和结束节点不应有出边（fork 场景下的可选节点允许 fork 出去但必须有后续）
    _optional_and_end_no_outgoing(nodes, edges, adjacency, errors)

    # 10. fork/join 合法性：允许一源多目标 (fork) 和多源一目标 (join)，无额外限制
    # V1 不做条件分支，fork 表示并行分叉，join 表示并行汇合

    return errors


def _build_adjacency(edges: list) -> dict[int, list[int]]:
    """构建邻接表：node_id → [target_ids]"""
    adj: dict[int, list[int]] = {}
    for e in edges:
        adj.setdefault(e.source_node_id, []).append(e.target_node_id)
    return adj


def _build_reverse_adjacency(edges: list) -> dict[int, list[int]]:
    """构建反向邻接表"""
    adj: dict[int, list[int]] = {}
    for e in edges:
        adj.setdefault(e.target_node_id, []).append(e.source_node_id)
    return adj


def _bfs_reachable(start_id: int, adj: dict[int, list[int]]) -> set[int]:
    """BFS 正向可达节点集合"""
    visited: set[int] = set()
    queue = deque([start_id])
    while queue:
        node_id = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        for next_id in adj.get(node_id, []):
            if next_id not in visited:
                queue.append(next_id)
    return visited


def _bfs_reachable_reverse(target_id: int, adj: dict[int, list[int]]) -> set[int]:
    """BFS 反向可达（哪些节点可以到达 target）"""
    return _bfs_reachable(target_id, adj)


def _get_node_name(nodes: list, node_id: int) -> str:
    for n in nodes:
        if n.id == node_id:
            return n.name
    return f"ID:{node_id}"


def _optional_and_end_no_outgoing(
    nodes: list,
    edges: list,
    adj: dict[int, list[int]],
    errors: list[str],
) -> None:
    """可选节点和结束节点不应有出边（跳出分支/汇合的特殊处理除外）
    V1 简化：仅检查结束节点是否有出边
    """
    end_nodes = [n for n in nodes if n.is_end]
    for n in end_nodes:
        if n.id in adj:
            errors.append(f"结束节点「{n.name}」不应有出边")
