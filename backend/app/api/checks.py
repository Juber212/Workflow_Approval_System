"""校验 API —— 校验列表、详情、通过、退回"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.check import CheckAction
from app.services import check_service
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["校验"])


@router.get("/checks")
async def get_checks(
    status: str | None = Query(None, description="校验状态筛选（默认 pending）"),
    keyword: str | None = Query(None, description="实例名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """我的校验列表 —— 默认筛选 pending"""
    result = await check_service.list_checks(
        db,
        checker_id=current_user.id,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(result)


@router.get("/checks/{check_id}")
async def get_check(
    check_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """校验详情 —— 含文件、校验进度"""
    detail = await check_service.get_check_detail(db, check_id, current_user.id)
    return ApiResponse.ok(detail)


@router.post("/checks/{check_id}/pass")
async def pass_check(
    check_id: int,
    data: CheckAction,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """校验通过 —— 全部通过后触发审批生成"""
    result = await check_service.pass_check(db, check_id, current_user.id, data.opinion, data.signatures)
    await db.commit()
    return ApiResponse.ok(result, message=result.get("message", "校验通过"))


@router.post("/checks/{check_id}/return")
async def return_check(
    check_id: int,
    data: CheckAction,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """校验退回 —— 退回负责人，删除当前轮文件"""
    result = await check_service.return_check(db, check_id, current_user.id, data.opinion or "")
    await db.commit()
    return ApiResponse.ok(result, message=result.get("message", "校验已退回"))
