"""方案 API —— 发起方案、方案列表、组织卡片"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.proposal import ProposalCreateRequest
from app.services import proposal_service
from app.api.deps import get_current_active_user, CurrentUser, require_manager, require_same_org

router = APIRouter(prefix="/api/v1", tags=["方案"])


@router.post("/proposals")
async def create_proposal(
    body: ProposalCreateRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """发起方案（仅所长，且只能为所属组织创建）"""
    require_manager(current_user)
    require_same_org(current_user, body.organization_id)
    result = await proposal_service.create_proposal(db, body, current_user)
    await db.commit()
    return ApiResponse.ok(result, message="方案已发起")


@router.get("/proposals")
async def list_proposals(
    organization_id: int | None = Query(None, description="组织筛选"),
    status: str | None = Query(None, description="状态筛选"),
    priority: str | None = Query(None, description="优先级筛选（urgent/high/normal/low）"),
    keyword: str | None = Query(None, description="名称搜索"),
    date_from: str | None = Query(None, description="创建时间起始（YYYY-MM-DD）"),
    date_to: str | None = Query(None, description="创建时间截止（YYYY-MM-DD）"),
    initiator_id: int | None = Query(None, description="发起人 ID 筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """方案列表（所有人可见，非管理员默认只看本所）"""
    # 组织隔离：非管理员默认只看本所数据
    if organization_id is None and not current_user.is_admin():
        organization_id = current_user.organization_id

    result = await proposal_service.list_proposals(
        db,
        organization_id=organization_id,
        status=status,
        priority=priority,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        initiator_id=initiator_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(result)


@router.get("/proposals/organizations")
async def get_proposal_organizations(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取有方案的组织卡片数据（含各状态数量 + 当前所属标记）"""
    result = await proposal_service.get_organization_summaries(db, current_user.organization_id)
    return ApiResponse.ok(result)
