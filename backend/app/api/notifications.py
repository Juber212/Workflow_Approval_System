"""通知 API —— 列表/未读数/已读/全部已读"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, CurrentUser
from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services import notification_service as ns

router = APIRouter(prefix="/api/v1", tags=["通知"])


@router.get("/notifications", summary="我的通知列表")
async def list_notifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的通知列表，按时间倒序"""
    result = await ns.list_notifications(db, user_id=current_user.id, page=page, page_size=page_size)
    return ApiResponse.ok(result)


@router.get("/notifications/unread-count", summary="未读通知数")
async def unread_count(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户未读通知数量"""
    result = await ns.get_unread_count(db, user_id=current_user.id)
    return ApiResponse.ok(result)


@router.put("/notifications/{notification_id}/read", summary="标记已读")
async def mark_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条通知为已读"""
    await ns.mark_read(db, notification_id=notification_id, user_id=current_user.id)
    return {"message": "已标记为已读"}


@router.put("/notifications/read-all", summary="全部已读")
async def mark_all_read(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """标记当前用户全部未读通知为已读"""
    await ns.mark_all_read(db, user_id=current_user.id)
    return {"message": "已全部标记为已读"}
