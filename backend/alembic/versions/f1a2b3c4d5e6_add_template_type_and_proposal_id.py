"""add_template_type_and_proposal_id

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-07-17 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为模板添加 type 字段，为实例添加 proposal_id 关联"""
    op.add_column(
        'flow_templates',
        sa.Column('type', sa.String(20), nullable=False, server_default='project', comment='模板类型：project / proposal')
    )
    op.add_column(
        'flow_instances',
        sa.Column('proposal_id', sa.Integer(), nullable=True, comment='关联的方案ID（仅项目类型可用）')
    )
    op.create_foreign_key(
        'fk_flow_instances_proposal_id',
        'flow_instances', 'flow_instances',
        ['proposal_id'], ['id']
    )


def downgrade() -> None:
    """移除 type 和 proposal_id 列"""
    op.drop_constraint('fk_flow_instances_proposal_id', 'flow_instances', type_='foreignkey')
    op.drop_column('flow_instances', 'proposal_id')
    op.drop_column('flow_templates', 'type')
