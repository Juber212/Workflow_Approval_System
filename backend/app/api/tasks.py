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
from app.services.notification_service import send_refresh_signal
from app.services.pdf_queue import enqueue_batch_conversion
from app.services.pdf_converter import convert_to_pdf
from app.services.document_service import (
    resolve_template_variables, fill_template, get_doc_template_abs_path,
    collect_instance_doc_ids,
)
from app.api.deps import get_current_active_user, CurrentUser
from app.models import Task, InstanceNode, File, DocumentTemplate, FlowInstance, TemplateDocumentLink, TemplateCategory, TemplateCategoryDocument
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
    # post-commit hook：commit 成功后才写入 PDF，避免磁盘与 DB 状态不一致
    from app.services.pdf_signature import apply_signatures_after_commit
    await apply_signatures_after_commit(result.get("_pending_sig_ids", []))
    await send_refresh_signal(current_user.id)
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

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

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

        # 先入队异步转换，再 commit —— 防止入队失败导致文件永久卡在 pending
        # 如果入队成功但 commit 失败，Worker 转换时会发现文件状态已回滚，安全跳过
        if to_convert:
            await enqueue_batch_conversion(to_convert, task_id, current_user.id)

        await db.commit()
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

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one_or_none()
    if node is None:
        raise AppException(ErrorCode.NOT_FOUND, "关联节点不存在")

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

    # 归属校验（产品口径 2026-08-10）：文件全员可见——与实例详情全员可见一致，
    # 任何登录用户可预览/下载（跨所查看/审阅场景；内网部署信任环境，产品确认放开）

    # 安全解析文件路径（防路径遍历攻击）
    from app.utils.file_utils import resolve_file_path, is_safe_path
    full_path = resolve_file_path(f.file_path)
    if not is_safe_path(f.file_path):
        raise AppException(ErrorCode.FORBIDDEN, "非法文件路径")
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
            # 文件会被签名/驳回/补交更新，禁用浏览器缓存——否则预览（pdfjs 同 URL）
            # 会拿到签名前的旧 PDF，出现「PDF 文件里有签名但在线预览没有」的假象
            "Cache-Control": "no-store",
        },
    )


@router.get("/tasks/{task_id}/document-templates")
async def list_task_document_templates(
    task_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取任务可用的文件模板列表（含模板包） —— 关联什么就显示什么"""
    # 校验 Task 存在且当前用户有权访问
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user.id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可查看")

    # 通过实例获取 template_id
    instance = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == task.instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "流程实例不存在")

    template_id = instance.template_id

    # ── 收集已关联的文档模板 ID（去重） ──
    linked_doc_ids: set[int] = set()
    linked_cat_ids: set[int] = set()

    # 实例级配置优先
    if instance.doc_template_ids:
        linked_doc_ids.update(instance.doc_template_ids)
    else:
        # 查中间表：单模板关联
        doc_links = (await db.execute(
            select(TemplateDocumentLink.document_id).where(
                TemplateDocumentLink.template_id == template_id,
                TemplateDocumentLink.document_id.isnot(None),
            )
        )).scalars().all()
        linked_doc_ids.update(d for d in doc_links if d is not None)

        # 查中间表：分类（包）关联
        cat_links = (await db.execute(
            select(TemplateDocumentLink.category_id).where(
                TemplateDocumentLink.template_id == template_id,
                TemplateDocumentLink.category_id.isnot(None),
            )
        )).scalars().all()
        linked_cat_ids.update(c for c in cat_links if c is not None)

    # ── 查询单个模板 ──
    templates: list[dict] = []
    if linked_doc_ids:
        docs = (await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.id.in_(list(linked_doc_ids))
            ).order_by(DocumentTemplate.created_at.desc())
        )).scalars().all()
        templates = [
            {
                "id": d.id, "name": d.name, "original_name": d.original_name,
                "file_size": d.file_size, "file_type": d.file_type,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]

    # ── 查询分类（包），含内部模板 ──
    categories: list[dict] = []
    if linked_cat_ids:
        cats = (await db.execute(
            select(TemplateCategory).where(
                TemplateCategory.id.in_(list(linked_cat_ids))
            ).order_by(TemplateCategory.created_at.desc())
        )).scalars().all()

        for cat in cats:
            # 查询包内模板
            cat_docs = (await db.execute(
                select(DocumentTemplate).join(
                    TemplateCategoryDocument, TemplateCategoryDocument.document_id == DocumentTemplate.id
                ).where(
                    TemplateCategoryDocument.category_id == cat.id,
                ).order_by(DocumentTemplate.created_at.desc())
            )).scalars().all()

            categories.append({
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "document_count": len(cat_docs),
                "documents": [
                    {
                        "id": d.id, "name": d.name, "original_name": d.original_name,
                        "file_size": d.file_size, "file_type": d.file_type,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                    }
                    for d in cat_docs
                ],
            })

    return ApiResponse.ok({"templates": templates, "categories": categories})




@router.get("/tasks/{task_id}/document-templates/download-zip")
async def download_task_template_zip(
    task_id: int,
    category_id: int = Query(..., description="模板包 ID"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """下载模板包 ZIP —— 填充包内所有模板的占位符后打包"""
    from fastapi.responses import StreamingResponse
    from app.services.category_service import batch_fill_and_zip

    # 校验 Task 权限
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user.id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可下载")

    # 查询包内模板 ID 列表
    cat_doc_rows = (await db.execute(
        select(TemplateCategoryDocument.document_id).where(
            TemplateCategoryDocument.category_id == category_id,
        )
    )).scalars().all()

    doc_ids = [d for d in cat_doc_rows if d is not None]
    if not doc_ids:
        raise AppException(ErrorCode.NOT_FOUND, "该包内无模板")

    # P1-2 修复：校验包内模板全部属于该实例的关联集（防跨实例枚举下载模板包）
    instance = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == task.instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "流程实例不存在")
    allowed_doc_ids = await collect_instance_doc_ids(db, instance)
    if any(d not in allowed_doc_ids for d in doc_ids):
        raise AppException(ErrorCode.FORBIDDEN, "模板包不属于该流程实例，无权下载")

    # 查询包名（用于 ZIP 文件名）
    cat = (await db.execute(
        select(TemplateCategory).where(TemplateCategory.id == category_id)
    )).scalar_one_or_none()
    zip_name = f"{cat.name}.zip" if cat else "templates.zip"

    # 填充 + 打包
    zip_buffer = await batch_fill_and_zip(db, doc_ids, task.instance_id, task.node_id)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename*=UTF-8\'\'{quote(zip_name)}',
        },
    )


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

    # P1-2 修复：校验模板属于该实例的关联集（防跨实例枚举下载文件模板）
    instance = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == task.instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "流程实例不存在")
    allowed_doc_ids = await collect_instance_doc_ids(db, instance)
    if doc_id not in allowed_doc_ids:
        raise AppException(ErrorCode.FORBIDDEN, "文件模板不属于该流程实例，无权下载")

    # 2. 查文档模板
    doc = (await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == doc_id)
    )).scalar_one_or_none()
    if doc is None:
        raise AppException(ErrorCode.NOT_FOUND, "文件模板不存在")

    # 3. 解析变量 → 实际值
    replacements = await resolve_template_variables(db, doc_id, task_id)

    # 4. 加载模板文件 → 替换 → 返回内存流
    abs_path = get_doc_template_abs_path(doc)
    if not os.path.exists(abs_path):
        raise AppException(ErrorCode.NOT_FOUND, "模板文件不存在于磁盘")

    try:
        output = fill_template(abs_path, doc.file_type, replacements)
    except Exception as e:
        logger = __import__('logging').getLogger(__name__)
        logger.warning(f"[文件模板] 下载失败: doc_id={doc_id}, task_id={task_id}, err={e}")
        raise AppException(ErrorCode.INTERNAL_ERROR, "模板文件处理失败，请检查模板格式")

    # 5. 确定 MIME 类型并返回
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
