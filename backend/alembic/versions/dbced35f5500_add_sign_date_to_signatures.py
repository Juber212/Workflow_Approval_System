"""add_sign_date_to_signatures

Revision ID: dbced35f5500
Revises: a1b2c3d4e5f7
Create Date: 2026-07-27 08:36:57.421202

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dbced35f5500'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """签名表新增签批日期字段"""
    op.add_column("signatures", sa.Column("sign_date", sa.Date(), nullable=True, comment="签名日期"))
    op.add_column("signatures", sa.Column("show_date", sa.Boolean(), nullable=False, server_default="1", comment="是否显示日期"))
    op.add_column("signatures", sa.Column("date_x", sa.Float(), nullable=True, comment="日期文本X坐标"))
    op.add_column("signatures", sa.Column("date_y", sa.Float(), nullable=True, comment="日期文本Y坐标"))
    op.add_column("signatures", sa.Column("date_font_size", sa.Integer(), nullable=False, server_default="12", comment="日期字号(pt)"))


def downgrade() -> None:
    op.drop_column("signatures", "date_font_size")
    op.drop_column("signatures", "date_y")
    op.drop_column("signatures", "date_x")
    op.drop_column("signatures", "show_date")
    op.drop_column("signatures", "sign_date")
