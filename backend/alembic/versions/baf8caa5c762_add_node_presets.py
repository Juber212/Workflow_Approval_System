"""add node_presets

Revision ID: baf8caa5c762
Revises: a6b7c8d9e0f1
Create Date: 2026-07-16 16:24:35.777483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'baf8caa5c762'
down_revision: Union[str, None] = 'a6b7c8d9e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建节点预设表 —— 用户保存常用节点配置以便复用"""
    op.create_table('node_presets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='所属用户'),
        sa.Column('name', sa.String(length=30), nullable=False, comment='预设名称（列表中显示）'),
        sa.Column('node_name', sa.String(length=30), nullable=False, comment='拖出后默认节点名称'),
        sa.Column('assignee_id', sa.Integer(), nullable=True, comment='负责人 ID'),
        sa.Column('checkers', sa.JSON(), nullable=True, comment='校验人列表 [{"user_id": N}]'),
        sa.Column('approvers', sa.JSON(), nullable=True, comment='审批人列表 [{"user_id": N}]'),
        sa.Column('time_limit_days', sa.Integer(), nullable=True, comment='完成时限（天）'),
        sa.Column('require_file', sa.Boolean(), nullable=False, comment='是否必须上传文件'),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='排序序号（预留拖拽排序）'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assignee_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """删除节点预设表"""
    op.drop_table('node_presets')
