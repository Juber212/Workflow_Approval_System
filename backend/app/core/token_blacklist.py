"""Token 黑名单 —— JWT 登出 / 禁用用户后使 Token 即时失效

包含两部分：
1. 黑名单增删查函数（add_to_blacklist / is_blacklisted）
2. TokenBlacklistMiddleware —— FastAPI 中间件，拦截所有请求检查黑名单

使用 Redis DB 2 存储黑名单条目：
- Key:  jti:<jti>
- Value: "1"
- TTL:  token 剩余有效时间（秒），过期后 Redis 自动删除
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.redis import get_token_blacklist_redis
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

# Redis key 前缀，便于调试和监控
_KEY_PREFIX = "jti:"


async def add_to_blacklist(jti: str, ttl_seconds: int) -> None:
    """将 token 加入黑名单，ttl_seconds 秒后自动过期删除

    调用时机：用户登出、管理员禁用用户。
    ttl_seconds = token 过期时间戳 - 当前时间戳，确保不会永久占用内存。
    """
    if not jti or ttl_seconds <= 0:
        return  # 已过期的 token 无需加入黑名单

    try:
        redis = await get_token_blacklist_redis()
        key = f"{_KEY_PREFIX}{jti}"
        await redis.set(key, "1", ex=ttl_seconds)
        logger.debug("Token 已加入黑名单: jti=%s, ttl=%ds", jti[:16], ttl_seconds)
    except Exception:
        # 黑名单写入失败不影响主流程（最坏情况下 token 仍有效直到自然过期）
        logger.warning("Token 黑名单写入失败: jti=%s", jti[:16], exc_info=True)


async def is_blacklisted(jti: str) -> bool:
    """检查 token 是否在黑名单中

    Args:
        jti: JWT 中的唯一 ID

    Returns:
        True 表示 token 已被吊销
    """
    if not jti:
        return False

    try:
        redis = await get_token_blacklist_redis()
        key = f"{_KEY_PREFIX}{jti}"
        exists = await redis.exists(key)
        return bool(exists)
    except Exception:
        # Redis 不可用时放行，避免整个系统不可用
        logger.warning("Token 黑名单查询失败: jti=%s", jti[:16], exc_info=True)
        return False


# ========== Token 黑名单中间件 ==========

# 不检查黑名单的路径（无需认证或认证逻辑自处理）
_BLACKLIST_WHITELIST = {
    "/api/v1/auth/login",
    "/api/v1/auth/logout",  # logout 自己需要取 jti 加入黑名单，不能先被拦截
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def _path_in_whitelist(path: str) -> bool:
    """检查路径是否在黑名单中间件的白名单中（支持前缀匹配）"""
    for w in _BLACKLIST_WHITELIST:
        if path == w or path.startswith(w):
            return True
    # WebSocket 升级路径不检查黑名单（由 WebSocket 端点自行认证）
    if path.startswith("/api/v1/ws"):
        return True
    return False


class TokenBlacklistMiddleware(BaseHTTPMiddleware):
    """Token 黑名单中间件 —— 在每次请求时检查 JWT 是否已被吊销

    注册在 RateLimitMiddleware 之后，利用 Redis DB 2 的 SET 查询。
    白名单路径（登录/登出/健康检查/文档/WebSocket）直接放行。
    """

    async def dispatch(self, request: Request, call_next):
        # 白名单路径直接放行
        if _path_in_whitelist(request.url.path):
            return await call_next(request)

        # 从 Authorization Header 提取 JWT 并解析 jti
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            payload = decode_access_token(token)
            if payload:
                jti = payload.get("jti", "")
                if jti and await is_blacklisted(jti):
                    return JSONResponse(
                        status_code=401,
                        content={
                            "code": 40100,
                            "message": "Token 已失效，请重新登录",
                            "data": None,
                        },
                    )

        return await call_next(request)
