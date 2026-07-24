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



async def permanent_delete_instance(db: AsyncSession, instance_id: int) -> None:
    """永久删除项目 —— 级联清除所有关联数据（仅管理员可操作，仅已终止实例可删）

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

    # 0. 删除批准记录（先于审批，避免外键冲突）
    await db.execute(sql_delete(Endorsement).where(Endorsement.instance_id == instance_id))

    # 1. 删除审批记录
    await db.execute(sql_delete(Approval).where(Approval.instance_id == instance_id))

    # 2. 删除校验记录
    await db.execute(sql_delete(CheckRecord).where(CheckRecord.instance_id == instance_id))

    # 3. 删除文件（先DB后物理文件，避免事务回滚后物理文件丢失）
    files_result = await db.execute(select(File).where(File.instance_id == instance_id))
    files = files_result.scalars().all()
    for f in files:
        await db.delete(f)
        abs_path = os.path.join(settings.STORAGE_ROOT, f.file_path) if not os.path.isabs(f.file_path) else f.file_path
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
        except OSError:
            pass

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

    # 9. 删除实例文件夹（文件已在步骤3删除，此处清理残留空目录）
    import shutil
    archive_subdir = settings.get_archive_dir(instance.template_type or "project")
    instance_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, instance.name)
    try:
        if os.path.isdir(instance_dir):
            shutil.rmtree(instance_dir)
    except OSError:
        pass  # 目录不存在或权限问题，忽略

