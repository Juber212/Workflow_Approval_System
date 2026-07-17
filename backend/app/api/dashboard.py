"""Dashboard API —— 首页看板全局统计（PRD §4）"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.schemas.common import ApiResponse
from app.services import dashboard_service

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard 全局统计数据（PRD §4.3-4.7）"""
    data = await dashboard_service.get_dashboard_stats(db)
    return ApiResponse.ok(data)
