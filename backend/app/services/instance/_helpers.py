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



async def _get_type_label(db: AsyncSession, template_id: int) -> str:
    """根据模板 ID 返回中文类型标签：'项目' 或 '方案'"""
    tpl_type = (await db.execute(
        select(FlowTemplate.type).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    return "方案" if tpl_type == "proposal" else "项目"



async def _batch_get_node_stats(db: AsyncSession, instance_ids: list[int]) -> dict[int, dict]:
    """批量查询实例节点统计（替代逐条 N+1）"""
    if not instance_ids:
        return {}
    stmt = select(
        InstanceNode.instance_id,
        func.count(InstanceNode.id).label("total"),
        func.sum(
            func.if_(func.lower(InstanceNode.status) == "finished", 1, 0)
        ).label("processed"),
    ).where(
        InstanceNode.instance_id.in_(instance_ids),
        InstanceNode.is_start == False,  # 排除开始节点
        InstanceNode.is_end == False,    # 排除结束节点
    ).group_by(InstanceNode.instance_id)

    result = await db.execute(stmt)
    return {
        row.instance_id: {"total": int(row.total or 0), "processed": int(row.processed or 0)}
        for row in result.all()
    }


async def _batch_get_current_assignees(db: AsyncSession, instance_ids: list[int]) -> dict[int, str | None]:
    """批量查询实例当前活跃节点的负责人（替代逐条 N+1）"""
    if not instance_ids:
        return {}
    # 子查询：每个实例取一个 running 节点的 assignee_id
    stmt = (
        select(InstanceNode.instance_id, User.real_name)
        .join(User, InstanceNode.assignee_id == User.id)
        .where(
            InstanceNode.instance_id.in_(instance_ids),
            InstanceNode.status == "running",
        )
        .distinct(InstanceNode.instance_id)  # 每个实例只取一条
    )
    result = await db.execute(stmt)
    return {row.instance_id: row.real_name for row in result.all()}


# ==================== 实例详情 ====================



