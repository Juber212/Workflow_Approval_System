"""流程模板业务逻辑"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate,
    TemplateNode,
    TemplateEdge,
    FlowVersion,
    FlowInstance,
    Organization,
    User,
)
from app.models.enums import InstanceStatus
from app.schemas.common import PaginatedData
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateListItem,
    TemplateDetail,
    VersionHistoryItem,
    OrgTemplateSummary,
)


async def get_organization_summaries(
    db: AsyncSession, *, is_active: bool | None = None
) -> list[OrgTemplateSummary]:
    """组织卡片列表 —— 含模板数和运行中实例数"""
    stmt = select(Organization).order_by(Organization.id)
    if is_active is not None:
        stmt = stmt.where(Organization.is_active == is_active)
    result = await db.execute(stmt)
    orgs = result.scalars().all()
    org_ids = [o.id for o in orgs]

    if not org_ids:
        return []

    # 批量模板数
    tpl_count_stmt = (
        select(FlowTemplate.organization_id, func.count(FlowTemplate.id))
        .where(FlowTemplate.organization_id.in_(org_ids), FlowTemplate.status != "disabled")
        .group_by(FlowTemplate.organization_id)
    )
    tpl_rows = (await db.execute(tpl_count_stmt)).all()
    tpl_map = {oid: cnt for oid, cnt in tpl_rows}

    # 批量运行中实例数
    inst_count_stmt = (
        select(FlowInstance.organization_id, func.count(FlowInstance.id))
        .where(
            FlowInstance.organization_id.in_(org_ids),
            FlowInstance.status == InstanceStatus.RUNNING,
        )
        .group_by(FlowInstance.organization_id)
    )
    inst_rows = (await db.execute(inst_count_stmt)).all()
    inst_map = {oid: cnt for oid, cnt in inst_rows}

    return [
        OrgTemplateSummary(
            id=o.id,
            name=o.name,
            template_count=tpl_map.get(o.id, 0),
            running_instance_count=inst_map.get(o.id, 0),
        )
        for o in orgs
    ]


async def list_templates(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    organization_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    current_user_id: int | None = None,
) -> PaginatedData:
    """分页查询模板列表，含权限标识和计算字段"""
    conditions = []
    if organization_id:
        conditions.append(FlowTemplate.organization_id == organization_id)
    if status:
        conditions.append(FlowTemplate.status == status)
    if keyword:
        conditions.append(FlowTemplate.name.like(f"%{keyword}%"))

    base_stmt = select(FlowTemplate)
    if conditions:
        base_stmt = base_stmt.where(*conditions)

    # 总数
    count_stmt = select(func.count()).select_from(FlowTemplate)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页数据
    stmt = base_stmt.order_by(FlowTemplate.id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    if not templates:
        return PaginatedData(items=[], total=total, page=page, page_size=page_size)

    tpl_ids = [t.id for t in templates]

    # 批量查组织名称
    org_ids = list(set(t.organization_id for t in templates))
    org_stmt = select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
    org_rows = (await db.execute(org_stmt)).all()
    org_map = {oid: name for oid, name in org_rows}

    # 批量查创建人姓名
    creator_ids = list(set(t.created_by for t in templates))
    creator_stmt = select(User.id, User.real_name).where(User.id.in_(creator_ids))
    creator_rows = (await db.execute(creator_stmt)).all()
    creator_map = {uid: name for uid, name in creator_rows}

    # 批量节点数
    node_count_stmt = (
        select(TemplateNode.template_id, func.count(TemplateNode.id))
        .where(TemplateNode.template_id.in_(tpl_ids))
        .group_by(TemplateNode.template_id)
    )
    node_rows = (await db.execute(node_count_stmt)).all()
    node_map = {tid: cnt for tid, cnt in node_rows}

    # 批量运行中实例数
    instance_count_stmt = (
        select(FlowInstance.template_id, func.count(FlowInstance.id))
        .where(FlowInstance.template_id.in_(tpl_ids), FlowInstance.status == InstanceStatus.RUNNING)
        .group_by(FlowInstance.template_id)
    )
    inst_rows = (await db.execute(instance_count_stmt)).all()
    inst_map = {tid: cnt for tid, cnt in inst_rows}

    items = []
    for t in templates:
        node_cnt = node_map.get(t.id, 0)
        items.append(
            TemplateListItem(
                id=t.id,
                name=t.name,
                description=t.description,
                organization_id=t.organization_id,
                organization_name=org_map.get(t.organization_id),
                status=t.status,
                current_version=t.current_version,
                node_count=node_cnt,
                instance_count=inst_map.get(t.id, 0),
                can_edit=t.status == "draft",
                can_publish=(t.status == "draft" and node_cnt >= 3),
                can_start=(t.status == "published" and current_user_id is not None),
                created_by=t.created_by,
                created_by_name=creator_map.get(t.created_by),
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def create_template(db: AsyncSession, data: TemplateCreate, user_id: int) -> FlowTemplate:
    """创建模板 —— 自动生成开始节点和结束节点"""
    org = (await db.execute(select(Organization).where(Organization.id == data.organization_id))).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "组织不存在")

    tpl = FlowTemplate(
        name=data.name,
        description=data.description,
        organization_id=data.organization_id,
        status="draft",
        created_by=user_id,
    )
    db.add(tpl)
    await db.flush()

    # 开始节点
    start_node = TemplateNode(
        template_id=tpl.id,
        name="开始",
        is_start=True,
        position_x=100,
        position_y=300,
        sort_order=0,
    )
    db.add(start_node)

    # 结束节点
    end_node = TemplateNode(
        template_id=tpl.id,
        name="结束",
        is_end=True,
        position_x=700,
        position_y=300,
        sort_order=999,
    )
    db.add(end_node)
    await db.flush()

    return tpl


async def get_template_detail(db: AsyncSession, template_id: int) -> TemplateDetail:
    """获取模板详情 —— 含节点/连线/版本历史"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    # 节点
    nodes_result = await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == template_id).order_by(TemplateNode.sort_order)
    )
    nodes = nodes_result.scalars().all()

    # 连线
    edges_result = await db.execute(select(TemplateEdge).where(TemplateEdge.template_id == template_id))
    edges = edges_result.scalars().all()

    # 版本历史
    versions_result = await db.execute(
        select(FlowVersion)
        .where(FlowVersion.template_id == template_id)
        .order_by(FlowVersion.version_number.desc())
    )
    versions = versions_result.scalars().all()

    # 组织名
    org_name = (await db.execute(select(Organization.name).where(Organization.id == tpl.organization_id))).scalar_one_or_none()

    # 批量查发布人
    publisher_ids = list(set(v.published_by for v in versions))
    publisher_map: dict = {}
    if publisher_ids:
        pr = await db.execute(select(User.id, User.real_name).where(User.id.in_(publisher_ids)))
        publisher_map = {uid: name for uid, name in pr.all()}

    # 创建人姓名
    creator_name = (await db.execute(select(User.real_name).where(User.id == tpl.created_by))).scalar_one_or_none()

    # 运行中实例数
    inst_count = (
        await db.execute(
            select(func.count()).where(
                FlowInstance.template_id == template_id,
                FlowInstance.status == InstanceStatus.RUNNING,
            )
        )
    ).scalar() or 0

    return TemplateDetail(
        id=tpl.id,
        name=tpl.name,
        description=tpl.description,
        organization_id=tpl.organization_id,
        organization_name=org_name,
        status=tpl.status,
        current_version=tpl.current_version,
        node_count=len(nodes),
        instance_count=inst_count,
        nodes=[_node_to_dict(n) for n in nodes],
        edges=[{"id": e.id, "source_node_id": e.source_node_id, "target_node_id": e.target_node_id} for e in edges],
        versions=[
            VersionHistoryItem(
                id=v.id,
                version_number=v.version_number,
                status=v.status,
                node_count=len(v.nodes_snapshot) if v.nodes_snapshot else 0,
                edge_count=len(v.edges_snapshot) if v.edges_snapshot else 0,
                has_soft_overrides=bool(v.soft_config_overrides),
                published_by=v.published_by,
                published_by_name=publisher_map.get(v.published_by),
                published_at=v.published_at,
            )
            for v in versions
        ],
        created_by=tpl.created_by,
        created_by_name=creator_name,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


async def update_template(db: AsyncSession, template_id: int, data: TemplateUpdate) -> tuple[FlowTemplate, bool]:
    """更新模板基本信息 —— 已发布模板修改名称会触发硬修改（版本号 +1，回到 draft）
    返回 (模板, 是否触发硬修改)
    """
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    # 检测名称是否变更（名称是硬字段）
    name_changed = data.name != tpl.name
    is_hard = name_changed and tpl.status == "published"

    # 更新基本信息
    tpl.name = data.name
    tpl.description = data.description

    # 已发布模板修改名称 → 版本号 +1，状态回到 draft
    if is_hard:
        tpl.current_version += 1
        tpl.status = "draft"

    await db.flush()
    return tpl, is_hard


async def delete_template(db: AsyncSession, template_id: int) -> None:
    """删除模板 —— 仅 draft 状态可删"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status != "draft":
        raise AppException(ErrorCode.FORBIDDEN, "仅草稿状态的模板可删除")
    await db.delete(tpl)
    await db.flush()


async def disable_template(db: AsyncSession, template_id: int) -> FlowTemplate:
    """停用已发布模板 —— 仅 published 状态可停用"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status != "published":
        raise AppException(ErrorCode.FORBIDDEN, "仅已发布状态的模板可停用")
    tpl.status = "disabled"
    await db.flush()
    return tpl


def _node_to_dict(node: TemplateNode) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "is_start": node.is_start,
        "is_end": node.is_end,
        "assignee_id": node.assignee_id,
        "time_limit_days": node.time_limit_days,
        "require_file": node.require_file,
        "approvers": node.approvers,
        "checkers": node.checkers,
        "approval_strategy": node.approval_strategy,
        "is_optional": node.is_optional,
        "position_x": node.position_x,
        "position_y": node.position_y,
        "sort_order": node.sort_order,
    }
