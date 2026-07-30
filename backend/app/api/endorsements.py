"""批准 API —— 难度4级的最终审核环节"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user, CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.endorsement import EndorseRequest, EndorseRejectRequest
from app.services.endorsement_service import (
    list_endorsements, get_endorsement_detail, endorse, endorse_reject,
)
from app.services.notification_service import send_refresh_signal

router = APIRouter(prefix="/api/v1", tags=["批准"])


@router.get("/endorsements")
async def get_endorsements(
    type: str = Query("project", description="实例类型：project / proposal"),
    status: str | None = Query(None, description="批准状态筛选"),
    keyword: str | None = Query(None, description="实例名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """我的批准列表 —— 分页 + 搜索"""
    result = await list_endorsements(
        db, current_user.id,
        type_filter=type,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(data=result)


@router.get("/endorsements/{endorsement_id}")
async def get_endorsement(
    endorsement_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批准详情 —— 含文件、校验/审批进度、签名配置"""
    detail = await get_endorsement_detail(db, endorsement_id, current_user.id)
    return ApiResponse.ok(data=detail)


@router.post("/endorsements/{endorsement_id}/approve")
async def endorse_approve(
    endorsement_id: int,
    body: EndorseRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批准通过 —— 签名上PDF → 节点完成 → 推进下游"""
    result = await endorse(
        db, endorsement_id, current_user.id,
        opinion=body.opinion,
        signatures=body.signatures,
        signature_x=body.signature_x,
        signature_y=body.signature_y,
        signature_page=body.signature_page,
    )
    await db.commit()
    # post-commit hook：commit 成功后才写入 PDF，避免磁盘与 DB 状态不一致
    from app.services.pdf_signature import apply_signatures_after_commit
    await apply_signatures_after_commit(result.get("_pending_sig_ids", []))
    await send_refresh_signal(current_user.id)
    return ApiResponse.ok(data=result, message=result.get("message", "批准通过"))


@router.post("/endorsements/{endorsement_id}/reject")
async def endorse_reject_route(
    endorsement_id: int,
    body: EndorseRejectRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批准驳回 —— 节点回到运行状态，负责人重新处理"""
    result = await endorse_reject(db, endorsement_id, current_user.id, body.opinion)
    await db.commit()
    await send_refresh_signal(current_user.id)  # commit 后推送，保证前端查询到最新数据
    return ApiResponse.ok(data=result, message=result.get("message", "已驳回"))
