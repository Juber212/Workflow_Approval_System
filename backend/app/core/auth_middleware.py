"""认证中间件 —— Token 黑名单检查 & 强制改密码拦截

在 RateLimitMiddleware 之后注册，执行顺序：
1. TokenBlacklistMiddleware — 检查 JWT 是否已吊销
2. MustChangePasswordMiddleware — 检查用户是否需要强制改密码
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy import select

from app.core.security import decode_access_token
from app.core.database import async_session_factory
from app.models.user import User

logger = logging.getLogger(__name__)

# 强制改密码检查的路径白名单 —— 这些路径即使 must_change_password=True 也允许访问
_MUST_CHANGE_PWD_WHITELIST = {
    "/api/v1/auth/login",
    "/api/v1/auth/password",   # 修改密码本身
    "/api/v1/auth/logout",     # 退出登录
    "/api/v1/auth/me",         # 获取用户信息（前端恢复状态需要）
    "/api/v1/health",          # 健康检查
    "/docs",                   # API 文档
    "/redoc",
    "/openapi.json",
}


def _path_in_whitelist(path: str) -> bool:
    """检查路径是否在 must_change_password 白名单中"""
    for w in _MUST_CHANGE_PWD_WHITELIST:
        if path == w or path.startswith(w):
            return True
    # WebSocket 路径放行（由 ws 端点自行认证）
    if path.startswith("/api/v1/ws"):
        return True
    return False


class MustChangePasswordMiddleware(BaseHTTPMiddleware):
    """强制改密码中间件 —— 拦截 must_change_password=True 用户的非白名单请求

    在 TokenBlacklistMiddleware 之后注册。
    每个需认证的请求额外查询一次 DB（SELECT must_change_password FROM users WHERE id=...）。
    对于企业内部系统，此开销可接受（单行主键查询，<1ms）。
    """

    async def dispatch(self, request: Request, call_next):
        # 白名单路径直接放行
        if _path_in_whitelist(request.url.path):
            return await call_next(request)

        # 从 Authorization Header 提取 user_id
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get("sub", "")
                if user_id:
                    try:
                        async with async_session_factory() as db:
                            result = await db.execute(
                                select(User.must_change_password).where(User.id == int(user_id))
                            )
                            must_change = result.scalar()
                            if must_change:
                                return JSONResponse(
                                    status_code=403,
                                    content={
                                        "code": 40310,
                                        "message": "请先修改密码后再操作",
                                        "data": None,
                                    },
                                )
                    except Exception:
                        # DB 查询失败不阻塞请求（避免中间件故障导致全站不可用）
                        logger.warning("强制改密码检查失败: user_id=%s", user_id, exc_info=True)

        return await call_next(request)
