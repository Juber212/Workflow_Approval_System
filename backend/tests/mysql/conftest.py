"""MySQL 真实数据库测试 fixture

每测试创建独立引擎+建表，测试结束后删表+释放引擎。
避免连接池跨测试残留导致的 Windows aiomysql 兼容问题。

运行：pytest tests/mysql/ -v
"""

import urllib.parse

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base
from app.core.config import settings
from app.models import *  # noqa: F401 — 注册所有模型


def _build_test_db_url() -> str:
    """构建测试库连接 URL

    P1-47：复用 .env 主库凭据（DB_USER/DB_PASSWORD 经 quote_plus 编码），
    仅库名指向独立测试库 TEST_DB_NAME（默认 workflow_approval_test）。
    密码由环境配置统一管理，不再硬编码进源码/测试历史。
    """
    user = urllib.parse.quote_plus(settings.DB_USER, safe="")
    password = urllib.parse.quote_plus(settings.DB_PASSWORD, safe="")
    return (
        f"mysql+aiomysql://{user}:{password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.TEST_DB_NAME}"
        f"?charset=utf8mb4"
    )


TEST_DB_URL = _build_test_db_url()


async def _create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def mysql_session():
    """每个测试：独立引擎 → 建表 → 测试 → 删表 → 释放"""
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_size=1, max_overflow=0)

    await _create_tables(engine)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()  # 回滚未提交事务
            await session.close()

    await _drop_tables(engine)
    await engine.dispose()
