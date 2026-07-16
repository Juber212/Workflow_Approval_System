"""文件模型"""

from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id"), nullable=False, comment="所属项目")
    node_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("instance_nodes.id"), comment="上传节点")
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tasks.id"), comment="关联任务（补交可为NULL）")
    round: Mapped[int] = mapped_column(Integer, default=1, comment="文件所属轮次")
    uploader_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="上传人")
    upload_type: Mapped[str] = mapped_column(String(20), default="normal", comment="上传类型")
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="存储文件名（UUID）")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="最终PDF存储相对路径")
    file_size: Mapped[int | None] = mapped_column(BigInteger, comment="最终PDF大小（字节）")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/pdf", comment="最终文件MIME类型")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
