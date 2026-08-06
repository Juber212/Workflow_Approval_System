"""企业项目审批系统 —— FastAPI 应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings, KNOWN_DEFAULT_SECRETS
from app.core.logging import setup_logging
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.core.rate_limit import RateLimitMiddleware
from app.core.token_blacklist import TokenBlacklistMiddleware
from app.schemas.common import ApiResponse
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.organizations import router as orgs_router
from app.api.roles import router as roles_router
from app.api.configs import router as configs_router
from app.api.templates import router as templates_router, admin_router as templates_admin_router
from app.api.designer import router as designer_router
from app.api.instances import router as instances_router
from app.api.tasks import router as tasks_router
from app.api.checks import router as checks_router
from app.api.approvals import router as approvals_router
from app.api.dashboard import router as dashboard_router
from app.api.presets import router as presets_router
from app.api.utils import router as utils_router
from app.api.proposals import router as proposals_router
from app.api.endorsements import router as endorsements_router
from app.api.notifications import router as notifications_router
from app.api.ws import router as ws_router
from app.core.database import async_session_factory, engine
from app.services.config_service import config_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()

    import sys

    # ── 生产守卫（P1-49）：防止弱配置带上线 ──
    # 1. DEBUG=true 只允许在开发环境开启：非开发环境开调试会暴露敏感信息
    if settings.DEBUG and settings.ENV != "development":
        print(f"[错误] 生产守卫: DEBUG=true 不允许在非开发环境（ENV={settings.ENV}）启动！")
        print("       请将 .env 中 DEBUG 设为 false，或显式设置 ENV=development。")
        sys.exit(1)

    # 2. SECRET_KEY 校验（分环境策略：生产/测试强制强密钥，开发环境弱密钥仅警告）
    if settings.ENV == "development":
        if not settings.SECRET_KEY:
            print("[错误] 严重安全错误: SECRET_KEY 未设置！")
            print("       请通过环境变量 SECRET_KEY 设置。")
            sys.exit(1)
        if len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY in KNOWN_DEFAULT_SECRETS:
            print("[警告] 提示: SECRET_KEY 为弱密钥，仅限开发环境使用。部署前请更换为随机强密钥。")
    else:
        if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
            print("[错误] 严重安全错误: SECRET_KEY 必须至少 32 字符！")
            print("       请通过环境变量 SECRET_KEY 设置一个至少 64 字符的随机密钥。")
            print("       示例: openssl rand -hex 32")
            sys.exit(1)
        if settings.SECRET_KEY in KNOWN_DEFAULT_SECRETS:
            print("[错误] 严重安全错误: SECRET_KEY 是已知默认值，必须更换！")
            sys.exit(1)

    # 3. DEFAULT_USER_PASSWORD 非空守卫（低危项）：管理员「重置密码」依赖它，
    #    未配置时重置会把用户密码置为空串（bcrypt 空串）而登录接口拒绝空密码 → 用户被锁定
    if not settings.DEFAULT_USER_PASSWORD:
        print("[错误] 生产守卫: DEFAULT_USER_PASSWORD 未设置！")
        print("       管理员执行「重置密码」会把用户密码置为空串导致用户无法登录。")
        sys.exit(1)

    # 启动时加载系统配置到内存缓存
    await config_service.load(async_session_factory)

    # 启动 Redis Pub/Sub → WebSocket 桥接器（50+ 优化：异步 PDF 转换完成通知）
    from app.services.ws_bridge import start_bridge, stop_bridge
    await start_bridge()

    yield

    # 关闭桥接器 + Token 黑名单 Redis 连接
    await stop_bridge()
    from app.core.redis import close_token_blacklist_redis
    await close_token_blacklist_redis()
    # 关闭时主动释放数据库连接池，避免事件循环关闭后 aiomysql 清理报错
    await engine.dispose()


# P1-50：生产环境（ENV=prod）关闭 Swagger/ReDoc/OpenAPI 文档，
# 避免向外部暴露接口结构（openapi.json 是文档数据源，须一并关闭）
_docs_enabled = settings.ENV != "prod"

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 中间件执行顺序：Starlette 的 add_middleware 把新中间件插入到栈顶（最外层），
# 因此最后注册的 RateLimit 最先执行。目标顺序（外层→内层）：RateLimit → TokenBlacklist → CORS → 路由。
# 限流放最外层：恶意高频请求在最便宜的内存层被拦截，不进入后续 Redis/DB 查询。
app.add_middleware(TokenBlacklistMiddleware)  # 拦截已吊销的 JWT（查 Redis）
# 强制改密检查已合并进 get_current_active_user 依赖（P1-28），不再需要独立中间件
app.add_middleware(RateLimitMiddleware)       # 最后注册 → 最外层（最先执行）


# ================= 全局异常处理器 =================

def _http_status(error_code: int) -> int:
    """将业务错误码映射为 HTTP 状态码（前三位即 HTTP 状态码）"""
    return error_code // 100  # 40000→400, 40101→401, 50000→500 等


@app.exception_handler(AppException)
async def app_exception_handler(_request: Request, exc: AppException):
    """业务异常 → 根据错误码返回对应 HTTP 状态码"""
    return JSONResponse(
        status_code=_http_status(exc.code),
        content=ApiResponse.fail(exc.code, exc.message, exc.data).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    """Pydantic 校验异常 → 422 Unprocessable Entity"""
    errors = exc.errors()
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors[:3])
    return JSONResponse(
        status_code=422,
        content=ApiResponse.fail(ErrorCode.VALIDATION_ERROR, detail or "参数校验失败").model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    """未知异常 → 500，不泄露内部信息"""
    import logging
    import traceback

    logger = logging.getLogger(__name__)
    logger.error(f"全局异常: {type(exc).__name__}: {exc}")
    logger.error(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content=ApiResponse.fail(
            ErrorCode.INTERNAL_ERROR,
            "服务器内部错误，请联系管理员",
        ).model_dump(),
    )


# 注册路由
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(orgs_router)
app.include_router(roles_router)
app.include_router(configs_router)
app.include_router(templates_router)
app.include_router(templates_admin_router)
app.include_router(designer_router)
app.include_router(instances_router)
app.include_router(tasks_router)
app.include_router(checks_router)
app.include_router(approvals_router)
app.include_router(dashboard_router)
app.include_router(presets_router)
app.include_router(utils_router)
app.include_router(proposals_router)
app.include_router(endorsements_router)
app.include_router(notifications_router)
app.include_router(ws_router)

# ================= 健康检查 =================


@app.get("/api/v1/health")
async def health_check():
    """健康检查端点 —— 含 DB/Redis 探活（任一不可用返回 503，供监控报警）"""
    from sqlalchemy import text
    from app.core.database import async_session_factory
    from app.core.redis import get_token_blacklist_redis

    checks: dict[str, str] = {}
    # DB 探活：SELECT 1（连接池复用，不新建连接）
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "down"
    # Redis 探活：PING（黑名单连接已配置 1 秒超时，快速失败）
    try:
        redis = await get_token_blacklist_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "down"

    if all(v == "ok" for v in checks.values()):
        return ApiResponse.ok({"status": "ok", "version": settings.APP_VERSION, **checks})
    return JSONResponse(
        status_code=503,
        content=ApiResponse.fail(
            ErrorCode.INTERNAL_ERROR,
            "依赖服务不可用",
            {"status": "degraded", **checks},
        ).model_dump(),
    )
