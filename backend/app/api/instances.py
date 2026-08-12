"""项目 API —— 发起、查询、终止、换人、优先级、补交文件"""

from fastapi import APIRouter, Depends, Query, UploadFile, File as FastAPIFile, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import FlowTemplate
from app.api.deps import get_current_active_user, CurrentUser, require_manager, require_same_org, resolve_org_scope
from app.services.notification_service import send_refresh_signal
from app.schemas.common import ApiResponse
from app.schemas.instance import (
    CreateInstanceRequest,
    InstanceResponse,
    TerminateInstanceRequest,
    ChangePersonnelRequest,
    ChangePriorityRequest,
    SupplementFileResponse,
)
from app.services.instance import (
    create_instance,
    list_instances,
    get_instance_detail,
    terminate_instance,
    change_personnel,
    change_priority,
    supplement_files,
    permanent_delete_instance,
)

router = APIRouter(prefix="/api/v1", tags=["项目"])


@router.get("/instances/check-name")
async def check_instance_name(
    name: str = Query(..., min_length=1, description="待检测的项目名称"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_active_user),
):
    """检测项目名称是否已被使用（仅限本组织范围内，防跨组织信息泄露）"""
    from app.models import FlowInstance
    stmt = select(FlowInstance.id).where(FlowInstance.name == name.strip())
    # 非管理员仅检查本组织内的重名
    if "system_admin" not in current_user.roles:
        stmt = stmt.where(FlowInstance.organization_id == current_user.organization_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    return ApiResponse.ok({"exists": existing is not None})


@router.post("/instances")
async def launch_instance(
    body: CreateInstanceRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """发起项目 —— 仅本所所长可从本所模板发起"""

    # 校验权限：仅本所所长
    require_manager(current_user)
    tpl_org = (await db.execute(
        select(FlowTemplate.organization_id).where(FlowTemplate.id == body.template_id)
    )).scalar_one_or_none()
    if tpl_org is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl_org)

    result = await create_instance(db, body, current_user)
    await db.commit()
    return ApiResponse.ok(result, message="项目发起成功")


@router.get("/instances")
async def get_instances(
    organization_id: int | None = Query(None, description="按组织筛选"),
    status: str | None = Query(None, description="状态筛选，多选用逗号分隔（running,completed,terminated）"),
    priority: str | None = Query(None, description="优先级筛选（urgent/high/normal/low）"),
    keyword: str | None = Query(None, description="关键词模糊搜索项目名称"),
    date_from: str | None = Query(None, description="创建时间起始（YYYY-MM-DD）"),
    date_to: str | None = Query(None, description="创建时间截止（YYYY-MM-DD）"),
    initiator_id: int | None = Query(None, description="发起人 ID 筛选"),
    sort_by: str | None = Query(None, description="排序方式：priority 按优先级排序"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目列表

    支持按组织、状态（多选）、优先级筛选，支持实例名称模糊搜索。
    返回当前进度（当前节点序号/总节点数）和当前处理人姓名。
    """
    # 解析状态多选：running,completed → ["running", "completed"]
    status_list: list[str] | None = None
    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]

    organization_id = resolve_org_scope(current_user, organization_id)

    result = await list_instances(
        db,
        organization_id=organization_id,
        status=status_list,
        priority=priority,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        initiator_id=initiator_id,
        sort_by=sort_by,
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
    """查询项目详情

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
    """终止项目

    权限：仅发起人。任意未 terminated 状态均可终止（含 completed）。
    效果：级联关闭全部非终态 node/task/check/approval，物理删除全部文件，不可撤销。
    """
    result = await terminate_instance(db, instance_id, body.reason, current_user)
    await db.commit()
    await send_refresh_signal(current_user.id)  # commit 后推送，保证前端查询到最新数据
    return ApiResponse.ok(result, message="项目已终止")


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
    # 推送给发起人 + 所有被换掉的人员：他们的待办通知被清除，角标需实时刷新
    refresh_users = set(result.get("removed_users") or [])
    refresh_users.add(current_user.id)
    for uid in refresh_users:
        await send_refresh_signal(uid)  # commit 后推送，保证前端查询到最新数据
    return ApiResponse.ok(result, message="人员更换成功")


@router.put("/instances/{instance_id}/priority")
async def change_instance_priority(
    instance_id: int,
    body: ChangePriorityRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """修改项目优先级

    权限：仅发起人。仅 running 状态可修改。
    """
    result = await change_priority(db, instance_id, body.priority, current_user)
    await db.commit()

    return ApiResponse.ok(result, message="优先级修改成功")


@router.post("/instances/{instance_id}/nodes/{node_id}/supplement-files")
async def supplement_instance_files(
    instance_id: int,
    node_id: int,
    files: list[UploadFile] = FastAPIFile(...),
    folder_name: str | None = Form(None, description="补交文件所属文件夹名称（节点有文件分类时必填）"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """补交文件到已完成实例的已完成节点

    权限：实例发起人（所长）或该节点的历史负责人。
    限制：仅 completed 实例 + finished 节点（排除开始/结束）。
    文件支持：Word/Excel/图片/PDF，单文件 ≤50MB。
    不触发审批/校验/签名。
    """
    result = await supplement_files(db, instance_id, node_id, files, current_user, folder_name)
    await db.commit()
    return ApiResponse.ok(result, message="文件补交成功")


@router.delete("/instances/{instance_id}/permanent")
async def delete_instance_permanent(
    instance_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """永久删除项目

    权限：仅系统管理员。仅已终止(terminated)实例可删除。
    级联清除：审批记录、校验记录、文件(物理+DB)、任务、连线、操作日志、节点、实例。
    """
    if not current_user.is_admin():
        raise AppException(ErrorCode.FORBIDDEN, "仅系统管理员可永久删除项目")
    await permanent_delete_instance(db, instance_id)
    await db.commit()
    return ApiResponse.ok(message="项目已永久删除")
