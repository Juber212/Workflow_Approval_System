"""添加 doc_template_ids 列到 flow_instances —— 实例级文件模板覆盖

Revision ID: 6247827b186e
Revises: p2q3r4s5t6u7
Create Date: 2026-07-24 06:35:44.381300
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6247827b186e'
down_revision: Union[str, None] = 'p2q3r4s5t6u7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """flow_instances 新增 doc_template_ids JSON 列"""
    op.add_column('flow_instances',
        sa.Column('doc_template_ids', sa.JSON(), nullable=True,
                  comment='实例级文件模板 ID 列表（为空则继承模板关联）'))


def downgrade() -> None:
    """回滚：删除 doc_template_ids 列"""
    op.drop_column('flow_instances', 'doc_template_ids')
