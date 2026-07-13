"""流程模板 API"""
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.services.template_service import (
    get_organization_summaries,
    list_templates,
    create_template,
    get_template_detail,
    update_template,
    delete_template,
    disable_template,
)
from app.api.deps import get_current_active_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["流程模板"])


@router.get("/templates/organizations")
async def get_orgs_for_template(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """组织选择页 → 展示组织卡片（含模板数+运行中实例数）"""
    summaries = await get_organization_summaries(db, is_active=True)
    return ApiResponse.ok([s.model_dump() for s in summaries])


@router.get("/templates")
async def get_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: int | None = Query(None, description="组织筛选"),
    status: str | None = Query(None, description="状态筛选"),
    keyword: str | None = Query(None, description="名称搜索"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """模板列表 —— 含权限标识（can_edit/can_publish/can_start）"""
    result = await list_templates(
        db,
        page=page,
        page_size=page_size,
        organization_id=organization_id,
        status=status,
        keyword=keyword,
        current_user_id=current_user.id,
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
    """模板详情 —— 含节点/连线/版本历史"""
    detail = await get_template_detail(db, template_id)
    return ApiResponse.ok(detail.model_dump())


@router.put("/templates/{template_id}")
async def put_template(
    template_id: int,
    data: TemplateUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """更新模板基本信息 —— 若修改名称且为已发布状态，自动触发硬修改（版本+1，回到 draft）"""
    tpl, is_hard = await update_template(db, template_id, data)
    await db.commit()

    if is_hard:
        return ApiResponse.ok(
            {"id": tpl.id, "name": tpl.name, "status": tpl.status, "current_version": tpl.current_version},
            message=f"名称变更为硬修改，模板已回到草稿（v{tpl.current_version}），请编辑后重新发布",
        )
    return ApiResponse.ok({"id": tpl.id, "name": tpl.name}, message="模板信息已更新")


@router.delete("/templates/{template_id}")
async def del_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除模板 —— 仅 draft 状态可删"""
    await delete_template(db, template_id)
    await db.commit()
    return ApiResponse.ok(message="模板已删除")


@router.put("/templates/{template_id}/nodes/{node_id}/soft-config")
async def put_node_soft_config(
    template_id: int,
    node_id: int,
    updates: dict = Body(..., description="软修改字段键值对"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """已发布模板节点软修改 —— 写入 soft_config_overrides，不产生新版本"""
    from app.services.version_service import apply_soft_config

    result = await apply_soft_config(db, template_id, node_id, updates)
    await db.commit()
    return ApiResponse.ok(result, message="软配置已更新")


@router.post("/templates/{template_id}/publish")
async def post_publish_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """发布模板 —— 校验 + 快照 + 版本递增"""
    from app.services.version_service import publish_template

    version = await publish_template(db, template_id, current_user.id)
    await db.commit()
    return ApiResponse.ok(
        {
            "version_id": version.id,
            "version_number": version.version_number,
            "node_count": len(version.nodes_snapshot),
            "edge_count": len(version.edges_snapshot),
        },
        message=f"模板已发布（v{version.version_number}）",
    )


@router.get("/templates/{template_id}/versions/{version_id}")
async def get_version_detail(
    template_id: int,
    version_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查看指定版本完整快照 —— 节点配置 + 连线关系 + 软配置覆盖层"""
    from app.services.version_service import get_version_detail as _get_version_detail

    detail = await _get_version_detail(db, template_id, version_id)
    return ApiResponse.ok(detail.model_dump())


@router.post("/templates/{template_id}/disable")
async def post_disable_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """停用已发布模板 —— 停用后不可再发起新实例，运行中实例不受影响"""
    tpl = await disable_template(db, template_id)
    await db.commit()
    return ApiResponse.ok({"id": tpl.id, "status": tpl.status}, message="模板已停用")


@router.post("/templates/{template_id}/new-version")
async def post_new_version(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """从已发布/已停用模板创建新草稿版本 —— 复制当前节点和连线，状态回到 draft"""
    from app.services.version_service import create_new_version

    tpl = await create_new_version(db, template_id, current_user.id)
    await db.commit()
    return ApiResponse.ok({"id": tpl.id, "status": tpl.status, "current_version": tpl.current_version}, message="新版本草稿已创建，请编辑后重新发布")

