"""remove_archive_status

Revision ID: a6b7c8d9e0f1
Revises: 3c01f8e662d2
Create Date: 2026-07-16 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6b7c8d9e0f1'
down_revision: Union[str, None] = '3c01f8e662d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除冗余的 archive_status 和 archived_at 字段（completed 等价于已归档）"""
    op.drop_column('flow_instances', 'archived_at')
    op.drop_column('flow_instances', 'archive_status')


def downgrade() -> None:
    op.add_column('flow_instances', sa.Column('archive_status', sa.String(length=20), nullable=False, server_default='not_archived', comment='归档状态'))
    op.add_column('flow_instances', sa.Column('archived_at', sa.DateTime(), nullable=True, comment='归档时间'))
