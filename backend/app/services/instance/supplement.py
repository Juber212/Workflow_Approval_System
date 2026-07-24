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



async def supplement_files(
    db: AsyncSession,
    instance_id: int,
    node_id: int,
    files: list[UploadFile],
    current_user: CurrentUser,
) -> dict:
    """补交文件到已完成实例的已完成节点

    权限：实例发起人（所长）或该节点的历史负责人。
    限制：仅 completed 实例 + finished 节点（排除开始/结束节点）。
    文件：多文件，支持 Word/Excel/图片/PDF，单文件 ≤50MB。
    表现：不触发审批/校验/签名，不创建 Task，仅追加 File 记录 + 操作日志。

    Args:
        db: 异步数据库会话
        instance_id: 实例 ID
        node_id: 目标节点 ID
        files: 上传文件列表
        current_user: 当前登录用户

    Returns:
        {"files": [NodeFileBrief, ...]}
    """
    # ========== 1. 校验实例状态 ==========
    instance = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")
    if (instance.status or "").lower() != "completed":
        raise AppException(ErrorCode.FORBIDDEN, "仅已完成流程可补交文件")

    # ========== 2. 校验节点状态 ==========
    node = (await db.execute(
        select(InstanceNode).where(
            InstanceNode.id == node_id,
            InstanceNode.instance_id == instance_id,
        )
    )).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "节点不存在或不属于该实例")
    if node.is_start or node.is_end:
        raise AppException(ErrorCode.FORBIDDEN, "开始/结束节点不可补交文件")
    if (node.status or "").lower() != "finished":
        raise AppException(ErrorCode.FORBIDDEN, "仅已完成节点可补交文件")

    # ========== 3. 权限校验：发起人或历史负责人 ==========
    is_initiator = current_user.id == instance.initiator_id
    is_assignee = current_user.id == node.assignee_id
    if not is_initiator and not is_assignee:
        raise AppException(ErrorCode.FORBIDDEN, "无权补交：仅发起人或该节点历史负责人可操作")

    # ========== 4. 查当前用户名（用于日志和返回值） ==========
    user_result = await db.execute(select(User.real_name).where(User.id == current_user.id))
    user_name = user_result.scalar() or current_user.username

    # ========== 5. 遍历上传文件 ==========
    file_records: list[File] = []
    written_files: list[str] = []  # 跟踪已写入的物理文件路径（DB失败时用于清理）
    archive_subdir = settings.get_archive_dir(instance.template_type or "project")
    archive_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, instance.name)
    os.makedirs(archive_dir, exist_ok=True)

    for upload_file_obj in files:
        # 5a. 校验文件类型
        if upload_file_obj.content_type not in settings.allowed_mime_types_list:
            raise AppException(
                ErrorCode.FILE_TYPE_UNSUPPORTED,
                f"不支持的文件类型: {upload_file_obj.content_type}（{upload_file_obj.filename}）",
            )

        # 5b. 校验文件大小
        contents = await upload_file_obj.read()
        if len(contents) > settings.max_file_size_bytes:
            raise AppException(
                ErrorCode.FILE_TOO_LARGE,
                f"文件大小超过限制（最大 50MB）: {upload_file_obj.filename}",
            )

        # 5c. 写入磁盘
        ext = os.path.splitext(upload_file_obj.filename or "file")[1] or ""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(archive_dir, stored_name)

        with open(file_path, "wb") as f:
            f.write(contents)

        # 5d. 创建 File 记录（task_id=NULL、upload_type=supplement）
        file_record = File(
            instance_id=instance_id,
            node_id=node_id,
            task_id=None,  # 补交不关联任务
            round=node.round,  # 使用节点完成时的轮次
            uploader_id=current_user.id,
            upload_type=UploadType.SUPPLEMENT,
            original_name=upload_file_obj.filename or "unknown",
            stored_name=stored_name,
            file_path=os.path.join(archive_subdir, instance.name, stored_name),
            file_size=len(contents),
            mime_type="application/pdf" if upload_file_obj.content_type == "application/pdf" else upload_file_obj.content_type,
        )
        db.add(file_record)
        file_records.append(file_record)
        # 记录物理文件路径（用于 DB 失败时清理）
        written_files.append(file_path)

    # ========== 6. 批量 flush + 记录操作日志 ==========
    try:
        await db.flush()
    except Exception:
        # DB 事务失败 → 清理已写入的物理文件
        for wf in written_files:
            if os.path.exists(wf):
                try:
                    os.remove(wf)
                except OSError:
                    pass
        raise

    log = OperationLog(
        instance_id=instance_id,
        operator_type="user",
        operator_id=current_user.id,
        node_id=node_id,
        operation_type="file_supplement",
        description=f"补交了 {len(file_records)} 个文件至节点「{node.name}」",
        detail={
            "node_name": node.name,
            "node_id": node_id,
            "file_count": len(file_records),
            "file_names": [fr.original_name for fr in file_records],
        },
    )
    db.add(log)

    # ========== 7. 构建返回值 ==========
    return SupplementFileResponse(
        files=[
            NodeFileBrief(
                id=fr.id,
                original_name=fr.original_name,
                file_size=fr.file_size,
                uploader_id=fr.uploader_id,
                uploader_name=user_name,
                upload_type=UploadType.SUPPLEMENT,
                folder_name=fr.folder_name,  # 所属文件夹名称
                round=fr.round,
                created_at=fr.created_at,
            )
            for fr in file_records
        ],
    )



