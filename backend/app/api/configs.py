"""系统配置 API —— 仅系统管理员可访问"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session_factory
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.config import ConfigItem, ConfigBatchUpdate
from app.services.config_service import config_service
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["系统配置"])


def _require_admin(current_user: CurrentUser):
    if not current_user.is_admin():
        raise AppException(ErrorCode.FORBIDDEN, "仅系统管理员可执行此操作")


@router.get("/configs")
async def get_configs(
    current_user: CurrentUser = Depends(get_current_active_user),
):
    """系统配置列表 —— 从内存缓存读取"""
    _require_admin(current_user)

    all_configs = config_service._cache
    items = [
        ConfigItem(
            id=cfg.id,
            config_key=cfg.config_key,
            config_value=cfg.config_value,
            description=cfg.description,
        ).model_dump()
        for cfg in all_configs.values()
    ]
    # 按 id 排序
    items.sort(key=lambda x: x["id"])
    return ApiResponse.ok(items)


@router.put("/configs")
async def put_configs(
    data: ConfigBatchUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
):
    """批量更新系统配置 —— 写 DB → 刷新缓存"""
    _require_admin(current_user)

    updates = {item.id: item.config_value for item in data.items}
    updated_keys = await config_service.update(async_session_factory, updates)

    return ApiResponse.ok({"updated": updated_keys}, message=f"已更新 {len(updated_keys)} 项配置")
