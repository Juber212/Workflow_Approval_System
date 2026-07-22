"""实例节点模型（运行时状态）"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class InstanceNode(Base):
    __tablename__ = "instance_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id", ondelete="CASCADE"), nullable=False, comment="所属实例")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="节点名称")
    description: Mapped[str | None] = mapped_column(String(500), comment="节点描述")
    is_start: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否开始节点")
    is_end: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否结束节点")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), comment="负责人")
    time_limit_days: Mapped[int | None] = mapped_column(Integer, comment="完成时限（工作日）")
    deadline: Mapped[datetime | None] = mapped_column(DateTime, comment="截止时间")
    require_file: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否必须上传文件")
    file_folders: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="文件提交文件夹配置快照")
    approvers: Mapped[dict | None] = mapped_column(JSON, comment="审批人列表")
    checkers: Mapped[dict | None] = mapped_column(JSON, comment="校验人列表")
    approval_strategy: Mapped[str] = mapped_column(String(30), default="all_approve", comment="审批策略")
    require_assignee_signature: Mapped[bool] = mapped_column(Boolean, default=True, comment="负责人提交时是否签名")
    require_checker_signature: Mapped[bool] = mapped_column(Boolean, default=True, comment="校验人通过时是否签名")
    require_approver_signature: Mapped[bool] = mapped_column(Boolean, default=True, comment="审批人通过时是否签名")
    signature_x: Mapped[float] = mapped_column(Float, default=400, comment="签名默认X坐标（距左边）")
    signature_y: Mapped[float] = mapped_column(Float, default=100, comment="签名默认Y坐标（距底部）")
    signature_page: Mapped[int] = mapped_column(Integer, default=-1, comment="签名默认页码（-1=最后一页）")
    status: Mapped[str] = mapped_column(String(20), default="waiting", comment="节点状态")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号")
    incoming_count: Mapped[int] = mapped_column(Integer, default=0, comment="汇合节点上游连线数")
    arrived_count: Mapped[int] = mapped_column(Integer, default=0, comment="已完成上游分支数")
    round: Mapped[int] = mapped_column(Integer, default=1, comment="执行轮次")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="节点激活时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="节点完成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
