"""项目设计器服务 —— 保存/加载画布数据（节点 + 连线）"""
import logging
from collections import deque
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import FlowTemplate, TemplateNode, TemplateEdge

logger = logging.getLogger(__name__)


# 节点可更新字段（排除系统字段和自动生成字段）
_NODE_UPDATABLE_FIELDS = [
    "name", "description", "assignee_id", "time_limit_days",
    "require_file", "approvers", "checkers", "approval_strategy",
    "position_x", "position_y", "sort_order",
]


async def save_design_data(
    db: AsyncSession,
    template_id: int,
    nodes_data: list[dict],
    edges_data: list[dict],
) -> dict:
    """批量保存设计器数据 —— 新增/更新/删除节点和连线，同一事务"""
    logger.debug(f"[designer] 开始 template_id={template_id} nodes={len(nodes_data)} edges={len(edges_data)}")
    # 校验模板存在且为 draft
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    # 所有模板均可编辑设计（无状态限制）

    # 获取现有节点和连线
    existing_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == template_id)
    )).scalars().all()
    existing_edges = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == template_id)
    )).scalars().all()

    logger.debug(f"[designer] 现有节点={len(existing_nodes)} 现有连线={len(existing_edges)}")

    existing_node_ids = {n.id for n in existing_nodes}
    existing_edge_ids = {e.id for e in existing_edges}
    # 系统节点（开始/结束）的 ID，不可删除
    system_node_ids = {n.id for n in existing_nodes if n.is_start or n.is_end}

    # === 处理节点 ===
    submitted_node_ids = set()
    new_node_id_map: dict[str, int] = {}  # 临时ID → 真实ID，用于连线映射
    # 查找现有系统节点（用于匹配更新而非新建）
    existing_start_node = next((n for n in existing_nodes if n.is_start), None)
    existing_end_node = next((n for n in existing_nodes if n.is_end), None)

    for item in nodes_data:
        nid = item.get("id")
        original_nid = nid  # 保存原始 ID（用于建立映射）

        # 系统节点：若 ID 不匹配，自动映射到现有系统节点 ID 进行更新
        if item.get("is_start") and existing_start_node and (nid is None or nid not in existing_node_ids):
            nid = existing_start_node.id
        elif item.get("is_end") and existing_end_node and (nid is None or nid not in existing_node_ids):
            nid = existing_end_node.id

        # 关键修复：若系统节点的前端 ID（如 UUID）与数据库 ID 不同，建立映射供边处理使用
        if original_nid is not None and nid != original_nid:
            new_node_id_map[str(original_nid)] = nid
            logger.debug(f"[designer] 系统节点 ID 映射: {original_nid} → {nid}")

        if nid and nid in existing_node_ids:
            # 更新已有节点
            submitted_node_ids.add(nid)
            await _update_node(db, nid, item)
        else:
            # 新增节点
            new_node = await _create_node(db, template_id, item)
            if nid is not None:
                new_node_id_map[str(nid)] = new_node.id
            submitted_node_ids.add(new_node.id)

    # 删除不在提交列表中的节点（系统节点除外）
    nodes_to_delete = existing_node_ids - submitted_node_ids - system_node_ids
    if nodes_to_delete:
        await db.execute(
            delete(TemplateEdge).where(
                TemplateEdge.template_id == template_id,
                (TemplateEdge.source_node_id.in_(nodes_to_delete)) |
                (TemplateEdge.target_node_id.in_(nodes_to_delete)),
            )
        )
        await db.execute(
            delete(TemplateNode).where(TemplateNode.id.in_(nodes_to_delete))
        )

    # === 处理连线 ===
    submitted_edge_ids = set()

    for item in edges_data:
        eid = item.get("id")
        raw_source = item.get("source_node_id")
        raw_target = item.get("target_node_id")

        # 跳过无效边：null、None、空字符串、0 都视为无效
        if not raw_source or not raw_target:
            logger.warning(f"[designer] 跳过无效边 raw_source={raw_source!r} raw_target={raw_target!r}")
            continue

        # 步骤1：通过 new_node_id_map 映射（临时 ID → 真实 ID，含系统节点映射）
        source_id = _resolve_edge_endpoint(raw_source, new_node_id_map, existing_start_node, existing_end_node)
        target_id = _resolve_edge_endpoint(raw_target, new_node_id_map, existing_start_node, existing_end_node)

        if source_id is None or target_id is None:
            logger.warning(f"[designer] 无法解析边端点，跳过: raw_source={raw_source!r} raw_target={raw_target!r}")
            continue

        if eid and eid in existing_edge_ids:
            submitted_edge_ids.add(eid)
            await _update_edge(db, eid, source_id, target_id)
        else:
            # 检查是否已存在相同端点的边（避免重复插入触发唯一约束）
            dup = _find_existing_edge(existing_edges, source_id, target_id)
            if dup:
                submitted_edge_ids.add(dup.id)
                await _update_edge(db, dup.id, source_id, target_id)
            else:
                new_edge = await _create_edge(db, template_id, source_id, target_id)
                submitted_edge_ids.add(new_edge.id)

    # 删除不在提交列表中的连线
    edges_to_delete = existing_edge_ids - submitted_edge_ids
    if edges_to_delete:
        await db.execute(
            delete(TemplateEdge).where(TemplateEdge.id.in_(edges_to_delete))
        )

    await db.flush()

    logger.debug(f"[designer] 保存完成: 节点={len(submitted_node_ids)} 连线={len(submitted_edge_ids)} "
                 f"删除节点={len(nodes_to_delete)} 删除连线={len(edges_to_delete) if edges_to_delete else 0}")

    # 拓扑排序：根据边的关系自动计算所有节点的 sort_order
    await _topological_sort(db, template_id)
    await db.flush()  # 确保 sort_order 变更持久化

    return {
        "template_id": template_id,
        "node_count": len(submitted_node_ids),
        "edge_count": len(submitted_edge_ids),
    }


async def _create_node(db: AsyncSession, template_id: int, data: dict) -> TemplateNode:
    """创建新节点"""
    node = TemplateNode(template_id=template_id)
    for field in _NODE_UPDATABLE_FIELDS:
        if field in data:
            setattr(node, field, data[field])
    # 确保系统标志
    if "is_start" in data:
        node.is_start = data["is_start"]
    if "is_end" in data:
        node.is_end = data["is_end"]
    db.add(node)
    await db.flush()
    return node


async def _update_node(db: AsyncSession, node_id: int, data: dict) -> None:
    """更新已有节点"""
    node = (await db.execute(select(TemplateNode).where(TemplateNode.id == node_id))).scalar_one()
    for field in _NODE_UPDATABLE_FIELDS:
        if field in data:
            setattr(node, field, data[field])


async def _create_edge(db: AsyncSession, template_id: int, source_id: int, target_id: int) -> TemplateEdge:
    """创建新连线"""
    edge = TemplateEdge(
        template_id=template_id,
        source_node_id=source_id,
        target_node_id=target_id,
    )
    db.add(edge)
    await db.flush()
    return edge


def _find_existing_edge(
    existing_edges: list[TemplateEdge], source_id: int, target_id: int
) -> TemplateEdge | None:
    """在已有连线列表中查找相同端点的连线（避免重复插入触发唯一约束）"""
    for e in existing_edges:
        if e.source_node_id == source_id and e.target_node_id == target_id:
            return e
    return None


def _resolve_edge_endpoint(
    raw: any,
    id_map: dict[str, int],
    start_node: TemplateNode | None,
    end_node: TemplateNode | None,
) -> int | None:
    """将连线的端点 ID 解析为整数数据库 ID。

    处理顺序：
    1. 数字字符串 → int
    2. 已是 int → 直接返回
    3. 查 id_map（临时 ID → 真实 ID，含系统节点映射）
    4. 匹配系统节点数据库 ID
    """
    # 数字字符串直接转换
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    # 已是整数
    if isinstance(raw, int):
        return raw
    # 查映射表
    mapped = id_map.get(str(raw))
    if mapped is not None:
        return mapped
    # 匹配系统节点
    s = str(raw)
    if start_node and s == str(start_node.id):
        return start_node.id
    if end_node and s == str(end_node.id):
        return end_node.id
    # 无法解析
    return None


async def _update_edge(db: AsyncSession, edge_id: int, source_id: int, target_id: int) -> None:
    """更新已有连线"""
    edge = (await db.execute(select(TemplateEdge).where(TemplateEdge.id == edge_id))).scalar_one()
    edge.source_node_id = source_id
    edge.target_node_id = target_id


# ==================== 单节点 CRUD（简化版，无版本/状态限制） ====================


async def add_node(db: AsyncSession, template_id: int, data: dict) -> dict:
    """添加单个工作节点 —— 自动设为中间节点"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    data["is_start"] = False
    data["is_end"] = False
    node = await _create_node(db, template_id, data)
    return {"id": node.id, "name": node.name, "position_x": node.position_x, "position_y": node.position_y}


async def update_node(db: AsyncSession, node_id: int, data: dict) -> dict:
    """更新单个节点"""
    node = (await db.execute(select(TemplateNode).where(TemplateNode.id == node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")

    # 系统节点不可修改类型
    if "is_start" in data and node.is_start != data["is_start"]:
        raise AppException(ErrorCode.FORBIDDEN, "开始节点不可变更类型")
    if "is_end" in data and node.is_end != data["is_end"]:
        raise AppException(ErrorCode.FORBIDDEN, "结束节点不可变更类型")

    await _update_node(db, node_id, data)
    return {"id": node.id, "name": data.get("name", node.name)}


async def delete_node(db: AsyncSession, node_id: int) -> None:
    """删除单个节点 —— 系统节点不可删除，关联连线自动清除"""
    node = (await db.execute(select(TemplateNode).where(TemplateNode.id == node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")
    if node.is_start or node.is_end:
        raise AppException(ErrorCode.FORBIDDEN, "系统节点不可删除")

    await db.execute(
        delete(TemplateEdge).where(
            TemplateEdge.template_id == node.template_id,
            (TemplateEdge.source_node_id == node_id) | (TemplateEdge.target_node_id == node_id),
        )
    )
    await db.delete(node)


# ==================== 单连线 CRUD ====================


async def add_edge(db: AsyncSession, template_id: int, source_node_id: int, target_node_id: int) -> dict:
    """添加单条连线 —— 含自环/重复/系统节点校验"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    source_node = (await db.execute(
        select(TemplateNode).where(TemplateNode.id == source_node_id, TemplateNode.template_id == template_id)
    )).scalar_one_or_none()
    if source_node is None:
        raise AppException(ErrorCode.NOT_FOUND, f"源节点（ID={source_node_id}）不存在")

    target_node = (await db.execute(
        select(TemplateNode).where(TemplateNode.id == target_node_id, TemplateNode.template_id == template_id)
    )).scalar_one_or_none()
    if target_node is None:
        raise AppException(ErrorCode.NOT_FOUND, f"目标节点（ID={target_node_id}）不存在")

    if source_node_id == target_node_id:
        raise AppException(ErrorCode.VALIDATION_ERROR, "连线不能连接自身")
    if target_node.is_start:
        raise AppException(ErrorCode.VALIDATION_ERROR, "开始节点不可作为连线的目标")
    if source_node.is_end:
        raise AppException(ErrorCode.VALIDATION_ERROR, "结束节点不可作为连线的源")

    existing = (await db.execute(
        select(TemplateEdge).where(
            TemplateEdge.template_id == template_id,
            TemplateEdge.source_node_id == source_node_id,
            TemplateEdge.target_node_id == target_node_id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise AppException(ErrorCode.CONFLICT, f"连线已存在（{source_node_id} → {target_node_id}）")

    edge = await _create_edge(db, template_id, source_node_id, target_node_id)
    return {"id": edge.id, "source_node_id": edge.source_node_id, "target_node_id": edge.target_node_id}


async def delete_edge(db: AsyncSession, edge_id: int, template_id: int) -> dict:
    """删除单条连线"""
    edge = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.id == edge_id, TemplateEdge.template_id == template_id)
    )).scalar_one_or_none()
    if edge is None:
        raise AppException(ErrorCode.NOT_FOUND, "连线不存在")

    await db.delete(edge)
    return {"id": edge_id}


# ==================== 拓扑排序：根据边计算节点层级 ====================


async def _topological_sort(db: AsyncSession, template_id: int) -> None:
    """BFS 遍历边，按拓扑深度自动计算所有节点的 sort_order

    算法：
    - 从开始节点出发，沿有向边做最长路径深度计算
    - 同一深度的并行节点赋相同 sort_order（它们将并排显示）
    - 同级内按 position_y 升序排列（贴合画布视觉布局）
    - 未被边连通的孤立节点放在末尾
    """
    # 查询所有节点和边
    nodes_result = await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == template_id)
    )
    all_nodes = list(nodes_result.scalars().all())

    edges_result = await db.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == template_id)
    )
    all_edges = list(edges_result.scalars().all())

    if not all_nodes:
        return

    # 找到开始节点
    start_nodes = [n for n in all_nodes if n.is_start]
    if not start_nodes:
        logger.warning(f"[designer] 模板 {template_id} 无开始节点，跳过拓扑排序")
        return

    start_id = start_nodes[0].id
    node_map = {n.id: n for n in all_nodes}

    # 构建邻接表 → 和反向邻接表 ←
    adjacency: dict[int, list[int]] = {n.id: [] for n in all_nodes}
    reverse_adj: dict[int, list[int]] = {n.id: [] for n in all_nodes}
    for edge in all_edges:
        if edge.source_node_id in adjacency:
            adjacency[edge.source_node_id].append(edge.target_node_id)
        if edge.target_node_id in reverse_adj:
            reverse_adj[edge.target_node_id].append(edge.source_node_id)

    # 递归计算每个节点的最长路径深度（带记忆化，防环）
    depth_cache: dict[int, int] = {}
    # BFS 标记从开始节点可达的节点
    reachable: set[int] = set()
    q = deque([start_id])
    reachable.add(start_id)
    while q:
        cur = q.popleft()
        for nxt in adjacency.get(cur, []):
            if nxt not in reachable:
                reachable.add(nxt)
                q.append(nxt)

    def compute_depth(node_id: int, visited: set[int]) -> int:
        """计算从开始节点到 node_id 的最长路径长度"""
        if node_id not in reachable:
            # 不可达节点返回极大值，放在末尾
            return 999
        if node_id == start_id:
            depth_cache[start_id] = 0
            return 0
        if node_id in depth_cache:
            return depth_cache[node_id]
        if node_id in visited:
            # 检测到环，使用 0 作为默认深度
            return 0
        visited.add(node_id)
        max_pred = 0
        for pred_id in reverse_adj.get(node_id, []):
            pred_depth = compute_depth(pred_id, visited.copy())
            max_pred = max(max_pred, pred_depth + 1)
        depth_cache[node_id] = max_pred
        return max_pred

    # 计算所有节点的深度
    for node in all_nodes:
        compute_depth(node.id, set())

    # 按深度分组，同深度内按 Y 坐标排序
    depth_groups: dict[int, list[TemplateNode]] = {}
    for node in all_nodes:
        d = depth_cache.get(node.id, 999)
        if d not in depth_groups:
            depth_groups[d] = []
        depth_groups[d].append(node)

    # 分配 sort_order：每层一个值，同层节点共享
    for depth in sorted(depth_groups.keys()):
        nodes_at_depth = depth_groups[depth]
        # 同深度内按 Y 坐标从上到下排列
        nodes_at_depth.sort(key=lambda n: n.position_y or 0)
        for node in nodes_at_depth:
            node.sort_order = depth

    logger.debug(
        f"[designer] 拓扑排序完成 template_id={template_id} "
        f"节点={len(all_nodes)} 边={len(all_edges)} 层级={len(depth_groups)} "
        f"深度映射={dict(sorted((k, [n.name for n in v]) for k, v in depth_groups.items()))}"
    )
