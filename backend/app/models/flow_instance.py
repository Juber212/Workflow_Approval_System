"""流程实例模型"""

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base
from app.models.enums import InstanceStatus, ArchiveStatus, Priority


class FlowInstance(Base):
    __tablename__ = "flow_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="流程实例名称")
    description: Mapped[str | None] = mapped_column(String(500), comment="补充说明")
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_templates.id"), nullable=False, comment="使用的模板")
    version_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_versions.id"), nullable=False, comment="基于的版本")
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, comment="所属组织")
    initiator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="发起人")
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.NORMAL, comment="优先级")
    status: Mapped[InstanceStatus] = mapped_column(Enum(InstanceStatus), default=InstanceStatus.CREATED, comment="主状态")
    archive_status: Mapped[ArchiveStatus] = mapped_column(Enum(ArchiveStatus), default=ArchiveStatus.NOT_ARCHIVED, comment="归档状态")
    termination_reason: Mapped[str | None] = mapped_column(String(500), comment="终止原因")
    initiated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="发起时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="完成时间")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, comment="归档时间")
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime, comment="终止时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
