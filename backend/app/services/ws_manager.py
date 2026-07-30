"""WebSocket 连接管理器 —— 维护在线用户连接，支持按用户广播通知"""

import asyncio
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器（单例模式，asyncio.Lock 保护并发安全）

    维护 user_id → [WebSocket, ...] 映射，支持同一用户多端连接。
    """

    def __init__(self):
        # user_id → list of WebSocket connections
        self._connections: dict[int, list[WebSocket]] = {}
        self._lock = asyncio.Lock()  # 保护 _connections 的并发读写

    async def connect(self, user_id: int, websocket: WebSocket):
        """接受 WebSocket 连接并注册（兼容旧调用方）"""
        await websocket.accept()
        await self.register(user_id, websocket)

    async def register(self, user_id: int, websocket: WebSocket):
        """注册已接受的 WebSocket 连接（async lock 保护）"""
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            self._connections[user_id].append(websocket)
        logger.debug(f"WebSocket 连接: user_id={user_id}, total_connections={len(self._connections[user_id])}")

    async def disconnect(self, user_id: int, websocket: WebSocket):
        """断开连接并清理"""
        async with self._lock:
            if user_id in self._connections:
                try:
                    self._connections[user_id].remove(websocket)
                except ValueError:
                    pass
                if not self._connections[user_id]:
                    del self._connections[user_id]
        logger.debug(f"WebSocket 断开: user_id={user_id}")

    async def send_to_user(self, user_id: int, data: dict):
        """向指定用户的所有连接推送消息"""
        # snapshot 当前连接列表，避免迭代时被修改
        async with self._lock:
            connections = list(self._connections.get(user_id, []))
        if not connections:
            return
        dead: list[WebSocket] = []
        message = json.dumps(data, ensure_ascii=False)
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        # 清理断开的连接
        for ws in dead:
            await self.disconnect(user_id, ws)


# 全局单例
manager = ConnectionManager()
