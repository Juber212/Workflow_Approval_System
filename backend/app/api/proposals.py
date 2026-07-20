"""方案 API —— 发起方案、方案列表、组织卡片"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.proposal import ProposalCreateRequest
from app.services import proposal_service
from app.api.deps import get_current_active_user, CurrentUser, require_manager

router = APIRouter(prefix="/api/v1", tags=["方案"])


@router.post("/proposals")
async def create_proposal(
    body: ProposalCreateRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """发起方案（仅所长）"""
    require_manager(current_user)
    result = await proposal_service.create_proposal(db, body, current_user)
    await db.commit()
    return ApiResponse.ok(result, message="方案已发起")


@router.get("/proposals")
async def list_proposals(
    organization_id: int | None = Query(None, description="组织筛选"),
    status: str | None = Query(None, description="状态筛选"),
    keyword: str | None = Query(None, description="名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """方案列表（所有人可见）"""
    result = await proposal_service.list_proposals(
        db,
        organization_id=organization_id,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(result)


@router.get("/proposals/organizations")
async def get_proposal_organizations(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取有方案的组织卡片数据（含各状态数量）"""
    result = await proposal_service.get_organization_summaries(db)
    return ApiResponse.ok(result)
