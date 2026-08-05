"""API 限流中间件 —— 内存滑动窗口，按用户/IP 分层限流

三层策略：
- 严格（20次/分钟/IP）：登录接口
- 中等（30次/分钟/用户）：文件上传、发起流程/方案、终止、提交任务
- 宽松（120次/分钟/用户）：其余所有 API（默认）

系统管理员自动跳过所有限流。
健康检查端点不限制。
"""

import time
import threading
import uuid
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_access_token


# ==================== 滑动窗口计数器 ====================

class _SlidingWindow:
    """线程安全的滑动窗口计数器，按 key 独立计数

    P1-25：加 key 数量上限 + 定期全量清理，防止长时间运行内存无限增长
    （攻击者可通过伪造大量 IP/用户 ID 制造海量 key）。
    """
    _MAX_KEYS = 10000            # key 数量上限（用户/IP 规模兜底）
    _CLEAN_EVERY_CALLS = 500     # 每 N 次调用触发一次全量过期清理

    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._call_count = 0

    def is_allowed(self, key: str, max_requests: int, window_seconds: float = 60.0) -> bool:
        """检查是否允许请求，如允许则记录时间戳

        Args:
            key: 限流键（user:xxx / ip:xxx）
            max_requests: 窗口内最大请求数
            window_seconds: 滑动窗口时长（秒）

        Returns:
            True 允许通过，False 触发限流
        """
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            self._call_count += 1
            # 定期全量清理过期 key（低频，O(n) 但间隔大，可忽略开销）
            if self._call_count % self._CLEAN_EVERY_CALLS == 0:
                self._sweep_expired(cutoff)
            # key 上限保护：超限先清过期，仍超限则淘汰最早访问的 key
            if len(self._buckets) >= self._MAX_KEYS:
                self._sweep_expired(cutoff)
                if len(self._buckets) >= self._MAX_KEYS:
                    self._evict_oldest()

            timestamps = self._buckets[key]
            # 惰性清理：只保留窗口内的记录
            if timestamps and timestamps[0] <= cutoff:
                cleaned = [t for t in timestamps if t > cutoff]
                if cleaned:
                    self._buckets[key] = cleaned
                else:
                    del self._buckets[key]  # 过期后删除 key
            if len(self._buckets[key]) >= max_requests:
                return False
            self._buckets[key].append(now)
            return True

    def _sweep_expired(self, cutoff: float) -> None:
        """全量清理：删除所有记录已全部过期的 key"""
        for k in list(self._buckets.keys()):
            ts_list = self._buckets[k]
            if not ts_list or ts_list[-1] <= cutoff:
                del self._buckets[k]

    def _evict_oldest(self) -> None:
        """淘汰最早记录的 key（上限兜底，罕见触发）"""
        oldest_key = None
        oldest_ts = None
        for k, ts_list in self._buckets.items():
            if ts_list:
                first = ts_list[0]
                if oldest_ts is None or first < oldest_ts:
                    oldest_ts = first
                    oldest_key = k
        if oldest_key is not None:
            del self._buckets[oldest_key]


# 全局窗口实例（跨请求共享）
_window = _SlidingWindow()


# ==================== 限流规则配置 ====================

# 全局默认：300次/分钟（宽松档，2026-07-24 从 120 提升以避免正常浏览误触限流）
DEFAULT_LIMIT = 300

# 严格规则：20次/分钟（登录用IP限流）
STRICT_LIMIT = 20
STRICT_RULES: list[tuple[str, str]] = [
    ("POST", "/api/v1/auth/login"),
]

# 中等规则：300次/分钟（文件上传、发起/终止流程、提交任务）
# 2026-08-03 从 60 提升至 300，且配合「按 method+path 独立计数」（见 _get_limit_key），
# 上传/提交/终止等操作互不挤占配额，避免测试与正常操作共享窗口触发 429
MEDIUM_LIMIT = 300
MEDIUM_RULES: list[tuple[str, str] | Callable[[str, str], bool]] = [
    # 精确路径匹配
    ("POST", "/api/v1/instances"),            # 发起项目
    ("POST", "/api/v1/proposals"),             # 发起方案
    ("POST", "/api/v1/auth/signature"),        # 签名上传
    # 模式匹配：POST 且路径以指定后缀结尾
    (lambda m, p: m == "POST" and p.endswith("/terminate")),    # 终止流程
    (lambda m, p: m == "POST" and p.endswith("/files")),        # 上传文件到任务
    (lambda m, p: m == "POST" and p.endswith("/submit")),       # 提交任务
    (lambda m, p: m == "POST" and p.endswith("/prepare-sign")), # 预提交（PDF转换）
    (lambda m, p: m == "POST" and p.endswith("/supplement-files")),  # 补交文件
]


# ==================== 限流键函数 ====================

def _get_limit_key(request: Request, method: str, path: str) -> str:
    """获取请求的限流键

    优先级：
    1. 系统管理员 → 每次请求唯一键，永不触发限制
    2. 已认证用户 → user:{user_id}:{method}:{path}
    3. 未认证请求 → ip:{客户端IP}:{method}:{path}

    按 method+path 独立计数（2026-08-03 用户调整）：上传/提交/终止/发起等
    操作各自独立配额，互不挤占，避免高频操作拖累其他接口触发 429。
    admin 键使用 uuid4() 确保每次请求都进入独立桶，永不会被限流。
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
            if payload:
                user_id = payload.get("sub", "unknown")
                roles = payload.get("roles", [])
                if "system_admin" in roles:
                    return f"admin:{uuid.uuid4()}"
                return f"user:{user_id}:{method}:{path}"
        except (AttributeError, ValueError, KeyError):
            pass  # JWT 解析失败 / payload 为 None / 缺少字段 → 降级为 IP 限流

    # 未认证：用直连 IP，不信任 X-Forwarded-For（P1-25）
    # XFF 可被客户端任意伪造，攻击者变换伪造 IP 即可绕过限流；
    # 内网直连部署下 client.host 即真实来源。若未来加反向代理，需配置
    # trusted proxy 解析真实 IP，而非直接信任请求头。
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}:{method}:{path}"


def _get_limit_for_request(method: str, path: str) -> int:
    """根据请求方法和路径返回限流阈值"""
    # 1. 优先匹配严格规则
    for rule_method, rule_path in STRICT_RULES:
        if method == rule_method and path == rule_path:
            return STRICT_LIMIT

    # 2. 匹配中等规则（精确路径 + lambda 模式匹配）
    for rule in MEDIUM_RULES:
        if isinstance(rule, tuple):
            if method == rule[0] and path == rule[1]:
                return MEDIUM_LIMIT
        elif callable(rule):
            if rule(method, path):
                return MEDIUM_LIMIT

    # 3. 兜底：默认宽松限制
    return DEFAULT_LIMIT


# ==================== 中间件 ====================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """API 限流中间件 —— 在请求到达路由前检查频率限制"""

    async def dispatch(self, request: Request, call_next):
        # 健康检查不限制（监控系统高频探测）
        if request.url.path == "/api/v1/health":
            return await call_next(request)

        # WebSocket 升级请求不占用 API 限流配额：
        # 连接建立仅一次（低频），认证由 ws 端点自负责（黑名单/is_active），心跳为 WS 帧不受限流
        if request.url.path.startswith("/api/v1/ws"):
            return await call_next(request)

        # 仅限制 API 路由，静态文件等跳过
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # 提取限流键（带管理员旁路；按 method+path 独立计数）
        key = _get_limit_key(request, request.method, request.url.path)
        if key.startswith("admin:"):
            return await call_next(request)

        # 匹配限流阈值
        max_req = _get_limit_for_request(request.method, request.url.path)

        # 检查滑动窗口
        if not _window.is_allowed(key, max_req):
            return Response(
                content='{"code":42900,"message":"请求过于频繁，请稍后重试","data":null}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
