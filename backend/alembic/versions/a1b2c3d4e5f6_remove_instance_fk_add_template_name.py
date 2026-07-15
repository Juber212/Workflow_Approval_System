"""移除 flow_instances.template_id 外键约束 + 新增 template_name 冗余列

实例已从模板独立复制节点/边/配置，不需要强关联。
删除模板时不再被实例阻挡。
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9a3b2c1d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 template_name 列 → 回填数据 → 移除 FK"""
    conn = op.get_bind()

    # 1. 新增列（允许为空，后续填充）
    op.add_column('flow_instances', sa.Column(
        'template_name', sa.String(100), nullable=True,
        comment='模板名称快照（创建实例时冗余存储）'
    ))

    # 2. 从 flow_templates 回填现有数据的 template_name
    conn.execute(sa.text(
        "UPDATE flow_instances fi "
        "JOIN flow_templates ft ON fi.template_id = ft.id "
        "SET fi.template_name = ft.name "
        "WHERE fi.template_name IS NULL"
    ))

    # 3. 回填后设为 NOT NULL
    op.alter_column('flow_instances', 'template_name',
                    existing_type=sa.String(100), nullable=False)

    # 4. 查询并删除外键约束
    result = conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'flow_instances' "
        "AND COLUMN_NAME = 'template_id' AND REFERENCED_TABLE_NAME = 'flow_templates'"
    ))
    fk_name = result.scalar()

    if fk_name:
        op.drop_constraint(fk_name, 'flow_instances', type_='foreignkey')


def downgrade() -> None:
    """删除 template_name 列 + 恢复 FK"""
    op.drop_column('flow_instances', 'template_name')
    op.create_foreign_key(
        'flow_instances_ibfk_1', 'flow_instances',
        'flow_templates', ['template_id'], ['id']
    )
