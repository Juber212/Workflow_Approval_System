"""实例节点模型（运行时状态）"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base
from app.models.enums import InstanceNodeStatus


class InstanceNode(Base):
    __tablename__ = "instance_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id", ondelete="CASCADE"), nullable=False, comment="所属实例")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="节点名称")
    description: Mapped[str | None] = mapped_column(String(500), comment="节点描述")
    is_start: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否开始节点")
    is_end: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否结束节点")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), comment="负责人")
    time_limit_days: Mapped[int | None] = mapped_column(Integer, comment="完成时限天数")
    deadline: Mapped[datetime | None] = mapped_column(DateTime, comment="截止时间")
    require_file: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否必须上传文件")
    approvers: Mapped[dict | None] = mapped_column(JSON, comment="审批人列表")
    checkers: Mapped[dict | None] = mapped_column(JSON, comment="校验人列表")
    approval_strategy: Mapped[str] = mapped_column(String(30), default="all_approve", comment="审批策略")
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否可选节点")
    is_skipped: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否被跳过")
    status: Mapped[InstanceNodeStatus] = mapped_column(Enum(InstanceNodeStatus), default=InstanceNodeStatus.WAITING, comment="节点状态")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号")
    incoming_count: Mapped[int] = mapped_column(Integer, default=0, comment="汇合节点上游连线数")
    arrived_count: Mapped[int] = mapped_column(Integer, default=0, comment="已完成上游分支数")
    round: Mapped[int] = mapped_column(Integer, default=1, comment="执行轮次")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="节点激活时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="节点完成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
