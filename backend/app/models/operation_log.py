"""操作日志模型（按年分区，只写不删）"""

from sqlalchemy import String, Integer, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base
from app.models.enums import OperatorType


class OperationLog(Base):
    __tablename__ = "operation_logs"
    # 索引名与既有 DB 索引对齐（P1-20 对账；分区表，索引均非分区键）
    __table_args__ = (
        Index("idx_instance", "instance_id"),
        Index("idx_created", "created_at"),
        Index("idx_instance_created", "instance_id", "created_at"),
        Index("idx_node_round", "node_id", "round"),
        Index("idx_operator", "operator_id"),
        Index("idx_type", "operation_type"),
    )

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True, comment="自增ID")
    instance_id: Mapped[int | None] = mapped_column(Integer, comment="所属项目")
    operator_type: Mapped[str] = mapped_column(String(20), default=OperatorType.USER.value, comment="操作者类型")
    operator_id: Mapped[int | None] = mapped_column(Integer, comment="操作人；系统操作为NULL")
    triggered_by: Mapped[int | None] = mapped_column(Integer, comment="可选触发人")
    node_id: Mapped[int | None] = mapped_column(Integer, comment="关联实例节点")
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作类型")
    round: Mapped[int] = mapped_column(Integer, default=1, comment="所属轮次")
    description: Mapped[str] = mapped_column(String(500), nullable=False, comment="自动生成的描述文本")
    detail: Mapped[dict | None] = mapped_column(JSON, comment="操作详情")
    # 注意：created_at 设为主键的一部分是 MySQL 分区强制要求 ——
    #   分区键必须属于所有唯一键（含主键），否则 CREATE TABLE 报错
    #   "A PRIMARY KEY must include all columns in the table's partitioning function"
    #   所以这里形成 (id, created_at) 复合主键，由 autoincrement 保证 id 自增唯一
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, primary_key=True, comment="操作时间（分区键）")
