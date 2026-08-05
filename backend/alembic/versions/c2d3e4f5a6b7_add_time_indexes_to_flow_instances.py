"""性能：flow_instances 时间列加单列索引

首页发起/归档趋势图（/dashboard/trends）按 initiated_at / completed_at
做时间范围聚合（月度近 12 个月 range 过滤），加单列索引后月度范围走
索引 range scan，防数据量大全表扫拖慢首页。

约定：模型索引声明与 DB 手工对账（同 P1-20 / b1c2d3e4f5a6）。
"""

from alembic import op
import sqlalchemy as sa

# revision 标识（前导：b1c2d3e4f5a6 为 idx_status 索引，当前 head）
revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # flow_instances 时间列单列索引：趋势图月度范围聚合走索引
    op.create_index("idx_initiated_at", "flow_instances", ["initiated_at"])
    op.create_index("idx_completed_at", "flow_instances", ["completed_at"])


def downgrade() -> None:
    op.drop_index("idx_completed_at", table_name="flow_instances")
    op.drop_index("idx_initiated_at", table_name="flow_instances")
