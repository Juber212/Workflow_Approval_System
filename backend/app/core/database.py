"""数据库引擎与会话管理"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 异步引擎（connect_args 兜底 charset，防止 aiomysql 连接参数丢失导致中文注释乱码）
# P1-29：pool_size/max_overflow 可经 DB_POOL_SIZE/DB_MAX_OVERFLOW 配置——
# 多 worker 部署时连接总量 = worker×(pool_size+max_overflow)，需 ≤ MySQL max_connections。
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,      # 30-50 人并发场景，默认 20
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=False,  # aiomysql 新版 ping() 签名不兼容，禁用连接池预检；用 pool_recycle 兜底
    pool_recycle=3600,   # 1 小时回收连接，防止 MySQL wait_timeout 后拿到 stale 连接
    connect_args={"charset": "utf8mb4"},
)


# ========== 连接事件：设置事务隔离级别为 READ COMMITTED ==========
# aiomysql 不支持 URL 参数 / connect_args 方式设置隔离级别，
# 需要在每个新连接建立后通过 SQL 语句设置，防止 fork-join 并发竞态
@event.listens_for(engine.sync_engine, "connect")
def _set_isolation_level(dbapi_connection, connection_record):
    """每个新连接建立后，设置会话隔离级别为 READ COMMITTED"""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
    cursor.close()

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
