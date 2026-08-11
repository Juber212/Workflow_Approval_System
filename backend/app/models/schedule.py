"""排产计划项模型 —— 实例发起时按流程节点自动生成的排产计划

排产独立于流程执行：记录每道工序（工作节点）的计划开始/结束日期和分配的负责人，
展示用甘特图，不参与流程流转。
"""

from datetime import date

from sqlalchemy import Integer, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("flow_instances.id"), comment="所属实例")
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_nodes.id"), comment="对应实例节点")
    assignee_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), comment="排产分配的负责人")
    plan_start_date: Mapped[date] = mapped_column(Date, comment="计划开始日期（自然日）")
    plan_end_date: Mapped[date] = mapped_column(Date, comment="计划结束日期")
    duration_days: Mapped[int] = mapped_column(Integer, comment="工期（天）")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="节点顺序")
