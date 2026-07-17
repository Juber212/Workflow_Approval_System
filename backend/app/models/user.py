"""用户模型"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, comment="登录用户名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="加密密码")
    real_name: Mapped[str] = mapped_column(String(20), nullable=False, comment="真实姓名")
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, comment="所属组织")
    email: Mapped[str | None] = mapped_column(String(100), comment="邮箱")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    signature_image: Mapped[str | None] = mapped_column(String(500), comment="签名图片路径")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联组织
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
