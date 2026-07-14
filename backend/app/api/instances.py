"""流程实例 API —— 发起、查询、终止、换人、优先级"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user, CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.instance import (
    CreateInstanceRequest,
    InstanceResponse,
    InstanceListResponse,
)
from app.services.instance_service import create_instance, list_instances, get_instance_detail

router = APIRouter(prefix="/api/v1", tags=["流程实例"])


@router.post("/instances")
async def launch_instance(
    body: CreateInstanceRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """发起流程实例

    权限：所长（manager），且模板状态为 published。
    后端处理：快照复制 → 配置合并（软覆盖 + 发起覆盖）→ 节点初始化 → 开始节点完成 → 激活首个工作节点。
    """
    # 权限校验：仅所长可发起实例
    if not current_user.is_manager():
        return ApiResponse.fail(40300, "仅所长可发起流程实例")

    result = await create_instance(db, body, current_user)
    await db.commit()

    return ApiResponse.ok(result, message="流程发起成功")


@router.get("/instances")
async def get_instances(
    organization_id: int | None = Query(None, description="按组织筛选"),
    status: str | None = Query(None, description="状态筛选，多选用逗号分隔（running,completed,terminated）"),
    priority: str | None = Query(None, description="优先级筛选（urgent/high/normal/low）"),
    keyword: str | None = Query(None, description="关键词模糊搜索实例名称"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查询流程实例列表

    支持按组织、状态（多选）、优先级筛选，支持实例名称模糊搜索。
    返回当前进度（当前节点序号/总节点数）和当前处理人姓名。
    """
    # 解析状态多选：running,completed → ["running", "completed"]
    status_list: list[str] | None = None
    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]

    result = await list_instances(
        db,
        organization_id=organization_id,
        status=status_list,
        priority=priority,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    return ApiResponse.ok(result)


@router.get("/instances/{instance_id}")
async def get_instance(
    instance_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查询流程实例详情

    返回完整聚合数据：基本信息 + 节点列表（含文件/校验/审批） + 进度 + 操作日志分页。
    """
    result = await get_instance_detail(db, instance_id)
    return ApiResponse.ok(result)
