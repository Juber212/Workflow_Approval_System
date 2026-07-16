"""节点预设 API —— CRUD"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user, CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.preset import PresetCreate, PresetUpdate
from app.services import preset_service

router = APIRouter(prefix="/api/v1", tags=["节点预设"])


@router.get("/node-presets")
async def get_presets(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的节点预设列表"""
    result = await preset_service.list_presets(db, current_user.id)
    return ApiResponse.ok(result)


@router.post("/node-presets")
async def create_preset(
    body: PresetCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """创建节点预设"""
    result = await preset_service.create_preset(db, body, current_user.id)
    await db.commit()
    return ApiResponse.ok(result, message="预设已创建")


@router.put("/node-presets/{preset_id}")
async def update_preset(
    preset_id: int,
    body: PresetUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """更新节点预设 —— 仅所有者可修改"""
    result = await preset_service.update_preset(db, preset_id, body, current_user.id)
    await db.commit()
    return ApiResponse.ok(result, message="预设已更新")


@router.delete("/node-presets/{preset_id}")
async def delete_preset(
    preset_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除节点预设 —— 仅所有者可删除"""
    await preset_service.delete_preset(db, preset_id, current_user.id)
    await db.commit()
    return ApiResponse.ok(message="预设已删除")
