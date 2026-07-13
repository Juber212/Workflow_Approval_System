"""流程实例 API —— 发起、查询、终止、换人、优先级"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user, CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.instance import CreateInstanceRequest, InstanceResponse
from app.services.instance_service import create_instance

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
