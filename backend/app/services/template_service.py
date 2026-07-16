"""项目模板业务逻辑 —— 简化版：无版本、无状态，画布即模板"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, Organization, User,
)
from app.models.enums import InstanceStatus
from app.schemas.common import PaginatedData
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateListItem,
    TemplateDetail, OrgTemplateSummary,
)


async def get_organization_summaries(
    db: AsyncSession, *, is_active: bool | None = None, current_user_id: int | None = None
) -> tuple[list[OrgTemplateSummary], int]:
    """组织卡片列表 —— 含模板数、运行中实例数、最近更新时间"""
    stmt = select(Organization).order_by(Organization.id)
    if is_active is not None:
        stmt = stmt.where(Organization.is_active == is_active)
    result = await db.execute(stmt)
    orgs = result.scalars().all()
    org_ids = [o.id for o in orgs]

    if not org_ids:
        return [], 0

    # 批量模板数
    tpl_count_stmt = (
        select(FlowTemplate.organization_id, func.count(FlowTemplate.id))
        .where(FlowTemplate.organization_id.in_(org_ids))
        .group_by(FlowTemplate.organization_id)
    )
    tpl_rows = (await db.execute(tpl_count_stmt)).all()
    tpl_map = {oid: cnt for oid, cnt in tpl_rows}

    # 批量运行中实例数
    inst_count_stmt = (
        select(FlowInstance.organization_id, func.count(FlowInstance.id))
        .where(FlowInstance.organization_id.in_(org_ids), FlowInstance.status == InstanceStatus.RUNNING)
        .group_by(FlowInstance.organization_id)
    )
    inst_rows = (await db.execute(inst_count_stmt)).all()
    inst_map = {oid: cnt for oid, cnt in inst_rows}

    # 批量最近更新时间
    tpl_time_stmt = (
        select(FlowTemplate.organization_id, func.max(FlowTemplate.updated_at))
        .where(FlowTemplate.organization_id.in_(org_ids))
        .group_by(FlowTemplate.organization_id)
    )
    tpl_time_rows = (await db.execute(tpl_time_stmt)).all()
    tpl_time_map = {oid: dt for oid, dt in tpl_time_rows}

    inst_time_stmt = (
        select(FlowInstance.organization_id, func.max(FlowInstance.updated_at))
        .where(FlowInstance.organization_id.in_(org_ids))
        .group_by(FlowInstance.organization_id)
    )
    inst_time_rows = (await db.execute(inst_time_stmt)).all()
    inst_time_map = {oid: dt for oid, dt in inst_time_rows}

    # 当前用户所属组织 ID
    user_org_id: int | None = None
    if current_user_id:
        user_stmt = select(User.organization_id).where(User.id == current_user_id)
        user_org_id = (await db.execute(user_stmt)).scalar_one_or_none()

    total_instance_count = 0
    result_list = []
    for o in orgs:
        tpl_time = tpl_time_map.get(o.id)
        inst_time = inst_time_map.get(o.id)
        latest = None
        if tpl_time and inst_time:
            latest = max(tpl_time, inst_time)
        elif tpl_time:
            latest = tpl_time
        elif inst_time:
            latest = inst_time

        running_cnt = inst_map.get(o.id, 0)
        total_instance_count += running_cnt

        result_list.append(OrgTemplateSummary(
            id=o.id, name=o.name,
            template_count=tpl_map.get(o.id, 0),
            running_instance_count=running_cnt,
            latest_update_time=latest.isoformat() if latest else None,
            is_current_user_org=(o.id == user_org_id),
        ))

    return result_list, total_instance_count


async def list_templates(
    db: AsyncSession, *, page: int = 1, page_size: int = 20,
    organization_id: int | None = None, keyword: str | None = None,
) -> PaginatedData:
    """分页查询模板列表"""
    conditions = []
    if organization_id:
        conditions.append(FlowTemplate.organization_id == organization_id)
    if keyword:
        conditions.append(FlowTemplate.name.like(f"%{keyword}%"))

    base_stmt = select(FlowTemplate)
    if conditions:
        base_stmt = base_stmt.where(*conditions)

    count_stmt = select(func.count()).select_from(FlowTemplate)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base_stmt.order_by(FlowTemplate.id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    if not templates:
        return PaginatedData(items=[], total=total, page=page, page_size=page_size)

    tpl_ids = [t.id for t in templates]

    # 批量组织名
    org_ids = list(set(t.organization_id for t in templates))
    org_stmt = select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
    org_rows = (await db.execute(org_stmt)).all()
    org_map = {oid: name for oid, name in org_rows}

    # 批量创建人名
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

    items = [
        TemplateListItem(
            id=t.id, name=t.name, description=t.description,
            organization_id=t.organization_id,
            organization_name=org_map.get(t.organization_id),
            node_count=node_map.get(t.id, 0),
            instance_count=inst_map.get(t.id, 0),
            created_by=t.created_by,
            created_by_name=creator_map.get(t.created_by),
            created_at=t.created_at, updated_at=t.updated_at,
        )
        for t in templates
    ]
    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def create_template(db: AsyncSession, data: TemplateCreate, user_id: int) -> FlowTemplate:
    """创建模板 —— 自动生成开始节点和结束节点"""
    org = (await db.execute(select(Organization).where(Organization.id == data.organization_id))).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "组织不存在")

    tpl = FlowTemplate(
        name=data.name, description=data.description,
        organization_id=data.organization_id, created_by=user_id,
    )
    db.add(tpl)
    await db.flush()

    # 开始节点
    db.add(TemplateNode(
        template_id=tpl.id, name="开始", is_start=True,
        position_x=100, position_y=300, sort_order=0,
    ))
    # 结束节点
    db.add(TemplateNode(
        template_id=tpl.id, name="结束", is_end=True,
        position_x=700, position_y=300, sort_order=999,
    ))
    await db.flush()
    return tpl


async def get_template_detail(db: AsyncSession, template_id: int) -> TemplateDetail:
    """获取模板详情 —— 含节点和连线，附带用户名称"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    nodes_result = await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == template_id).order_by(TemplateNode.sort_order)
    )
    nodes = nodes_result.scalars().all()

    edges_result = await db.execute(select(TemplateEdge).where(TemplateEdge.template_id == template_id))
    edges = edges_result.scalars().all()

    # 收集所有涉及的用户 ID，批量查询名称
    user_ids: set[int] = set()
    for n in nodes:
        if n.assignee_id:
            user_ids.add(n.assignee_id)
        for uid in _extract_ids(n.approvers):
            user_ids.add(uid)
        for uid in _extract_ids(n.checkers):
            user_ids.add(uid)

    # 批量查询用户名称
    user_name_map: dict[int, str] = {}
    if user_ids:
        users_result = await db.execute(select(User.id, User.real_name).where(User.id.in_(list(user_ids))))
        for row in users_result:
            user_name_map[row[0]] = row[1]

    org_name = (await db.execute(select(Organization.name).where(Organization.id == tpl.organization_id))).scalar_one_or_none()
    creator_name = (await db.execute(select(User.real_name).where(User.id == tpl.created_by))).scalar_one_or_none()

    inst_count = (await db.execute(
        select(func.count()).where(FlowInstance.template_id == template_id, FlowInstance.status == InstanceStatus.RUNNING)
    )).scalar() or 0

    return TemplateDetail(
        id=tpl.id, name=tpl.name, description=tpl.description,
        organization_id=tpl.organization_id, organization_name=org_name,
        node_count=len(nodes), instance_count=inst_count,
        nodes=[_node_to_dict(n, user_name_map) for n in nodes],
        edges=[{"id": e.id, "source_node_id": e.source_node_id, "target_node_id": e.target_node_id, "points": e.points} for e in edges],
        created_by=tpl.created_by, created_by_name=creator_name,
        created_at=tpl.created_at, updated_at=tpl.updated_at,
    )


async def update_template(db: AsyncSession, template_id: int, data: TemplateUpdate) -> FlowTemplate:
    """更新模板基本信息"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    tpl.name = data.name
    tpl.description = data.description
    await db.flush()
    return tpl


async def delete_template(db: AsyncSession, template_id: int) -> None:
    """删除模板 —— 关联节点和连线级联删除"""
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    await db.delete(tpl)
    await db.flush()


def _extract_ids(raw: any) -> list[int]:
    """从 approvers/checkers JSON 字段中提取用户 ID 列表"""
    if raw is None:
        return []
    if isinstance(raw, list):
        ids = []
        for item in raw:
            if isinstance(item, dict):
                uid = item.get("user_id") or item.get("id")
                if isinstance(uid, int):
                    ids.append(uid)
            elif isinstance(item, int):
                ids.append(item)
        return ids
    return []


def _node_to_dict(node: TemplateNode, user_name_map: dict[int, str] | None = None) -> dict:
    """将模板节点转为字典，附带用户名称"""
    name_map = user_name_map or {}

    # 解析负责人名称
    assignee_name = name_map.get(node.assignee_id) if node.assignee_id else None

    # 解析校验人名称列表
    checker_ids = _extract_ids(node.checkers)
    checkers_names = [name_map[uid] for uid in checker_ids if uid in name_map]

    # 解析审批人名称列表
    approver_ids = _extract_ids(node.approvers)
    approvers_names = [name_map[uid] for uid in approver_ids if uid in name_map]

    return {
        "id": node.id, "name": node.name,
        "is_start": node.is_start, "is_end": node.is_end,
        "assignee_id": node.assignee_id, "assignee_name": assignee_name,
        "time_limit_days": node.time_limit_days,
        "require_file": node.require_file, "approvers": node.approvers,
        "approvers_names": approvers_names,
        "checkers": node.checkers, "checkers_names": checkers_names,
        "approval_strategy": node.approval_strategy,
        "position_x": node.position_x, "position_y": node.position_y,
        "sort_order": node.sort_order,
    }
