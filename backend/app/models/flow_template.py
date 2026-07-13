"""流程模板模型"""

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class FlowTemplate(Base):
    __tablename__ = "flow_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="流程名称")
    description: Mapped[str | None] = mapped_column(String(500), comment="流程描述")
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, comment="所属组织")
    status: Mapped[str] = mapped_column(String(20), default="draft", comment="模板状态")
    current_version: Mapped[int] = mapped_column(Integer, default=0, comment="当前最新版本号")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="创建人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
