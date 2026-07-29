"""系统配置 API —— 仅系统管理员可访问"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session_factory
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.config import ConfigItem, ConfigBatchUpdate
from app.services.config_service import config_service
from app.api.deps import get_current_active_user, CurrentUser, require_admin

router = APIRouter(prefix="/api/v1", tags=["系统配置"])


@router.get("/configs")
async def get_configs(
    current_user: CurrentUser = Depends(get_current_active_user),
):
    """系统配置列表 —— 从内存缓存读取"""
    require_admin(current_user)

    all_configs = config_service.get_all_items()
    items = [
        ConfigItem(
            id=cfg.id,
            config_key=cfg.config_key,
            config_value=cfg.config_value,
            description=cfg.description,
        ).model_dump()
        for cfg in all_configs
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
    require_admin(current_user)

    # 校验数字型配置值（签名坐标等不能为负数）
    _NUMBER_CONFIG_IDS = _get_number_config_ids()
    for item in data.items:
        if item.id in _NUMBER_CONFIG_IDS:
            try:
                val = int(item.config_value)
                if val < 0:
                    raise AppException(ErrorCode.BAD_REQUEST, f"配置项 #{item.id} 的值不能为负数")
            except ValueError:
                raise AppException(ErrorCode.BAD_REQUEST, f"配置项 #{item.id} 必须是整数")

    updates = {item.id: item.config_value for item in data.items}
    updated_keys = await config_service.update(async_session_factory, updates)

    return ApiResponse.ok({"updated": updated_keys}, message=f"已更新 {len(updated_keys)} 项配置")


def _get_number_config_ids() -> set[int]:
    """获取所有数字型配置的 ID（从缓存中按 key 匹配）"""
    number_keys = {
        'max_file_size_mb', 'pdf_signature_x', 'pdf_signature_y', 'pdf_signature_offset',
        'pdf_signature_max_width', 'pdf_signature_max_height',
        'pdf_signature_assignee_x', 'pdf_signature_assignee_y',
        'pdf_signature_checker_x', 'pdf_signature_checker_y',
        'pdf_signature_approver_x', 'pdf_signature_approver_y',
        'pdf_signature_endorser_x', 'pdf_signature_endorser_y',
        'default_time_limit_days', 'pdf_signature_page',
    }
    all_items = config_service.get_all_items()
    return {item.id for item in all_items if item.config_key in number_keys}
