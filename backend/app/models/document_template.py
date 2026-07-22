"""文件模板模型 —— 挂在流程模板下，下载时自动替换 {{占位符}}"""

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class DocumentTemplate(Base):
    """流程模板关联的文件模板（Word/Excel），内含 {{变量}} 占位符"""

    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("flow_templates.id", ondelete="CASCADE"),
        nullable=False, comment="所属流程模板"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称（显示给用户）")
    original_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="文件存储路径（相对 STORAGE_ROOT）")
    file_size: Mapped[int] = mapped_column(Integer, default=0, comment="文件大小（字节）")
    file_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="文件类型：docx / xlsx")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="上传人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
