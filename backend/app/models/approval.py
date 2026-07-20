"""审批记录模型"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id"), nullable=False, comment="所属项目")
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id"), nullable=False, comment="所属节点")
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tasks.id"), comment="关联Task（结束节点为NULL）")
    approver_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="审批人")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="审批状态")
    opinion: Mapped[str | None] = mapped_column(String(500), comment="审批意见")
    round: Mapped[int] = mapped_column(Integer, default=1, comment="节点轮次（第几轮审批）")
    reject_target_node_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("instance_nodes.id"), comment="仅结束节点终审总驳回目标")
    signature_applied: Mapped[bool] = mapped_column(Boolean, default=False, comment="签名是否已上PDF")
    signature_x: Mapped[float | None] = mapped_column(Float, nullable=True, comment="审批人调整后的签名X坐标")
    signature_y: Mapped[float | None] = mapped_column(Float, nullable=True, comment="审批人调整后的签名Y坐标")
    signature_page: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="审批人选择的签名页码")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, comment="审批决定时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
