"""任务 API —— 待办列表、任务详情、提交、草稿保存、文件上传、文件下载"""
import asyncio
import os
from fastapi import APIRouter, Depends, Query, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.task import TaskSaveDraft, TaskSubmit
from app.services import task_service, file_service
from app.services.pdf_queue import enqueue_batch_conversion
from app.services.pdf_converter import convert_to_pdf
from app.services.document_service import (
    resolve_template_variables, fill_template, get_doc_template_abs_path,
)
from app.api.deps import get_current_active_user, CurrentUser
from app.models import Task, InstanceNode, File, DocumentTemplate, FlowInstance, TemplateDocumentLink
from app.models.enums import TaskStatus
from sqlalchemy import select
from urllib.parse import quote

router = APIRouter(prefix="/api/v1", tags=["任务"])


@router.get("/tasks")
async def get_tasks(
    status: str | None = Query(None, description="任务状态筛选"),
    keyword: str | None = Query(None, description="实例名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: str | None = Query(None, description="实例类型：project / proposal"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """我的待办列表 —— 按 deadline 排序，逾期优先"""
    result = await task_service.list_tasks(
        db,
        assignee_id=current_user.id,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
        instance_type=type,
    )
    return ApiResponse.ok(result)


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """任务详情 —— 含文件/校验/审批进度"""
    detail = await task_service.get_task_detail(db, task_id, current_user.id)
    return ApiResponse.ok(detail)


@router.put("/tasks/{task_id}")
async def save_task_draft(
    task_id: int,
    data: TaskSaveDraft,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """保存草稿 —— 更新负责人备注"""
    await task_service.save_draft(db, task_id, current_user.id, data.assignee_note)
    await db.commit()
    return ApiResponse.ok(message="草稿已保存")


@router.post("/tasks/{task_id}/submit")
async def submit_task(
    task_id: int,
    data: TaskSubmit,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """提交任务 —— PDF 转换 + 签批 + 生成校验/审批记录"""
    result = await task_service.submit_task(db, task_id, current_user.id, data)
    await db.commit()
    return ApiResponse.ok(message=result["message"])


@router.post("/tasks/{task_id}/prepare-sign")
async def prepare_sign(
    task_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """预提交：将文件转换任务入队，立即返回（50+ 并发优化）

    改造前：同步转换所有文件为 PDF（阻塞 5-30 秒），转换完成后返回 PDF 列表。
    改造后：将转换任务入队 ARQ，立即返回 conversion_pending=true，
    前端等待 WebSocket 通知或轮询 status 端点。
    """
    import os
    from datetime import datetime

    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user.id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可操作")
    if task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise AppException(ErrorCode.FORBIDDEN, "当前状态不可操作")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one()

    # 查询所有文件
    task_files = (await db.execute(
        select(File).where(File.task_id == task_id, File.round == node.round)
    )).scalars().all()

    conversion_pending = False
    file_ids: list[int] = []

    if task_files:
        # 分类：PDF 直接 ready，非 PDF 标记 pending 并入队
        to_convert: list[dict] = []
        for f in task_files:
            full_path = os.path.join(settings.STORAGE_ROOT, f.file_path)
            if f.file_path.lower().endswith(".pdf") and os.path.exists(full_path):
                # 已是 PDF，无需转换
                f.conversion_status = "ready"
            elif os.path.exists(full_path):
                # 需要转换的文件：标记 pending，准备入队
                f.conversion_status = "pending"
                to_convert.append({"id": f.id, "file_path": f.file_path})
                conversion_pending = True
            file_ids.append(f.id)

        await db.commit()

        # 入队异步转换（不等待结果）
        if to_convert:
            await enqueue_batch_conversion(to_convert, task_id, current_user.id)
    else:
        await db.commit()

    # 返回当前文件列表和转换状态
    updated_files = (await db.execute(
        select(File).where(File.task_id == task_id, File.round == node.round)
    )).scalars().all()

    return ApiResponse.ok({
        "files": [
            {
                "id": f.id,
                "original_name": f.original_name,
                "mime_type": f.mime_type,
                "conversion_status": f.conversion_status,
                "url": f"/api/v1/files/{f.id}/download",
            }
            for f in updated_files
        ],
        "conversion_pending": conversion_pending,
        "file_ids": [f.id for f in updated_files],
    })


@router.get("/tasks/{task_id}/files/status")
async def get_files_conversion_status(
    task_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查询任务文件的转换状态（前端轮询兜底）

    当 WebSocket 未收到 conversion_all_done 消息时，前端每 2 秒轮询此端点。
    返回文件列表及各自状态，前端根据状态决定是否打开签批弹框。
    """
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user.id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可操作")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one()

    task_files = (await db.execute(
        select(File).where(File.task_id == task_id, File.round == node.round)
    )).scalars().all()

    all_ready = all(f.conversion_status == "ready" for f in task_files)
    has_failed = any(f.conversion_status == "failed" for f in task_files)

    return ApiResponse.ok({
        "files": [
            {
                "id": f.id,
                "original_name": f.original_name,
                "conversion_status": f.conversion_status,
                "conversion_error": f.conversion_error,
            }
            for f in task_files
        ],
        "all_ready": all_ready,
        "has_failed": has_failed,
    })


@router.post("/tasks/{task_id}/files")
async def upload_task_file(
    task_id: int,
    file: UploadFile = FastAPIFile(...),
    folder_name: str | None = Query(None, description="文件夹名称"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文件到任务 —— 支持文件夹分组"""
    result = await file_service.upload_file(db, task_id, file, current_user.id, folder_name)
    await db.commit()
    return ApiResponse.ok(result, message="文件上传成功")


@router.delete("/tasks/{task_id}/files/{file_id}")
async def delete_task_file(
    task_id: int,
    file_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除任务文件"""
    await file_service.delete_file(db, task_id, file_id, current_user.id)
    await db.commit()
    return ApiResponse.ok(message="文件已删除")


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """下载/预览文件 —— 返回文件流，支持 PDF 内联预览和其他格式下载"""
    from urllib.parse import quote

    f = (await db.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
    if f is None:
        raise AppException(ErrorCode.NOT_FOUND, "文件不存在")

    # 归属校验：检查文件所属实例的组织是否与当前用户组织一致（管理员除外）
    if "system_admin" not in current_user.roles and f.instance_id:
        inst = (await db.execute(
            select(FlowInstance).where(FlowInstance.id == f.instance_id)
        )).scalar_one_or_none()
        if inst is None or inst.organization_id != current_user.organization_id:
            raise AppException(ErrorCode.FORBIDDEN, "无权访问此文件")

    # 拼接完整路径
    full_path = os.path.join(settings.STORAGE_ROOT, f.file_path)
    if not os.path.exists(full_path):
        raise AppException(ErrorCode.NOT_FOUND, "文件已被删除或不存在于磁盘")

    # 确定 MIME 类型和预览模式
    mime = f.mime_type or "application/octet-stream"
    inline_types = ("application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp")

    # RFC 5987 编码文件名：只编码名称部分，保留扩展名点号
    name_part, ext = os.path.splitext(f.original_name)
    encoded = quote(name_part, safe='') + ext  # 例: %E6%8A%A5%E5%91%8A.pdf
    ascii_fallback = f"file{ext}"              # ASCII 兜底: file.pdf

    disp = "inline" if mime in inline_types else "attachment"
    return FileResponse(
        path=full_path,
        media_type=mime,
        filename=f.original_name,
        headers={
            "Content-Disposition": (
                f'{disp}; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{encoded}"
            ),
        },
    )


@router.get("/tasks/{task_id}/document-templates")
async def list_task_document_templates(
    task_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取任务可用的文件模板列表 —— 通过中间表查找流程模板关联的文件模板"""
    from app.schemas.template import DocTemplateItem, DocTemplateListResponse

    # 校验 Task 存在且当前用户有权访问
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user.id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可查看")

    # 通过实例获取 template_id，再通过中间表查关联的文档模板
    instance = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == task.instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "流程实例不存在")

    # 优先使用实例级配置，为空则继承模板关联
    doc_ids = instance.doc_template_ids
    if doc_ids:
        docs = (await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.id.in_(doc_ids)
            ).order_by(DocumentTemplate.created_at.desc())
        )).scalars().all()
    else:
        docs = (await db.execute(
            select(DocumentTemplate).join(
                TemplateDocumentLink, TemplateDocumentLink.document_id == DocumentTemplate.id
            ).where(
                TemplateDocumentLink.template_id == instance.template_id,
            ).order_by(DocumentTemplate.created_at.desc())
        )).scalars().all()

    items = [
        {
            "id": d.id, "name": d.name, "original_name": d.original_name,
            "file_size": d.file_size, "file_type": d.file_type,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]

    return ApiResponse.ok({"items": items})


@router.get("/tasks/{task_id}/document-templates/{doc_id}/download")
async def download_document_template(
    task_id: int,
    doc_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """下载文件模板 —— 系统自动替换 {{占位符}} 为实例实际值

    支持 .docx（Word）和 .xlsx（Excel）格式。
    变量替换在内存中完成，不修改原模板文件。
    """
    from fastapi.responses import Response

    # 1. 校验 Task 存在且当前用户有权访问
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user.id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可下载模板")

    # 2. 查文档模板
    doc = (await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == doc_id)
    )).scalar_one_or_none()
    if doc is None:
        raise AppException(ErrorCode.NOT_FOUND, "文件模板不存在")

    # 3. 查模板是否通过中间表关联到此 Task 对应的流程模板
    instance = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == task.instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "流程实例不存在")

    link = (await db.execute(
        select(TemplateDocumentLink).where(
            TemplateDocumentLink.template_id == instance.template_id,
            TemplateDocumentLink.document_id == doc_id,
        )
    )).scalar_one_or_none()
    if link is None:
        raise AppException(ErrorCode.FORBIDDEN, "该文件模板未关联到此项目")

    # 4. 解析变量 → 实际值
    replacements = await resolve_template_variables(db, doc_id, task_id)

    # 5. 加载模板文件 → 替换 → 返回内存流
    abs_path = get_doc_template_abs_path(doc)
    if not os.path.exists(abs_path):
        raise AppException(ErrorCode.NOT_FOUND, "模板文件不存在于磁盘")

    try:
        output = fill_template(abs_path, doc.file_type, replacements)
    except Exception as e:
        logger = __import__('logging').getLogger(__name__)
        logger.warning(f"[文件模板] 下载失败: doc_id={doc_id}, task_id={task_id}, err={e}")
        raise AppException(ErrorCode.INTERNAL_ERROR, "模板文件处理失败，请检查模板格式")

    # 6. 确定 MIME 类型并返回
    mime_map = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    mime = mime_map.get(doc.file_type, "application/octet-stream")

    # 文件名：原始模板名（保留扩展名），URL 编码
    name_part, ext = os.path.splitext(doc.original_name)
    encoded = quote(name_part, safe='') + ext
    ascii_fallback = f"template{ext}"

    return Response(
        content=output.getvalue(),
        media_type=mime,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{encoded}"
            ),
        },
    )
