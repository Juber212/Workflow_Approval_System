"""流程设计器服务 —— 保存/加载画布数据（节点 + 连线）"""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import FlowTemplate, TemplateNode, TemplateEdge


# 节点可更新字段（排除系统字段和自动生成字段）
_NODE_UPDATABLE_FIELDS = [
    "name", "description", "assignee_id", "time_limit_days",
    "require_file", "approvers", "checkers", "approval_strategy",
    "is_optional", "position_x", "position_y", "sort_order",
]


async def save_design_data(
    db: AsyncSession,
    template_id: int,
    nodes_data: list[dict],
    edges_data: list[dict],
) -> dict:
    """批量保存设计器数据 —— 新增/更新/删除节点和连线，同一事务"""
    # 校验模板存在且为 draft
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status not in ("draft", "published"):
        raise AppException(ErrorCode.FORBIDDEN, "仅草稿或已发布模板可编辑设计")

    # 获取现有节点和连线
    existing_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == template_id)
    )).scalars().all()
    existing_edges = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == template_id)
    )).scalars().all()

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

        # 系统节点：若 ID 不匹配，自动映射到现有系统节点 ID 进行更新
        if item.get("is_start") and existing_start_node and (nid is None or nid not in existing_node_ids):
            nid = existing_start_node.id
        elif item.get("is_end") and existing_end_node and (nid is None or nid not in existing_node_ids):
            nid = existing_end_node.id

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
        source_id = item["source_node_id"]
        target_id = item["target_node_id"]

        # 映射临时节点 ID → 真实节点 ID
        source_id = new_node_id_map.get(str(source_id), source_id)
        target_id = new_node_id_map.get(str(target_id), target_id)

        if eid and eid in existing_edge_ids:
            # 更新已有连线
            submitted_edge_ids.add(eid)
            await _update_edge(db, eid, source_id, target_id)
        else:
            # 新增连线
            new_edge = await _create_edge(db, template_id, source_id, target_id)
            submitted_edge_ids.add(new_edge.id)

    # 删除不在提交列表中的连线
    edges_to_delete = existing_edge_ids - submitted_edge_ids
    if edges_to_delete:
        await db.execute(
            delete(TemplateEdge).where(TemplateEdge.id.in_(edges_to_delete))
        )

    # 发布状态模板检测硬修改 → 版本号 +1 + 回到 draft
    if tpl.status == "published":
        from app.services.version_service import hard_modify_template
        tpl = await hard_modify_template(db, template_id)

    await db.flush()

    return {
        "template_id": template_id,
        "node_count": len(submitted_node_ids),
        "edge_count": len(submitted_edge_ids),
        "is_hard_modified": tpl.status == "draft" and tpl.current_version > 0,
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


async def _update_edge(db: AsyncSession, edge_id: int, source_id: int, target_id: int) -> None:
    """更新已有连线"""
    edge = (await db.execute(select(TemplateEdge).where(TemplateEdge.id == edge_id))).scalar_one()
    edge.source_node_id = source_id
    edge.target_node_id = target_id


# 节点软修改字段 —— 变更不触发版本递增
_NODE_SOFT_FIELDS = {"assignee_id", "time_limit_days", "description", "checkers", "approvers"}


def _is_hard_node_change(old: dict, new: dict) -> bool:
    """检测节点变更是否包含硬字段（非 SOFT_FIELDS 的字段）"""
    for key, new_val in new.items():
        if key in _NODE_SOFT_FIELDS:
            continue
        old_val = old.get(key)
        if new_val != old_val:
            return True
    return False


async def add_node(db: AsyncSession, template_id: int, data: dict) -> dict:
    """添加单个工作节点 —— 自动设为中间节点"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    # 确保不是系统节点
    data["is_start"] = False
    data["is_end"] = False

    node = await _create_node(db, template_id, data)

    # 已发布模板添加节点 → 硬修改
    is_hard = tpl.status == "published"
    if is_hard:
        from app.services.version_service import hard_modify_template
        await hard_modify_template(db, template_id)

    return {
        "id": node.id,
        "name": node.name,
        "position_x": node.position_x,
        "position_y": node.position_y,
        "is_hard_modified": is_hard,
    }


async def update_node(db: AsyncSession, node_id: int, data: dict) -> dict:
    """更新单个节点 —— 含软/硬修改判定"""
    node = (await db.execute(select(TemplateNode).where(TemplateNode.id == node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")

    # 系统节点不可修改类型
    if "is_start" in data and node.is_start != data["is_start"]:
        raise AppException(ErrorCode.FORBIDDEN, "开始节点不可变更类型")
    if "is_end" in data and node.is_end != data["is_end"]:
        raise AppException(ErrorCode.FORBIDDEN, "结束节点不可变更类型")

    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == node.template_id))).scalar_one()

    # 检测是否为硬修改
    old_data = {f: getattr(node, f, None) for f in _NODE_UPDATABLE_FIELDS}
    is_hard = _is_hard_node_change(old_data, data)

    await _update_node(db, node_id, data)

    # 已发布模板硬修改 → 版本递增
    is_hard_modified = is_hard and tpl.status == "published"
    if is_hard_modified:
        from app.services.version_service import hard_modify_template
        await hard_modify_template(db, tpl.id)

    return {
        "id": node.id,
        "name": data.get("name", node.name),
        "is_hard_modified": is_hard_modified,
    }


async def delete_node(db: AsyncSession, node_id: int) -> None:
    """删除单个节点 —— 系统节点不可删除，关联连线自动清除"""
    node = (await db.execute(select(TemplateNode).where(TemplateNode.id == node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")
    if node.is_start or node.is_end:
        raise AppException(ErrorCode.FORBIDDEN, "系统节点不可删除")

    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == node.template_id))).scalar_one()

    # 删除关联连线
    await db.execute(
        delete(TemplateEdge).where(
            TemplateEdge.template_id == node.template_id,
            (TemplateEdge.source_node_id == node_id) | (TemplateEdge.target_node_id == node_id),
        )
    )
    await db.delete(node)

    # 已发布模板删除节点 → 硬修改
    if tpl.status == "published":
        from app.services.version_service import hard_modify_template
        await hard_modify_template(db, tpl.id)


# ==================== 单连线 CRUD ====================


async def add_edge(db: AsyncSession, template_id: int, source_node_id: int, target_node_id: int) -> dict:
    """添加单条连线 —— 含自环/重复/系统节点校验，支持 fork 和 join"""
    # 校验模板存在且可编辑
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status not in ("draft", "published"):
        raise AppException(ErrorCode.FORBIDDEN, "仅草稿或已发布模板可编辑连线")

    # 校验源节点和目标节点存在且属于同一模板
    source_node = (await db.execute(
        select(TemplateNode).where(TemplateNode.id == source_node_id, TemplateNode.template_id == template_id)
    )).scalar_one_or_none()
    if source_node is None:
        raise AppException(ErrorCode.NOT_FOUND, f"源节点（ID={source_node_id}）不存在或不属于该模板")

    target_node = (await db.execute(
        select(TemplateNode).where(TemplateNode.id == target_node_id, TemplateNode.template_id == template_id)
    )).scalar_one_or_none()
    if target_node is None:
        raise AppException(ErrorCode.NOT_FOUND, f"目标节点（ID={target_node_id}）不存在或不属于该模板")

    # 校验：禁止自环
    if source_node_id == target_node_id:
        raise AppException(ErrorCode.VALIDATION_ERROR, "连线不能连接自身（禁止自环）")

    # 校验：开始节点不可作为目标（target）
    if target_node.is_start:
        raise AppException(ErrorCode.VALIDATION_ERROR, "开始节点不可作为连线的目标")

    # 校验：结束节点不可作为源（source）
    if source_node.is_end:
        raise AppException(ErrorCode.VALIDATION_ERROR, "结束节点不可作为连线的源")

    # 校验：已存在相同连线（不重复）
    existing = (await db.execute(
        select(TemplateEdge).where(
            TemplateEdge.template_id == template_id,
            TemplateEdge.source_node_id == source_node_id,
            TemplateEdge.target_node_id == target_node_id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise AppException(ErrorCode.CONFLICT, f"连线已存在（{source_node_id} → {target_node_id}）")

    # 创建连线
    edge = await _create_edge(db, template_id, source_node_id, target_node_id)

    # 已发布模板添加连线 → 硬修改
    is_hard = tpl.status == "published"
    if is_hard:
        from app.services.version_service import hard_modify_template
        await hard_modify_template(db, template_id)

    return {
        "id": edge.id,
        "source_node_id": edge.source_node_id,
        "target_node_id": edge.target_node_id,
        "is_hard_modified": is_hard,
    }


async def delete_edge(db: AsyncSession, edge_id: int, template_id: int) -> dict:
    """删除单条连线 —— 已发布模板自动触发硬修改"""
    edge = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.id == edge_id, TemplateEdge.template_id == template_id)
    )).scalar_one_or_none()
    if edge is None:
        raise AppException(ErrorCode.NOT_FOUND, "连线不存在")

    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one()

    await db.delete(edge)

    # 已发布模板删除连线 → 硬修改
    is_hard = False
    if tpl.status == "published":
        from app.services.version_service import hard_modify_template
        await hard_modify_template(db, template_id)
        is_hard = True

    return {
        "id": edge_id,
        "is_hard_modified": is_hard,
    }
