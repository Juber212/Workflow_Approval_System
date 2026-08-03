"""通知表加 instance_id 列 —— 支持按实例精确清理通知

背景（P1-7）：clear_related 原按 user_id + 类型清理，会把该用户其他实例的
同类型通知一并清掉（过度清理）。新增 instance_id 冗余列后，终止/驳回/换人
时可只清理指定实例的通知。列可空，历史通知不强制回填。

Revision ID: c3d4e5f6a7b8
Revises: b0c1d2e3f4a5
Create Date: 2026-08-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """通知表新增 instance_id 列（可空，兼容历史数据）"""
    op.add_column(
        'notifications',
        sa.Column('instance_id', sa.Integer(), nullable=True,
                  comment='所属流程实例 ID（用于按实例精确清理通知，可空兼容历史数据）'),
    )


def downgrade() -> None:
    """回滚：删除 instance_id 列"""
    op.drop_column('notifications', 'instance_id')
