"""add_template_type_to_flow_instances

Revision ID: 18f54d3e1cb6
Revises: 7413b2c017db
Create Date: 2026-07-23 14:49:37.687533

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18f54d3e1cb6'
down_revision: Union[str, None] = '7413b2c017db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 template_type 列到 flow_instances，并回填已有数据"""
    op.add_column(
        'flow_instances',
        sa.Column(
            'template_type',
            sa.String(length=20),
            nullable=False,
            server_default='project',
            comment='模板类型快照: project / proposal（用于存储分目录等）',
        ),
    )
    # 根据关联的模板回填已有数据的 template_type
    op.execute("""
        UPDATE flow_instances fi
        JOIN flow_templates ft ON ft.id = fi.template_id
        SET fi.template_type = ft.type
        WHERE fi.template_type = 'project'
    """)


def downgrade() -> None:
    """移除 template_type 列"""
    op.drop_column('flow_instances', 'template_type')
