"""系统配置相关 Schema"""
from pydantic import BaseModel, Field


class ConfigItem(BaseModel):
    """配置项"""

    id: int
    config_key: str
    config_value: str
    description: str | None = None

    model_config = {"from_attributes": True}


class ConfigUpdateItem(BaseModel):
    """单条配置更新"""

    id: int = Field(..., description="配置项 ID")
    config_value: str = Field(..., description="新值")


class ConfigBatchUpdate(BaseModel):
    """批量更新配置"""

    items: list[ConfigUpdateItem] = Field(..., min_length=1, description="更新列表")
