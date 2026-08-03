"""文件服务 —— 上传、删除、PDF 转换"""
import logging
import os

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.utils.file_utils import resolve_file_path
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import File, Task, InstanceNode, FlowInstance
from app.models.enums import TaskStatus, UploadType

logger = logging.getLogger(__name__)


def _unique_stored_name(directory: str, original_name: str) -> str:
    """为原始文件名生成唯一存储名，同名时自动追加序号

    Args:
        directory: 目标存储目录
        original_name: 用户上传的原始文件名

    Returns:
        唯一的存储文件名，如 技术方案.docx / 技术方案 (1).docx
    """
    # 清理文件名中的路径分隔符，防止路径穿越
    base, ext = os.path.splitext(original_name)
    safe_base = base.replace("/", "_").replace("\\", "_")
    candidate = f"{safe_base}{ext}" if ext else safe_base
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        if ext:
            candidate = f"{safe_base} ({counter}){ext}"
        else:
            candidate = f"{safe_base} ({counter})"
        counter += 1
    return candidate


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
    # ⚠️ Office 文件（.docx/.xlsx）底层是 ZIP，filetype 库无法区分，改用扩展名校验
    import filetype
    ext = os.path.splitext(upload_file_obj.filename or "")[1].lower()
    OFFICE_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".pdf", ".png", ".jpg", ".jpeg"}

    if ext in OFFICE_EXTS:
        # 已知类型：跳过魔数检测，信任扩展名 + Content-Type 双重校验
        # filetype 库对 .docx/.xlsx 只能识别到 application/zip，能力不足
        pass
    else:
        header = upload_file_obj.file.read(8192)
        upload_file_obj.file.seek(0)  # 回到开头以便后续流式写入
        detected = filetype.guess(header)
        if detected is None:
            # 未知类型：可能是纯文本/CSV 等无魔数文件，退回到扩展名白名单
            if ext not in (".txt", ".csv", ".json", ".xml"):
                raise AppException(ErrorCode.BAD_REQUEST, f"无法识别文件类型，请上传支持的格式")
        elif detected.mime not in settings.allowed_mime_types_list:
            raise AppException(ErrorCode.BAD_REQUEST, f"不支持的文件类型: {detected.mime}（检测到真实类型与声明不符）")

    # 获取实例名称和节点信息
    inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == task.instance_id))).scalar_one_or_none()
    if inst is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联流程实例不存在")
    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

    # ===== P0-2 修复：folder_name 白名单 + 路径穿越防护 =====
    # folder_name 来自前端参数，若直接拼入存储路径可被传 ".." 实现目录穿越写盘
    if folder_name:
        # 1. 禁止路径分隔符与穿越段（folder_name 只允许普通文件夹名）
        if "/" in folder_name or "\\" in folder_name or ".." in folder_name:
            raise AppException(ErrorCode.BAD_REQUEST, "文件夹名称不合法：不能包含路径分隔符或 '..'")
        # 2. 节点配置了文件夹分类时，folder_name 必须属于配置列表
        folders_config = node.file_folders or []
        if folders_config:
            allowed_names = {
                f.get("name", "").strip() for f in folders_config
                if isinstance(f, dict) and f.get("name")
            }
            if folder_name.strip() not in allowed_names:
                raise AppException(ErrorCode.BAD_REQUEST, f"文件夹「{folder_name}」不在该节点的文件夹配置中")
        else:
            # 3. 节点未配置文件夹分类时不允许指定子目录（folder_name 仅在有分类的节点使用）
            raise AppException(ErrorCode.BAD_REQUEST, "该节点未配置文件夹分类，不可指定文件夹")

    # 创建存储目录（根据模板类型分目录，有文件夹时存入子目录）
    archive_subdir = settings.get_archive_dir(inst.template_type or "project")
    if folder_name:
        archive_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, inst.name, folder_name)
    else:
        archive_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, inst.name)

    # 纵深防御：断言目标目录位于 STORAGE_ROOT 内（防 symlink / 拼接穿越绕过上述校验）
    real_root = os.path.realpath(settings.STORAGE_ROOT)
    real_dir = os.path.realpath(archive_dir)
    if not (real_dir == real_root or real_dir.startswith(real_root + os.sep)):
        raise AppException(ErrorCode.BAD_REQUEST, "非法的存储目录")

    # 生成唯一文件名（用原始文件名，同名时自动追加序号）
    ext = os.path.splitext(upload_file_obj.filename or "file")[1] or ""
    stored_name = _unique_stored_name(archive_dir, upload_file_obj.filename or "file")

    # 文件相对路径（存入 DB）
    if folder_name:
        file_path_rel = os.path.join(archive_subdir, inst.name, folder_name, stored_name)
    else:
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
        file_size=file_size,
        mime_type="application/pdf" if upload_file_obj.content_type == "application/pdf" else upload_file_obj.content_type,
        # 非 PDF 文件上传后尚未转换（提交时才转 PDF），标记待转换，避免误显示 ready
        conversion_status="ready" if upload_file_obj.content_type == "application/pdf" else "pending",
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

    # 先删除 DB 记录，再删物理文件（避免事务回滚后物理文件丢失）
    await db.delete(file_rec)
    await db.flush()

    abs_path = resolve_file_path(file_rec.file_path)
    try:
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except OSError as e:
        # 物理文件删除失败 → 记录错误并报告，DB 记录已删，防止静默残留
        logger.error(f"物理文件删除失败，磁盘残留孤儿文件: {abs_path}，错误: {e}", exc_info=True)


async def batch_delete_files_with_physical(db: AsyncSession, files: list) -> list[str]:
    """批量删除文件：先 flush DB 记录，再删物理文件（防止事务回滚导致磁盘文件丢失但 DB 记录还在）

    返回删除失败的物理文件路径列表（供调用方决策是否重试或告警）
    """
    failed_paths: list[str] = []
    # 1. 批量删除 DB 记录
    for f in files:
        await db.delete(f)
    await db.flush()  # 先确保持久化，再删物理文件

    # 2. 事务已持久化，安全删除物理文件
    for f in files:
        abs_path = resolve_file_path(f.file_path)
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
        except OSError as e:
            logger.warning(f"物理文件删除失败: {abs_path}, err={e}", exc_info=True)
            failed_paths.append(abs_path)
    return failed_paths
