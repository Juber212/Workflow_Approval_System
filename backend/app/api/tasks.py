"""任务 API —— 待办列表、任务详情、提交、草稿保存、文件上传"""
import asyncio
from fastapi import APIRouter, Depends, Query, UploadFile, File as FastAPIFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.task import TaskSaveDraft, TaskSubmit
from app.services import task_service, file_service
from app.services.pdf_converter import convert_to_pdf
from app.api.deps import get_current_active_user, CurrentUser
from app.models import Task, InstanceNode, CheckRecord, File
from app.models.enums import TaskStatus, InstanceNodeStatus, CheckStatus
from sqlalchemy import select

router = APIRouter(prefix="/api/v1", tags=["任务"])


@router.get("/tasks")
async def get_tasks(
    status: str | None = Query(None, description="任务状态筛选"),
    keyword: str | None = Query(None, description="实例名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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
    """提交任务 —— PDF 转换 + 生成校验记录，进入 waiting_check"""
    from datetime import datetime

    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "任务不存在")
    if task.assignee_id != current_user.id:
        raise AppException(ErrorCode.FORBIDDEN, "仅任务负责人可提交")
    if task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise AppException(ErrorCode.FORBIDDEN, "当前状态不可提交")

    node = (await db.execute(select(InstanceNode).where(InstanceNode.id == task.node_id))).scalar_one()

    # 前置校验：require_file
    if node.require_file:
        files = (await db.execute(
            select(File).where(File.task_id == task_id, File.round == node.round)
        )).scalars().all()
        if not files:
            raise AppException(ErrorCode.BAD_REQUEST, "该节点要求必须上传文件")

    # 更新备注和提交时间
    if data.assignee_note:
        task.assignee_note = data.assignee_note
    now = datetime.now()
    task.submitted_at = now

    # PDF 转换（并发 + 限流）
    task_files = (await db.execute(
        select(File).where(File.task_id == task_id, File.round == node.round)
    )).scalars().all()

    convert_failed = False
    if task_files:
        tasks = []
        for f in task_files:
            abs_path = None
            # 尝试找到文件真实路径（基于 STORAGE_ROOT）
            import os
            from app.core.config import settings
            full_path = os.path.join(settings.STORAGE_ROOT, f.file_path)
            if os.path.exists(full_path):
                tasks.append(convert_to_pdf(full_path))

        if tasks:
            results = await asyncio.gather(*tasks)
            # 检查是否有失败
            for r in results:
                if r is None:
                    convert_failed = True
                    break

            # 更新文件记录：mime_type → application/pdf
            if not convert_failed:
                for f in task_files:
                    f.mime_type = "application/pdf"

    if convert_failed:
        await db.rollback()
        raise AppException(ErrorCode.INTERNAL_ERROR, "文件转换失败，请检查文件格式后重试")

    # 状态推进：Task → waiting_check、Node → waiting_check
    task.status = TaskStatus.WAITING_CHECK
    node.status = InstanceNodeStatus.WAITING_CHECK

    # 按 checkers 创建 CheckRecord
    checkers = node.checkers or []
    if checkers:
        for ch in checkers:
            checker_id = ch.get("user_id") if isinstance(ch, dict) else ch.user_id
            check_rec = CheckRecord(
                instance_id=task.instance_id,
                node_id=task.node_id,
                task_id=task_id,
                checker_id=checker_id,
                status=CheckStatus.PENDING,
            )
            db.add(check_rec)

    await db.commit()
    return ApiResponse.ok(message="任务已提交，等待校验")


@router.post("/tasks/{task_id}/files")
async def upload_task_file(
    task_id: int,
    file: UploadFile = FastAPIFile(...),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文件到任务"""
    result = await file_service.upload_file(db, task_id, file, current_user.id)
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
