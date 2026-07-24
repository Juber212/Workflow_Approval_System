"""实例列表查询服务"""

import os
import uuid

from ._helpers import _batch_get_node_stats, _batch_get_current_assignees

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



async def list_instances(
    db: AsyncSession,
    *,
    organization_id: int | None = None,
    status: list[str] | None = None,
    priority: str | None = None,
    keyword: str | None = None,
    sort_by: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询项目列表（分页 + 多条件筛选）

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
        .join(FlowTemplate, FlowInstance.template_id == FlowTemplate.id, isouter=True)  # LEFT JOIN：模板删除后实例依然可见
    )

    # 过滤：仅项目，排除方案（方案的列表走 /proposals 端点）
    base_stmt = base_stmt.where(FlowInstance.template_type == "project")

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
    if sort_by == "priority":
        # 运行中实例按优先级排序：urgent > high > normal > low
        # 同优先级按当前活跃节点的截止时间（最近截止在先），无截止时间排最后
        current_deadline = (
            select(InstanceNode.deadline)
            .where(
                InstanceNode.instance_id == FlowInstance.id,
                InstanceNode.status.in_(["pending", "processing"]),
            )
            .order_by(InstanceNode.sort_order)
            .limit(1)
            .correlate(FlowInstance)
            .scalar_subquery()
        )
        # MySQL 不支持 NULLS LAST，用 CASE 将 null 推到末尾
        list_stmt = base_stmt.order_by(
            case((current_deadline.is_(None), 1), else_=0),  # 无截止时间排最后
            current_deadline.asc(),
            case(
                (FlowInstance.priority == "urgent", 0),
                (FlowInstance.priority == "high", 1),
                (FlowInstance.priority == "normal", 2),
                else_=3,
            ),
            FlowInstance.initiated_at.asc(),
        )
    else:
        # 默认按 ID 倒序（最近发起的在前）
        list_stmt = base_stmt.order_by(FlowInstance.id.desc())
    list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(list_stmt)
    rows = result.all()

    # ========== 批量查询节点统计和当前负责人（避免 N+1） ==========
    instance_ids = [row[0].id for row in rows]

    # 单次 GROUP BY 查询所有实例的节点统计
    node_stats_map = await _batch_get_node_stats(db, instance_ids)

    # 单次查询所有实例的当前负责人
    assignee_map = await _batch_get_current_assignees(db, instance_ids)

    # 批量查询关联方案名称（避免 N+1）
    proposal_ids = list(set(
        row[0].proposal_id for row in rows if row[0].proposal_id
    ))
    proposal_name_map: dict[int, str] = {}
    if proposal_ids:
        prop_result = await db.execute(
            select(FlowInstance.id, FlowInstance.name).where(
                FlowInstance.id.in_(proposal_ids)
            )
        )
        proposal_name_map = {pid: pname for pid, pname in prop_result.all()}

    # ========== 组装结果 ==========
    items: list[InstanceListItem] = []
    for row in rows:
        instance = row[0]  # FlowInstance 对象（元组第一项）
        initiator_name = row[1]
        org_name = row[2]

        node_stats = node_stats_map.get(instance.id, {"total": 0, "processed": 0})

        items.append(InstanceListItem(
            id=instance.id,
            name=instance.name,
            organization_id=instance.organization_id,
            organization_name=org_name or "",
            initiator_id=instance.initiator_id,
            initiator_name=initiator_name or "",
            priority=(instance.priority or "normal").lower(),
            difficulty=instance.difficulty or "1",
            status=(instance.status or "created").lower(),
            current_node_index=node_stats["processed"],
            total_nodes=node_stats["total"],
            current_assignee_name=assignee_map.get(instance.id),
            proposal_name=proposal_name_map.get(instance.proposal_id) if instance.proposal_id else None,
            initiated_at=instance.initiated_at,
            completed_at=instance.completed_at,
            terminated_at=instance.terminated_at,
        ))

    return PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )



