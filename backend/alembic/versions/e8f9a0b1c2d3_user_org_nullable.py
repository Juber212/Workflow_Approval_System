"""用户 organization_id 改可空 —— 管理员可不归属任何组织

Revision ID: e8f9a0b1c2d3
Revises: dbced35f5500
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, None] = 'dbced35f5500'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """users.organization_id 允许 NULL —— 管理员可独立于组织"""
    op.alter_column(
        'users', 'organization_id',
        existing_type=sa.Integer(),
        nullable=True,
        existing_comment='所属组织（管理员可选空）',
    )


def downgrade() -> None:
    """回滚：恢复 organization_id NOT NULL"""
    op.alter_column(
        'users', 'organization_id',
        existing_type=sa.Integer(),
        nullable=False,
        existing_comment='所属组织',
    )
