"""流程实例服务 —— 发起实例、配置合并、快照复制"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate,
    FlowVersion,
    FlowInstance,
    InstanceNode,
    InstanceEdge,
    OperationLog,
)
from app.schemas.instance import CreateInstanceRequest
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
