"""模板分类 —— 管理员可为文件模板创建自定义分类（模板包），按组织隔离

新增表：
  - template_categories：分类（模板包），按组织隔离
  - template_category_documents：分类 ↔ 文件模板（多对多）
修改表：
  - template_document_links：新增 category_id 字段（可选），document_id 改可空
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "q3r4s5t6u7v8"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 模板分类表（前次失败可能已建，加 IF NOT EXISTS 保护）
    op.execute("""
        CREATE TABLE IF NOT EXISTS template_categories (
            id INTEGER NOT NULL AUTO_INCREMENT,
            organization_id INTEGER NOT NULL COMMENT '所属组织',
            name VARCHAR(100) NOT NULL COMMENT '分类名称',
            description VARCHAR(200) COMMENT '分类描述',
            created_by INTEGER NOT NULL COMMENT '创建人',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    """)

    # 2. 分类 ↔ 文件模板 多对多中间表
    op.execute("""
        CREATE TABLE IF NOT EXISTS template_category_documents (
            id INTEGER NOT NULL AUTO_INCREMENT,
            category_id INTEGER NOT NULL COMMENT '分类 ID',
            document_id INTEGER NOT NULL COMMENT '文件模板 ID',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uq_category_document (category_id, document_id),
            FOREIGN KEY (category_id) REFERENCES template_categories (id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES document_templates (id) ON DELETE CASCADE
        )
    """)

    # 3. template_document_links：新增 category_id（可选），document_id 改可空
    #    注意：不删旧唯一约束 uq_template_document，MySQL 在 document_id 可空后
    #    允许多个 (template_id, NULL) 行，旧约束仍然有效
    #    用异常捕获处理列/约束已存在的情况
    from alembic.ddl import mysql as alembic_mysql
    import sqlalchemy as sa

    try:
        op.add_column(
            "template_document_links",
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("template_categories.id", ondelete="CASCADE"), nullable=True, comment="关联整个分类（与 document_id 互斥）"),
        )
    except Exception:
        pass  # 前次失败可能已建

    # document_id 改可空
    op.alter_column("template_document_links", "document_id", existing_type=sa.Integer(), nullable=True)

    # 新增 (template_id, category_id) 唯一约束（可能已存在）
    try:
        op.create_unique_constraint("uq_template_category_link", "template_document_links", ["template_id", "category_id"])
    except Exception:
        pass


def downgrade() -> None:
    # 1. 回退 template_document_links
    op.drop_constraint("uq_template_category_link", "template_document_links", type_="unique")
    # 删除有 category_id 的行
    op.execute("DELETE FROM template_document_links WHERE category_id IS NOT NULL")
    op.drop_column("template_document_links", "category_id")
    op.alter_column("template_document_links", "document_id", existing_type=sa.Integer(), nullable=False)

    # 2. 删除中间表
    op.drop_table("template_category_documents")

    # 3. 删除分类表
    op.drop_table("template_categories")
