"""项目设计器 API —— 画布数据保存/加载 + 单节点/连线 CRUD"""

from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.designer_service import (
    save_design_data, add_node, update_node, delete_node, add_edge, delete_edge,
)
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["项目设计器"])


@router.put("/templates/{template_id}/design")
async def put_design_data(
    template_id: int,
    data: dict = Body(..., description="画布完整数据 { nodes: [...], edges: [...] }"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批量保存设计器内容 —— 节点坐标 + 连线"""
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
    """添加单个工作节点"""
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
    """更新单个节点"""
    result = await update_node(db, node_id, data)
    await db.commit()
    return ApiResponse.ok(result, message="节点已更新")


@router.delete("/templates/{template_id}/nodes/{node_id}")
async def del_node(
    template_id: int, node_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除节点 —— 系统节点不可删除"""
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
    """添加单条连线"""
    source_node_id = data.get("source_node_id")
    target_node_id = data.get("target_node_id")
    if not source_node_id or not target_node_id:
        from app.core.exceptions import AppException
        from app.core.error_codes import ErrorCode
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
    """删除单条连线"""
    result = await delete_edge(db, edge_id, template_id)
    await db.commit()
    return ApiResponse.ok(result, message="连线已删除")
