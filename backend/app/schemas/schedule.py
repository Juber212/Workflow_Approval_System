"""排产计划 schema"""

from pydantic import BaseModel


class ScheduleItemOut(BaseModel):
    """排产计划项（甘特图数据源）"""
    node_id: int = 0
    node_name: str = ""
    assignee_id: int = 0
    assignee_name: str = ""
    plan_start: str = ""  # ISO 日期
    plan_end: str = ""
    duration: int = 0
    sort_order: int = 0
