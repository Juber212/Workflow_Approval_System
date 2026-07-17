"""项目设计器 API —— 画布数据保存/加载 + 单节点/连线 CRUD"""

from fastapi import APIRouter, Depends, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.models import FlowTemplate
from app.services.designer_service import (
    save_design_data, add_node, update_node, delete_node, add_edge, delete_edge,
)
from app.api.deps import get_current_active_user, CurrentUser, require_manager, require_same_org

router = APIRouter(prefix="/api/v1", tags=["项目设计器"])


async def _check_template_ownership(db: AsyncSession, template_id: int, current_user: CurrentUser) -> int:
    """校验模板存在 + 当前用户是本所所长 → 返回模板所属组织 ID"""
    require_manager(current_user)
    org_id = (await db.execute(
        select(FlowTemplate.organization_id).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if org_id is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, org_id)
    return org_id


@router.put("/templates/{template_id}/design")
async def put_design_data(
    template_id: int,
    data: dict = Body(..., description="画布完整数据 { nodes: [...], edges: [...] }"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批量保存设计器内容 —— 仅本所所长可操作"""
    await _check_template_ownership(db, template_id, current_user)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    result = await save_design_data(db, template_id, nodes, edges)
    await db.commit()
    return ApiResponse.ok(result, message="设计器内容已保存")


# ==================== 单节点 CRUD ====================


@router.post("/templates/{template_id}/nodes")
async def post_node(
    template_id: int,
    data: dict = Body(..., description="节点属性"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """添加单个工作节点 —— 仅本所所长可操作"""
    await _check_template_ownership(db, template_id, current_user)
    result = await add_node(db, template_id, data)
    await db.commit()
    return ApiResponse.ok(result, message="节点已添加")


@router.put("/templates/{template_id}/nodes/{node_id}")
async def put_node(
    template_id: int, node_id: int,
    data: dict = Body(..., description="需更新的字段"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """更新单个节点 —— 仅本所所长可操作"""
    await _check_template_ownership(db, template_id, current_user)
    result = await update_node(db, node_id, data)
    await db.commit()
    return ApiResponse.ok(result, message="节点已更新")


@router.delete("/templates/{template_id}/nodes/{node_id}")
async def del_node(
    template_id: int, node_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除节点 —— 仅本所所长可操作"""
    await _check_template_ownership(db, template_id, current_user)
    await delete_node(db, node_id)
    await db.commit()
    return ApiResponse.ok(message="节点已删除")


# ==================== 单连线 CRUD ====================


@router.post("/templates/{template_id}/edges")
async def post_edge(
    template_id: int,
    data: dict = Body(..., description="连线属性 { source_node_id, target_node_id }"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """添加单条连线 —— 仅本所所长可操作"""
    await _check_template_ownership(db, template_id, current_user)
    source_node_id = data.get("source_node_id")
    target_node_id = data.get("target_node_id")
    if not source_node_id or not target_node_id:
        raise AppException(ErrorCode.VALIDATION_ERROR, "source_node_id 和 target_node_id 为必填字段")
    result = await add_edge(db, template_id, int(source_node_id), int(target_node_id))
    await db.commit()
    return ApiResponse.ok(result, message="连线已添加")


@router.delete("/templates/{template_id}/edges/{edge_id}")
async def del_edge(
    template_id: int, edge_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除单条连线 —— 仅本所所长可操作"""
    await _check_template_ownership(db, template_id, current_user)
    result = await delete_edge(db, edge_id, template_id)
    await db.commit()
    return ApiResponse.ok(result, message="连线已删除")
