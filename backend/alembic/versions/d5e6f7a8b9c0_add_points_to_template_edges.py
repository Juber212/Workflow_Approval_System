"""add_points_to_template_edges

Revision ID: d5e6f7a8b9c0
Revises: baf8caa5c762
Create Date: 2026-07-16 22:09:45.510747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'baf8caa5c762'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 template_edges 添加 points 列 —— 存储折线路径点串（LogicFlow points 字符串）"""
    op.add_column(
        'template_edges',
        sa.Column('points', sa.Text(), nullable=True, comment='折线路径点串（LogicFlow points 字符串，保存后恢复避免路由重算）')
    )


def downgrade() -> None:
    """移除 points 列"""
    op.drop_column('template_edges', 'points')
