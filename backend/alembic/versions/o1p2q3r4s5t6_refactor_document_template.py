"""文件模板重构：template_id → organization_id + 中间表

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-07-22
"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision: str = 'o1p2q3r4s5t6'
down_revision: Union[str, None] = 'n1o2p3q4r5s6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 提前保存旧数据：(doc_id, old_template_id)
    old_rows = conn.execute(sa.text(
        "SELECT dt.id, dt.template_id, ft.organization_id "
        "FROM document_templates dt JOIN flow_templates ft ON ft.id = dt.template_id"
    )).fetchall()

    # 2. 新增 organization_id 列（先允许为空）
    op.add_column('document_templates',
        sa.Column('organization_id', sa.Integer(), nullable=True, comment='所属组织'))

    # 3. 用旧数据填充 organization_id
    for doc_id, _tpl_id, org_id in old_rows:
        conn.execute(sa.text(
            "UPDATE document_templates SET organization_id = :org_id WHERE id = :id"
        ), {"org_id": org_id, "id": doc_id})

    op.alter_column('document_templates', 'organization_id', nullable=False, existing_type=sa.Integer())
    op.create_foreign_key(
        'fk_dt_org', 'document_templates', 'organizations',
        ['organization_id'], ['id'], ondelete='CASCADE'
    )

    # 4. 删除旧的 template_id 列（先删外键再删列）
    op.drop_constraint('document_templates_ibfk_1', 'document_templates', type_='foreignkey')
    op.drop_column('document_templates', 'template_id')

    # 5. 创建中间表
    op.create_table(
        'template_document_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False, comment='流程模板 ID'),
        sa.Column('document_id', sa.Integer(), nullable=False, comment='文件模板 ID'),
        sa.Column('created_at', sa.DateTime(), default=datetime.now),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['flow_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['document_templates.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('template_id', 'document_id', name='uq_template_document'),
    )

    # 6. 为旧模板数据创建 link 记录
    for doc_id, tpl_id, _org_id in old_rows:
        conn.execute(sa.text(
            "INSERT INTO template_document_links (template_id, document_id) "
            "VALUES (:tpl_id, :doc_id) ON DUPLICATE KEY UPDATE id=id"
        ), {"tpl_id": tpl_id, "doc_id": doc_id})


def downgrade() -> None:
    conn = op.get_bind()

    # 1. 重建 template_id 列
    op.add_column('document_templates',
        sa.Column('template_id', sa.Integer(), nullable=True, comment='所属流程模板'))

    # 2. 从中间表恢复 template_id（取第一个关联的模板）
    links = conn.execute(sa.text(
        "SELECT document_id, MIN(template_id) FROM template_document_links GROUP BY document_id"
    )).fetchall()
    for doc_id, tpl_id in links:
        conn.execute(sa.text(
            "UPDATE document_templates SET template_id = :tpl_id WHERE id = :id"
        ), {"tpl_id": tpl_id, "id": doc_id})

    # 没有 link 记录的 doc 兜底
    conn.execute(sa.text(
        "UPDATE document_templates SET template_id = 0 WHERE template_id IS NULL"
    ))

    op.alter_column('document_templates', 'template_id', nullable=False, existing_type=sa.Integer())
    op.create_foreign_key(
        'document_templates_ibfk_1', 'document_templates', 'flow_templates',
        ['template_id'], ['id'], ondelete='CASCADE'
    )

    # 3. 删除中间表和组织外键
    op.drop_table('template_document_links')
    op.drop_constraint('fk_dt_org', 'document_templates', type_='foreignkey')
    op.drop_column('document_templates', 'organization_id')
