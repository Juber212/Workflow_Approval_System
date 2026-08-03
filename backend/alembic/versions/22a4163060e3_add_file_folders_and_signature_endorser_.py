"""add_file_folders_and_signature_endorser_to_presets

Revision ID: 22a4163060e3
Revises: q3r4s5t6u7v8
Create Date: 2026-07-31 12:18:38.151760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22a4163060e3'
down_revision: Union[str, None] = 'q3r4s5t6u7v8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """节点预设表新增：文件提交配置 + 签批开关 + 批准人"""
    op.add_column('node_presets', sa.Column('file_folders', sa.JSON(), nullable=True, comment='文件提交文件夹配置'))
    op.add_column('node_presets', sa.Column('require_assignee_signature', sa.Boolean(), nullable=False, server_default='1', comment='负责人提交时是否需要签名'))
    op.add_column('node_presets', sa.Column('require_checker_signature', sa.Boolean(), nullable=False, server_default='1', comment='校验人通过时是否需要签名'))
    op.add_column('node_presets', sa.Column('require_approver_signature', sa.Boolean(), nullable=False, server_default='1', comment='审批人通过时是否需要签名'))
    op.add_column('node_presets', sa.Column('require_endorser_signature', sa.Boolean(), nullable=False, server_default='1', comment='批准人通过时是否需要签名'))
    op.add_column('node_presets', sa.Column('endorser_id', sa.Integer(), nullable=True, comment='批准人 ID'))
    op.create_foreign_key(None, 'node_presets', 'users', ['endorser_id'], ['id'])


def downgrade() -> None:
    """回退：移除新增字段"""
    op.drop_constraint(None, 'node_presets', type_='foreignkey')  # endorser_id → users FK
    op.drop_column('node_presets', 'endorser_id')
    op.drop_column('node_presets', 'require_endorser_signature')
    op.drop_column('node_presets', 'require_approver_signature')
    op.drop_column('node_presets', 'require_checker_signature')
    op.drop_column('node_presets', 'require_assignee_signature')
    op.drop_column('node_presets', 'file_folders')
