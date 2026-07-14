"""流程模板 API —— 简化版"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.services.template_service import (
    get_organization_summaries, list_templates, create_template,
    get_template_detail, update_template, delete_template,
)
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["流程模板"])


@router.get("/templates/organizations")
async def get_orgs_for_template(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """组织选择页 → 展示组织卡片"""
    summaries, total_instances = await get_organization_summaries(
        db, is_active=True, current_user_id=current_user.id
    )
    return ApiResponse.ok({
        "organizations": [s.model_dump() for s in summaries],
        "total_running_instances": total_instances,
    })


@router.get("/templates")
async def get_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: int | None = Query(None, description="组织筛选"),
    keyword: str | None = Query(None, description="名称搜索"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """模板列表"""
    result = await list_templates(
        db, page=page, page_size=page_size,
        organization_id=organization_id, keyword=keyword,
    )
    return ApiResponse.ok(result.model_dump())


@router.post("/templates")
async def post_template(
    data: TemplateCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """创建模板 —— 自动生成开始和结束节点"""
    tpl = await create_template(db, data, current_user.id)
    await db.commit()
    return ApiResponse.ok({"id": tpl.id, "name": tpl.name}, message="模板创建成功")


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """模板详情 —— 含节点/连线"""
    detail = await get_template_detail(db, template_id)
    return ApiResponse.ok(detail.model_dump())


@router.put("/templates/{template_id}")
async def put_template(
    template_id: int, data: TemplateUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """更新模板基本信息"""
    tpl = await update_template(db, template_id, data)
    await db.commit()
    return ApiResponse.ok({"id": tpl.id, "name": tpl.name}, message="模板信息已更新")


@router.delete("/templates/{template_id}")
async def del_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除模板"""
    await delete_template(db, template_id)
    await db.commit()
    return ApiResponse.ok(message="模板已删除")
