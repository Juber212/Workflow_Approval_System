"""任务模型"""

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base
from app.models.enums import TaskStatus


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id"), nullable=False, comment="所属流程实例")
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id"), nullable=False, comment="所属节点")
    assignee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="负责人")
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, comment="任务状态")
    assignee_note: Mapped[str | None] = mapped_column(String(500), comment="负责人备注")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, comment="提交时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="完成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
