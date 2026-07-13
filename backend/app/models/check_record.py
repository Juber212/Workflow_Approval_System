"""校验记录模型"""

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class CheckRecord(Base):
    __tablename__ = "check_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id"), nullable=False, comment="所属流程实例")
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id"), nullable=False, comment="所属节点")
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False, comment="关联Task")
    checker_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="校验人")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="校验状态")
    opinion: Mapped[str | None] = mapped_column(String(500), comment="校验意见")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, comment="校验决定时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
