"""项目服务 —— 发起实例、配置合并、快照复制、列表查询、终止项目、补交文件"""

import os
import uuid

from fastapi import UploadFile
from datetime import datetime

from sqlalchemy import select, func, case, and_, delete as sql_delete, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge,
    OperationLog, User, Organization,
    Task, CheckRecord, Approval, Endorsement, File,
)
from app.models.enums import UploadType, InstanceStatus, InstanceNodeStatus, TaskStatus, ApprovalStatus, CheckStatus, EndorsementStatus
from app.schemas.common import PaginatedData
from app.schemas.instance import (
    CreateInstanceRequest,
    InstanceResponse,
    InstanceNodeBrief,
    InstanceListItem,
    InstanceDetailResponse,
    DetailNodeInfo,
    NodeFileBrief,
    CheckRecordBrief,
    ApprovalBrief,
    LogItemBrief,
    SupplementFileResponse,
    ChangePersonnelRequest,
    ChangePriorityRequest,
)
from app.api.deps import CurrentUser
from app.engine.flow_engine import (
    calculate_incoming_counts,
    activate_start_node,
    propagate_from_node,
)
from app.utils.workday import add_workdays
from datetime import date as date_type



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
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在或无权访问")

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
        # 从 checkers/approvers JSON 中提取 user_id，以及 endorser_id
        if n.endorser_id:
            user_ids.add(n.endorser_id)
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

    # ========== 3. 节点统计（排除开始/结束节点） ==========
    work_nodes = [n for n in node_models if not n.is_start and not n.is_end]
    total_nodes = len(work_nodes)
    processed_count = sum(
        1 for n in work_nodes
        if (n.status or "").lower() == "finished"
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
                    folder_name=f.folder_name,  # 所属文件夹名称
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
            .where(CheckRecord.node_id.in_(node_ids), CheckRecord.status != CheckStatus.TERMINATED)
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
                    round=c.round or 1,
                    decided_at=c.decided_at,
                )
            )

    # 审批记录（按 node_id 分组）
    approvals_by_node: dict[int, list] = {}
    if node_ids:
        approvals_stmt = (
            select(Approval, User.real_name.label("approver_name"))
            .join(User, Approval.approver_id == User.id)
            .where(Approval.node_id.in_(node_ids), Approval.status != ApprovalStatus.TERMINATED)
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
                    signature_x=a.signature_x,
                    signature_y=a.signature_y,
                    signature_page=a.signature_page,
                    round=a.round or 1,
                    decided_at=a.decided_at,
                )
            )

    # 批准记录（按 node_id 分组）—— 仅难度4时存在
    endorsements_by_node: dict[int, list] = {}
    if node_ids:
        end_stmt = (
            select(Endorsement, User.real_name.label("endorser_name"))
            .join(User, Endorsement.endorser_id == User.id)
            .where(Endorsement.node_id.in_(node_ids), Endorsement.status != EndorsementStatus.TERMINATED)
            .order_by(Endorsement.created_at)
        )
        end_result = await db.execute(end_stmt)
        for e, e_name in end_result:
            if e.node_id not in endorsements_by_node:
                endorsements_by_node[e.node_id] = []
            endorsements_by_node[e.node_id].append({
                "id": e.id,
                "endorser_id": e.endorser_id,
                "endorser_name": e_name or "",
                "status": (e.status or "pending").lower(),
                "opinion": e.opinion,
                "signature_applied": e.signature_applied,
                "round": e.round or 1,
                "decided_at": e.decided_at,
            })

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
            file_folders=n.file_folders,  # 文件夹配置快照
            require_assignee_signature=n.require_assignee_signature,
            require_checker_signature=n.require_checker_signature,
            require_approver_signature=n.require_approver_signature,
            endorser_id=n.endorser_id,
            endorser_name=user_name_map.get(n.endorser_id) if n.endorser_id else None,
            require_endorser_signature=n.require_endorser_signature if hasattr(n, 'require_endorser_signature') else True,
            signature_x=n.signature_x,
            signature_y=n.signature_y,
            signature_page=n.signature_page,
            approval_strategy=n.approval_strategy,
            started_at=n.started_at,
            completed_at=n.completed_at,
            files=files_by_node.get(n.id, []),
            checks=checks_by_node.get(n.id, []),
            approvals=approvals_by_node.get(n.id, []),
            endorsements=endorsements_by_node.get(n.id, []),
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
    log_items: list[LogItemBrief] = []
    for log, op_name in logs_result:
        log_items.append(LogItemBrief(
            id=log.id,
            operator_type=(log.operator_type or "user").lower(),
            operator_id=log.operator_id,
            operator_name=op_name,
            node_id=log.node_id,
            operation_type=log.operation_type,
            round=log.round,
            description=log.description,
            detail=log.detail,
            created_at=log.created_at,
        ))

    # ========== 7. 关联方案名称 + 模板类型 ==========
    proposal_name: str | None = None
    template_type = instance.template_type or "project"  # 使用实例快照值

    if instance.proposal_id:
        prop = (await db.execute(
            select(FlowInstance.name).where(FlowInstance.id == instance.proposal_id)
        )).scalar_one_or_none()
        proposal_name = prop

    # ========== 8. 组装最终结果 ==========
    return InstanceDetailResponse(
        id=instance.id,
        name=instance.name,
        description=instance.description,
        organization_id=instance.organization_id,
        organization_name=org_name or "",
        initiator_id=instance.initiator_id,
        initiator_name=initiator_name or "",
        priority=(instance.priority or "normal").lower(),
        difficulty=instance.difficulty or "1",
        status=(instance.status or "created").lower(),
        termination_reason=instance.termination_reason,
        contract_no=instance.contract_no,
        product_model=instance.product_model,
        sales_manager=instance.sales_manager,
        proposal_id=instance.proposal_id,
        proposal_name=proposal_name,
        template_type=template_type,
        current_node_index=processed_count,
        total_nodes=total_nodes,
        initiated_at=instance.initiated_at,
        completed_at=instance.completed_at,
        terminated_at=instance.terminated_at,
        nodes=nodes,
        logs={"items": log_items, "total": len(log_items)},
    )



