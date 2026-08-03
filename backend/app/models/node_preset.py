"""节点预设模型 —— 用户保存常用节点配置以便复用"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class NodePreset(Base):
    """节点预设 —— 用户可将常用节点配置（负责人、校验人、审批人、时限等）保存为预设，拖拽到画布复用"""

    __tablename__ = "node_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="所属用户")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="预设名称（列表中显示）")
    node_name: Mapped[str] = mapped_column(String(30), nullable=False, comment="拖出后默认节点名称")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), comment="负责人 ID")
    checkers: Mapped[dict | None] = mapped_column(JSON, comment='校验人列表 [{"user_id": N}]')
    approvers: Mapped[dict | None] = mapped_column(JSON, comment='审批人列表 [{"user_id": N}]')
    time_limit_days: Mapped[int | None] = mapped_column(Integer, comment="完成时限（工作日）")
    require_file: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否必须上传文件")
    file_folders: Mapped[dict | None] = mapped_column(JSON, comment="文件提交文件夹配置")
    require_assignee_signature: Mapped[bool] = mapped_column(Boolean, default=True, comment="负责人提交时是否需要签名")
    require_checker_signature: Mapped[bool] = mapped_column(Boolean, default=True, comment="校验人通过时是否需要签名")
    require_approver_signature: Mapped[bool] = mapped_column(Boolean, default=True, comment="审批人通过时是否需要签名")
    require_endorser_signature: Mapped[bool] = mapped_column(Boolean, default=True, comment="批准人通过时是否需要签名")
    endorser_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), comment="批准人 ID")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号（预留拖拽排序）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
