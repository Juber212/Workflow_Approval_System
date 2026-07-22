"""add file_folders to template_nodes and instance_nodes, folder_name to files

Revision ID: 7a1b2c3d4e5f
Revises: g1h2i3j4k5l6
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a1b2c3d4e5f'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade():
    """新增 file_folders 和 folder_name 列"""
    # 1. 模板节点新增文件提交配置
    op.add_column('template_nodes',
        sa.Column('file_folders', sa.JSON(), nullable=True,
                  comment='文件提交文件夹配置 [{name, required, file_count}]'))

    # 2. 实例节点新增文件提交配置快照
    op.add_column('instance_nodes',
        sa.Column('file_folders', sa.JSON(), nullable=True,
                  comment='文件提交文件夹配置快照'))

    # 3. 文件表新增所属文件夹名称
    op.add_column('files',
        sa.Column('folder_name', sa.String(100), nullable=True,
                  comment='所属文件夹名称'))


def downgrade():
    """回滚：删除新增列"""
    op.drop_column('files', 'folder_name')
    op.drop_column('instance_nodes', 'file_folders')
    op.drop_column('template_nodes', 'file_folders')
