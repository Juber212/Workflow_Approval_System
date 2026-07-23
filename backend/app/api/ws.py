"""WebSocket 端点 —— 实时推送通知"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点

    客户端需通过 URL 参数传递 token：
    ws://host/api/v1/ws?token=<jwt_token>

    连接成功后，服务端通过该连接实时推送通知。
    """
    # 从 query string 获取 token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="缺少 token 参数")
        return

    # 解析 token 获取 user_id
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
        # 保持连接，等待客户端断开
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug(f"WebSocket 异常断开: user_id={user_id}", exc_info=True)
    finally:
        manager.disconnect(user_id, websocket)
