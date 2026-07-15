"""流程实例服务 —— 发起实例、配置合并、快照复制、列表查询、终止流程"""

import os
from datetime import datetime

from sqlalchemy import select, func, text, or_, delete as sql_delete, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge,
    OperationLog, User, Organization,
    Task, CheckRecord, Approval, File,
)
from app.schemas.instance import (
    CreateInstanceRequest,
    InstanceListItem,
    DetailNodeInfo,
    NodeFileBrief,
    CheckRecordBrief,
    ApprovalBrief,
    LogItemBrief,
    ChangePersonnelRequest,
    ChangePriorityRequest,
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
    """发起流程实例 —— 从模板节点/连线直接复制生成实例快照

    步骤：
    1. 验证模板存在
    2. 从模板节点复制 → instance_nodes（合并 node_overrides）
    3. 从模板连线复制 → instance_edges
    4. 计算 incoming_count + 激活开始节点 + 首个工作节点
    5. 实例状态 → running + 记录日志
    """

    # ========== 1. 验证模板 ==========
    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == request.template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    # ========== 2. 读取模板节点和连线 ==========
    tpl_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == request.template_id).order_by(TemplateNode.sort_order)
    )).scalars().all()

    tpl_edges = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == request.template_id)
    )).scalars().all()

    if not tpl_nodes:
        raise AppException(ErrorCode.VALIDATION_ERROR, "模板没有节点数据，无法发起实例")

    # ========== 3. 构建覆盖查找表 ==========
    override_map: dict[int, dict] = {}
    if request.node_overrides:
        for override in request.node_overrides:
            override_map[override.node_id] = override.model_dump(
                exclude_none=True, exclude={"node_id"}
            )

    # ========== 4. 创建 FlowInstance ==========
    priority = request.priority
    if priority not in ("urgent", "high", "normal", "low"):
        priority = "normal"

    instance = FlowInstance(
        name=request.name.strip(),
        description=request.description,
        template_id=request.template_id,
        template_name=tpl.name,
        organization_id=tpl.organization_id,
        initiator_id=current_user.id,
        priority=priority,
        status="created",
    )
    db.add(instance)
    await db.flush()

    # ========== 5. 复制节点（合并 node_overrides） ==========
    node_id_map: dict[int, int] = {}  # template_node_id → instance_node_id
    instance_nodes: list[InstanceNode] = []

    for tn in tpl_nodes:
        node_override: dict = override_map.get(tn.id, {})

        # 校验 skip 权限
        is_skipped = bool(node_override.get("skip"))
        if is_skipped and not tn.is_optional:
            raise AppException(ErrorCode.VALIDATION_ERROR, f"节点「{tn.name}」不是可选节点，不能跳过")
        if is_skipped and (tn.is_start or tn.is_end):
            raise AppException(ErrorCode.VALIDATION_ERROR, "开始/结束节点不能被跳过")

        # 配置合并：发起覆盖 > 模板默认值
        assignee_id = node_override.get("assignee_id") or tn.assignee_id
        time_limit_days = node_override.get("time_limit_days") or tn.time_limit_days
        approvers = node_override.get("approvers") or tn.approvers
        checkers = node_override.get("checkers") or tn.checkers

        # 结束节点：审批人默认设为发起人（发起人终审）
        if tn.is_end and not approvers:
            approvers = [{"user_id": current_user.id}]

        deadline = None
        if node_override.get("deadline"):
            try:
                deadline = datetime.fromisoformat(node_override["deadline"])
            except (ValueError, TypeError):
                raise AppException(ErrorCode.VALIDATION_ERROR, f"节点「{tn.name}」的截止日期格式不正确")

        inode = InstanceNode(
            instance_id=instance.id,
            name=tn.name,
            is_start=tn.is_start,
            is_end=tn.is_end,
            assignee_id=assignee_id,
            time_limit_days=time_limit_days,
            deadline=deadline,
            require_file=tn.require_file,
            approvers=approvers,
            checkers=checkers,
            approval_strategy=tn.approval_strategy,
            is_optional=tn.is_optional,
            is_skipped=is_skipped,
            status="waiting",
            sort_order=tn.sort_order,
        )
        db.add(inode)
        await db.flush()
        node_id_map[tn.id] = inode.id
        instance_nodes.append(inode)

    # ========== 6. 复制连线 ==========
    for te in tpl_edges:
        src = node_id_map.get(te.source_node_id)
        tgt = node_id_map.get(te.target_node_id)
        if src and tgt:
            db.add(InstanceEdge(instance_id=instance.id, source_node_id=src, target_node_id=tgt))

    await db.flush()

    # ========== 7. 计算 incoming_count + 激活 ==========
    await calculate_incoming_counts(db, instance.id)
    await activate_start_node(db, instance.id)

    start_node = next((n for n in instance_nodes if n.is_start), None)
    if start_node:
        await propagate_from_node(db, instance.id, start_node.id)

    # ========== 8. 实例状态 → running ==========
    instance.status = "running"
    instance.initiated_at = datetime.now()

    # ========== 9. 记录操作日志 ==========
    db.add(OperationLog(
        instance_id=instance.id,
        operator_type="user", operator_id=current_user.id,
        operation_type="initiate",
        description=f"发起了流程实例「{instance.name}」",
        detail={
            "template_id": request.template_id,
            "priority": priority,
            "node_count": len(instance_nodes),
            "skipped_count": sum(1 for n in instance_nodes if n.is_skipped),
        },
    ))
    await db.flush()

    return {
        "id": instance.id, "name": instance.name,
        "organization_id": instance.organization_id,
        "initiator_id": instance.initiator_id,
        "priority": instance.priority, "status": instance.status,
        "nodes": [
            {"id": n.id, "name": n.name, "is_start": n.is_start, "is_end": n.is_end,
             "is_skipped": n.is_skipped, "status": n.status, "sort_order": n.sort_order}
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

    # ========== 基础查询（联表获取名称字段；template_name 已冗余在实例表） ==========
    Initiator = aliased(User)
    Org = aliased(Organization)

    base_stmt = (
        select(
            FlowInstance,
            Initiator.real_name.label("initiator_name"),
            Org.name.label("organization_name"),
        )
        .join(Initiator, FlowInstance.initiator_id == Initiator.id)
        .join(Org, FlowInstance.organization_id == Org.id)
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

        # 批量查询节点数据（为每个实例单独查 — 后续可优化为批量查询）
        node_stats = await _get_instance_node_stats(db, instance.id)
        current_assignee = await _get_current_assignee_name(db, instance.id)

        items.append(InstanceListItem(
            id=instance.id,
            name=instance.name,
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
    """查询实例完整详情 —— 基础信息 + 节点列表（含文件/校验/审批/日志）

    Args:
        db: 异步数据库会话
        instance_id: 实例 ID

    Returns:
        完整实例详情字典，含嵌套节点信息
    """
    # ========== 1. 查询实例基本信息（template_name 已冗余在实例表，无需 JOIN） ==========
    stmt = (
        select(
            FlowInstance,
            User.real_name.label("initiator_name"),
            Organization.name.label("organization_name"),
        )
        .join(User, FlowInstance.initiator_id == User.id)
        .join(Organization, FlowInstance.organization_id == Organization.id)
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

    # ========== 2. 查询所有节点（按 sort_order 排序） ==========
    nodes_stmt = (
        select(InstanceNode)
        .where(InstanceNode.instance_id == instance_id)
        .order_by(InstanceNode.sort_order)
    )
    nodes_result = await db.execute(nodes_stmt)
    node_models = nodes_result.scalars().all()

    # 获取节点相关人员名称（批量查询，避免 N+1）
    # 收集负责人 ID + 校验人/审批人 ID
    user_ids: set[int] = set()
    for n in node_models:
        if n.assignee_id:
            user_ids.add(n.assignee_id)
        # 从 checkers/approvers JSON 中提取 user_id
        for raw in (n.checkers, n.approvers):
            if raw and isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and item.get("user_id"):
                        user_ids.add(item["user_id"])
                    elif isinstance(item, int):
                        user_ids.add(item)

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
        def _normalize_personnel(raw: list | None, name_map: dict[int, str]) -> list[dict] | None:
            """标准化人员列表并补全 user_name —— [1,2] → [{"user_id":1,"user_name":"张三"}]"""
            if raw is None:
                return None
            result = []
            for item in raw:
                if isinstance(item, dict):
                    uid = item.get("user_id")
                    result.append({
                        "user_id": uid,
                        "user_name": name_map.get(uid) if uid else None,
                    })
                elif isinstance(item, int):
                    result.append({
                        "user_id": item,
                        "user_name": name_map.get(item),
                    })
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
            checkers=_normalize_personnel(n.checkers, user_name_map),
            approvers=_normalize_personnel(n.approvers, user_name_map),
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
        "id": instance.id, "name": instance.name, "description": instance.description,
        "organization_id": instance.organization_id, "organization_name": org_name or "",
        "initiator_id": instance.initiator_id, "initiator_name": initiator_name or "",
        "priority": (instance.priority or "normal").lower(),
        "status": (instance.status or "created").lower(),
        "archive_status": (instance.archive_status or "").lower() if instance.archive_status else None,
        "termination_reason": instance.termination_reason,
        "current_node_index": processed_count, "total_nodes": total_nodes,
        "initiated_at": instance.initiated_at,
        "completed_at": instance.completed_at,
        "terminated_at": instance.terminated_at,
        "nodes": nodes,
        "logs": {"items": log_items, "total": len(log_items)},
    }


async def terminate_instance(
    db: AsyncSession,
    instance_id: int,
    reason: str,
    current_user: CurrentUser,
) -> dict:
    """终止流程实例 —— 级联关闭所有关联记录并物理删除文件

    处理步骤：
    1. 校验实例存在 + 发起人权限 + 未已终止
    2. 物理删除磁盘文件 + 删除 files 记录
    3. 级联关闭：非终态 node/task → terminated, pending check/approval → terminated
    4. 更新实例状态为 terminated
    5. 记录操作日志
    """
    # ========== 1. 查询实例 ==========
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id)
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()

    if not instance:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")

    # ========== 2. 校验发起人权限 ==========
    if instance.initiator_id != current_user.id:
        raise AppException(ErrorCode.NOT_INITIATOR, "仅发起人可终止流程")

    # ========== 3. 校验未已终止 ==========
    if (instance.status or "").lower() == "terminated":
        raise AppException(ErrorCode.INSTANCE_ALREADY_TERMINATED, "流程已终止，不可重复操作")

    now = datetime.now()

    # ========== 4. 物理删除文件 + 删除 files 记录 ==========
    file_stmt = select(File).where(File.instance_id == instance_id)
    file_result = await db.execute(file_stmt)
    files = file_result.scalars().all()

    # 逐个物理删除磁盘文件
    for f in files:
        if f.file_path:
            # 存储路径：STORAGE_ROOT / file_path
            full_path = os.path.join(settings.STORAGE_ROOT, f.file_path)
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
            except OSError:
                # 文件不存在或无权删除，不阻断流程
                pass

    # 删除文件记录（物理删除，非软删除）
    if files:
        await db.execute(sql_delete(File).where(File.instance_id == instance_id))

    # ========== 5. 关闭非终态 instance_nodes ==========
    non_terminal_statuses = ["finished", "terminated", "skipped"]
    await db.execute(
        sql_update(InstanceNode)
        .where(
            InstanceNode.instance_id == instance_id,
            InstanceNode.status.notin_(non_terminal_statuses),
        )
        .values(status="terminated", completed_at=now)
    )

    # ========== 6. 关闭非终态 tasks ==========
    task_terminal = ["completed", "terminated"]
    await db.execute(
        sql_update(Task)
        .where(
            Task.instance_id == instance_id,
            Task.status.notin_(task_terminal),
        )
        .values(status="terminated", completed_at=now)
    )

    # ========== 7. 关闭 pending check_records ==========
    await db.execute(
        sql_update(CheckRecord)
        .where(
            CheckRecord.instance_id == instance_id,
            CheckRecord.status == "pending",
        )
        .values(status="terminated", decided_at=now)
    )

    # ========== 8. 关闭 pending approvals ==========
    await db.execute(
        sql_update(Approval)
        .where(
            Approval.instance_id == instance_id,
            Approval.status == "pending",
        )
        .values(status="terminated", decided_at=now)
    )

    # ========== 9. 更新实例状态 ==========
    instance.status = "terminated"
    instance.termination_reason = reason
    instance.terminated_at = now

    # ========== 10. 记录操作日志 ==========
    log = OperationLog(
        instance_id=instance_id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="instance_terminated",
        description=f"终止流程：「{instance.name}」，原因：{reason}",
        detail={"reason": reason, "instance_name": instance.name},
    )
    db.add(log)

    return {
        "id": instance.id,
        "name": instance.name,
        "status": "terminated",
        "termination_reason": reason,
        "terminated_at": now,
    }


async def change_personnel(
    db: AsyncSession,
    instance_id: int,
    node_id: int,
    body: ChangePersonnelRequest,
    current_user: CurrentUser,
) -> dict:
    """紧急换人 —— 更换运行中实例节点的负责人/校验人/审批人

    处理步骤：
    1. 校验实例存在 + 发起人权限
    2. 校验节点存在且未完成
    3. 对比新旧人员列表，决定增删
    4. pending 记录不在新列表 → terminated
    5. 新人员生成 CheckRecord/Approval
    6. 更新 instance_node 人员字段
    7. 若仅换负责人且节点 running → 更新 Task.assignee_id
    8. 记录操作日志
    """
    # ========== 辅助函数：从人员列表提取 user_id 集合 ==========
    def extract_user_ids(personnel: list | None) -> set[int]:
        if not personnel:
            return set()
        result = set()
        for item in personnel:
            if isinstance(item, dict):
                result.add(item.get("user_id", 0))
            elif isinstance(item, int):
                result.add(item)
        return result - {0}  # 排除无效 0

    # ========== 1. 校验实例 ==========
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id)
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    if not instance:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")
    if instance.initiator_id != current_user.id:
        raise AppException(ErrorCode.NOT_INITIATOR, "仅发起人可更换人员")

    # ========== 2. 校验节点 ==========
    node_stmt = select(InstanceNode).where(
        InstanceNode.id == node_id,
        InstanceNode.instance_id == instance_id,
    )
    node_result = await db.execute(node_stmt)
    node = node_result.scalar_one_or_none()
    if not node:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在")
    if node.status in ("finished", "terminated", "skipped"):
        raise AppException(ErrorCode.NOT_RUNNING, "已完成/已终止/已跳过的节点不可更换人员")

    now = datetime.now()
    changes: list[str] = []  # 记录变更描述

    # ========== 3. 处理校验人变更 ==========
    if body.checkers is not None:
        old_ids = extract_user_ids(node.checkers)
        new_checkers = _normalize_list(body.checkers)
        new_ids = extract_user_ids(new_checkers)

        removed = old_ids - new_ids
        added = new_ids - old_ids

        if removed or added:
            # 不在新列表的 pending CheckRecord → terminated
            await db.execute(
                sql_update(CheckRecord)
                .where(
                    CheckRecord.instance_id == instance_id,
                    CheckRecord.node_id == node_id,
                    CheckRecord.status == "pending",
                    CheckRecord.checker_id.in_(list(removed)),
                )
                .values(status="terminated", decided_at=now)
            )

            # 新校验人生成 CheckRecord
            for uid in added:
                db.add(CheckRecord(
                    instance_id=instance_id,
                    node_id=node_id,
                    task_id=0,  # 换人时可能无 task
                    checker_id=uid,
                    status="pending",
                ))

            changes.append(f"校验人: {_describe_change(old_ids, new_ids)}")
            node.checkers = new_checkers

    # ========== 4. 处理审批人变更 ==========
    if body.approvers is not None:
        old_ids = extract_user_ids(node.approvers)
        new_approvers = _normalize_list(body.approvers)
        new_ids = extract_user_ids(new_approvers)

        removed = old_ids - new_ids
        added = new_ids - old_ids

        if removed or added:
            # 不在新列表的 pending Approval → terminated
            await db.execute(
                sql_update(Approval)
                .where(
                    Approval.instance_id == instance_id,
                    Approval.node_id == node_id,
                    Approval.status == "pending",
                    Approval.approver_id.in_(list(removed)),
                )
                .values(status="terminated", decided_at=now)
            )

            # 新审批人生成 Approval
            for uid in added:
                db.add(Approval(
                    instance_id=instance_id,
                    node_id=node_id,
                    task_id=None,
                    approver_id=uid,
                    status="pending",
                ))

            changes.append(f"审批人: {_describe_change(old_ids, new_ids)}")
            node.approvers = new_approvers

    # ========== 5. 处理负责人变更 ==========
    if body.assignee_id is not None and body.assignee_id != node.assignee_id:
        old_name = f"ID:{node.assignee_id}" if node.assignee_id else "无"
        node.assignee_id = body.assignee_id
        changes.append(f"负责人: {old_name} → ID:{body.assignee_id}")

        # 若节点正运行且只有负责人变更 → 更新 Task.assignee_id
        node_status = (node.status or "").lower()
        if node_status in ("arrived", "running"):
            await db.execute(
                sql_update(Task)
                .where(
                    Task.instance_id == instance_id,
                    Task.node_id == node_id,
                    Task.status.in_(["pending", "processing"]),
                )
                .values(assignee_id=body.assignee_id)
            )

    # ========== 6. 无变更时返回 ==========
    if not changes:
        return {"id": node_id, "message": "无需变更"}

    # ========== 7. 记录操作日志 ==========
    log = OperationLog(
        instance_id=instance_id,
        node_id=node_id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="personnel_changed",
        description=f"节点「{node.name}」人员变更：{'；'.join(changes)}",
        detail={
            "node_id": node_id,
            "node_name": node.name,
            "changes": changes,
        },
    )
    db.add(log)

    return {
        "id": node_id,
        "node_name": node.name,
        "assignee_id": node.assignee_id,
        "checkers": node.checkers,
        "approvers": node.approvers,
        "changes": changes,
    }


def _normalize_list(raw: list | None) -> list[dict] | None:
    """标准化人员列表：[1,2] → [{'user_id':1},{'user_id':2}]，已是 dict 则保持"""
    if raw is None:
        return None
    result = []
    for item in raw:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, int):
            result.append({"user_id": item})
    return result if result else None


def _describe_change(old_ids: set[int], new_ids: set[int]) -> str:
    """将人员变更描述为可读字符串"""
    parts = []
    if old_ids - new_ids:
        parts.append(f"移除 {_ids_str(old_ids - new_ids)}")
    if new_ids - old_ids:
        parts.append(f"新增 {_ids_str(new_ids - old_ids)}")
    return "、".join(parts)


def _ids_str(ids: set[int]) -> str:
    return "ID:" + ",ID:".join(str(i) for i in sorted(ids))


async def change_priority(
    db: AsyncSession,
    instance_id: int,
    priority: str,
    current_user: CurrentUser,
) -> dict:
    """修改流程实例优先级 —— 仅发起人 + running 状态可操作

    返回更新后的优先级和实例基本信息。
    """
    # 1. 查询实例
    stmt = select(FlowInstance).where(FlowInstance.id == instance_id)
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    if not instance:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")

    # 2. 仅发起人
    if instance.initiator_id != current_user.id:
        raise AppException(ErrorCode.NOT_INITIATOR, "仅发起人可修改优先级")

    # 3. 仅 running 状态
    if (instance.status or "").lower() != "running":
        raise AppException(ErrorCode.PRIORITY_ONLY_RUNNING, "仅运行中的流程可修改优先级")

    old_priority = instance.priority
    instance.priority = priority

    # 4. 操作日志
    priority_names = {"urgent": "紧急", "high": "高", "normal": "普通", "low": "低"}
    old_label = priority_names.get(old_priority, old_priority)
    new_label = priority_names.get(priority, priority)

    log = OperationLog(
        instance_id=instance_id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="priority_changed",
        description=f"优先级变更：{old_label} → {new_label}",
        detail={"old_priority": old_priority, "new_priority": priority},
    )
    db.add(log)

    return {
        "id": instance.id,
        "priority": priority,
        "old_priority": old_priority,
    }


async def permanent_delete_instance(db: AsyncSession, instance_id: int) -> None:
    """永久删除流程实例 —— 级联清除所有关联数据（仅管理员可操作，仅已终止实例可删）

    删除顺序（避免外键约束冲突）：
    approval → check_record → file → task → instance_edge → operation_log → instance_node → flow_instance
    """
    # 查询实例
    result = await db.execute(select(FlowInstance).where(FlowInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")
    if instance.status != "terminated":
        raise AppException(ErrorCode.FORBIDDEN, "仅已终止的实例可永久删除")

    # 先获取所有关联 node ID（用于后续查询）
    node_ids_result = await db.execute(
        select(InstanceNode.id).where(InstanceNode.instance_id == instance_id)
    )
    node_ids = [row[0] for row in node_ids_result.all()]

    # 获取所有关联 task ID
    task_ids: list[int] = []
    if node_ids:
        task_ids_result = await db.execute(
            select(Task.id).where(Task.instance_id == instance_id)
        )
        task_ids = [row[0] for row in task_ids_result.all()]

    # 1. 删除审批记录
    await db.execute(sql_delete(Approval).where(Approval.instance_id == instance_id))

    # 2. 删除校验记录
    await db.execute(sql_delete(CheckRecord).where(CheckRecord.instance_id == instance_id))

    # 3. 删除文件（物理文件 + DB 记录）
    files_result = await db.execute(select(File).where(File.instance_id == instance_id))
    files = files_result.scalars().all()
    for f in files:
        abs_path = os.path.join(settings.STORAGE_ROOT, f.file_path) if not os.path.isabs(f.file_path) else f.file_path
        if os.path.exists(abs_path):
            os.remove(abs_path)
        await db.delete(f)

    # 4. 删除任务
    if task_ids:
        await db.execute(sql_delete(Task).where(Task.instance_id == instance_id))

    # 5. 删除实例连线
    await db.execute(sql_delete(InstanceEdge).where(InstanceEdge.instance_id == instance_id))

    # 6. 删除操作日志
    await db.execute(sql_delete(OperationLog).where(OperationLog.instance_id == instance_id))

    # 7. 删除实例节点
    await db.execute(sql_delete(InstanceNode).where(InstanceNode.instance_id == instance_id))

    # 8. 删除实例本身
    await db.delete(instance)
    await db.flush()
