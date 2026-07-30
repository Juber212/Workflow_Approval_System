"""删除实例服务"""

import logging
import os

from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.services.file_service import batch_delete_files_with_physical
from app.models import (
    FlowInstance, InstanceNode, InstanceEdge,
    OperationLog,
    Task, CheckRecord, Approval, Endorsement, File,
)

logger = logging.getLogger(__name__)


async def permanent_delete_instance(db: AsyncSession, instance_id: int) -> None:
    """永久删除项目 —— 级联清除所有关联数据（仅管理员可操作，仅已终止实例可删）

    删除顺序（避免外键约束冲突）：
    approval → check_record → file → task → instance_edge → operation_log → instance_node → flow_instance
    """
    # 查询实例（加锁防并发删除冲突）
    result = await db.execute(
        select(FlowInstance).where(FlowInstance.id == instance_id).with_for_update()
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "实例不存在")
    if instance.status != "terminated":
        raise AppException(ErrorCode.FORBIDDEN, "仅已终止的实例可永久删除")

    # 先获取所有关联 node ID（用于后续查询）
    node_ids_result = await db.execute(
        select(InstanceNode.id).where(InstanceNode.instance_id == instance_id)
    )
    node_ids = [row[0] for row in node_ids_result.all()]

    # 获取所有关联 task ID
    task_ids: list[int] = []
    if node_ids:
        task_ids_result = await db.execute(
            select(Task.id).where(Task.instance_id == instance_id)
        )
        task_ids = [row[0] for row in task_ids_result.all()]

    # 0. 删除批准记录（先于审批，避免外键冲突）
    await db.execute(sql_delete(Endorsement).where(Endorsement.instance_id == instance_id))

    # 1. 删除审批记录
    await db.execute(sql_delete(Approval).where(Approval.instance_id == instance_id))

    # 2. 删除校验记录
    await db.execute(sql_delete(CheckRecord).where(CheckRecord.instance_id == instance_id))

    # 3. 删除文件（先DB后物理文件，避免事务回滚后物理文件丢失）
    files_result = await db.execute(select(File).where(File.instance_id == instance_id))
    files = files_result.scalars().all()
    if files:
        await batch_delete_files_with_physical(db, list(files))

    # 4. 删除任务
    if task_ids:
        await db.execute(sql_delete(Task).where(Task.instance_id == instance_id))

    # 5. 删除实例连线
    await db.execute(sql_delete(InstanceEdge).where(InstanceEdge.instance_id == instance_id))

    # 6. 删除操作日志
    await db.execute(sql_delete(OperationLog).where(OperationLog.instance_id == instance_id))

    # 7. 删除实例节点
    await db.execute(sql_delete(InstanceNode).where(InstanceNode.instance_id == instance_id))

    # 8. 删除实例本身
    await db.delete(instance)
    await db.flush()

    # 9. 删除实例文件夹（文件已在步骤3删除，此处清理残留空目录）
    import shutil
    archive_subdir = settings.get_archive_dir(instance.template_type or "project")
    instance_dir = os.path.join(settings.STORAGE_ROOT, archive_subdir, instance.name)
    try:
        if os.path.isdir(instance_dir):
            shutil.rmtree(instance_dir)
    except OSError as e:
        logger.warning(f"文件操作失败: {e}", exc_info=True)
        pass  # 目录不存在或权限问题，忽略

