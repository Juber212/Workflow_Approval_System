"""创建实例服务"""

import os
from collections import deque, defaultdict
from datetime import datetime, date as date_type

from ._helpers import _get_type_label

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge,
    OperationLog,
)
from app.models.enums import InstanceStatus
from app.schemas.instance import (
    CreateInstanceRequest,
    InstanceResponse,
    InstanceNodeBrief,
)
from app.api.deps import CurrentUser
from app.engine.flow_engine import (
    calculate_incoming_counts,
    activate_start_node,
    propagate_from_node,
)
from app.utils.workday import add_workdays, next_workday
from app.services.validation_service import extract_person_ids, validate_user_ids_exist, validate_template_for_publish


def _topological_order(
    tpl_nodes: list[TemplateNode],
    tpl_edges: list[TemplateEdge],
    new_nodes: list,
    new_edges: list,
) -> list:
    """按连线拓扑排序实例节点（模板节点 + 发起新增节点），确定执行顺序

    - 模板节点 key = 模板节点 id（int）
    - 新增节点 key = temp_id（str，前端临时标识）
    - 边 = 模板连线 + 用户新增连线
    - Kahn 算法（入度拓扑排序）；环/孤立节点兜底追加末尾
    无新增节点时返回模板节点原始顺序（零回归）。
    """
    keys: list = [tn.id for tn in tpl_nodes] + [nd.temp_id for nd in new_nodes]
    if not new_nodes:
        return keys

    edges: list[tuple] = [(te.source_node_id, te.target_node_id) for te in tpl_edges]
    edges += [(e.source, e.target) for e in new_edges]

    adj: dict = defaultdict(list)
    indeg: dict = {k: 0 for k in keys}
    for s, t in edges:
        if s in indeg and t in indeg:
            adj[s].append(t)
            indeg[t] += 1

    queue = deque([k for k in keys if indeg[k] == 0])
    order: list = []
    while queue:
        k = queue.popleft()
        order.append(k)
        for t in adj[k]:
            indeg[t] -= 1
            if indeg[t] == 0:
                queue.append(t)

    # 环 / 孤立节点兜底：未排序的追加到末尾
    for k in keys:
        if k not in order:
            order.append(k)
    return order


async def create_instance(
    db: AsyncSession,
    request: CreateInstanceRequest,
    current_user: CurrentUser,
) -> dict:
    """发起项目 —— 从模板节点/连线直接复制生成实例快照

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

    # M16：发起前校验模板结构——防止设计器单节点 CRUD 绕过发布校验留下非法模板，
    # 用非法模板发起会导致实例卡死（无任务无审批，只能终止兜底）。
    # 方案模板（proposal）结构特殊（人员发起时才配置），跳过此校验。
    if tpl.type != "proposal":
        publish_errors = await validate_template_for_publish(db, request.template_id)
        if publish_errors:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                f"模板结构不完整，无法发起：{'；'.join(publish_errors[:3])}",
            )

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

    # ========== 3.5 人员 ID 存在性校验（P1-22） ==========
    # node_overrides / new_nodes 里的负责人/审批人/校验人/批准人必须真实存在，
    # 否则实例节点留下悬空引用，任务会分派给不存在的用户
    person_ids: set[int] = set()
    if request.node_overrides:
        for override in request.node_overrides:
            if override.assignee_id:
                person_ids.add(override.assignee_id)
            if override.endorser_id:
                person_ids.add(override.endorser_id)
            person_ids |= extract_person_ids(override.approvers)
            person_ids |= extract_person_ids(override.checkers)
    if request.new_nodes:
        for nd in request.new_nodes:
            if nd.assignee_id:
                person_ids.add(nd.assignee_id)
            if nd.endorser_id:
                person_ids.add(nd.endorser_id)
            person_ids |= extract_person_ids(nd.approvers)
            person_ids |= extract_person_ids(nd.checkers)
    if person_ids:
        missing = await validate_user_ids_exist(db, person_ids)
        if missing:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                f"以下用户不存在或已停用，请重新选择：{'、'.join(map(str, sorted(missing)))}",
            )

    # ========== 4. 创建 FlowInstance ==========
    # 实例名校验：禁止路径遍历字符，防止逃逸存储目录
    instance_name = request.name.strip()
    _illegal_chars = {"../", "..\\", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"}
    if not instance_name or any(c in instance_name for c in _illegal_chars):
        raise AppException(
            ErrorCode.BAD_REQUEST,
            f"实例名称不能为空或包含特殊字符（{' '.join(sorted(_illegal_chars))}）",
        )

    # M14：同组织同类型同名实例禁止创建——归档目录按「类型/实例名」隔离，
    # 同名会共享目录，永久删除一实例时会误删另一实例的全部文件
    dup = (await db.execute(
        select(FlowInstance.id).where(
            FlowInstance.name == instance_name,
            FlowInstance.organization_id == tpl.organization_id,
            FlowInstance.template_type == tpl.type,
        )
    )).first()
    if dup:
        raise AppException(ErrorCode.BAD_REQUEST, "该组织下已存在同名流程，请更换名称")

    priority = request.priority
    if priority not in ("urgent", "high", "normal", "low"):
        priority = "normal"
    difficulty = getattr(request, "difficulty", "1") or "1"
    if difficulty not in ("1", "2", "3", "4"):
        difficulty = "1"

    instance = FlowInstance(
        name=instance_name,
        description=request.description,
        template_id=request.template_id,
        template_name=tpl.name,
        template_type=tpl.type,  # 快照模板类型，用于存储分目录等
        organization_id=tpl.organization_id,
        initiator_id=current_user.id,
        priority=priority,
        difficulty=difficulty,
        contract_no=request.contract_no.strip() if request.contract_no else None,
        product_model=request.product_model.strip() if request.product_model else None,
        sales_manager=request.sales_manager.strip() if request.sales_manager else None,
        proposal_id=request.proposal_id,
        doc_template_ids=request.doc_template_ids,  # 实例级文件模板（为空则继承模板关联）
        status=InstanceStatus.CREATED,
    )
    db.add(instance)
    await db.flush()

    # ========== 5. 复制节点（合并 node_overrides + 发起新增节点，按连线拓扑序） ==========
    node_id_map: dict = {}  # 模板节点 id / 新节点 temp_id → instance_node id
    instance_nodes: list[InstanceNode] = []
    new_nodes = request.new_nodes or []
    new_edges = request.new_edges or []
    new_node_map = {nd.temp_id: nd for nd in new_nodes}

    # 按连线拓扑排序（无新增节点时返回模板原始顺序，零回归）
    ordered_keys = _topological_order(tpl_nodes, tpl_edges, new_nodes, new_edges)

    for sort_idx, key in enumerate(ordered_keys):
        if isinstance(key, int):
            # ── 模板节点：合并发起覆盖（node_overrides） ──
            tn = next(t for t in tpl_nodes if t.id == key)
            node_override: dict = override_map.get(tn.id, {})

            # 配置合并：发起覆盖 > 模板默认值
            # 注意：不能用 `or`，因为 0/[]/False 是合法值，会被 or 吞掉
            assignee_id = node_override.get("assignee_id") or tn.assignee_id
            time_limit_days = node_override["time_limit_days"] if "time_limit_days" in node_override else tn.time_limit_days
            approvers = node_override["approvers"] if "approvers" in node_override else tn.approvers
            checkers = node_override["checkers"] if "checkers" in node_override else tn.checkers
            require_assignee_signature = node_override.get("require_assignee_signature")
            if require_assignee_signature is None:
                require_assignee_signature = tn.require_assignee_signature
            require_checker_signature = node_override.get("require_checker_signature")
            if require_checker_signature is None:
                require_checker_signature = tn.require_checker_signature
            require_approver_signature = node_override.get("require_approver_signature")
            if require_approver_signature is None:
                require_approver_signature = tn.require_approver_signature
            endorser_id = node_override["endorser_id"] if "endorser_id" in node_override else (tn.endorser_id if hasattr(tn, 'endorser_id') else None)
            require_endorser_signature = node_override.get("require_endorser_signature")
            if require_endorser_signature is None:
                require_endorser_signature = tn.require_endorser_signature if hasattr(tn, 'require_endorser_signature') else True
            signature_x = node_override.get("signature_x")
            if signature_x is None:
                signature_x = tn.signature_x
            signature_y = node_override.get("signature_y")
            if signature_y is None:
                signature_y = tn.signature_y
            signature_page = node_override.get("signature_page")
            if signature_page is None:
                signature_page = tn.signature_page

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
                file_folders=tn.file_folders,  # 文件夹配置快照
                require_assignee_signature=require_assignee_signature,
                require_checker_signature=require_checker_signature,
                require_approver_signature=require_approver_signature,
                endorser_id=endorser_id,
                require_endorser_signature=require_endorser_signature,
                signature_x=signature_x,
                signature_y=signature_y,
                signature_page=signature_page,
                approvers=approvers,
                checkers=checkers,
                approval_strategy=tn.approval_strategy,
                status="waiting",
                sort_order=sort_idx,  # 拓扑序序号（新增节点插入后重排）
            )
        else:
            # ── 发起新增节点（NewNodeDef 完整配置，不进模板） ──
            nd = new_node_map[key]
            inode = InstanceNode(
                instance_id=instance.id,
                name=nd.name,
                is_start=False,
                is_end=False,
                assignee_id=nd.assignee_id,
                time_limit_days=nd.time_limit_days,
                deadline=None,
                require_file=nd.require_file,
                file_folders=nd.file_folders,
                require_assignee_signature=nd.require_assignee_signature,
                require_checker_signature=nd.require_checker_signature,
                require_approver_signature=nd.require_approver_signature,
                endorser_id=nd.endorser_id,
                require_endorser_signature=nd.require_endorser_signature,
                signature_x=nd.signature_x,
                signature_y=nd.signature_y,
                signature_page=nd.signature_page,
                approvers=nd.approvers,
                checkers=nd.checkers,
                approval_strategy=nd.approval_strategy,
                status="waiting",
                sort_order=sort_idx,
            )
        db.add(inode)
        await db.flush()
        node_id_map[key] = inode.id
        instance_nodes.append(inode)

    # ========== 5.5 难度4 强制批准人校验（P1-10）==========
    # 难度4 的所有工作节点必须配置批准人（endorser_id），否则审批通过后
    # 流程会跳过批准环节直接完成，难度4 形同虚设
    if difficulty == "4":
        missing = [n.name for n in instance_nodes if not n.is_start and not n.is_end and not n.endorser_id]
        if missing:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                f"难度4流程的所有工作节点必须配置批准人，以下节点未配置：{'、'.join(missing)}",
            )

    # ========== 6. 复制连线（模板边 + 发起新增连线） ==========
    all_edges = [(te.source_node_id, te.target_node_id) for te in tpl_edges]
    all_edges += [(e.source, e.target) for e in new_edges]
    for src_key, tgt_key in all_edges:
        src = node_id_map.get(src_key)
        tgt = node_id_map.get(tgt_key)
        if src and tgt:
            db.add(InstanceEdge(instance_id=instance.id, source_node_id=src, target_node_id=tgt))

    await db.flush()

    # ========== 6.1 创建文件提交文件夹目录（实例根目录 + 子文件夹一次性建好） ==========
    folder_names: set[str] = set()
    for inode in instance_nodes:  # 含发起新增节点
        if inode.file_folders and isinstance(inode.file_folders, list):
            for folder in inode.file_folders:
                name = (folder.get("name") or "").strip()
                if name:
                    folder_names.add(name)

    if folder_names:
        archive_subdir = settings.get_archive_dir(instance.template_type or "project")
        instance_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, instance.name)
        for fname in folder_names:
            os.makedirs(os.path.join(instance_dir, fname), exist_ok=True)

    # ========== 6.5 计算工作日截止日期 ==========
    # 从发起日期起，按模板节点顺序链式推算每个工作节点的截止日期（P1-39 统一口径）：
    #   - 首个工作节点 开始 = 发起日，截止 = 开始 + time_limit_days 工作日
    #   - 后续节点 开始 = 上一节点截止日的下一个工作日，截止 = 开始 + time_limit_days 工作日
    # 用 add_workdays / next_workday 跳过法定节假日和周末，
    # 与 /api/v1/utils/calculate-deadlines 接口语义完全一致。
    # 已通过 node_override 手动指定 deadline 的节点跳过此计算。
    initiation_date = date_type.today()

    # 按拓扑序遍历（含新增节点），链式推算工作节点截止日期
    prev_deadline: date_type | None = None
    for inode in instance_nodes:
        # 只处理工作节点（跳过开始/结束）；已有手动 deadline 则跳过
        if inode.is_start or inode.is_end or inode.deadline:
            continue

        wd = inode.time_limit_days or 0
        if wd <= 0:
            continue

        # 链式衔接：本节点开始日 = 上一节点截止日的下一个工作日（首个工作节点从发起日起算）
        begin_date = initiation_date if prev_deadline is None else next_workday(prev_deadline)
        inode.deadline = datetime.combine(
            add_workdays(begin_date, wd),
            datetime.min.time(),
        )
        prev_deadline = inode.deadline.date()

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
        description=f"发起了{await _get_type_label(db, request.template_id)}「{instance.name}」",
        detail={
            "template_id": request.template_id,
            "priority": priority,
            "difficulty": difficulty,
            "node_count": len(instance_nodes),
        },
    ))
    await db.flush()

    return InstanceResponse(
        id=instance.id,
        name=instance.name,
        organization_id=instance.organization_id,
        initiator_id=instance.initiator_id,
        priority=instance.priority,
        difficulty=instance.difficulty,  # P1-21：发起响应补难度等级，前端发起后回显
        status=instance.status,
        nodes=[
            InstanceNodeBrief(
                id=n.id, name=n.name,
                is_start=n.is_start, is_end=n.is_end,
                status=n.status, sort_order=n.sort_order,
            )
            for n in instance_nodes
        ],
        initiated_at=instance.initiated_at,
    )



