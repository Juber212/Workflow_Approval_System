"""文件服务 —— 上传、删除、PDF 转换"""
import os
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import File, Task, InstanceNode, FlowInstance
from app.models.enums import TaskStatus, UploadType

# 允许的文件类型
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


async def upload_file(
    db: AsyncSession,
    task_id: int,
    upload_file_obj: UploadFile,
    current_user_id: int,
    folder_name: str | None = None,  # 所属文件夹名称
) -> dict:
    """上传文件到任务 —— 支持文件夹分组"""
    # 校验任务
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可上传文件")
    if task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise AppException(ErrorCode.FORBIDDEN, "当前状态不可上传文件")

    # 校验文件类型
    if upload_file_obj.content_type not in ALLOWED_MIME_TYPES:
        raise AppException(ErrorCode.BAD_REQUEST, f"不支持的文件类型: {upload_file_obj.content_type}")

    # 读取并校验大小
    contents = await upload_file_obj.read()
    if len(contents) > MAX_FILE_SIZE:
        raise AppException(ErrorCode.BAD_REQUEST, "文件大小不能超过 50MB")

    # 获取实例名称和节点信息
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == task.instance_id))).scalar_one()
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one()

    # 生成唯一文件名
    ext = os.path.splitext(upload_file_obj.filename or "file")[1] or ""
    stored_name = f"{uuid.uuid4().hex}{ext}"

    # 创建存储目录（有文件夹时存入子目录，否则存入实例根目录）
    if folder_name:
        archive_dir = os.path.join(settings.STORAGE_ROOT, "archive", inst.name, folder_name)
        file_path_rel = os.path.join("archive", inst.name, folder_name, stored_name)
    else:
        archive_dir = os.path.join(settings.STORAGE_ROOT, "archive", inst.name)
        file_path_rel = os.path.join("archive", inst.name, stored_name)
    os.makedirs(archive_dir, exist_ok=True)

    # 写入物理文件
    file_path = os.path.join(archive_dir, stored_name)

    # 写入文件
    with open(file_path, "wb") as f:
        f.write(contents)

    # 创建 File 记录
    file_record = File(
        instance_id=task.instance_id,
        node_id=task.node_id,
        task_id=task_id,
        round=node.round,
        uploader_id=current_user_id,
        upload_type=UploadType.NORMAL,
        folder_name=folder_name,  # 所属文件夹
        original_name=upload_file_obj.filename or "unknown",
        stored_name=stored_name,
        file_path=file_path_rel,
        file_size=len(contents),
        mime_type="application/pdf" if upload_file_obj.content_type == "application/pdf" else upload_file_obj.content_type,
    )
    db.add(file_record)
    await db.flush()

    return {
        "id": file_record.id,
        "original_name": file_record.original_name,
        "file_size": file_record.file_size,
        "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
    }


async def delete_file(db: AsyncSession, task_id: int, file_id: int, current_user_id: int) -> None:
    """删除文件 —— 仅未提交任务的文件可删除"""
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user_id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可删除")
    if task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise AppException(ErrorCode.FORBIDDEN, "任务已提交，不可删除文件")

    file_rec = (await db.execute(select(File).where(File.id == file_id, File.task_id == task_id))).scalar_one_or_none()
    if file_rec is None:
        raise AppException(ErrorCode.NOT_FOUND, "文件不存在")

    # 物理删除
    abs_path = os.path.join(settings.STORAGE_ROOT, file_rec.file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)

    await db.delete(file_rec)
    await db.flush()
