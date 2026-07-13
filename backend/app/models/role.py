"""角色模型"""

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, comment="角色标识")
    description: Mapped[str | None] = mapped_column(String(200), comment="角色描述")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
