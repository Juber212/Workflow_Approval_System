"""企业项目审批系统 —— FastAPI 应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.organizations import router as orgs_router
from app.api.roles import router as roles_router
from app.api.configs import router as configs_router
from app.api.templates import router as templates_router
from app.api.designer import router as designer_router
from app.api.instances import router as instances_router
from app.api.tasks import router as tasks_router
from app.api.checks import router as checks_router
from app.api.approvals import router as approvals_router
from app.api.dashboard import router as dashboard_router
from app.api.presets import router as presets_router
from app.api.utils import router as utils_router
from app.core.database import async_session_factory, engine
from app.services.config_service import config_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()
    # 启动时加载系统配置到内存缓存
    await config_service.load(async_session_factory)
    yield
    # 关闭时主动释放数据库连接池，避免事件循环关闭后 aiomysql 清理报错
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
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
app.include_router(designer_router)
app.include_router(instances_router)
app.include_router(tasks_router)
app.include_router(checks_router)
app.include_router(approvals_router)
app.include_router(dashboard_router)
app.include_router(presets_router)
app.include_router(utils_router)

# ================= 健康检查 =================


@app.get("/api/v1/health")
async def health_check():
    """健康检查端点"""
    return ApiResponse.ok({"status": "ok", "version": settings.APP_VERSION})
