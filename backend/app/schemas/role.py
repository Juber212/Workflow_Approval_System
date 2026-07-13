"""角色相关 Schema"""
from pydantic import BaseModel


class RoleListItem(BaseModel):
    """角色列表项（含用户数计算字段）"""

    id: int
    name: str
    code: str
    description: str | None = None
    user_count: int = 0  # 拥有该角色的用户数

    class Config:
        from_attributes = True
