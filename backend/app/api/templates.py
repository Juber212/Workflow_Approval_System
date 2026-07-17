"""项目模板 API —— 简化版"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.models import FlowTemplate
from app.services.template_service import (
    get_organization_summaries, list_templates, create_template,
    get_template_detail, update_template, delete_template,
)
from app.api.deps import get_current_active_user, CurrentUser, require_manager, require_same_org

router = APIRouter(prefix="/api/v1", tags=["项目模板"])


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
    """创建模板 —— 仅本所所长可创建"""
    require_manager(current_user)
    require_same_org(current_user, data.organization_id)
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
    """更新模板基本信息 —— 仅本所所长可编辑"""
    require_manager(current_user)
    tpl_org = (await db.execute(
        select(FlowTemplate.organization_id).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl_org is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl_org)
    tpl = await update_template(db, template_id, data)
    await db.commit()
    return ApiResponse.ok({"id": tpl.id, "name": tpl.name}, message="模板信息已更新")


@router.delete("/templates/{template_id}")
async def del_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除模板 —— 仅本所所长可删除"""
    require_manager(current_user)
    tpl_org = (await db.execute(
        select(FlowTemplate.organization_id).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl_org is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl_org)
    await delete_template(db, template_id)
    await db.commit()
    return ApiResponse.ok(message="模板已删除")
