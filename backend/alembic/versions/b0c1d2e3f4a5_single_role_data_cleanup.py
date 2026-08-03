"""单角色化：清理 user_roles 历史多角色数据

产品决策（2026-08-03）：角色从多选改为单选，管理员专职。
同一用户若历史残留多行角色，保留最高优先级一条（system_admin > manager > user）。

Revision ID: b0c1d2e3f4a5
Revises: 22a4163060e3
Create Date: 2026-08-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, None] = '22a4163060e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 模块级常量：清理脚本 SQL。抽成常量供 tests/mysql 复用，避免测试与迁移 SQL 漂移
_DEDUP_SQL = """
DELETE FROM user_roles
WHERE id IN (
    SELECT id FROM (
        SELECT
            ur.id,
            ROW_NUMBER() OVER (
                PARTITION BY ur.user_id
                ORDER BY
                    CASE r.code
                        WHEN 'system_admin' THEN 3
                        WHEN 'manager' THEN 2
                        WHEN 'user' THEN 1
                        ELSE 0
                    END DESC,
                    ur.id ASC
            ) AS rn
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
    ) ranked
    WHERE ranked.rn > 1
)
"""


def upgrade() -> None:
    """角色改单选：每个用户仅保留最高优先级角色，删除其余残留行

    优先级：system_admin(3) > manager(2) > user(1)。
    同优先级多行时保留 id 最小的一条（防御未知角色代码）。
    MySQL 8 窗口函数 ROW_NUMBER() 实现，三层子查询绕过
    「DELETE 目标表不能出现在子查询 FROM」限制（派生表物化）。
    """
    op.execute(_DEDUP_SQL)


def downgrade() -> None:
    """数据清理不可逆（被删除的多角色行无法精确还原），回退仅作占位"""
    pass
