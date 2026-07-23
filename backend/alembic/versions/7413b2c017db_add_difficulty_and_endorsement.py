"""难度等级 + 批准人（Endorser）—— 数据库迁移

Revision ID: 7413b2c017db
Revises: o1p2q3r4s5t6
Create Date: 2026-07-23 12:22:53.682480
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7413b2c017db'
down_revision: Union[str, None] = 'o1p2q3r4s5t6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """难度等级 + 批准人：新增字段和表"""

    # ─── 1. flow_instances 新增 difficulty 列 ───
    op.add_column('flow_instances',
        sa.Column('difficulty', sa.String(length=20), nullable=False,
                  server_default='1', comment='难度等级: 1/2/3/4'))

    # ─── 2. template_nodes 新增批准人字段 ───
    op.add_column('template_nodes',
        sa.Column('endorser_id', sa.Integer(), nullable=True,
                  comment='批准人（仅difficulty=4时生效，单人）'))
    op.add_column('template_nodes',
        sa.Column('require_endorser_signature', sa.Boolean(), nullable=False,
                  server_default=sa.text('1'), comment='批准人通过时是否签名'))
    op.create_foreign_key('fk_template_nodes_endorser', 'template_nodes', 'users',
                          ['endorser_id'], ['id'])

    # ─── 3. instance_nodes 新增批准人字段 ───
    op.add_column('instance_nodes',
        sa.Column('endorser_id', sa.Integer(), nullable=True,
                  comment='批准人（单人）'))
    op.add_column('instance_nodes',
        sa.Column('require_endorser_signature', sa.Boolean(), nullable=False,
                  server_default=sa.text('1'), comment='批准人通过时是否签名'))
    op.create_foreign_key('fk_instance_nodes_endorser', 'instance_nodes', 'users',
                          ['endorser_id'], ['id'])

    # ─── 4. 新建 endorsements 表 ───
    op.create_table(
        'endorsements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('instance_id', sa.Integer(), nullable=False, comment='所属项目'),
        sa.Column('node_id', sa.Integer(), nullable=False, comment='所属节点'),
        sa.Column('task_id', sa.Integer(), nullable=True, comment='关联Task（结束节点为NULL）'),
        sa.Column('endorser_id', sa.Integer(), nullable=False, comment='批准人'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', comment='批准状态'),
        sa.Column('opinion', sa.String(length=500), nullable=True, comment='批准意见'),
        sa.Column('round', sa.Integer(), nullable=False, server_default='1', comment='节点轮次（第几轮批准）'),
        sa.Column('signature_applied', sa.Boolean(), nullable=False, server_default=sa.text('0'), comment='签名是否已上PDF'),
        sa.Column('signature_x', sa.Float(), nullable=True, comment='批准人调整后的签名X坐标'),
        sa.Column('signature_y', sa.Float(), nullable=True, comment='批准人调整后的签名Y坐标'),
        sa.Column('signature_page', sa.Integer(), nullable=True, comment='批准人选择的签名页码'),
        sa.Column('decided_at', sa.DateTime(), nullable=True, comment='批准决定时间'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['endorser_id'], ['users.id']),
        sa.ForeignKeyConstraint(['instance_id'], ['flow_instances.id']),
        sa.ForeignKeyConstraint(['node_id'], ['instance_nodes.id']),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """回滚：删除 endorsements 表和所有新增字段"""

    # 1. 删除 endorsements 表
    op.drop_table('endorsements')

    # 2. instance_nodes 移除批准人字段
    op.drop_constraint('fk_instance_nodes_endorser', 'instance_nodes', type_='foreignkey')
    op.drop_column('instance_nodes', 'require_endorser_signature')
    op.drop_column('instance_nodes', 'endorser_id')

    # 3. template_nodes 移除批准人字段
    op.drop_constraint('fk_template_nodes_endorser', 'template_nodes', type_='foreignkey')
    op.drop_column('template_nodes', 'require_endorser_signature')
    op.drop_column('template_nodes', 'endorser_id')

    # 4. flow_instances 移除 difficulty 列
    op.drop_column('flow_instances', 'difficulty')
