"""节点预设服务 —— CRUD + 人员姓名填充"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node_preset import NodePreset
from app.models.user import User
from app.schemas.preset import PresetCreate, PresetUpdate, PresetResponse, PresetListResponse
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode


async def list_presets(db: AsyncSession, user_id: int) -> PresetListResponse:
    """获取当前用户的预设列表（按 sort_order + 创建时间排序）"""
    count_stmt = select(func.count()).select_from(NodePreset).where(NodePreset.user_id == user_id)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(NodePreset)
        .where(NodePreset.user_id == user_id)
        .order_by(NodePreset.sort_order, NodePreset.created_at.desc())
    )
    result = await db.execute(stmt)
    presets = result.scalars().all()

    # 批量收集所有 user_id，一次性查询姓名
    name_map = await _batch_resolve_names(db, presets)

    items = [_preset_to_response(p, name_map) for p in presets]
    return PresetListResponse(items=items, total=total)


async def create_preset(db: AsyncSession, data: PresetCreate, user_id: int) -> PresetResponse:
    """创建预设"""
    preset = NodePreset(
        user_id=user_id,
        name=data.name,
        node_name=data.node_name,
        assignee_id=data.assignee_id,
        checkers=data.checkers,
        approvers=data.approvers,
        time_limit_days=data.time_limit_days,
        require_file=data.require_file,
    )
    db.add(preset)
    await db.flush()
    return await _preset_to_response_async(db, preset)


async def update_preset(db: AsyncSession, preset_id: int, data: PresetUpdate, user_id: int) -> PresetResponse:
    """更新预设 —— 仅所有者可修改"""
    preset = await _get_owned_preset(db, preset_id, user_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(preset, key, val)
    await db.flush()
    return await _preset_to_response_async(db, preset)


async def delete_preset(db: AsyncSession, preset_id: int, user_id: int) -> None:
    """删除预设 —— 仅所有者可删除"""
    preset = await _get_owned_preset(db, preset_id, user_id)
    await db.delete(preset)


async def _get_owned_preset(db: AsyncSession, preset_id: int, user_id: int) -> NodePreset:
    """获取预设并校验所有权"""
    stmt = select(NodePreset).where(NodePreset.id == preset_id)
    result = await db.execute(stmt)
    preset = result.scalar_one_or_none()
    if not preset:
        raise AppException(ErrorCode.NOT_FOUND, "预设不存在")
    if preset.user_id != user_id:
        raise AppException(ErrorCode.FORBIDDEN, "无权操作此预设")
    return preset


async def _preset_to_response_async(db: AsyncSession, preset: NodePreset) -> PresetResponse:
    """异步版：模型 → 响应（填充人员姓名）—— 用于创建/更新后返回单条"""
    name_map = await _batch_resolve_names(db, [preset])
    return _preset_to_response(preset, name_map)


async def _batch_resolve_names(db: AsyncSession, presets: list[NodePreset]) -> dict[int, str]:
    """批量查询预设中所有引用用户的姓名"""
    user_ids: set[int] = set()
    for preset in presets:
        if preset.assignee_id:
            user_ids.add(preset.assignee_id)
        for item in (preset.checkers or []):
            if isinstance(item, dict) and "user_id" in item:
                user_ids.add(item["user_id"])
        for item in (preset.approvers or []):
            if isinstance(item, dict) and "user_id" in item:
                user_ids.add(item["user_id"])

    name_map: dict[int, str] = {}
    if user_ids:
        user_stmt = select(User.id, User.real_name).where(User.id.in_(user_ids))
        user_result = await db.execute(user_stmt)
        for uid, name in user_result:
            name_map[uid] = name
    return name_map


def _preset_to_response(preset: NodePreset, name_map: dict[int, str]) -> PresetResponse:
    """模型 → PresetResponse（含人员姓名填充）—— 用于列表批量转换和单条构建"""
    return PresetResponse(
        id=preset.id,
        name=preset.name,
        node_name=preset.node_name,
        assignee_id=preset.assignee_id,
        assignee_name=name_map.get(preset.assignee_id) if preset.assignee_id else None,
        checkers=preset.checkers,
        checkers_names=_extract_names(preset.checkers, name_map),
        approvers=preset.approvers,
        approvers_names=_extract_names(preset.approvers, name_map),
        time_limit_days=preset.time_limit_days,
        require_file=preset.require_file,
        sort_order=preset.sort_order,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


def _extract_names(items: list[dict] | None, name_map: dict[int, str]) -> list[str]:
    """从 [{"user_id": N}] 列表提取姓名，保持与输入列表等长"""
    if not items:
        return []
    names = []
    for item in items:
        if isinstance(item, dict) and "user_id" in item:
            name = name_map.get(item["user_id"])
            names.append(name or "")  # None 时用空字符串占位，保持数组长度一致
    return names
