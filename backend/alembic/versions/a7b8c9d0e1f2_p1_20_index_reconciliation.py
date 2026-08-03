"""P1-20 模型索引对账 —— 只增不删

补齐 DB 缺失的热点索引：
1. flow_instances.idx_status / idx_template_type —— 列表页按状态/类型筛选高频
2. notifications.idx_instance —— 按实例清理通知（clear_related）
3. signatures.idx_source —— 按业务记录 source_id 查签名

说明：user_roles 的外键级联（ondelete=CASCADE）DB 初始 schema 已具备
（user_roles_ibfk_1/2），模型补 ForeignKey 声明仅为元数据对齐，无需迁移。

约定：此后禁用 autogenerate 直改生产，模型索引声明须与 DB 手工对账。
"""

from alembic import op
import sqlalchemy as sa

# revision 标识（前导：c3d4e5f6a7b8 为当前 head）
revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. flow_instances 状态 / 类型筛选索引（列表页 WHERE status IN (...) / template_type='project'）
    op.create_index("idx_status", "flow_instances", ["status"])
    op.create_index("idx_template_type", "flow_instances", ["template_type"])
    # 2. notifications 按实例清理通知
    op.create_index("idx_instance", "notifications", ["instance_id"])
    # 3. signatures 按业务记录查签名（source_id）
    op.create_index("idx_source", "signatures", ["source_id"])


def downgrade() -> None:
    op.drop_index("idx_source", table_name="signatures")
    op.drop_index("idx_instance", table_name="notifications")
    op.drop_index("idx_template_type", table_name="flow_instances")
    op.drop_index("idx_status", table_name="flow_instances")
