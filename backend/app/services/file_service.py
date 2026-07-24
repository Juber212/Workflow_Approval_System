"""文件服务 —— 上传、删除、PDF 转换"""
import os
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.utils.file_utils import resolve_file_path
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import File, Task, InstanceNode, FlowInstance
from app.models.enums import TaskStatus, UploadType


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

    # 校验文件类型（先 Client MIME 粗筛，再魔数精确校验）
    if upload_file_obj.content_type not in settings.allowed_mime_types_list:
        raise AppException(ErrorCode.BAD_REQUEST, f"不支持的文件类型: {upload_file_obj.content_type}")

    # 流式获取文件大小（seek 到尾端再回位，避免全量读入内存）
    upload_file_obj.file.seek(0, 2)  # os.SEEK_END
    file_size = upload_file_obj.file.tell()
    upload_file_obj.file.seek(0)  # 回到开头
    if file_size > settings.max_file_size_bytes:
        raise AppException(ErrorCode.BAD_REQUEST, "文件大小不能超过 50MB")

    # 文件魔数校验（仅读取前 8KB，防止伪造 Content-Type）
    import filetype
    header = upload_file_obj.file.read(8192)
    upload_file_obj.file.seek(0)  # 回到开头以便后续流式写入
    detected = filetype.guess(header)
    if detected is None:
        # 未知类型：可能是纯文本/CSV 等无魔数文件，退回到扩展名白名单
        ext = os.path.splitext(upload_file_obj.filename or "")[1].lower()
        if ext not in (".txt", ".csv", ".json", ".xml"):
            raise AppException(ErrorCode.BAD_REQUEST, f"无法识别文件类型，请上传支持的格式")
    elif detected.mime not in settings.allowed_mime_types_list:
        raise AppException(ErrorCode.BAD_REQUEST, f"不支持的文件类型: {detected.mime}（检测到真实类型与声明不符）")

    # 获取实例名称和节点信息
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == task.instance_id))).scalar_one()
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one()

    # 生成唯一文件名
    ext = os.path.splitext(upload_file_obj.filename or "file")[1] or ""
    stored_name = f"{uuid.uuid4().hex}{ext}"

    # 创建存储目录（根据模板类型分目录，有文件夹时存入子目录）
    archive_subdir = settings.get_archive_dir(inst.template_type or "project")
    if folder_name:
        archive_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, inst.name, folder_name)
        file_path_rel = os.path.join(archive_subdir, inst.name, folder_name, stored_name)
    else:
        archive_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, inst.name)
        file_path_rel = os.path.join(archive_subdir, inst.name, stored_name)
    os.makedirs(archive_dir, exist_ok=True)

    # 流式写入物理文件（分块读 + 异步写，避免大文件全量加载到内存）
    file_path = os.path.join(archive_dir, stored_name)
    import aiofiles
    async with aiofiles.open(file_path, "wb") as f:
        while True:
            chunk = upload_file_obj.file.read(64 * 1024)  # 64KB 分块
            if not chunk:
                break
            await f.write(chunk)

    # 创建 File 记录（失败时清理物理文件，防止孤儿文件残留）
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
    try:
        db.add(file_record)
        await db.flush()
    except Exception:  # 安全网：任何 DB 异常都需清理已写入的物理文件，避免孤儿文件
        # DB 写入失败，清理已写入的物理文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

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
    abs_path = resolve_file_path(file_rec.file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)

    await db.delete(file_rec)
    await db.flush()
