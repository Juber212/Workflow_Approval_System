"""API 限流中间件单元测试"""

import time
import pytest
from unittest.mock import MagicMock, patch

from app.core.rate_limit import (
    _SlidingWindow,
    _get_limit_key,
    _get_limit_for_request,
    DEFAULT_LIMIT,
    STRICT_LIMIT,
    MEDIUM_LIMIT,
)


class TestSlidingWindow:
    """滑动窗口计数器测试"""

    def test_allow_within_limit(self):
        """窗口内请求数未达上限，应允许通过"""
        window = _SlidingWindow()
        for _ in range(10):
            assert window.is_allowed("test_key", 20) is True

    def test_deny_when_full(self):
        """窗口内请求数达到上限，应拒绝"""
        window = _SlidingWindow()
        # 填满窗口
        for _ in range(5):
            window.is_allowed("test_key", 5)
        # 第6次应拒绝
        assert window.is_allowed("test_key", 5) is False

    def test_independent_keys(self):
        """不同 key 的桶互相独立"""
        window = _SlidingWindow()
        # 填满 key_a
        for _ in range(3):
            window.is_allowed("key_a", 3)
        # key_b 不受影响
        assert window.is_allowed("key_b", 3) is True

    def test_cleanup_old_entries(self):
        """窗口滑动后，过期记录应被清理，允许新请求"""
        window = _SlidingWindow()
        # 用 monkeypatch 把时间倒推到 61 秒前
        real_time = time.time
        fake_now = real_time()

        class FakeTime:
            def __init__(self):
                self._offset = 0

            def __call__(self):
                return real_time() + self._offset

        fake_time = FakeTime()
        with patch("app.core.rate_limit.time.time", fake_time):
            # 在 t0 填满窗口
            for _ in range(3):
                window.is_allowed("key", 3)
            assert window.is_allowed("key", 3) is False

            # 时间推进 61 秒，旧记录过期
            fake_time._offset = 61
            assert window.is_allowed("key", 3) is True

    def test_key_cap_evicts_oldest(self):
        """key 超过上限 → 淘汰最早 key，桶数量受控（P1-25 防内存增长）"""
        window = _SlidingWindow()
        window._MAX_KEYS = 5  # 缩小上限便于测试
        for i in range(10):
            window.is_allowed(f"key_{i}", 100)
        assert len(window._buckets) <= 5

    def test_rate_limit_is_outermost_middleware(self):
        """限流中间件在最外层执行（P1-28：恶意高频请求先被内存层拦截）"""
        from app.main import app
        from app.core.rate_limit import RateLimitMiddleware
        from app.core.token_blacklist import TokenBlacklistMiddleware
        middleware = [m.cls for m in app.user_middleware]
        assert middleware[0] is RateLimitMiddleware  # 栈顶 = 最外层
        assert middleware.index(TokenBlacklistMiddleware) > middleware.index(RateLimitMiddleware)

    def test_periodic_sweep_removes_expired(self):
        """定期全量清理：过期 key 被移除（P1-25）"""
        window = _SlidingWindow()
        window._CLEAN_EVERY_CALLS = 3  # 每 3 次调用触发全量清理
        real_time = time.time
        fake_now = real_time()

        class FakeTime:
            def __init__(self):
                self._offset = 0

            def __call__(self):
                return real_time() + self._offset

        fake_time = FakeTime()
        with patch("app.core.rate_limit.time.time", fake_time):
            window.is_allowed("expired_key", 100)   # call 1
            fake_time._offset = 61                    # 61 秒后过期
            window.is_allowed("live_key", 100)        # call 2
            window.is_allowed("live_key", 100)        # call 3 → 触发全量清理
            assert "expired_key" not in window._buckets
            assert "live_key" in window._buckets


class TestGetLimitKey:
    """限流键获取测试"""

    def test_ip_key_no_auth_header(self):
        """无 Authorization 头 → 按 IP + method+path 限流"""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock(host="10.0.0.1")
        key = _get_limit_key(request, "POST", "/api/v1/instances")
        assert key == "ip:10.0.0.1:POST:/api/v1/instances"

    def test_ip_key_ignores_x_forwarded_for(self):
        """X-Forwarded-For 可伪造，不信任——一律用直连 IP（P1-25）"""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        request.client = MagicMock(host="10.0.0.1")
        key = _get_limit_key(request, "GET", "/api/v1/dashboard")
        assert key == "ip:10.0.0.1:GET:/api/v1/dashboard"

    @patch("app.core.rate_limit.decode_access_token")
    def test_user_key_with_valid_jwt(self, mock_decode):
        """有效 JWT → 按用户 ID + method+path 限流（操作独立计数）"""
        mock_decode.return_value = {"sub": "42", "username": "test", "roles": ["manager"]}
        request = MagicMock()
        request.headers = {"Authorization": "Bearer valid.token.here"}
        key = _get_limit_key(request, "POST", "/api/v1/instances")
        assert key == "user:42:POST:/api/v1/instances"

    @patch("app.core.rate_limit.decode_access_token")
    def test_admin_bypass(self, mock_decode):
        """系统管理员 → 唯一键，每次不同（旁路限流）"""
        mock_decode.return_value = {"sub": "1", "username": "admin", "roles": ["system_admin"]}
        request = MagicMock()
        request.headers = {"Authorization": "Bearer admin.token.here"}
        key1 = _get_limit_key(request, "POST", "/api/v1/instances")
        key2 = _get_limit_key(request, "POST", "/api/v1/instances")
        assert key1.startswith("admin:")
        assert key2.startswith("admin:")
        assert key1 != key2  # 每次请求唯一键，永不冲突

    @patch("app.core.rate_limit.decode_access_token")
    def test_ip_fallback_invalid_jwt(self, mock_decode):
        """JWT 解析失败 → 降级为 IP 限流"""
        mock_decode.return_value = None  # 解析失败
        request = MagicMock()
        request.headers = {"Authorization": "Bearer invalid.token"}
        request.client = MagicMock(host="10.0.0.5")
        key = _get_limit_key(request, "POST", "/api/v1/tasks/1/files")
        assert key == "ip:10.0.0.5:POST:/api/v1/tasks/1/files"


class TestGetLimitForRequest:
    """限流阈值匹配测试"""

    def test_strict_login(self):
        """登录接口 → 严格限制 20/min"""
        assert _get_limit_for_request("POST", "/api/v1/auth/login") == STRICT_LIMIT

    def test_medium_create_instance(self):
        """发起项目 → 中等限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/instances") == MEDIUM_LIMIT

    def test_medium_create_proposal(self):
        """发起方案 → 中等限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/proposals") == MEDIUM_LIMIT

    def test_medium_terminate(self):
        """终止流程 → 中等限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/instances/123/terminate") == MEDIUM_LIMIT

    def test_medium_file_upload(self):
        """文件上传 → 中等限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/tasks/456/files") == MEDIUM_LIMIT

    def test_medium_submit(self):
        """提交任务 → 中等限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/tasks/456/submit") == MEDIUM_LIMIT

    def test_medium_prepare_sign(self):
        """预提交 → 中等限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/tasks/456/prepare-sign") == MEDIUM_LIMIT

    def test_medium_signature_upload(self):
        """签名上传 → 中等限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/auth/signature") == MEDIUM_LIMIT

    def test_default_relaxed_get(self):
        """普通 GET 请求 → 默认宽松限制 300/min"""
        assert _get_limit_for_request("GET", "/api/v1/dashboard") == DEFAULT_LIMIT
        assert _get_limit_for_request("GET", "/api/v1/instances") == DEFAULT_LIMIT

    def test_default_relaxed_other_post(self):
        """非特殊 POST（校验/审批操作）→ 默认宽松限制 300/min"""
        assert _get_limit_for_request("POST", "/api/v1/checks/1/pass") == DEFAULT_LIMIT
        assert _get_limit_for_request("POST", "/api/v1/approvals/1/approve") == DEFAULT_LIMIT
        assert _get_limit_for_request("POST", "/api/v1/endorsements/1/approve") == DEFAULT_LIMIT

    def test_get_login_not_strict(self):
        """GET 登录路径不应被严格规则命中"""
        assert _get_limit_for_request("GET", "/api/v1/auth/login") == DEFAULT_LIMIT
