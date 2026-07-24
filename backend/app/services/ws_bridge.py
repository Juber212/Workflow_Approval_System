"""Redis Pub/Sub → WebSocket 桥接

ARQ Worker 在独立进程中运行，无法直接操作 FastAPI WebSocket。
Worker 完成转换后发布 Redis Pub/Sub 消息，此桥接器订阅并转发到 WS。

生命周期：在 FastAPI lifespan 中启动，shutdown 时关闭。
"""

import asyncio
import json
import logging
import re

from app.core.redis import get_pubsub_redis, close_pubsub_redis
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

# 订阅的频道 pattern（匹配 conversion:user:{user_id}）
CHANNEL_PATTERN = "conversion:user:*"

# 用于解析用户 ID 的正则
_CHANNEL_RE = re.compile(r"^conversion:user:(\d+)$")

# 后台监听任务引用（供 lifespan 关闭）
_listener_task: asyncio.Task | None = None


def _extract_user_id(channel: str) -> int | None:
    """从 Redis 频道名中提取 user_id，如 conversion:user:42 → 42"""
    m = _CHANNEL_RE.match(channel)
    return int(m.group(1)) if m else None


async def start_bridge() -> None:
    """启动 Redis Pub/Sub 监听（在 lifespan startup 中调用）"""
    global _listener_task
    if _listener_task is not None and not _listener_task.done():
        return

    _listener_task = asyncio.create_task(_listen_loop())
    logger.info("WebSocket 桥接器已启动（订阅频道: %s）", CHANNEL_PATTERN)


async def stop_bridge() -> None:
    """关闭桥接器（在 lifespan shutdown 中调用）"""
    global _listener_task
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
    await close_pubsub_redis()
    logger.info("WebSocket 桥接器已关闭")


async def _listen_loop() -> None:
    """后台循环：监听 Redis Pub/Sub 并转发到 WebSocket"""
    while True:
        try:
            redis = await get_pubsub_redis()
            pubsub = redis.pubsub()
            await pubsub.psubscribe(CHANNEL_PATTERN)

            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue

                # 解析频道名获取 user_id
                channel = message.get("channel", "")
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8", errors="replace")
                user_id = _extract_user_id(channel)
                if user_id is None:
                    continue

                # 解析消息数据
                data_str = message.get("data", "")
                if isinstance(data_str, bytes):
                    data_str = data_str.decode("utf-8", errors="replace")
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    logger.warning("WebSocket 桥接收到无效 JSON: %s", data_str)
                    continue

                # 转发到 WebSocket（fire-and-forget）
                try:
                    await manager.send_to_user(user_id, data)
                except Exception:
                    logger.debug("WebSocket 转发失败: user_id=%d", user_id, exc_info=True)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.error("WebSocket 桥接器异常，5 秒后重连", exc_info=True)
            await asyncio.sleep(5)
