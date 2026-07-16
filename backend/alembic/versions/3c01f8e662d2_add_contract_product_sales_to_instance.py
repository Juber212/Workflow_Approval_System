"""add_contract_product_sales_to_instance

Revision ID: 3c01f8e662d2
Revises: b4c5d6e7f8a9
Create Date: 2026-07-16 13:51:49.624339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c01f8e662d2'
down_revision: Union[str, None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """flow_instances 新增合同号、产品型号、销售经理字段"""
    op.add_column('flow_instances', sa.Column('contract_no', sa.String(length=100), nullable=True, comment='合同号'))
    op.add_column('flow_instances', sa.Column('product_model', sa.String(length=100), nullable=True, comment='产品型号'))
    op.add_column('flow_instances', sa.Column('sales_manager', sa.String(length=50), nullable=True, comment='销售经理'))


def downgrade() -> None:
    op.drop_column('flow_instances', 'sales_manager')
    op.drop_column('flow_instances', 'product_model')
    op.drop_column('flow_instances', 'contract_no')
