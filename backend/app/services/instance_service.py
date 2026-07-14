"""流程实例服务 —— 发起实例、配置合并、快照复制、列表查询"""

from datetime import datetime

from sqlalchemy import select, func, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate,
    FlowVersion,
    FlowInstance,
    InstanceNode,
    InstanceEdge,
    OperationLog,
    User,
    Organization,
    Task,
    CheckRecord,
    Approval,
    File,
)
from app.schemas.instance import (
    CreateInstanceRequest,
    InstanceListItem,
    DetailNodeInfo,
    NodeFileBrief,
    CheckRecordBrief,
    ApprovalBrief,
    LogItemBrief,
)
from app.api.deps import CurrentUser
from app.engine.flow_engine import (
    calculate_incoming_counts,
    activate_start_node,
    propagate_from_node,
)


async def create_instance(
    db: AsyncSession,
    request: CreateInstanceRequest,
    current_user: CurrentUser,
) -> dict:
    """发起流程实例 —— 完整初始化逻辑

    步骤：
    1. 验证模板存在且已发布
    2. 验证版本存在且属于该模板
    3. 创建 FlowInstance 记录（status=created）
    4. 从版本快照复制节点 → instance_nodes
    5. 合并配置：快照默认值 → 软覆盖(soft_config_overrides) → 发起覆盖(node_overrides)
    6. 从版本快照复制连线 → instance_edges
    7. 计算每个节点的 incoming_count
    8. 开始节点自动 finished
    9. 激活下游第一个工作节点 → running + 生成 Task
    10. 实例状态 → running
    11. 记录操作日志
    """

    # ========== 1. 验证模板 ==========
    tpl_result = await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == request.template_id)
    )
    tpl = tpl_result.scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.status != "published":
        raise AppException(ErrorCode.FORBIDDEN, "仅已发布状态的模板可发起流程实例")

    # ========== 2. 验证版本归属 ==========
    version_result = await db.execute(
        select(FlowVersion).where(
            FlowVersion.id == request.version_id,
            FlowVersion.template_id == request.template_id,
        )
    )
    version = version_result.scalar_one_or_none()
    if version is None:
        raise AppException(ErrorCode.NOT_FOUND, "版本不存在或不属于该模板")

    nodes_snapshot: list[dict] = version.nodes_snapshot if isinstance(version.nodes_snapshot, list) else []
    edges_snapshot: list[dict] = version.edges_snapshot if isinstance(version.edges_snapshot, list) else []

    if not nodes_snapshot:
        raise AppException(ErrorCode.VALIDATION_ERROR, "版本快照中没有节点数据，无法发起实例")

    # ========== 3. 构建覆盖查找表 ==========
    # 发起覆盖：按 node_id（模板快照中的 id）索引
    override_map: dict[int, dict] = {}
    if request.node_overrides:
        for override in request.node_overrides:
            override_map[override.node_id] = override.model_dump(
                exclude_none=True, exclude={"node_id"}
            )

    # 软配置覆盖：{ "node_id_str": { field: value } }
    soft_overrides: dict[str, dict] = version.soft_config_overrides or {}

    # ========== 4. 创建 FlowInstance ==========
    priority = request.priority
    if priority not in ("urgent", "high", "normal", "low"):
        priority = "normal"

    instance = FlowInstance(
        name=request.name.strip(),
        description=request.description,
        template_id=request.template_id,
        version_id=request.version_id,
        organization_id=tpl.organization_id,
        initiator_id=current_user.id,
        priority=priority,
        status="created",
    )
    db.add(instance)
    await db.flush()  # 获取 instance.id

    # ========== 5. 复制节点（合并配置） ==========
    node_id_map: dict[int, int] = {}  # template_node_id → instance_node_id
    instance_nodes: list[InstanceNode] = []

    for sn in nodes_snapshot:
        sn_id: int = sn["id"]  # 模板节点 ID（快照中的原始 id）

        # 获取软配置覆盖
        node_soft: dict = soft_overrides.get(str(sn_id), {})

        # 获取发起覆盖
        node_override: dict = override_map.get(sn_id, {})

        # 校验 skip 权限：仅 is_optional=1 的节点可跳过
        is_skipped = bool(node_override.get("skip"))
        if is_skipped and not sn.get("is_optional"):
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                f"节点「{sn['name']}」不是可选节点，不能跳过",
            )
        # 开始/结束节点不能被跳过（即使前端没传，后端也兜底校验）
        if is_skipped and (sn.get("is_start") or sn.get("is_end")):
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                f"开始/结束节点不能被跳过",
            )

        # 配置合并优先级：发起覆盖 > 软覆盖 > 快照默认值
        assignee_id = node_override.get("assignee_id") or node_soft.get("assignee_id") or sn.get("assignee_id")
        time_limit_days = node_override.get("time_limit_days") or node_soft.get("time_limit_days") or sn.get("time_limit_days")
        approvers = node_override.get("approvers") or node_soft.get("approvers") or sn.get("approvers")
        checkers = node_override.get("checkers") or node_soft.get("checkers") or sn.get("checkers")

        # deadline 优先使用发起覆盖中的日期，否则在节点激活时根据 time_limit_days 计算
        deadline = None
        if node_override.get("deadline"):
            try:
                deadline = datetime.fromisoformat(node_override["deadline"])
            except (ValueError, TypeError):
                raise AppException(
                    ErrorCode.VALIDATION_ERROR,
                    f"节点「{sn['name']}」的截止日期格式不正确",
                )

        inode = InstanceNode(
            instance_id=instance.id,
            name=sn["name"],
            description=sn.get("description"),
            is_start=sn.get("is_start", False),
            is_end=sn.get("is_end", False),
            assignee_id=assignee_id,
            time_limit_days=time_limit_days,
            deadline=deadline,
            require_file=sn.get("require_file", False),
            approvers=approvers,
            checkers=checkers,
            approval_strategy=sn.get("approval_strategy", "all_approve"),
            is_optional=sn.get("is_optional", False),
            is_skipped=is_skipped,
            status="waiting",  # 初始状态，后续激活
            sort_order=sn.get("sort_order", 0),
        )
        db.add(inode)
        await db.flush()
        node_id_map[sn_id] = inode.id
        instance_nodes.append(inode)

    # ========== 6. 复制连线（映射模板节点 ID → 实例节点 ID） ==========
    for se in edges_snapshot:
        source_instance_id = node_id_map.get(se["source_node_id"])
        target_instance_id = node_id_map.get(se["target_node_id"])
        if source_instance_id and target_instance_id:
            edge = InstanceEdge(
                instance_id=instance.id,
                source_node_id=source_instance_id,
                target_node_id=target_instance_id,
            )
            db.add(edge)

    await db.flush()

    # ========== 7. 计算 incoming_count ==========
    await calculate_incoming_counts(db, instance.id)

    # ========== 8. 开始节点自动 finished ==========
    await activate_start_node(db, instance.id)

    # ========== 9. 激活开始节点的下游（第一个工作节点） ==========
    start_node = next((n for n in instance_nodes if n.is_start), None)
    if start_node:
        await propagate_from_node(db, instance.id, start_node.id)

    # ========== 10. 实例状态 → running ==========
    instance.status = "running"
    instance.initiated_at = datetime.now()

    # ========== 11. 记录操作日志 ==========
    log = OperationLog(
        instance_id=instance.id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="initiate",
        description=f"发起了流程实例「{instance.name}」",
        detail={
            "template_id": request.template_id,
            "version_id": request.version_id,
            "priority": priority,
            "node_count": len(instance_nodes),
            "skipped_count": sum(1 for n in instance_nodes if n.is_skipped),
        },
    )
    db.add(log)
    await db.flush()

    return {
        "id": instance.id,
        "name": instance.name,
        "template_id": instance.template_id,
        "version_id": instance.version_id,
        "organization_id": instance.organization_id,
        "initiator_id": instance.initiator_id,
        "priority": instance.priority,
        "status": instance.status,
        "nodes": [
            {
                "id": n.id,
                "name": n.name,
                "is_start": n.is_start,
                "is_end": n.is_end,
                "is_skipped": n.is_skipped,
                "status": n.status,
                "sort_order": n.sort_order,
            }
            for n in instance_nodes
        ],
        "initiated_at": instance.initiated_at,
    }


async def list_instances(
    db: AsyncSession,
    *,
    organization_id: int | None = None,
    status: list[str] | None = None,
    priority: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询流程实例列表（分页 + 多条件筛选）

    返回每个实例的：
    - current_node_index: 已完成/跳过节点数（反映当前进度）
    - total_nodes: 总节点数
    - current_assignee_name: 当前活跃节点的负责人姓名
    """

    # ========== 基础查询（联表获取名称字段） ==========
    Initiator = aliased(User)
    Org = aliased(Organization)

    base_stmt = (
        select(
            FlowInstance,
            Initiator.real_name.label("initiator_name"),
            Org.name.label("organization_name"),
            FlowTemplate.name.label("template_name"),
        )
        .join(Initiator, FlowInstance.initiator_id == Initiator.id)
        .join(Org, FlowInstance.organization_id == Org.id)
        .outerjoin(FlowTemplate, FlowInstance.template_id == FlowTemplate.id)
    )

    # ========== 筛选条件 ==========
    if organization_id is not None:
        base_stmt = base_stmt.where(FlowInstance.organization_id == organization_id)

    if status:
        # 多选：status=running,completed
        base_stmt = base_stmt.where(FlowInstance.status.in_(status))

    if priority:
        base_stmt = base_stmt.where(FlowInstance.priority == priority)

    if keyword:
        # 模糊搜索实例名称
        base_stmt = base_stmt.where(FlowInstance.name.like(f"%{keyword}%"))

    # ========== 总数 ==========
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # ========== 排序 + 分页 ==========
    list_stmt = base_stmt.order_by(FlowInstance.id.desc())
    list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(list_stmt)
    rows = result.all()

    # ========== 组装结果 ==========
    items: list[InstanceListItem] = []
    for row in rows:
        instance = row[0]  # FlowInstance 对象（元组第一项）
        initiator_name = row[1]
        org_name = row[2]
        template_name = row[3]

        # 批量查询节点数据（为每个实例单独查 — 后续可优化为批量查询）
        node_stats = await _get_instance_node_stats(db, instance.id)
        current_assignee = await _get_current_assignee_name(db, instance.id)

        items.append(InstanceListItem(
            id=instance.id,
            name=instance.name,
            template_id=instance.template_id,
            template_name=template_name or "",
            organization_id=instance.organization_id,
            organization_name=org_name or "",
            initiator_id=instance.initiator_id,
            initiator_name=initiator_name or "",
            priority=(instance.priority or "normal").lower(),
            status=(instance.status or "created").lower(),
            archive_status=(instance.archive_status or "").lower() if instance.archive_status else None,
            current_node_index=node_stats["processed"],
            total_nodes=node_stats["total"],
            current_assignee_name=current_assignee,
            initiated_at=instance.initiated_at,
            completed_at=instance.completed_at,
            terminated_at=instance.terminated_at,
        ))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def _get_instance_node_stats(db: AsyncSession, instance_id: int) -> dict:
    """获取实例节点统计：总节点数、已完成/跳过节点数（大小写不敏感）"""
    stmt = select(
        func.count(InstanceNode.id).label("total"),
        func.sum(
            func.if_(
                func.lower(InstanceNode.status).in_(["finished", "skipped"]), 1, 0
            )
        ).label("processed"),
    ).where(InstanceNode.instance_id == instance_id)

    result = await db.execute(stmt)
    row = result.first()
    return {
        "total": int(row.total) if row and row.total else 0,
        "processed": int(row.processed) if row and row.processed else 0,
    }


async def _get_current_assignee_name(db: AsyncSession, instance_id: int) -> str | None:
    """获取当前活跃节点（running）的负责人姓名"""
    stmt = (
        select(User.real_name)
        .join(InstanceNode, InstanceNode.assignee_id == User.id)
        .where(
            InstanceNode.instance_id == instance_id,
            InstanceNode.status == "running",
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar()


# ==================== 实例详情 ====================


async def get_instance_detail(db: AsyncSession, instance_id: int) -> dict:
    """查询实例完整详情 —— 基础信息 + 节点列表（含文件/校验/审批/日志） + 操作日志分页

    Args:
        db: 异步数据库会话
        instance_id: 实例 ID

    Returns:
        完整实例详情字典，含嵌套节点信息
    """
    # ========== 1. 查询实例基本信息（联表获取名称） ==========
    stmt = (
        select(
            FlowInstance,
            User.real_name.label("initiator_name"),
            Organization.name.label("organization_name"),
            FlowTemplate.name.label("template_name"),
            FlowVersion.version_number,
        )
        .join(User, FlowInstance.initiator_id == User.id)
        .join(Organization, FlowInstance.organization_id == Organization.id)
        .outerjoin(FlowTemplate, FlowInstance.template_id == FlowTemplate.id)
        .outerjoin(FlowVersion, FlowInstance.version_id == FlowVersion.id)
        .where(FlowInstance.id == instance_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        from app.core.exceptions import AppException
        from app.core.error_codes import ErrorCode
        raise AppException(ErrorCode.NOT_FOUND, "流程实例不存在")

    instance = row[0]
    initiator_name = row[1]
    org_name = row[2]
    template_name = row[3]
    version_number = row[4]

    # ========== 2. 查询所有节点（按 sort_order 排序） ==========
    nodes_stmt = (
        select(InstanceNode)
        .where(InstanceNode.instance_id == instance_id)
        .order_by(InstanceNode.sort_order)
    )
    nodes_result = await db.execute(nodes_stmt)
    node_models = nodes_result.scalars().all()

    # 获取节点相关人员名称（批量查询，避免 N+1）
    user_ids: set[int | None] = set()
    for n in node_models:
        if n.assignee_id:
            user_ids.add(n.assignee_id)
    user_ids.discard(None)

    user_name_map: dict[int, str] = {}
    if user_ids:
        users_stmt = select(User.id, User.real_name).where(User.id.in_(list(user_ids)))
        users_result = await db.execute(users_stmt)
        for uid, uname in users_result:
            user_name_map[uid] = uname

    # ========== 3. 节点统计 ==========
    total_nodes = len(node_models)
    processed_count = sum(
        1 for n in node_models
        if (n.status or "").lower() in ("finished", "skipped")
    )

    # ========== 4. 批量查询各节点的文件/校验/审批 ==========
    node_ids = [n.id for n in node_models]

    # 文件（按 node_id 分组）
    files_by_node: dict[int, list] = {}
    if node_ids:
        files_stmt = (
            select(File, User.real_name.label("uploader_name"))
            .join(User, File.uploader_id == User.id)
            .where(File.node_id.in_(node_ids))
            .order_by(File.created_at)
        )
        files_result = await db.execute(files_stmt)
        for f, u_name in files_result:
            if f.node_id not in files_by_node:
                files_by_node[f.node_id] = []
            files_by_node[f.node_id].append(
                NodeFileBrief(
                    id=f.id,
                    original_name=f.original_name,
                    file_size=f.file_size,
                    uploader_id=f.uploader_id,
                    uploader_name=u_name or "",
                    upload_type=(f.upload_type or "normal").lower(),
                    round=f.round,
                    created_at=f.created_at,
                )
            )

    # 校验记录（按 node_id 分组）
    checks_by_node: dict[int, list] = {}
    if node_ids:
        checks_stmt = (
            select(CheckRecord, User.real_name.label("checker_name"))
            .join(User, CheckRecord.checker_id == User.id)
            .where(CheckRecord.node_id.in_(node_ids))
            .order_by(CheckRecord.created_at)
        )
        checks_result = await db.execute(checks_stmt)
        for c, c_name in checks_result:
            if c.node_id not in checks_by_node:
                checks_by_node[c.node_id] = []
            checks_by_node[c.node_id].append(
                CheckRecordBrief(
                    id=c.id,
                    checker_id=c.checker_id,
                    checker_name=c_name or "",
                    status=(c.status or "pending").lower(),
                    opinion=c.opinion,
                    decided_at=c.decided_at,
                )
            )

    # 审批记录（按 node_id 分组）
    approvals_by_node: dict[int, list] = {}
    if node_ids:
        approvals_stmt = (
            select(Approval, User.real_name.label("approver_name"))
            .join(User, Approval.approver_id == User.id)
            .where(Approval.node_id.in_(node_ids))
            .order_by(Approval.created_at)
        )
        approvals_result = await db.execute(approvals_stmt)
        for a, a_name in approvals_result:
            if a.node_id not in approvals_by_node:
                approvals_by_node[a.node_id] = []
            approvals_by_node[a.node_id].append(
                ApprovalBrief(
                    id=a.id,
                    approver_id=a.approver_id,
                    approver_name=a_name or "",
                    status=(a.status or "pending").lower(),
                    opinion=a.opinion,
                    signature_applied=a.signature_applied,
                    decided_at=a.decided_at,
                )
            )

    # ========== 5. 组装节点列表 ==========
    nodes: list[DetailNodeInfo] = []
    for n in node_models:
        # 标准化 checkers/approvers 为 dict 列表格式
        def _normalize_personnel(raw: list | None) -> list[dict] | None:
            """将 [1, 2] 转为 [{\"user_id\": 1}, {\"user_id\": 2}]，已是正确格式则不变"""
            if raw is None:
                return None
            result = []
            for item in raw:
                if isinstance(item, dict):
                    result.append(item)
                elif isinstance(item, int):
                    result.append({"user_id": item})
            return result if result else None

        nodes.append(DetailNodeInfo(
            id=n.id,
            name=n.name,
            is_start=n.is_start,
            is_end=n.is_end,
            is_optional=n.is_optional,
            is_skipped=n.is_skipped,
            status=(n.status or "waiting").lower(),
            sort_order=n.sort_order,
            round=n.round,
            assignee_id=n.assignee_id,
            assignee_name=user_name_map.get(n.assignee_id) if n.assignee_id else None,
            deadline=n.deadline,
            time_limit_days=n.time_limit_days,
            checkers=_normalize_personnel(n.checkers),
            approvers=_normalize_personnel(n.approvers),
            require_file=n.require_file,
            approval_strategy=n.approval_strategy,
            started_at=n.started_at,
            completed_at=n.completed_at,
            files=files_by_node.get(n.id, []),
            checks=checks_by_node.get(n.id, []),
            approvals=approvals_by_node.get(n.id, []),
        ))

    # ========== 6. 操作日志（前 50 条，后续可做分页） ==========
    logs_stmt = (
        select(OperationLog, User.real_name.label("operator_name"))
        .outerjoin(User, OperationLog.operator_id == User.id)
        .where(OperationLog.instance_id == instance_id)
        .order_by(OperationLog.created_at.desc())
        .limit(50)
    )
    logs_result = await db.execute(logs_stmt)
    log_items: list[dict] = []
    for log, op_name in logs_result:
        log_items.append({
            "id": log.id,
            "operator_type": (log.operator_type or "user").lower(),
            "operator_id": log.operator_id,
            "operator_name": op_name,
            "node_id": log.node_id,
            "operation_type": log.operation_type,
            "round": log.round,
            "description": log.description,
            "detail": log.detail,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    # ========== 7. 组装最终结果 ==========
    return {
        "id": instance.id,
        "name": instance.name,
        "description": instance.description,
        "template_id": instance.template_id,
        "template_name": template_name or "",
        "version_id": instance.version_id,
        "version_number": version_number,
        "organization_id": instance.organization_id,
        "organization_name": org_name or "",
        "initiator_id": instance.initiator_id,
        "initiator_name": initiator_name or "",
        "priority": (instance.priority or "normal").lower(),
        "status": (instance.status or "created").lower(),
        "archive_status": (instance.archive_status or "").lower() if instance.archive_status else None,
        "termination_reason": instance.termination_reason,
        "current_node_index": processed_count,
        "total_nodes": total_nodes,
        "initiated_at": instance.initiated_at,
        "completed_at": instance.completed_at,
        "terminated_at": instance.terminated_at,
        "nodes": nodes,
        "logs": {
            "items": log_items,
            "total": len(log_items),
        },
    }
