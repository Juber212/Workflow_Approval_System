"""WebSocket 端点 —— 实时推送通知

认证方式：连接后首条消息发送 token（不在 URL 中传递，避免 token 泄露到日志）。
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点

    客户端连接后需立即发送认证消息：
    {"type": "auth", "token": "<jwt_token>"}

    服务端验证通过后，通过该连接实时推送通知。
    连接后 10 秒内未认证则自动断开。
    """
    await websocket.accept()

    # 等待客户端首条认证消息，超时 10 秒
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="认证超时，请重新连接")
        return
    except WebSocketDisconnect:
        return
    except Exception:
        logger.debug("WebSocket 认证阶段异常断开", exc_info=True)
        return

    # 解析认证消息
    try:
        msg = json.loads(raw)
        if msg.get("type") != "auth" or not msg.get("token"):
            await websocket.close(code=4001, reason="首条消息必须是认证信息")
            return
        token = msg["token"]
    except (json.JSONDecodeError, KeyError):
        await websocket.close(code=4001, reason="认证消息格式无效")
        return

    # 验证 token
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="token 无效或已过期")
        return

    user_id = int(payload.get("sub", 0))
    if not user_id:
        await websocket.close(code=4001, reason="token 中缺少用户标识")
        return

    await manager.connect(user_id, websocket)
    try:
        # 保持连接，接收后续消息（心跳等），等待客户端断开
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except Exception:
        logger.debug(f"WebSocket 异常断开: user_id={user_id}", exc_info=True)
    finally:
        manager.disconnect(user_id, websocket)
