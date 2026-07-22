"""签名记录增加独立宽高 —— 支持签批预览中拖拽缩放

Revision ID: m8n9o0p1q2r3
Revises: h3i4j5k6l7m8
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'm8n9o0p1q2r3'
down_revision: Union[str, None] = 'h3i4j5k6l7m8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('signatures', sa.Column(
        'signature_width', sa.Float(), nullable=True,
        comment='签名指定宽度（NULL=使用全局配置）'
    ))
    op.add_column('signatures', sa.Column(
        'signature_height', sa.Float(), nullable=True,
        comment='签名指定高度（NULL=使用全局配置）'
    ))


def downgrade() -> None:
    op.drop_column('signatures', 'signature_height')
    op.drop_column('signatures', 'signature_width')
