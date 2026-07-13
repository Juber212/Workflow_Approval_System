"""企业流程审批系统 —— FastAPI 应用入口"""

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
from app.core.database import async_session_factory
from app.services.config_service import config_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()
    # 启动时加载系统配置到内存缓存
    await config_service.load(async_session_factory)
    yield


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


@app.exception_handler(AppException)
async def app_exception_handler(_request: Request, exc: AppException):
    """业务异常 → 统一错误响应"""
    return JSONResponse(
        status_code=200,
        content=ApiResponse.fail(exc.code, exc.message, exc.data).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    """Pydantic 校验异常 → 统一错误响应"""
    errors = exc.errors()
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors[:3])
    return JSONResponse(
        status_code=200,
        content=ApiResponse.fail(ErrorCode.VALIDATION_ERROR, detail or "参数校验失败").model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    """未知异常 → 500，不泄露堆栈"""
    import logging

    logger = logging.getLogger("app")
    logger.exception(f"未捕获异常: {exc}")
    return JSONResponse(
        status_code=200,
        content=ApiResponse.fail(
            ErrorCode.INTERNAL_ERROR, "服务器内部错误，请联系管理员"
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

# ================= 健康检查 =================


@app.get("/api/v1/health")
async def health_check():
    """健康检查端点"""
    return ApiResponse.ok({"status": "ok", "version": settings.APP_VERSION})
