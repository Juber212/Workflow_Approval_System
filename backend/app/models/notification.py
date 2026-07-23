"""通知模型 —— 站内通知，用户离线也可回看"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="接收人")
    type: Mapped[str] = mapped_column(String(30), nullable=False, comment="通知类型: task_assigned/check_assigned/approval_assigned/endorsement_assigned/check_returned/approval_rejected/final_rejected/endorsement_rejected")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="通知标题")
    content: Mapped[str] = mapped_column(String(500), nullable=False, comment="通知内容")
    link: Mapped[str | None] = mapped_column(String(300), comment="点击跳转路径")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已读")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="通知时间")
