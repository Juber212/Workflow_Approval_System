"""签名记录模型 —— 统一管理负责人/校验人/审批人的签名记录"""

from sqlalchemy import String, Integer, Boolean, DateTime, Date, ForeignKey, Float, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date

from app.core.database import Base


class Signature(Base):
    __tablename__ = "signatures"
    # 索引名与既有 DB 索引对齐（P1-20 对账），另补 idx_source（按业务记录查签名）
    __table_args__ = (
        Index("file_id", "file_id"),
        Index("node_id", "node_id"),
        Index("signer_id", "signer_id"),
        Index("idx_source", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, comment="签在哪个文件")
    signer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="签名人")
    role_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="签名角色 assignee|checker|approver|endorser")
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="业务记录ID task_id/check_id/approval_id")
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id"), nullable=False, comment="所属节点")
    signature_x: Mapped[float] = mapped_column(Float, default=400, comment="签名X坐标（距左边）")
    signature_y: Mapped[float] = mapped_column(Float, default=100, comment="签名Y坐标（距底部）")
    signature_page: Mapped[int] = mapped_column(Integer, default=-1, comment="签名页码 -1=最后一页")
    signature_width: Mapped[float | None] = mapped_column(Float, nullable=True, default=None, comment="签名指定宽度（NULL=使用全局配置）")
    signature_height: Mapped[float | None] = mapped_column(Float, nullable=True, default=None, comment="签名指定高度（NULL=使用全局配置）")
    applied: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已写入PDF")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="同文件同角色多次签名排序")
    # 签批日期
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="签名日期")
    show_date: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否在PDF上显示日期")
    date_x: Mapped[float | None] = mapped_column(Float, nullable=True, comment="日期文本X坐标")
    date_y: Mapped[float | None] = mapped_column(Float, nullable=True, comment="日期文本Y坐标")
    date_font_size: Mapped[int] = mapped_column(Integer, default=14, comment="日期字号(pt)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
