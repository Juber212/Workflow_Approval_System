"""文件模板表 —— 挂在流程模板下，下载时自动替换 {{占位符}}

Revision ID: n1o2p3q4r5s6
Revises: m8n9o0p1q2r3
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'n1o2p3q4r5s6'
down_revision: Union[str, None] = 'm8n9o0p1q2r3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False, comment='所属流程模板'),
        sa.Column('name', sa.String(100), nullable=False, comment='模板名称（显示给用户）'),
        sa.Column('original_name', sa.String(200), nullable=False, comment='原始文件名'),
        sa.Column('file_path', sa.String(500), nullable=False, comment='文件存储路径'),
        sa.Column('file_size', sa.Integer(), default=0, comment='文件大小（字节）'),
        sa.Column('file_type', sa.String(10), nullable=False, comment='文件类型：docx / xlsx'),
        sa.Column('created_by', sa.Integer(), nullable=False, comment='上传人'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['flow_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )


def downgrade() -> None:
    op.drop_table('document_templates')
