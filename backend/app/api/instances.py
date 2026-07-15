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
    TerminateInstanceRequest,
    ChangePersonnelRequest,
    ChangePriorityRequest,
)
from app.services.instance_service import (
    create_instance,
    list_instances,
    get_instance_detail,
    terminate_instance,
    change_personnel,
    change_priority,
)

router = APIRouter(prefix="/api/v1", tags=["流程实例"])


@router.post("/instances")
async def launch_instance(
    body: CreateInstanceRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """发起流程实例 —— 从模板节点/连线复制生成实例快照"""

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


@router.get("/instances/my-initiated")
async def my_initiated_instances(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """我发起的流程 —— 所长查看自己发起的所有实例（PRD §7.5）"""
    from app.models import FlowInstance
    from sqlalchemy import select, func

    # 直接用简单查询，按发起时间倒序
    count_stmt = select(func.count()).select_from(FlowInstance).where(
        FlowInstance.initiator_id == current_user.id
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(FlowInstance)
        .where(FlowInstance.initiator_id == current_user.id)
        .order_by(FlowInstance.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    instances = result.scalars().all()

    items = [
        {
            "id": i.id, "name": i.name,
            "status": i.status, "archive_status": i.archive_status,
            "priority": i.priority, "initiated_at": i.initiated_at.isoformat() if i.initiated_at else None,
            "completed_at": i.completed_at.isoformat() if i.completed_at else None,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in instances
    ]
    return ApiResponse.ok({"items": items, "total": total, "page": page, "page_size": page_size})


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


@router.post("/instances/{instance_id}/terminate")
async def terminate_flow_instance(
    instance_id: int,
    body: TerminateInstanceRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """终止流程实例

    权限：仅发起人。任意未 terminated 状态均可终止（含 completed）。
    效果：级联关闭全部非终态 node/task/check/approval，物理删除全部文件，不可撤销。
    """
    result = await terminate_instance(db, instance_id, body.reason, current_user)
    await db.commit()

    return ApiResponse.ok(result, message="流程已终止")


@router.put("/instances/{instance_id}/nodes/{node_id}/personnel")
async def change_node_personnel(
    instance_id: int,
    node_id: int,
    body: ChangePersonnelRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """紧急换人 —— 更换运行中实例节点的负责人/校验人/审批人

    权限：仅发起人。仅未完成节点可修改。
    效果：不在新列表的 pending 校验/审批 → terminated，新人员生成对应记录，已完成的保留不动。
    """
    result = await change_personnel(db, instance_id, node_id, body, current_user)
    await db.commit()

    return ApiResponse.ok(result, message="人员更换成功")


@router.put("/instances/{instance_id}/priority")
async def change_instance_priority(
    instance_id: int,
    body: ChangePriorityRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """修改流程优先级

    权限：仅发起人。仅 running 状态可修改。
    """
    result = await change_priority(db, instance_id, body.priority, current_user)
    await db.commit()

    return ApiResponse.ok(result, message="优先级修改成功")
