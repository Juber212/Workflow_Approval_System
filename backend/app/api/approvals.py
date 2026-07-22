"""审批 API —— 审批列表、详情、通过、退回"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.approval import ApprovalAction
from app.services import approval_service
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["审批"])


@router.get("/approvals")
async def get_approvals(
    status: str | None = Query(None, description="审批状态筛选（默认 pending）"),
    keyword: str | None = Query(None, description="实例名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: str | None = Query(None, description="实例类型：project / proposal"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """我的审批列表"""
    result = await approval_service.list_approvals(
        db,
        approver_id=current_user.id,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
        instance_type=type,
    )
    return ApiResponse.ok(result)


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """审批详情 —— 含文件、校验/审批进度、驳回目标候选"""
    detail = await approval_service.get_approval_detail(db, approval_id, current_user.id)
    return ApiResponse.ok(detail)


@router.post("/approvals/{approval_id}/approve")
async def approve(
    approval_id: int,
    data: ApprovalAction,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """审批通过 —— 签名 + 流程推进"""
    result = await approval_service.approve(
        db, approval_id, current_user.id, data.opinion,
        signatures=data.signatures,
        signature_x=data.signature_x,
        signature_y=data.signature_y,
        signature_page=data.signature_page,
    )
    await db.commit()
    return ApiResponse.ok(result, message=result.get("message", "审批通过"))


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: int,
    data: ApprovalAction,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """审批退回 —— 中间节点退回负责人 / 结束节点总驳回"""
    result = await approval_service.reject(
        db, approval_id, current_user.id,
        data.opinion or "", data.target_node_id,
    )
    await db.commit()
    return ApiResponse.ok(result, message=result.get("message", "审批已退回"))
