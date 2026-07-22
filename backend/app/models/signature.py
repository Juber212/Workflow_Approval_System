"""签名记录模型 —— 统一管理负责人/校验人/审批人的签名记录"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class Signature(Base):
    __tablename__ = "signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, comment="签在哪个文件")
    signer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="签名人")
    role_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="签名角色 assignee|checker|approver")
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="业务记录ID task_id/check_id/approval_id")
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id"), nullable=False, comment="所属节点")
    signature_x: Mapped[float] = mapped_column(Float, default=400, comment="签名X坐标（距左边）")
    signature_y: Mapped[float] = mapped_column(Float, default=100, comment="签名Y坐标（距底部）")
    signature_page: Mapped[int] = mapped_column(Integer, default=-1, comment="签名页码 -1=最后一页")
    signature_width: Mapped[float | None] = mapped_column(Float, nullable=True, default=None, comment="签名指定宽度（NULL=使用全局配置）")
    signature_height: Mapped[float | None] = mapped_column(Float, nullable=True, default=None, comment="签名指定高度（NULL=使用全局配置）")
    applied: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已写入PDF")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="同文件同角色多次签名排序")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
