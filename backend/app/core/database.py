"""数据库引擎与会话管理"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 异步引擎（connect_args 兜底 charset，防止 aiomysql 连接参数丢失导致中文注释乱码）
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_size=20,  # 30-50 人并发场景，10→20
    max_overflow=20,
    pool_pre_ping=False,  # aiomysql 新版 ping() 签名不兼容，禁用连接池预检；用 pool_recycle 兜底
    pool_recycle=3600,   # 1 小时回收连接，防止 MySQL wait_timeout 后拿到 stale 连接
    connect_args={"charset": "utf8mb4"},
)

# 异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy ORM 模型基类"""

    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话

    NOTE: 此函数在 endpoint 成功返回后自动调用 commit()。
    现有部分端点也显式调用 db.commit()（导致双重 commit，第二次为 no-op）。
    理想模式是仅依赖 get_db 的自动提交，端点的显式 commit 应逐步移除。
    在此之前，请确保 send_refresh_signal() 等 post-commit 回调在显式 commit 之后调用。
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
