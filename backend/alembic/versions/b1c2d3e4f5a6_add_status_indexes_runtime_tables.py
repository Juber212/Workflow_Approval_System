"""性能：四张运行时表加 status 单列索引

优化全局超期/统计查询（首页统计超期数字 + 超期预警页）——
`Task.status NOT IN (completed, terminated)` 原无 status 单列索引可走，
数据量增大时全表扫拖慢首页/超期页。加单列索引后按状态索引扫描。

涉及表：tasks / check_records / approvals / endorsements
（status 在各表 per-table 命名空间下可重名，与 flow_instances.idx_status 不冲突）

约定：模型索引声明与 DB 手工对账（同 P1-20）。
"""

from alembic import op
import sqlalchemy as sa

# revision 标识（前导：a7b8c9d0e1f2 为 P1-20 索引对账，当前 head）
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 四张运行时表 status 单列索引：全局超期 count / 列表按状态过滤走索引
    op.create_index("idx_status", "tasks", ["status"])
    op.create_index("idx_status", "check_records", ["status"])
    op.create_index("idx_status", "approvals", ["status"])
    op.create_index("idx_status", "endorsements", ["status"])


def downgrade() -> None:
    op.drop_index("idx_status", table_name="endorsements")
    op.drop_index("idx_status", table_name="approvals")
    op.drop_index("idx_status", table_name="check_records")
    op.drop_index("idx_status", table_name="tasks")
