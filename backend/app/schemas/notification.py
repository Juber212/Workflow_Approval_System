"""通知 Schema —— 请求/响应模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    """通知列表项"""
    id: int
    type: str
    title: str
    content: str
    link: str | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    """未读通知数量"""
    count: int
