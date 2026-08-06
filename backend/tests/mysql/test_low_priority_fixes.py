"""低危项修复测试 —— is_active 过滤 + GET_LOCK 并发只建一个模板

真实 MySQL 集成测试（每测试独立建表删表）。
运行：pytest tests/mysql/test_low_priority_fixes.py -v
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models import Organization, User, FlowTemplate
from app.services.validation_service import validate_user_ids_exist
from app.services.proposal_service import ensure_proposal_template
from tests.mysql.conftest import TEST_DB_URL


async def _make_org_user(session) -> tuple[Organization, User]:
    """建一个组织 + 一个活跃用户（供模板 created_by 使用），提交后供并发连接可见"""
    org = Organization(name="低危测试组织", description="")
    session.add(org)
    await session.flush()
    user = User(
        username="lowprio_user",
        password_hash="x",
        real_name="测试用户",
        organization_id=org.id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return org, user


async def test_validate_user_ids_exist_filters_inactive(mysql_session):
    """低危 1.2：is_active=False 的用户视为不可用（归入缺失集合）"""
    org = Organization(name="校验组织", description="")
    mysql_session.add(org)
    await mysql_session.flush()
    active = User(
        username="v_active", password_hash="x", real_name="活跃用户",
        organization_id=org.id, is_active=True,
    )
    inactive = User(
        username="v_inactive", password_hash="x", real_name="停用用户",
        organization_id=org.id, is_active=False,
    )
    mysql_session.add_all([active, inactive])
    await mysql_session.commit()

    missing = await validate_user_ids_exist(mysql_session, {active.id, inactive.id})
    assert missing == {inactive.id}  # 仅禁用用户被拒


async def test_ensure_proposal_template_concurrent_only_one(mysql_session):
    """低危 1.1：并发发起方案模板只建 1 个（GET_LOCK 锁内 commit 后释放）

    旧代码 RELEASE_LOCK 早于事务 commit：并发下后到请求复查看不到未提交模板，
    会重复创建（撞唯一索引抛错或建出 2 个模板）；锁内 commit 后第二个请求复用已有模板。
    """
    org, user = await _make_org_user(mysql_session)

    # 独立连接池并发两个请求（GET_LOCK 绑定连接，需不同连接才真正并发）
    engine = create_async_engine(TEST_DB_URL, pool_size=2, max_overflow=0)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _run():
        async with factory() as s:
            return await ensure_proposal_template(s, org.id, user.id)

    try:
        tpls = await asyncio.gather(_run(), _run())
    finally:
        await engine.dispose()

    # 两个请求返回同一模板对象
    assert len({t.id for t in tpls}) == 1
    # 数据库仅 1 个模板
    count = (await mysql_session.execute(
        select(FlowTemplate).where(FlowTemplate.organization_id == org.id)
    )).scalars().all()
    assert len(count) == 1
