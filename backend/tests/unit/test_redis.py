"""Redis 连接配置单元测试 —— 黑名单连接超时参数 + 惰性单例"""

import pytest
from unittest.mock import patch

import app.core.redis as redis_mod
from app.core.redis import get_token_blacklist_redis


class TestTokenBlacklistRedis:
    """Token 黑名单 Redis 连接（P1-26）"""

    async def _reset(self):
        """重置惰性单例（mock 环境无真实连接，直接清空即可）"""
        redis_mod._token_blacklist_redis = None

    @pytest.fixture(autouse=True)
    async def _cleanup_after_test(self):
        """每个测试结束后清空全局惰性单例，防止 mock 的 fake Redis 泄漏污染后续测试

        health 探活等真实代码会读取该全局：若残留普通 object()，
        get_token_blacklist_redis() 直接返回它、ping 报错被误判为 Redis down。
        """
        yield
        await self._reset()

    @pytest.mark.asyncio
    async def test_connection_has_short_timeouts(self):
        """黑名单连接必须带 1 秒连接/读写超时（P1-26，Redis 不可用时中间件快速失败）"""
        await self._reset()
        fake_redis = object()
        with patch("app.core.redis.Redis.from_url", return_value=fake_redis) as mock_from_url:
            got = await get_token_blacklist_redis()
            assert got is fake_redis

        # from_url 调用参数必须包含 1 秒超时
        kwargs = mock_from_url.call_args.kwargs
        assert kwargs["socket_connect_timeout"] == 1
        assert kwargs["socket_timeout"] == 1

    @pytest.mark.asyncio
    async def test_lazy_singleton(self):
        """惰性单例：重复获取复用同一连接，不重复建立"""
        await self._reset()
        fake_redis = object()
        with patch("app.core.redis.Redis.from_url", return_value=fake_redis) as mock_from_url:
            first = await get_token_blacklist_redis()
            second = await get_token_blacklist_redis()
            assert first is second
            mock_from_url.assert_called_once()
