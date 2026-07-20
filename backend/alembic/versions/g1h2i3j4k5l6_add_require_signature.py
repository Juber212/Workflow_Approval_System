"""添加签批开关和签名位置字段

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-07-17 17:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'g1h2i3j4k5l6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # ── template_nodes：模板默认签批配置 ──
    op.add_column('template_nodes',
        sa.Column('require_signature', sa.Boolean(), nullable=False,
                  server_default=sa.text('1'), comment='是否要求签批'))
    op.add_column('template_nodes',
        sa.Column('signature_x', sa.Float(), nullable=False,
                  server_default=sa.text('400'), comment='签名默认X坐标（距左边）'))
    op.add_column('template_nodes',
        sa.Column('signature_y', sa.Float(), nullable=False,
                  server_default=sa.text('100'), comment='签名默认Y坐标（距底部）'))
    op.add_column('template_nodes',
        sa.Column('signature_page', sa.Integer(), nullable=False,
                  server_default=sa.text('-1'), comment='签名默认页码（-1=最后一页）'))

    # ── instance_nodes：实例节点签批配置（从模板复制，可覆盖） ──
    op.add_column('instance_nodes',
        sa.Column('require_signature', sa.Boolean(), nullable=False,
                  server_default=sa.text('1'), comment='是否要求签批'))
    op.add_column('instance_nodes',
        sa.Column('signature_x', sa.Float(), nullable=False,
                  server_default=sa.text('400'), comment='签名默认X坐标（距左边）'))
    op.add_column('instance_nodes',
        sa.Column('signature_y', sa.Float(), nullable=False,
                  server_default=sa.text('100'), comment='签名默认Y坐标（距底部）'))
    op.add_column('instance_nodes',
        sa.Column('signature_page', sa.Integer(), nullable=False,
                  server_default=sa.text('-1'), comment='签名默认页码（-1=最后一页）'))

    # ── approvals：审批人微调后的签名位置（NULL=使用节点默认值） ──
    op.add_column('approvals',
        sa.Column('signature_x', sa.Float(), nullable=True,
                  comment='审批人调整后的签名X坐标'))
    op.add_column('approvals',
        sa.Column('signature_y', sa.Float(), nullable=True,
                  comment='审批人调整后的签名Y坐标'))
    op.add_column('approvals',
        sa.Column('signature_page', sa.Integer(), nullable=True,
                  comment='审批人选择的签名页码'))


def downgrade():
    op.drop_column('approvals', 'signature_page')
    op.drop_column('approvals', 'signature_y')
    op.drop_column('approvals', 'signature_x')
    op.drop_column('instance_nodes', 'signature_page')
    op.drop_column('instance_nodes', 'signature_y')
    op.drop_column('instance_nodes', 'signature_x')
    op.drop_column('instance_nodes', 'require_signature')
    op.drop_column('template_nodes', 'signature_page')
    op.drop_column('template_nodes', 'signature_y')
    op.drop_column('template_nodes', 'signature_x')
    op.drop_column('template_nodes', 'require_signature')
