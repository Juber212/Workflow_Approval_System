"""Redis 连接 —— FastAPI 端 Pub/Sub 订阅 + ARQ Worker 任务队列 + Token 黑名单

使用三个 DB 号隔离：
- DB 0: ARQ 任务队列
- DB 1: Pub/Sub 桥接（Worker → FastAPI → WebSocket）
- DB 2: Token 黑名单（jti → TTL 自动过期）
"""

import logging
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# ARQ 使用的 Redis 连接参数（在 worker.py 的 WorkerSettings 中引用）
ARQ_REDIS_URL = settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.REDIS_ARQ_DB}"

# Pub/Sub 桥接用的 Redis 客户端（FastAPI lifespan 中初始化）
_pubsub_redis: Redis | None = None

# Token 黑名单用的 Redis 客户端（惰性初始化，DB 2）
_token_blacklist_redis: Redis | None = None


def get_pubsub_redis_url() -> str:
    """返回 Pub/Sub 专用 Redis URL（DB 1）"""
    return settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.REDIS_PUBSUB_DB}"


def _get_token_blacklist_redis_url() -> str:
    """返回 Token 黑名单专用 Redis URL（DB 2）"""
    return settings.REDIS_URL.rsplit("/", 1)[0] + "/2"


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


async def get_token_blacklist_redis() -> Redis:
    """获取 Token 黑名单 Redis 客户端（惰性初始化，DB 2）

    P1-26：socket_connect_timeout/socket_timeout 各 1 秒 —— 黑名单中间件每个请求
    都查 Redis，若 Redis 挂起默认连接会阻塞数秒至数十秒拖垮全站；
    1 秒快速失败后走 is_blacklisted 的 except 分支放行请求。
    """
    global _token_blacklist_redis
    if _token_blacklist_redis is None:
        _token_blacklist_redis = Redis.from_url(
            _get_token_blacklist_redis_url(),
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,  # 连接建立 1 秒超时
            socket_timeout=1,          # 读写操作 1 秒超时
        )
    return _token_blacklist_redis


async def close_token_blacklist_redis() -> None:
    """关闭 Token 黑名单 Redis 连接"""
    global _token_blacklist_redis
    if _token_blacklist_redis is not None:
        await _token_blacklist_redis.close()
        _token_blacklist_redis = None
        logger.info("Redis Token 黑名单连接已关闭")
