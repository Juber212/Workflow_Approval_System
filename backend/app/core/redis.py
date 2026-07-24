"""Redis 连接 —— FastAPI 端 Pub/Sub 订阅 + ARQ Worker 任务队列

使用两个 DB 号隔离：
- DB 0: ARQ 任务队列
- DB 1: Pub/Sub 桥接（Worker → FastAPI → WebSocket）
"""

import logging
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# ARQ 使用的 Redis 连接参数（在 worker.py 的 WorkerSettings 中引用）
ARQ_REDIS_URL = settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.REDIS_ARQ_DB}"

# Pub/Sub 桥接用的 Redis 客户端（FastAPI lifespan 中初始化）
_pubsub_redis: Redis | None = None


def get_pubsub_redis_url() -> str:
    """返回 Pub/Sub 专用 Redis URL（DB 1）"""
    return settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.REDIS_PUBSUB_DB}"


async def get_pubsub_redis() -> Redis:
    """获取 Pub/Sub Redis 客户端（惰性初始化）"""
    global _pubsub_redis
    if _pubsub_redis is None:
        _pubsub_redis = Redis.from_url(
            get_pubsub_redis_url(),
            encoding="utf-8",
            decode_responses=True,
        )
    return _pubsub_redis


async def close_pubsub_redis() -> None:
    """关闭 Pub/Sub Redis 连接"""
    global _pubsub_redis
    if _pubsub_redis is not None:
        await _pubsub_redis.close()
        _pubsub_redis = None
        logger.info("Redis Pub/Sub 连接已关闭")
