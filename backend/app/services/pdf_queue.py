"""PDF 转换任务队列 —— ARQ Job 定义 + 入队函数

ARQ Worker 从 Redis 队列中拿任务，在独立进程中转换文件。
FastAPI 端通过 enqueue 函数提交转换任务，不等待结果。

转换完成后通过 Redis Pub/Sub 通知 FastAPI → WebSocket → 前端。
"""

import asyncio
import json
import logging
import os

from arq import create_pool
from arq.connections import RedisSettings
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.redis import ARQ_REDIS_URL, get_pubsub_redis_url
from app.models.file import File
from app.utils.file_utils import resolve_file_path

logger = logging.getLogger(__name__)

# ARQ 连接池（FastAPI 端用于入队，惰性初始化）
_arq_pool = None
_arq_pool_lock = asyncio.Lock()  # 防并发重复创建


async def _get_arq_pool():
    """获取或创建 ARQ 连接池（asyncio.Lock 防并发重复创建）"""
    global _arq_pool
    if _arq_pool is None:
        async with _arq_pool_lock:
            # 双重检查：锁内再次确认未被并发创建
            if _arq_pool is None:
                _arq_pool = await create_pool(RedisSettings.from_dsn(ARQ_REDIS_URL))
    return _arq_pool


# ==================== 入队函数（FastAPI 端调用） ====================


async def enqueue_file_conversion(file_id: int, file_path: str) -> None:
    """将单个文件转换任务入队（不等待结果，fire-and-forget）"""
    pool = await _get_arq_pool()
    await pool.enqueue_job("convert_file_job", file_id, file_path)


async def enqueue_batch_conversion(files: list[dict], task_id: int, user_id: int) -> None:
    """批量入队转换任务，并在全部入队后注册一个聚合完成检查任务

    Args:
        files: [{"id": file_id, "file_path": file_path}, ...]
        task_id: 关联的任务 ID
        user_id: 文件上传者（转换完成后通知此人）
    """
    pool = await _get_arq_pool()
    file_ids = [f["id"] for f in files]

    # 逐个入队文件转换任务
    for f in files:
        await pool.enqueue_job("convert_file_job", f["id"], f["file_path"])

    # 注册聚合检查任务（延迟 2 秒执行，等转换任务跑完再检查状态）
    await pool.enqueue_job(
        "convert_all_files_job",
        file_ids,
        task_id,
        user_id,
        _defer_by=2,  # 延迟 2 秒
    )


# ==================== ARQ Job 定义（Worker 端执行） ====================


async def convert_file_job(ctx, file_id: int, file_path: str) -> dict:
    """ARQ 任务：转换单个文件为 PDF

    在 Worker 进程中执行，不阻塞 FastAPI 事件循环。
    """
    from app.services.pdf_converter import convert_to_pdf

    async with async_session_factory() as db:
        try:
            # 查询文件记录
            file = (await db.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
            if file is None:
                return {"file_id": file_id, "status": "not_found"}

            # 已是 PDF，直接标记 ready
            if file_path.lower().endswith(".pdf"):
                file.conversion_status = "ready"
                await db.commit()
                return {"file_id": file_id, "status": "ready"}

            # 更新状态为转换中
            file.conversion_status = "converting"
            await db.commit()

            # 执行转换
            full_path = resolve_file_path(file_path)
            if not os.path.exists(full_path):
                file.conversion_status = "failed"
                file.conversion_error = "源文件不存在"
                await db.commit()
                return {"file_id": file_id, "status": "failed", "error": "file not found"}

            result = await convert_to_pdf(full_path)

            if result:
                # 转换成功：更新路径和文件名（只改扩展名，保留原始文件名 base）
                # convert_to_pdf 已生成 同目录/同base.pdf，并删除了源文件
                file.file_path = os.path.splitext(file.file_path)[0] + ".pdf"
                file.stored_name = os.path.splitext(file.stored_name)[0] + ".pdf"
                file.mime_type = "application/pdf"
                file.conversion_status = "ready"
                file.conversion_error = None
                await db.commit()
                logger.info(f"[PDF转换] 完成: file_id={file_id}")
                return {"file_id": file_id, "status": "ready"}
            else:
                # 转换失败
                file.conversion_status = "failed"
                file.conversion_error = "文件格式转换失败，请检查文件是否损坏"
                await db.commit()
                logger.warning(f"[PDF转换] 失败: file_id={file_id}")
                return {"file_id": file_id, "status": "failed", "error": "conversion returned None"}

        except Exception as e:
            logger.error(f"[PDF转换] 异常: file_id={file_id}, err={e}", exc_info=True)
            # 尝试更新状态为失败
            try:
                file = (await db.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
                if file:
                    file.conversion_status = "failed"
                    file.conversion_error = str(e)[:500]
                    await db.commit()
            except Exception:
                pass
            return {"file_id": file_id, "status": "failed", "error": str(e)[:200]}


# 聚合检查最大重试次数（每次延迟 3 秒，约 60 秒兜底，对齐前端轮询超时）
# 防 convert_file_job 丢失/Worker 挂起时无限自重新入队
_CONVERT_ALL_MAX_ATTEMPTS = 20


async def convert_all_files_job(ctx, file_ids: list[int], task_id: int, user_id: int, attempt: int = 1) -> dict:
    """ARQ 聚合任务：检查所有文件是否转换完成，通过 Redis Pub/Sub 通知前端

    此任务在所有 convert_file_job 之后执行（带延迟），
    检查所有 file_ids 的状态，然后发布 Pub/Sub 消息。

    attempt（P1-15）：自重新入队次数，超限后把仍卡在 pending/converting 的
    文件标记 failed 并通知前端，避免无限重试消耗资源。
    """
    # 1. 先在 DB 事务内计算状态并 commit
    message: dict | None = None
    async with async_session_factory() as db:
        try:
            files = (await db.execute(select(File).where(File.id.in_(file_ids)))).scalars().all()

            # 统计状态
            pending = sum(1 for f in files if f.conversion_status in ("pending", "converting"))
            failed = sum(1 for f in files if f.conversion_status == "failed")
            ready = sum(1 for f in files if f.conversion_status == "ready")

            if pending > 0 and attempt < _CONVERT_ALL_MAX_ATTEMPTS:
                # 还有文件未完成，重新入队延迟检查（attempt+1）
                logger.info(f"[PDF转换] 聚合检查: {ready}/{len(file_ids)} ready, {pending} pending, 重新入队(第{attempt}次)")
                await ctx["redis"].enqueue_job(
                    "convert_all_files_job",
                    file_ids, task_id, user_id, attempt + 1,
                    _defer_by=3,
                )
                return {"task_id": task_id, "status": "checking", "ready": ready, "pending": pending}

            if pending > 0:
                # 重试超限（P1-15）：仍卡在 pending/converting 的文件标记失败，停止无限重试
                for f in files:
                    if f.conversion_status in ("pending", "converting"):
                        f.conversion_status = "failed"
                        f.conversion_error = "转换超时，请重新提交文件"
                await db.commit()
                failed = sum(1 for f in files if f.conversion_status == "failed")
                ready = sum(1 for f in files if f.conversion_status == "ready")
                logger.warning(f"[PDF转换] 聚合检查超时: task_id={task_id}, {pending} 个文件标记转换失败")

            # 全部完成（无论成功或失败）
            status = "all_ready" if failed == 0 else "partial_failed"
            message = {
                "type": "conversion_all_done",
                "task_id": task_id,
                "status": status,
                "total": len(file_ids),
                "ready": ready,
                "failed": failed,
            }
            logger.info(f"[PDF转换] 全部完成: task_id={task_id}, status={status}")

        except Exception as e:
            logger.error(f"[PDF转换] 聚合检查异常: task_id={task_id}, err={e}", exc_info=True)
            return {"task_id": task_id, "status": "error", "error": str(e)[:200]}

    # 2. DB 事务提交成功后，发送 Pub/Sub 通知前端（避免 commit 失败时前端已收到通知）
    if message:
        pubsub_redis = AsyncRedis.from_url(
            get_pubsub_redis_url(),
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await pubsub_redis.publish(
                f"conversion:user:{user_id}",
                json.dumps(message),
            )
        finally:
            await pubsub_redis.close()

    return message
