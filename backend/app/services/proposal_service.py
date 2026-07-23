"""方案服务 —— 发起方案、方案列表、方案库"""
from datetime import datetime

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate,
    FlowInstance,
    TemplateNode,
    TemplateEdge,
    InstanceNode,
    InstanceEdge,
    User,
    Organization,
    Task,
    OperationLog,
)
from app.models.enums import (
    InstanceStatus,
    InstanceNodeStatus,
    TaskStatus,
    OperatorType,
)
from app.schemas.common import PaginatedData
from app.schemas.proposal import ProposalCreateRequest, ProposalListItem
from app.api.deps import CurrentUser


# 方案内置模板固定名称
BUILTIN_PROPOSAL_TEMPLATE_NAME = "方案默认模板"


async def ensure_proposal_template(db: AsyncSession, org_id: int, user_id: int) -> FlowTemplate:
    """获取或创建组织的方案默认模板（每个组织一个）

    使用 SELECT ... FOR UPDATE 防止并发调用创建重复模板。
    """
    # 锁定查——确保两个并发请求只有一个能进入创建逻辑
    existing = (await db.execute(
        select(FlowTemplate).where(
            FlowTemplate.organization_id == org_id,
            FlowTemplate.type == "proposal",
        ).with_for_update()
    )).scalar_one_or_none()
    if existing:
        return existing

    # 创建方案默认模板
    tpl = FlowTemplate(
        name=BUILTIN_PROPOSAL_TEMPLATE_NAME,
        description="系统内置方案流程模板（固定三节点：开始→工作→结束）",
        organization_id=org_id,
        created_by=user_id,
        type="proposal",
    )
    db.add(tpl)
    await db.flush()

    # 创建三个固定节点
    nodes_data = [
        {"name": "开始", "is_start": True, "is_end": False, "sort_order": 1},
        {"name": "方案工作", "is_start": False, "is_end": False, "sort_order": 2},
        {"name": "结束", "is_start": False, "is_end": True, "sort_order": 3},
    ]
    for nd in nodes_data:
        db.add(TemplateNode(template_id=tpl.id, **nd))
    await db.flush()

    # 查询模板节点以获取 ID
    tpl_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == tpl.id).order_by(TemplateNode.sort_order)
    )).scalars().all()

    # 创建连线
    db.add(TemplateEdge(
        template_id=tpl.id,
        source_node_id=tpl_nodes[0].id,
        target_node_id=tpl_nodes[1].id,
    ))
    db.add(TemplateEdge(
        template_id=tpl.id,
        source_node_id=tpl_nodes[1].id,
        target_node_id=tpl_nodes[2].id,
    ))
    await db.flush()
    return tpl


async def create_proposal(
    db: AsyncSession,
    body: ProposalCreateRequest,
    current_user: CurrentUser,
) -> dict:
    """发起方案 —— 使用内置模板创建实例"""

    # 验证组织
    org = (await db.execute(
        select(Organization).where(Organization.id == body.organization_id)
    )).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "组织不存在")

    # 确保方案模板存在
    tpl = await ensure_proposal_template(db, body.organization_id, current_user.id)

    # 读取模板节点
    tpl_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == tpl.id).order_by(TemplateNode.sort_order)
    )).scalars().all()

    # 创建方案实例
    instance = FlowInstance(
        name=body.name.strip(),
        description=body.description,
        template_id=tpl.id,
        template_name=tpl.name,
        template_type=tpl.type,  # 快照模板类型，用于存储分目录
        organization_id=body.organization_id,
        initiator_id=current_user.id,
        priority="normal",
        status=InstanceStatus.CREATED,
    )
    db.add(instance)
    await db.flush()

    # 复制节点
    node_id_map: dict[int, int] = {}
    instance_nodes: list[InstanceNode] = []
    deadline = body.deadline

    for tn in tpl_nodes:
        inode = InstanceNode(
            instance_id=instance.id,
            name=tn.name,
            is_start=tn.is_start,
            is_end=tn.is_end,
            sort_order=tn.sort_order,
            # 工作节点：使用用户指定的配置
            assignee_id=body.designer_id if not tn.is_start and not tn.is_end else None,
            time_limit_days=None,
            deadline=deadline if not tn.is_start else None,
            require_file=True,
            approvers=body.approvers if not tn.is_start and not tn.is_end else (
                [{"user_id": current_user.id}] if tn.is_end else None
            ),
            checkers=None,  # 方案无校验环节
            approval_strategy="all_approve",
            require_assignee_signature=tn.require_assignee_signature,
            require_checker_signature=tn.require_checker_signature,
            require_approver_signature=tn.require_approver_signature,
            signature_x=tn.signature_x,
            signature_y=tn.signature_y,
            signature_page=tn.signature_page,
            status="waiting",
        )
        db.add(inode)
        await db.flush()
        node_id_map[tn.id] = inode.id
        instance_nodes.append(inode)

    # 复制连线
    tpl_edges = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == tpl.id)
    )).scalars().all()
    for te in tpl_edges:
        db.add(InstanceEdge(
            instance_id=instance.id,
            source_node_id=node_id_map[te.source_node_id],
            target_node_id=node_id_map[te.target_node_id],
        ))

    # 计算节点 incoming_counts + 激活开始节点 + 传播到工作节点
    from app.engine.flow_engine import calculate_incoming_counts, activate_start_node, propagate_from_node
    await calculate_incoming_counts(db, instance.id)
    start_node = next((n for n in instance_nodes if n.is_start), None)
    if start_node:
        await activate_start_node(db, instance.id)
        # 激活第一个工作节点，创建 Task
        await propagate_from_node(db, instance.id, start_node.id)

    # 实例状态 → running
    instance.status = InstanceStatus.RUNNING
    instance.initiated_at = datetime.now()

    # 操作日志
    first_work = next((n for n in instance_nodes if not n.is_start and not n.is_end), None)
    db.add(OperationLog(
        instance_id=instance.id,
        node_id=first_work.id if first_work else start_node.id if start_node else None,
        operator_type=OperatorType.USER,
        operator_id=current_user.id,
        operation_type="initiate",
        round=1,
        description=f"发起方案：{body.name}",
    ))

    await db.flush()
    return {
        "id": instance.id,
        "name": instance.name,
        "status": instance.status,
    }


async def get_organization_summaries(db: AsyncSession, user_org_id: int) -> dict:
    """获取各组织的方案统计（卡片展示用）—— user_org_id 用于标记当前所属组织"""
    # 找到所有方案模板 ID
    tpl_sub = select(FlowTemplate.id).where(FlowTemplate.type == "proposal")

    # 关联查询：按组织分组统计
    stmt = (
        select(
            FlowInstance.organization_id,
            Organization.name.label("org_name"),
            func.count(FlowInstance.id).label("total"),
            func.sum(case((FlowInstance.status == "running", 1), else_=0)).label("running"),
            func.sum(case((FlowInstance.status == "completed", 1), else_=0)).label("completed"),
            func.sum(case((FlowInstance.status == "terminated", 1), else_=0)).label("terminated"),
            func.max(FlowInstance.updated_at).label("latest_update"),
        )
        .join(Organization, FlowInstance.organization_id == Organization.id)
        .where(FlowInstance.template_id.in_(tpl_sub))
        .group_by(FlowInstance.organization_id, Organization.name)
        .order_by(FlowInstance.organization_id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    organizations = [
        {
            "id": row.organization_id,
            "name": row.org_name,
            "total_count": row.total,
            "running_count": int(row.running or 0),
            "completed_count": int(row.completed or 0),
            "terminated_count": int(row.terminated or 0),
            "latest_update_time": row.latest_update.isoformat() if row.latest_update else None,
            "is_current_user_org": row.organization_id == user_org_id,  # 标记当前用户所属组织
        }
        for row in rows
    ]
    return {"organizations": organizations}


async def list_proposals(
    db: AsyncSession,
    *,
    organization_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """方案列表 —— 返回所有 type=proposal 模板创建的实例"""
    # 找到所有方案模板 ID
    proposal_tpl_ids_sub = select(FlowTemplate.id).where(FlowTemplate.type == "proposal")
    if organization_id:
        proposal_tpl_ids_sub = proposal_tpl_ids_sub.where(FlowTemplate.organization_id == organization_id)

    conditions = [FlowInstance.template_id.in_(proposal_tpl_ids_sub)]
    if status:
        conditions.append(FlowInstance.status == status)
    if keyword:
        conditions.append(FlowInstance.name.like(f"%{keyword}%"))

    base_stmt = select(FlowInstance).where(*conditions)
    count_stmt = select(func.count()).select_from(FlowInstance).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = base_stmt.order_by(FlowInstance.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    instances = result.scalars().all()

    # 批量查发起人 + 组织名
    initiator_ids = list(set(inst.initiator_id for inst in instances))
    users_map: dict[int, str] = {}
    if initiator_ids:
        users_result = await db.execute(select(User).where(User.id.in_(initiator_ids)))
        users_map = {u.id: u.real_name for u in users_result.scalars().all()}

    org_ids = list(set(inst.organization_id for inst in instances))
    orgs_map: dict[int, str] = {}
    if org_ids:
        orgs_result = await db.execute(select(Organization).where(Organization.id.in_(org_ids)))
        orgs_map = {o.id: o.name for o in orgs_result.scalars().all()}

    items = [
        ProposalListItem(
            id=inst.id,
            name=inst.name,
            description=inst.description,
            organization_id=inst.organization_id,
            organization_name=orgs_map.get(inst.organization_id, ""),
            initiator_id=inst.initiator_id,
            initiator_name=users_map.get(inst.initiator_id, ""),
            status=inst.status,
            created_at=inst.created_at,
        )
        for inst in instances
    ]
    return PaginatedData(items=items, total=total, page=page, page_size=page_size)
