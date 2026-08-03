"""用户角色关联模型"""

from sqlalchemy import Integer, UniqueConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(Base):
    __tablename__ = "user_roles"
    # 索引名与既有 DB 索引对齐（P1-20 对账）；user_id 查询由 uk_user_role 最左前缀覆盖
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uk_user_role"),
        Index("role_id", "role_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # P1-20：补外键 + ondelete=CASCADE —— 删除用户/角色时自动清理关联（DB 原无 FK）
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户")
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, comment="角色")
