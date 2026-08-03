"""补交文件服务"""

import logging
import os
import uuid

from fastapi import UploadFile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import (
    FlowInstance, InstanceNode,
    OperationLog, User,
    File,
)
from app.models.enums import UploadType
from app.schemas.instance import (
    NodeFileBrief,
    SupplementFileResponse,
)
from app.api.deps import CurrentUser

logger = logging.getLogger(__name__)


async def supplement_files(
    db: AsyncSession,
    instance_id: int,
    node_id: int,
    files: list[UploadFile],
    current_user: CurrentUser,
    folder_name: str | None = None,
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

    # ========== 4.5 校验补交文件夹规则（P1-9：白名单 + 必填）==========
    folders_config = node.file_folders or []
    if folders_config:
        # 白名单：folder_name 必须属于节点配置的文件夹分类
        valid_names = {(f.get("name") or "").strip() for f in folders_config if (f.get("name") or "").strip()}
        if not folder_name or folder_name not in valid_names:
            raise AppException(ErrorCode.BAD_REQUEST, "请选择正确的目标文件夹（节点配置的文件夹分类）")

        # 必填：连同历史文件统计，必填文件夹补交后必须非空
        history_files = (await db.execute(
            select(File).where(File.node_id == node_id, File.round == node.round)
        )).scalars().all()
        folder_counts: dict[str, int] = {}
        for f in history_files:
            fn = f.folder_name or ""
            folder_counts[fn] = folder_counts.get(fn, 0) + 1
        # 本次补交的文件全部进入 folder_name
        folder_counts[folder_name] = folder_counts.get(folder_name, 0) + len(files)
        for folder in folders_config:
            name = (folder.get("name") or "").strip()
            if not name:
                continue
            if folder.get("required") and folder_counts.get(name, 0) == 0:
                raise AppException(ErrorCode.BAD_REQUEST, f"文件夹「{name}」必须至少提交 1 个文件")
    elif folder_name:
        # 节点无文件夹分类配置，却传了 folder_name → 拒绝
        raise AppException(ErrorCode.BAD_REQUEST, "该节点无文件夹分类配置，无需指定文件夹")

    # ========== 5. 遍历上传文件 ==========
    file_records: list[File] = []
    written_files: list[str] = []  # 跟踪已写入的物理文件路径（DB失败时用于清理）
    archive_subdir = settings.get_archive_dir(instance.template_type or "project")
    archive_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, instance.name)
    os.makedirs(archive_dir, exist_ok=True)

    for upload_file_obj in files:
        # 5a. 校验文件类型（Client MIME 粗筛）
        if upload_file_obj.content_type not in settings.allowed_mime_types_list:
            raise AppException(
                ErrorCode.FILE_TYPE_UNSUPPORTED,
                f"不支持的文件类型: {upload_file_obj.content_type}（{upload_file_obj.filename}）",
            )

        # 5b. 流式校验文件大小（seek 到尾端避免全量读入内存）
        upload_file_obj.file.seek(0, 2)
        file_size_val = upload_file_obj.file.tell()
        upload_file_obj.file.seek(0)
        if file_size_val > settings.max_file_size_bytes:
            raise AppException(
                ErrorCode.FILE_TOO_LARGE,
                f"文件大小超过限制（最大 50MB）: {upload_file_obj.filename}",
            )

        # 5c. 魔数校验（防伪造 Content-Type，与 file_service.py 一致）
        import filetype
        ext = os.path.splitext(upload_file_obj.filename or "file")[1].lower()
        OFFICE_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".pdf", ".png", ".jpg", ".jpeg"}
        if ext not in OFFICE_EXTS:
            header = upload_file_obj.file.read(8192)
            upload_file_obj.file.seek(0)
            detected = filetype.guess(header)
            if detected is None:
                if ext not in (".txt", ".csv", ".json", ".xml"):
                    raise AppException(
                        ErrorCode.FILE_TYPE_UNSUPPORTED,
                        f"无法识别文件类型: {upload_file_obj.filename}，请上传支持的格式",
                    )
            elif detected.mime not in settings.allowed_mime_types_list:
                raise AppException(
                    ErrorCode.FILE_TYPE_UNSUPPORTED,
                    f"不支持的文件类型: {detected.mime}（检测到真实类型与声明不符）",
                )

        # 5d. 流式写入磁盘（分块读 + 写，避免大文件全量加载）
        ext = os.path.splitext(upload_file_obj.filename or "file")[1] or ""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(archive_dir, stored_name)

        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            while True:
                chunk = upload_file_obj.file.read(64 * 1024)  # 64KB 分块
                if not chunk:
                    break
                await f.write(chunk)

        # 5d. 创建 File 记录（task_id=NULL、upload_type=supplement）
        # P1-9：非 PDF 补交文件标记 pending 并写入后入转换队列，转换完成可在线预览
        is_pdf = upload_file_obj.content_type == "application/pdf"
        file_record = File(
            instance_id=instance_id,
            node_id=node_id,
            task_id=None,  # 补交不关联任务
            round=node.round,  # 使用节点完成时的轮次
            uploader_id=current_user.id,
            upload_type=UploadType.SUPPLEMENT,
            folder_name=folder_name,  # 补交文件所属文件夹（有分类的节点必选）
            original_name=upload_file_obj.filename or "unknown",
            stored_name=stored_name,
            file_path=os.path.join(archive_subdir, instance.name, stored_name),
            file_size=file_size_val,
            mime_type="application/pdf" if is_pdf else upload_file_obj.content_type,
            conversion_status="ready" if is_pdf else "pending",
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
                except OSError as e:
                    logger.warning(f"文件操作失败: {e}", exc_info=True)
                    pass
        raise

    # ========== 6.5 非 PDF 补交文件入转换队列（P1-9：转换完成后可在线预览）==========
    pending_files = [fr for fr in file_records if fr.conversion_status == "pending"]
    if pending_files:
        from app.services.pdf_queue import enqueue_file_conversion
        for fr in pending_files:
            try:
                await enqueue_file_conversion(fr.id, fr.file_path)
            except Exception:
                logger.warning(f"补交文件入转换队列失败: file_id={fr.id}", exc_info=True)

    log = OperationLog(
        instance_id=instance_id,
        operator_type="user",
        operator_id=current_user.id,
        node_id=node_id,
        operation_type="file_supplement",
        round=node.round,  # 记录当前节点轮次
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
                conversion_status=fr.conversion_status or "ready",
            )
            for fr in file_records
        ],
    )



