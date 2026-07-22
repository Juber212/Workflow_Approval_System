"""多角色签批 —— 新建 signatures 表 + 节点签批开关拆分为三个

Revision ID: h3i4j5k6l7m8
Revises: 7a1b2c3d4e5f
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h3i4j5k6l7m8'
down_revision: Union[str, None] = '7a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 新建 signatures 表
    op.create_table(
        'signatures',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.id', ondelete='CASCADE'), nullable=False, comment='签在哪个文件'),
        sa.Column('signer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, comment='签名人'),
        sa.Column('role_type', sa.String(20), nullable=False, comment='签名角色 assignee|checker|approver'),
        sa.Column('source_id', sa.Integer(), nullable=False, comment='业务记录ID task_id/check_id/approval_id'),
        sa.Column('node_id', sa.Integer(), sa.ForeignKey('instance_nodes.id'), nullable=False, comment='所属节点'),
        sa.Column('signature_x', sa.Float(), default=400, comment='签名X坐标'),
        sa.Column('signature_y', sa.Float(), default=100, comment='签名Y坐标'),
        sa.Column('signature_page', sa.Integer(), default=-1, comment='签名页码 -1=最后一页'),
        sa.Column('applied', sa.Boolean(), default=False, comment='是否已写入PDF'),
        sa.Column('sort_order', sa.Integer(), default=0, comment='同文件同角色多次签名排序'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
    )

    # 2. template_nodes: require_signature → require_approver_signature + 新增两个开关
    op.alter_column(
        'template_nodes', 'require_signature',
        new_column_name='require_approver_signature',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default=sa.text('1'),
    )
    op.add_column('template_nodes', sa.Column(
        'require_assignee_signature', sa.Boolean(), nullable=False,
        server_default=sa.text('1'), comment='负责人提交时是否签名'
    ))
    op.add_column('template_nodes', sa.Column(
        'require_checker_signature', sa.Boolean(), nullable=False,
        server_default=sa.text('1'), comment='校验人通过时是否签名'
    ))

    # 3. instance_nodes: 同上
    op.alter_column(
        'instance_nodes', 'require_signature',
        new_column_name='require_approver_signature',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default=sa.text('1'),
    )
    op.add_column('instance_nodes', sa.Column(
        'require_assignee_signature', sa.Boolean(), nullable=False,
        server_default=sa.text('1'), comment='负责人提交时是否签名'
    ))
    op.add_column('instance_nodes', sa.Column(
        'require_checker_signature', sa.Boolean(), nullable=False,
        server_default=sa.text('1'), comment='校验人通过时是否签名'
    ))


def downgrade() -> None:
    # 1. 恢复 instance_nodes
    op.drop_column('instance_nodes', 'require_checker_signature')
    op.drop_column('instance_nodes', 'require_assignee_signature')
    op.alter_column(
        'instance_nodes', 'require_approver_signature',
        new_column_name='require_signature',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default=sa.text('1'),
    )

    # 2. 恢复 template_nodes
    op.drop_column('template_nodes', 'require_checker_signature')
    op.drop_column('template_nodes', 'require_assignee_signature')
    op.alter_column(
        'template_nodes', 'require_approver_signature',
        new_column_name='require_signature',
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default=sa.text('1'),
    )

    # 3. 删除 signatures 表
    op.drop_table('signatures')
