"""add notifications table

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-07-23 17:20:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p2q3r4s5t6u7'
down_revision: Union[str, None] = '18f54d3e1cb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建通知表"""
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='接收人'),
        sa.Column('type', sa.String(30), nullable=False, comment='通知类型'),
        sa.Column('title', sa.String(200), nullable=False, comment='通知标题'),
        sa.Column('content', sa.String(500), nullable=False, comment='通知内容'),
        sa.Column('link', sa.String(300), nullable=True, comment='点击跳转路径'),
        sa.Column('is_read', sa.Boolean(), default=False, comment='是否已读'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='通知时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_notif_user'),
    )
    # 为 user_id + is_read 创建复合索引（常用查询：某用户未读列表）
    op.create_index('idx_notif_user_unread', 'notifications', ['user_id', 'is_read'])


def downgrade() -> None:
    """删除通知表"""
    op.drop_index('idx_notif_user_unread', table_name='notifications')
    op.drop_table('notifications')
