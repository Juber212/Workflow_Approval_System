"""流程版本模型"""

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class FlowVersion(Base):
    __tablename__ = "flow_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_templates.id"), nullable=False, comment="所属模板")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号")
    status: Mapped[str] = mapped_column(String(20), default="published", comment="版本状态")
    nodes_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, comment="节点快照")
    edges_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, comment="连线快照")
    published_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="发布人")
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="发布时间")
    soft_config_overrides: Mapped[dict | None] = mapped_column(JSON, comment="版本级节点软配置覆盖层")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
