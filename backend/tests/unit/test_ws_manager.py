"""ws_manager 单元测试 —— WebSocket 连接注册 / 强制下线（P0-8）"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.ws_manager import ConnectionManager


@pytest.fixture
def mgr():
    """每个测试独立的 ConnectionManager 实例（隔离全局单例）"""
    return ConnectionManager()


def _fake_ws():
    """构造一个可 await close / send_text 的假 WebSocket"""
    ws = MagicMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestConnectionManager:
    """连接注册与强制下线"""

    @pytest.mark.asyncio
    async def test_disconnect_user_closes_all_connections(self, mgr):
        """disconnect_user 关闭该用户全部连接并清空映射"""
        ws1, ws2 = _fake_ws(), _fake_ws()
        await mgr.register(1, ws1)
        await mgr.register(1, ws2)

        await mgr.disconnect_user(1)

        assert 1 not in mgr._connections
        ws1.close.assert_awaited_once()
        ws2.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_user_only_target_user(self, mgr):
        """只断开目标用户，不影响其他用户连接"""
        ws_a, ws_b = _fake_ws(), _fake_ws()
        await mgr.register(1, ws_a)
        await mgr.register(2, ws_b)

        await mgr.disconnect_user(1)

        assert 1 not in mgr._connections
        assert 2 in mgr._connections
        assert ws_b in mgr._connections[2]
        ws_b.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_user_unknown_user_no_error(self, mgr):
        """断开不存在的用户不抛异常"""
        await mgr.disconnect_user(999)

    @pytest.mark.asyncio
    async def test_disconnect_then_register_new_connection(self, mgr):
        """强制下线后用户可重新连接（新连接注册正常）"""
        ws = _fake_ws()
        await mgr.register(1, ws)
        await mgr.disconnect_user(1)

        ws_new = _fake_ws()
        await mgr.register(1, ws_new)
        assert ws_new in mgr._connections[1]
