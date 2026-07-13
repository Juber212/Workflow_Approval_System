"""模板节点模型（统一节点模型）"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class TemplateNode(Base):
    __tablename__ = "template_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_templates.id", ondelete="CASCADE"), nullable=False, comment="所属模板")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="节点名称")
    description: Mapped[str | None] = mapped_column(String(500), comment="节点描述")
    is_start: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否开始节点")
    is_end: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否结束节点")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), comment="负责人")
    time_limit_days: Mapped[int | None] = mapped_column(Integer, comment="完成时限天数")
    require_file: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否必须上传文件")
    approvers: Mapped[dict | None] = mapped_column(JSON, comment="审批人列表")
    checkers: Mapped[dict | None] = mapped_column(JSON, comment="校验人列表")
    approval_strategy: Mapped[str] = mapped_column(String(30), default="all_approve", comment="审批策略")
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否可选节点")
    position_x: Mapped[float] = mapped_column(Float, default=0, comment="画布X坐标")
    position_y: Mapped[float] = mapped_column(Float, default=0, comment="画布Y坐标")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
