"""文件模板模型 —— 挂在组织下，通过中间表关联流程模板，下载时自动替换 {{占位符}}"""

from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class DocumentTemplate(Base):
    """组织级别的文件模板（Word/Excel），内含 {{变量}} 占位符，由管理员统一上传"""

    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, comment="所属组织"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称（显示给用户）")
    original_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="文件存储路径（相对 STORAGE_ROOT）")
    file_size: Mapped[int] = mapped_column(Integer, default=0, comment="文件大小（字节）")
    file_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="文件类型：docx / xlsx")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="上传人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class TemplateDocumentLink(Base):
    """流程模板 ↔ 文件模板 多对多关联中间表"""

    __tablename__ = "template_document_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("flow_templates.id", ondelete="CASCADE"),
        nullable=False, comment="流程模板 ID"
    )
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_templates.id", ondelete="CASCADE"),
        nullable=False, comment="文件模板 ID"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("template_id", "document_id", name="uq_template_document"),
    )
