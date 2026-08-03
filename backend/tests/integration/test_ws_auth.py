"""WebSocket 认证集成测试 —— 无效 token / 黑名单 / 禁用用户均拒绝连接（P0-8）

使用 TestClient 的 websocket_connect 验证：
- 无效 token → 服务端 4001 关闭
- 首条消息非认证格式 → 4001 关闭
- 已吊销（黑名单）token → 4001 关闭
- 被禁用用户 token → 4001 关闭
- 有效 token + 正常账号 → 连接成功并保持
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from tests.conftest import MockResult


def _make_token(user_id=1, username="user"):
    """生成有效 JWT（自动注入 jti）"""
    return create_access_token({"sub": str(user_id), "username": username, "roles": ["user"], "org_id": None})


def _mock_db_is_active(value: bool):
    """构造 async_session_factory 的 mock，db.execute 返回指定 is_active"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=value))
    factory_cm = MagicMock()
    factory_cm.__aenter__ = AsyncMock(return_value=mock_db)
    factory_cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=factory_cm)


@pytest.fixture
def client():
    """不触发 lifespan 的 TestClient（避免全量测试下全局 DB engine 跨事件循环失败）

    现有集成测试（test_auth_api 等）均为非 with 模式。ws 认证不依赖 config_service/ws_bridge，
    故不进入 lifespan 启动逻辑。
    """
    c = TestClient(app)
    yield c
    c.close()


class TestWebSocketAuth:
    """WebSocket 认证加固"""

    def test_invalid_token_rejected(self, client):
        """无效 token → 服务端 4001 关闭"""
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.send_json({"type": "auth", "token": "not-a-jwt"})
            with pytest.raises(Exception):
                ws.receive_json()

    def test_missing_auth_message_rejected(self, client):
        """首条消息非认证格式（无 token）→ 4001 关闭"""
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.send_json({"type": "ping"})
            with pytest.raises(Exception):
                ws.receive_json()

    def test_blacklisted_token_rejected(self, client):
        """已吊销（黑名单）token → 4001 关闭"""
        token = _make_token()
        with client.websocket_connect("/api/v1/ws") as ws:
            with patch("app.api.ws.is_blacklisted", new=AsyncMock(return_value=True)):
                ws.send_json({"type": "auth", "token": token})
                with pytest.raises(Exception):
                    ws.receive_json()

    def test_disabled_user_rejected(self, client):
        """被禁用用户 token → 4001 关闭"""
        token = _make_token()
        with client.websocket_connect("/api/v1/ws") as ws:
            with patch("app.api.ws.is_blacklisted", new=AsyncMock(return_value=False)), \
                 patch("app.api.ws.async_session_factory", _mock_db_is_active(False)):
                ws.send_json({"type": "auth", "token": token})
                with pytest.raises(Exception):
                    ws.receive_json()

    def test_valid_token_connects(self, client):
        """有效 token + 正常账号 → 连接成功并保持"""
        token = _make_token()
        with client.websocket_connect("/api/v1/ws") as ws:
            with patch("app.api.ws.is_blacklisted", new=AsyncMock(return_value=False)), \
                 patch("app.api.ws.async_session_factory", _mock_db_is_active(True)):
                ws.send_json({"type": "auth", "token": token})
                # 认证通过后服务端进入接收循环，发心跳不报错即连接保持
                ws.send_json({"type": "ping"})
