"""add_conversion_status_to_files

Revision ID: a1b2c3d4e5f7
Revises: fix_comments_001
Create Date: 2026-07-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "fix_comments_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """File 表新增 conversion_status 和 conversion_error 字段"""
    op.add_column(
        "files",
        sa.Column(
            "conversion_status",
            sa.String(20),
            nullable=False,
            server_default="ready",
            comment="PDF转换状态: pending/converting/ready/failed。PDF文件默认ready",
        ),
    )
    op.add_column(
        "files",
        sa.Column(
            "conversion_error",
            sa.String(500),
            nullable=True,
            comment="转换失败原因",
        ),
    )


def downgrade() -> None:
    op.drop_column("files", "conversion_error")
    op.drop_column("files", "conversion_status")
