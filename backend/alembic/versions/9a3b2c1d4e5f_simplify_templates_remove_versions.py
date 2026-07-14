"""simplify_templates_remove_versions

Revision ID: 9a3b2c1d4e5f
Revises: cdc82f5bf321
Create Date: 2026-07-14 15:30:00.000000

变更内容：
- 删除 flow_versions 表
- flow_instances 删除 version_id 列及其外键
- flow_templates 删除 status、current_version 列
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '9a3b2c1d4e5f'
down_revision: Union[str, None] = 'cdc82f5bf321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """简化：删除版本系统"""

    # 1. 删 flow_instances 的 version_id FK（名称由 MySQL 自动生成，需动态查找）
    #    先查 FK 名称再删除
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'flow_instances'
          AND COLUMN_NAME = 'version_id'
          AND REFERENCED_TABLE_NAME = 'flow_versions'
    """))
    fk_name = result.scalar()
    if fk_name:
        op.drop_constraint(fk_name, 'flow_instances', type_='foreignkey')

    # 2. 删除 version_id 列
    op.drop_column('flow_instances', 'version_id')

    # 3. 删除 flow_versions 表
    op.drop_table('flow_versions')

    # 4. 删除 flow_templates 的状态字段
    op.drop_column('flow_templates', 'status')
    op.drop_column('flow_templates', 'current_version')


def downgrade() -> None:
    """恢复（仅结构，不恢复数据）"""
    op.add_column('flow_templates', sa.Column('current_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('flow_templates', sa.Column('status', sa.String(20), nullable=False, server_default='draft'))
    op.create_table(
        'flow_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), server_default='published'),
        sa.Column('nodes_snapshot', sa.JSON(), nullable=False),
        sa.Column('edges_snapshot', sa.JSON(), nullable=False),
        sa.Column('published_by', sa.Integer(), nullable=False),
        sa.Column('published_at', sa.DateTime()),
        sa.Column('soft_config_overrides', sa.JSON()),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('flow_instances', sa.Column('version_id', sa.Integer(), nullable=True))
