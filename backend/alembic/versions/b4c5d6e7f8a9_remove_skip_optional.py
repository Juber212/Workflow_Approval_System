"""删除 is_skipped / is_optional 列 —— 跳过节点功能已废除

补交文件功能覆盖了跳过节点的使用场景，清理相关数据库列。
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """先做数据兼容（skipped → finished），再 DROP 列"""
    conn = op.get_bind()

    # 1. 将已跳过的节点状态改为已完成
    conn.execute(sa.text(
        "UPDATE instance_nodes SET status = 'finished' WHERE status = 'skipped'"
    ))

    # 2. 删除 instance_nodes 中的 is_skipped 和 is_optional 列
    op.drop_column('instance_nodes', 'is_skipped')
    op.drop_column('instance_nodes', 'is_optional')

    # 3. 删除 template_nodes 中的 is_optional 列
    op.drop_column('template_nodes', 'is_optional')


def downgrade() -> None:
    """恢复列（默认值 False）"""
    op.add_column('template_nodes', sa.Column(
        'is_optional', sa.Boolean(), nullable=False, server_default=sa.text('0'),
        comment='是否可选节点'
    ))
    op.add_column('instance_nodes', sa.Column(
        'is_optional', sa.Boolean(), nullable=False, server_default=sa.text('0'),
        comment='是否可选节点'
    ))
    op.add_column('instance_nodes', sa.Column(
        'is_skipped', sa.Boolean(), nullable=False, server_default=sa.text('0'),
        comment='是否被跳过'
    ))
