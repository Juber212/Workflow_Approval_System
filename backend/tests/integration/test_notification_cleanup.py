"""P1-7 集成测试：clear_related 按实例维度精确清理通知

问题背景：原按 user_id + 类型清理，会把该用户其他实例的同类型通知一并清掉。
修复后：传 instance_id 时只清指定实例的通知；不传保持原行为。
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.notification import Notification
from app.services.notification_service import clear_related


@pytest.fixture
async def notif_session():
    """只建 notifications 表的 SQLite 会话

    不用 conftest 的 sqlite_session（其 Base.metadata.create_all 因 operation_logs
    复合主键在 SQLite 下报错，见 P1-48）。此处仅建本测试用到的表。
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Notification.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_clear_related_by_instance(notif_session):
    """同用户同类型、不同实例的通知 → 只清指定实例的"""
    notif_session.add_all([
        Notification(user_id=1, type="approval_assigned", title="实例10-审批", content="A", instance_id=10),
        Notification(user_id=1, type="approval_assigned", title="实例20-审批", content="B", instance_id=20),
        Notification(user_id=1, type="task_assigned", title="实例10-任务", content="C", instance_id=10),
    ])
    await notif_session.commit()

    # 只清理实例 10 的 approval_assigned 通知
    await clear_related(notif_session, user_id=1, types=["approval_assigned"], instance_id=10)
    await notif_session.commit()

    remaining = (await notif_session.execute(select(Notification))).scalars().all()
    titles = {n.title for n in remaining}
    # 「实例10-审批」被清；「实例20-审批」「实例10-任务」保留（不同实例/不同类型不被误伤）
    assert titles == {"实例20-审批", "实例10-任务"}


@pytest.mark.asyncio
async def test_clear_related_without_instance_keeps_legacy(notif_session):
    """不传 instance_id → 保持原行为：按 user_id + 类型清理该用户该类型全部"""
    notif_session.add_all([
        Notification(user_id=1, type="approval_assigned", title="实例10-审批", content="A", instance_id=10),
        Notification(user_id=1, type="approval_assigned", title="实例20-审批", content="B", instance_id=20),
        Notification(user_id=2, type="approval_assigned", title="他用户-审批", content="C", instance_id=10),
    ])
    await notif_session.commit()

    await clear_related(notif_session, user_id=1, types=["approval_assigned"])
    await notif_session.commit()

    remaining = (await notif_session.execute(select(Notification))).scalars().all()
    titles = {n.title for n in remaining}
    # 用户1 的 A/B 全清，用户2 的 C 保留
    assert titles == {"他用户-审批"}


@pytest.mark.asyncio
async def test_create_notification_persists_instance_id(notif_session):
    """创建通知时 instance_id 透传写入（供后续按实例清理）"""
    from unittest.mock import AsyncMock, patch
    from app.services.notification_service import create_notification

    # 避免真实 WS 推送：patch notification_service 模块内的 manager.send_to_user
    with patch("app.services.notification_service.manager.send_to_user", new=AsyncMock()):
        notif = await create_notification(
            notif_session, user_id=1, type="approval_assigned",
            title="待审批", content="新任务", link="/x", instance_id=42,
        )
    await notif_session.commit()

    assert notif is not None
    assert notif.instance_id == 42

    # 落库后仍保留 instance_id
    loaded = (await notif_session.execute(select(Notification))).scalar_one()
    assert loaded.instance_id == 42
