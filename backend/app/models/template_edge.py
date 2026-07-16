"""模板连线模型"""

from sqlalchemy import Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TemplateEdge(Base):
    __tablename__ = "template_edges"
    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", name="uk_edge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_templates.id", ondelete="CASCADE"), nullable=False, comment="所属模板")
    source_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("template_nodes.id", ondelete="CASCADE"), nullable=False, comment="源节点")
    target_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("template_nodes.id", ondelete="CASCADE"), nullable=False, comment="目标节点")
    points: Mapped[str | None] = mapped_column(Text, nullable=True, comment="折线路径点串（LogicFlow points 字符串，保存后恢复避免路由重算）")
