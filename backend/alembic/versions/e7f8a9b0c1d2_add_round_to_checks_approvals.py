"""add_round_to_checks_approvals

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-07-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给 check_records 和 approvals 表添加 round 列 —— 标识节点第几轮的校验/审批"""
    op.add_column(
        'check_records',
        sa.Column('round', sa.Integer(), nullable=False, server_default='1', comment='节点轮次（第几轮校验）')
    )
    op.add_column(
        'approvals',
        sa.Column('round', sa.Integer(), nullable=False, server_default='1', comment='节点轮次（第几轮审批）')
    )


def downgrade() -> None:
    """移除 round 列"""
    op.drop_column('approvals', 'round')
    op.drop_column('check_records', 'round')
