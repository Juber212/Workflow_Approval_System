"""终止项目服务"""

import os
import uuid

from ._helpers import _get_type_label

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



async def terminate_instance(
    db: AsyncSession,
    instance_id: int,
    reason: str,
    current_user: CurrentUser,
) -> dict:
    """终止项目 —— 级联关闭所有关联记录并物理删除文件

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
        type_label = await _get_type_label(db, instance.template_id)
        raise AppException(ErrorCode.NOT_INITIATOR, f"仅发起人可终止{type_label}")

    # ========== 3. 校验未已终止 ==========
    if (instance.status or "").lower() == "terminated":
        raise AppException(ErrorCode.INSTANCE_ALREADY_TERMINATED, "流程已终止，不可重复操作")

    now = datetime.now()

    # ========== 4. 物理删除文件 + 删除 files 记录 ==========
    file_stmt = select(File).where(File.instance_id == instance_id)
    file_result = await db.execute(file_stmt)
    files = file_result.scalars().all()

    # 先删除文件记录（DB），再删物理文件（避免事务回滚后物理文件丢失）
    if files:
        await db.execute(sql_delete(File).where(File.instance_id == instance_id))

    # 逐个物理删除磁盘文件（DB记录已删，物理删除失败不影响DB一致性）
    for f in files:
        if f.file_path:
            full_path = os.path.join(settings.STORAGE_ROOT, f.file_path)
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
            except OSError:
                # 文件不存在或无权删除，不阻断流程
                pass

    # ========== 5. 关闭非终态 instance_nodes ==========
    non_terminal_statuses = ["finished", "terminated"]
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
            CheckRecord.status == CheckStatus.PENDING,
        )
        .values(status=CheckStatus.TERMINATED, decided_at=now)
    )

    # ========== 8. 关闭 pending approvals ==========
    await db.execute(
        sql_update(Approval)
        .where(
            Approval.instance_id == instance_id,
            Approval.status == ApprovalStatus.PENDING,
        )
        .values(status=ApprovalStatus.TERMINATED, decided_at=now)
    )

    # ========== 8b. 关闭 pending endorsements ==========
    await db.execute(
        sql_update(Endorsement)
        .where(
            Endorsement.instance_id == instance_id,
            Endorsement.status == EndorsementStatus.PENDING,
        )
        .values(status=EndorsementStatus.TERMINATED, decided_at=now)
    )

    # ========== 9. 更新实例状态 ==========
    instance.status = "terminated"
    instance.termination_reason = reason
    instance.terminated_at = now

    # ========== 10. 记录操作日志 ==========
    term_type_label = await _get_type_label(db, instance.template_id)
    log = OperationLog(
        instance_id=instance_id,
        operator_type="user",
        operator_id=current_user.id,
        operation_type="instance_terminated",
        description=f"终止{term_type_label}：「{instance.name}」，原因：{reason}",
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



