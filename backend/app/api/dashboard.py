"""Dashboard API —— 首页看板全局统计（PRD §4）"""
from fastapi import APIRouter, Depends, Query
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
    data = await dashboard_service.get_dashboard_stats(db, user_id=current_user.id)
    return ApiResponse.ok(data)


@router.get("/dashboard/trends")
async def get_dashboard_trends(
    granularity: str = Query(..., pattern="^(month|year)$"),
    category: str = Query(..., pattern="^(project|proposal)$"),
    year: int | None = Query(None, ge=2000, le=2100),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """发起/归档趋势 —— 月/年粒度对比（首页趋势卡片）

    Args:
        granularity: month | year
        category: project | proposal（口径与统计卡片一致）
        year: 仅 month 粒度使用；省略 = 近 12 个月，指定 = 该年 12 个月
    """
    data = await dashboard_service.get_flow_trends(db, granularity, category, year)
    return ApiResponse.ok(data)
