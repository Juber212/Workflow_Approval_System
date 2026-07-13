"""实例连线模型"""

from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InstanceEdge(Base):
    __tablename__ = "instance_edges"
    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", name="uk_edge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id", ondelete="CASCADE"), nullable=False, comment="所属实例")
    source_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id", ondelete="CASCADE"), nullable=False, comment="源节点")
    target_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id", ondelete="CASCADE"), nullable=False, comment="目标节点")
