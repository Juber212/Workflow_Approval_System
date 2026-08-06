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
from app.services.validation_service import extract_person_ids, validate_user_ids_exist
from app.services.instance._helpers import compute_deadline_info, _batch_get_active_deadlines, _batch_get_flow_deadlines


# 方案内置模板固定名称
BUILTIN_PROPOSAL_TEMPLATE_NAME = "方案默认模板"


async def ensure_proposal_template(db: AsyncSession, org_id: int, user_id: int) -> FlowTemplate:
    """获取或创建组织的方案默认模板（每个组织一个）

    M10 修复：原 SELECT ... FOR UPDATE 在 READ COMMITTED 隔离级别下对「无匹配行」
    不产生 gap lock，两个并发请求会同时看到无模板并各自创建重复模板。
    改用 MySQL GET_LOCK 命名锁串行化「查-建」段（GET_LOCK 绑定当前连接，
    与事务同连接，READ COMMITTED 下可靠；10 秒等待超时）。
    """
    from sqlalchemy import text

    lock_name = f"proposal_default_tpl:org{org_id}"
    await db.execute(text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name})
    try:
        # 锁内复查——前一请求可能已创建成功
        existing = (await db.execute(
            select(FlowTemplate).where(
                FlowTemplate.organization_id == org_id,
                FlowTemplate.type == "proposal",
            )
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
        # 锁内提交（低危项）：GET_LOCK 绑定当前连接、事务 commit 不会释放锁；
        # 必须在 RELEASE_LOCK 之前完成事务，否则后到请求获锁复查看不到未提交的模板
        # → 重复创建撞 (organization_id, type) 唯一索引返回 500。
        await db.commit()
        return tpl
    finally:
        await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})


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

    # M11：人员 ID 存在性校验 + 审批人非空（对齐项目发起 create.py P1-22）——
    # 无效 designer_id/approver_id 会写进节点并在流程中途触发外键 500；空审批人致 waiting_approval 卡死
    person_ids: set[int] = {body.designer_id} if body.designer_id else set()
    person_ids |= extract_person_ids(body.approvers)
    missing = await validate_user_ids_exist(db, person_ids)
    if missing:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            f"以下用户不存在或已停用，请重新选择：{'、'.join(map(str, sorted(missing)))}",
        )
    if not extract_person_ids(body.approvers):
        raise AppException(ErrorCode.VALIDATION_ERROR, "请至少选择一位审批人")

    # 确保方案模板存在
    tpl = await ensure_proposal_template(db, body.organization_id, current_user.id)

    # 读取模板节点
    tpl_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == tpl.id).order_by(TemplateNode.sort_order)
    )).scalars().all()

    # 方案名称校验：禁止路径遍历字符
    proposal_name = body.name.strip()
    _illegal_chars = {"../", "..\\", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"}
    if not proposal_name or any(c in proposal_name for c in _illegal_chars):
        raise AppException(
            ErrorCode.BAD_REQUEST,
            f"方案名称不能为空或包含特殊字符（{' '.join(sorted(_illegal_chars))}）",
        )

    # M14：同组织同名方案禁止创建——归档目录按「类型/实例名」隔离，
    # 同名会共享目录，永久删除一方案时会误删另一方案的全部文件
    dup = (await db.execute(
        select(FlowInstance.id).where(
            FlowInstance.name == proposal_name,
            FlowInstance.organization_id == body.organization_id,
            FlowInstance.template_type == "proposal",
        )
    )).first()
    if dup:
        raise AppException(ErrorCode.BAD_REQUEST, "该组织下已存在同名方案，请更换名称")

    # 创建方案实例
    instance = FlowInstance(
        name=proposal_name,
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
    # M15：改用实例快照 template_type 口径（不依赖方案模板是否仍存在，与 list_proposals 一致）
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
        .where(FlowInstance.template_type == "proposal")
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
    priority: str | None = None,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    initiator_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """方案列表 —— 返回所有 template_type=proposal 的实例（不依赖模板是否存在）"""
    conditions = [FlowInstance.template_type == "proposal"]
    if organization_id:
        conditions.append(FlowInstance.organization_id == organization_id)
    if status:
        conditions.append(FlowInstance.status == status)
    if priority:
        conditions.append(FlowInstance.priority == priority)
    if keyword:
        conditions.append(FlowInstance.name.like(f"%{keyword}%"))
    if date_from:
        conditions.append(FlowInstance.created_at >= date_from)
    if date_to:
        conditions.append(FlowInstance.created_at <= f"{date_to} 23:59:59")
    if initiator_id is not None:
        conditions.append(FlowInstance.initiator_id == initiator_id)

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

    # 批量查活跃节点截止时间（专用 helper）
    inst_ids = [inst.id for inst in instances]
    deadline_map = await _batch_get_active_deadlines(db, inst_ids) if inst_ids else {}
    flow_deadline_map = await _batch_get_flow_deadlines(db, inst_ids) if inst_ids else {}

    items = []
    for inst in instances:
        d = deadline_map.get(inst.id)
        is_overdue, days_remaining = compute_deadline_info(d)
        fd = flow_deadline_map.get(inst.id)
        items.append(ProposalListItem(
            id=inst.id,
            name=inst.name,
            description=inst.description,
            organization_id=inst.organization_id,
            organization_name=orgs_map.get(inst.organization_id, ""),
            initiator_id=inst.initiator_id,
            initiator_name=users_map.get(inst.initiator_id, ""),
            status=inst.status,
            deadline=d.isoformat() if d else None,
            flow_deadline=fd.isoformat() if fd else None,
            is_overdue=is_overdue,
            days_remaining=days_remaining,
            created_at=inst.created_at,
        ))
    return PaginatedData(items=items, total=total, page=page, page_size=page_size)
