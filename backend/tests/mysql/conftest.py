"""MySQL 真实数据库测试 fixture

每测试创建独立引擎+建表，测试结束后删表+释放引擎。
避免连接池跨测试残留导致的 Windows aiomysql 兼容问题。

运行：pytest tests/mysql/ -v
"""

import pytest
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base
from app.models import *  # noqa: F401 — 注册所有模型

TEST_DB_URL = "mysql+aiomysql://root:REDACTED@localhost:3306/workflow_approval_test?charset=utf8mb4"


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
