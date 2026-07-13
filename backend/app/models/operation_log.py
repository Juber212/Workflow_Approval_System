"""操作日志模型（按年分区，只写不删）"""

from sqlalchemy import String, Integer, DateTime, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base
from app.models.enums import OperatorType


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True, comment="自增ID")
    instance_id: Mapped[int | None] = mapped_column(Integer, comment="所属流程实例")
    operator_type: Mapped[OperatorType] = mapped_column(Enum(OperatorType), default=OperatorType.USER, comment="操作者类型")
    operator_id: Mapped[int | None] = mapped_column(Integer, comment="操作人；系统操作为NULL")
    triggered_by: Mapped[int | None] = mapped_column(Integer, comment="可选触发人")
    node_id: Mapped[int | None] = mapped_column(Integer, comment="关联实例节点")
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作类型")
    round: Mapped[int] = mapped_column(Integer, default=1, comment="所属轮次")
    description: Mapped[str] = mapped_column(String(500), nullable=False, comment="自动生成的描述文本")
    detail: Mapped[dict | None] = mapped_column(JSON, comment="操作详情")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, primary_key=True, comment="操作时间（分区键）")
