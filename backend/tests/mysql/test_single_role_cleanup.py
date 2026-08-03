"""MySQL 迁移验证 —— 角色改单选：清理 user_roles 历史多角色数据（保留最高优先级角色）

直接复用迁移脚本的 _DEDUP_SQL 常量，保证测试与迁移不漂移。
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.models import User, UserRole, Role


# alembic/versions 非 Python 包，用 importlib 按路径加载迁移模块
_MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "alembic" / "versions" / "b0c1d2e3f4a5_single_role_data_cleanup.py"
)
_spec = importlib.util.spec_from_file_location("single_role_cleanup_migration", _MIGRATION_FILE)
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)


async def _seed_roles_and_users(session):
    """构造多角色残留场景：u1 三角色 / u2 双角色 / u3 单角色"""
    roles = [
        Role(id=1, code="system_admin", name="系统管理员"),
        Role(id=2, code="manager", name="所长"),
        Role(id=3, code="user", name="普通用户"),
    ]
    session.add_all(roles)
    for uid, role_ids in [(1, [1, 2, 3]), (2, [2, 3]), (3, [3])]:
        session.add(User(
            id=uid, username=f"u{uid}", real_name=f"用户{uid}",
            password_hash="x", is_active=True,
        ))
        for rid in role_ids:
            session.add(UserRole(user_id=uid, role_id=rid))
    await session.flush()


async def _role_codes(session, user_id):
    """按 user_roles.id 顺序返回某用户的角色代码"""
    stmt = (
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(UserRole.id)
    )
    return (await session.execute(stmt)).scalars().all()


@pytest.mark.asyncio
async def test_dedup_keeps_highest_priority_role(mysql_session):
    """多角色用户保留最高优先级，单角色用户不受影响"""
    await _seed_roles_and_users(mysql_session)

    # 执行迁移清理 SQL
    await mysql_session.execute(text(_migration._DEDUP_SQL))
    await mysql_session.commit()

    # u1：system_admin + manager + user → 仅保留 system_admin（最高优先级）
    assert await _role_codes(mysql_session, 1) == ["system_admin"]
    # u2：manager + user → 仅保留 manager
    assert await _role_codes(mysql_session, 2) == ["manager"]
    # u3：user → 单角色不受影响
    assert await _role_codes(mysql_session, 3) == ["user"]
