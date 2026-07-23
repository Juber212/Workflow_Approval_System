"""pytest 全局 fixtures —— mock DB 会话、SQLite 测试引擎、FastAPI TestClient"""

import sys
import os

# 确保 backend 目录在 sys.path 中（可从项目根或 backend 目录运行 pytest）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base


# ============================================================
# 单元测试 fixtures —— Mock AsyncSession
# ============================================================

class MockResult:
    """模拟 SQLAlchemy Result 对象，支持 .scalar() / .scalar_one() / .scalar_one_or_none() / .scalars().all()"""

    def __init__(self, scalar_value=None, scalars_all=None, scalar_one=None):
        self._scalar_value = scalar_value
        self._scalars_all = scalars_all or []
        self._scalar_one = scalar_one

    def scalar(self):
        return self._scalar_value

    def scalar_one(self):
        """submit_task 中用到的 scalar_one()（必须存在，否则抛异常）"""
        if self._scalar_one is not None:
            return self._scalar_one
        # 兼容 scalars_all 中有数据的情况，取第一个
        if self._scalars_all:
            return self._scalars_all[0]
        raise ValueError("MockResult: scalar_one() called but no data")

    def scalar_one_or_none(self):
        return self._scalar_one

    def scalars(self):
        return _MockScalars(self._scalars_all)


class _MockScalars:
    """模拟 Result.scalars() 返回的迭代器"""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None

    def __iter__(self):
        return iter(self._items)


@pytest.fixture
def mock_db():
    """创建一个 Mock AsyncSession，所有异步方法均为 AsyncMock

    用法：
        db = mock_db
        # 配置 execute 返回值
        db.execute.return_value = MockResult(scalar_one=mock_instance)
        # 调用被测 service 函数
        result = await some_service(db, ...)
        # 断言
        db.add.assert_called_once()
    """
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.delete = MagicMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_db_factory(mock_db):
    """返回一个总是产生同一个 mock_db 的异步生成器工厂

    用法：
        mocker.patch("app.api.deps.get_db", return_value=mock_db_factory)
    """
    async def _get_db():
        yield mock_db
    return _get_db()


# ============================================================
# 集成测试 fixtures —— SQLite 内存数据库
# ============================================================

@pytest.fixture
async def sqlite_session():
    """每个测试函数独立的 SQLite 会话（自动建表/回滚，函数级隔离）"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # 建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 创建会话
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()
