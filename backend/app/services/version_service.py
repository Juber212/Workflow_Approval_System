"""版本服务 —— 流程发布、软配置覆盖、快照管理、新版本创建"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import FlowTemplate, TemplateNode, TemplateEdge, FlowVersion


# 节点表中需要复制的字段（排除 id、template_id、created_at 等自动生成字段）
_NODE_COPY_FIELDS = [
    "name", "is_start", "is_end", "assignee_id", "time_limit_days",
    "require_file", "approvers", "checkers", "approval_strategy",
    "is_optional", "position_x", "position_y", "sort_order",
]

# 模板级硬修改字段 —— 变更时触发版本递增
_TEMPLATE_HARD_FIELDS = {"name"}


async def hard_modify_template(db: AsyncSession, template_id: int) -> FlowTemplate:
    """已发布模板检测到硬修改时调用 —— 版本号 +1，状态回到 draft"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status != "published":
        raise AppException(ErrorCode.FORBIDDEN, "仅已发布状态的模板可进行硬修改")

    # 版本号递增，状态回到草稿
    tpl.current_version += 1
    tpl.status = "draft"
    await db.flush()
    return tpl


# 允许软修改的字段（已发布模板，不改版本号）
SOFT_MODIFIABLE_FIELDS = {"assignee_id", "time_limit_days", "description", "checkers", "approvers"}


async def publish_template(db: AsyncSession, template_id: int, user_id: int) -> FlowVersion:
    """发布模板 —— 生成快照 + 版本号递增 + 状态变更"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status != "draft":
        raise AppException(ErrorCode.FORBIDDEN, "仅草稿状态的模板可发布")

    # 校验
    from app.services.validation_service import validate_template_for_publish

    errors = await validate_template_for_publish(db, template_id)
    if errors:
        raise AppException(ErrorCode.VALIDATION_ERROR, "发布校验不通过", data={"errors": errors})

    # 生成快照
    nodes_result = await db.execute(select(TemplateNode).where(TemplateNode.template_id == template_id))
    nodes = nodes_result.scalars().all()
    edges_result = await db.execute(select(TemplateEdge).where(TemplateEdge.template_id == template_id))
    edges = edges_result.scalars().all()

    nodes_snapshot = [
        {
            "id": n.id,
            "name": n.name,
            "is_start": n.is_start,
            "is_end": n.is_end,
            "assignee_id": n.assignee_id,
            "time_limit_days": n.time_limit_days,
            "require_file": n.require_file,
            "approvers": n.approvers,
            "checkers": n.checkers,
            "approval_strategy": n.approval_strategy,
            "is_optional": n.is_optional,
            "position_x": n.position_x,
            "position_y": n.position_y,
            "sort_order": n.sort_order,
        }
        for n in nodes
    ]

    edges_snapshot = [
        {
            "id": e.id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
        }
        for e in edges
    ]

    # 版本号递增
    new_version = tpl.current_version + 1
    tpl.current_version = new_version
    tpl.status = "published"

    version = FlowVersion(
        template_id=template_id,
        version_number=new_version,
        status="published",
        nodes_snapshot=nodes_snapshot,
        edges_snapshot=edges_snapshot,
        published_by=user_id,
        published_at=datetime.now(),
    )
    db.add(version)
    await db.flush()

    return version


async def get_version_detail(db: AsyncSession, template_id: int, version_id: int):
    """获取版本快照详情 —— 含完整 nodes_snapshot / edges_snapshot"""
    from app.schemas.template import VersionDetail
    from app.models import User

    version = (
        await db.execute(
            select(FlowVersion).where(
                FlowVersion.id == version_id,
                FlowVersion.template_id == template_id,
            )
        )
    ).scalar_one_or_none()

    if version is None:
        raise AppException(ErrorCode.NOT_FOUND, "版本不存在")

    # 发布人姓名
    publisher_name = None
    if version.published_by:
        user = (await db.execute(select(User).where(User.id == version.published_by))).scalar_one_or_none()
        if user:
            publisher_name = user.real_name

    return VersionDetail(
        id=version.id,
        version_number=version.version_number,
        status=version.status,
        nodes_snapshot=version.nodes_snapshot if isinstance(version.nodes_snapshot, list) else [],
        edges_snapshot=version.edges_snapshot if isinstance(version.edges_snapshot, list) else [],
        soft_config_overrides=version.soft_config_overrides,
        published_by=version.published_by,
        published_by_name=publisher_name,
        published_at=version.published_at,
        created_at=version.created_at,
    )


async def apply_soft_config(
    db: AsyncSession,
    template_id: int,
    node_id: int,
    updates: dict,
) -> dict:
    """对已发布模板的节点应用软配置覆盖 —— 写入当前发布版本的 soft_config_overrides"""

    # 校验模板
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status != "published":
        raise AppException(ErrorCode.FORBIDDEN, "仅已发布模板可进行软修改")

    # 校验节点
    node = (await db.execute(select(TemplateNode).where(TemplateNode.id == node_id, TemplateNode.template_id == template_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")

    # 校验不允许修改的硬字段
    hard_fields = set(updates.keys()) - SOFT_MODIFIABLE_FIELDS
    if hard_fields:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            f"以下字段不可软修改（请通过发布新版本修改）：{', '.join(sorted(hard_fields))}",
        )

    # 获取当前发布版本
    version = (
        await db.execute(
            select(FlowVersion)
            .where(FlowVersion.template_id == template_id, FlowVersion.status == "published")
            .order_by(FlowVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if version is None:
        raise AppException(ErrorCode.NOT_FOUND, "该模板没有已发布的版本")

    # 读取现有覆盖层
    overrides = dict(version.soft_config_overrides) if version.soft_config_overrides else {}
    node_overrides = overrides.get(str(node_id), {})

    # 合并更新
    node_overrides.update(updates)
    overrides[str(node_id)] = node_overrides
    version.soft_config_overrides = overrides

    await db.flush()

    return {
        "template_id": template_id,
        "node_id": node_id,
        "version_number": version.version_number,
        "overrides": overrides[str(node_id)],
    }


async def get_effective_node_config(
    db: AsyncSession,
    node_id: int,
    version_id: int | None = None,
) -> dict:
    """获取节点的有效配置（快照 + 覆盖层合并）"""
    node = (await db.execute(select(TemplateNode).where(TemplateNode.id == node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")

    base = {
        "id": node.id,
        "name": node.name,
        "assignee_id": node.assignee_id,
        "time_limit_days": node.time_limit_days,
        "require_file": node.require_file,
        "approvers": node.approvers,
        "checkers": node.checkers,
        "approval_strategy": node.approval_strategy,
        "is_optional": node.is_optional,
        "is_start": node.is_start,
        "is_end": node.is_end,
    }

    # 如果指定了版本，合并覆盖层
    if version_id:
        version = (await db.execute(select(FlowVersion).where(FlowVersion.id == version_id))).scalar_one_or_none()
        if version and version.soft_config_overrides:
            node_overrides = version.soft_config_overrides.get(str(node_id))
            if node_overrides:
                base.update(node_overrides)

    return base


async def create_new_version(db: AsyncSession, template_id: int, user_id: int) -> FlowTemplate:
    """从已发布/已停用模板创建新草稿版本 —— 复制当前节点和连线，状态变回 draft"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status not in ("published", "disabled"):
        raise AppException(ErrorCode.FORBIDDEN, "仅已发布或已停用状态的模板可创建新版本")

    # 获取当前节点和连线
    nodes_result = await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == template_id).order_by(TemplateNode.sort_order)
    )
    old_nodes = nodes_result.scalars().all()

    edges_result = await db.execute(select(TemplateEdge).where(TemplateEdge.template_id == template_id))
    old_edges = edges_result.scalars().all()

    # 删除旧节点和连线（新版本重新生成）
    for e in old_edges:
        await db.delete(e)
    for n in old_nodes:
        await db.delete(n)
    await db.flush()

    # 复制节点（使用相同的字段值，生成新 id）
    node_id_map: dict[int, int] = {}
    for old_node in old_nodes:
        new_node = TemplateNode(template_id=template_id)
        for field in _NODE_COPY_FIELDS:
            setattr(new_node, field, getattr(old_node, field))
        db.add(new_node)
        await db.flush()
        node_id_map[old_node.id] = new_node.id

    # 复制连线（映射到新节点 id）
    for old_edge in old_edges:
        new_edge = TemplateEdge(
            template_id=template_id,
            source_node_id=node_id_map[old_edge.source_node_id],
            target_node_id=node_id_map[old_edge.target_node_id],
        )
        db.add(new_edge)
    await db.flush()

    # 模板状态回到 draft，版本号不变化（下次发布时 +1）
    tpl.status = "draft"
    await db.flush()

    return tpl
