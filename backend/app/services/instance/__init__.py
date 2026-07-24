"""项目服务 —— 按功能拆分到子模块

外部调用方无需改动 import 路径：from app.services.instance_service import xyz
"""

from app.services.instance._helpers import (
    _get_type_label,
    _batch_get_node_stats,
    _batch_get_current_assignees,
)
from app.services.instance.create import create_instance
from app.services.instance.list import list_instances
from app.services.instance.detail import get_instance_detail
from app.services.instance.terminate import terminate_instance
from app.services.instance.change import (
    change_personnel,
    change_priority,
    _normalize_list,
    _describe_change,
    _ids_str,
)
from app.services.instance.supplement import supplement_files
from app.services.instance.delete import permanent_delete_instance

__all__ = [
    "_get_type_label",
    "_batch_get_node_stats",
    "_batch_get_current_assignees",
    "create_instance",
    "list_instances",
    "get_instance_detail",
    "terminate_instance",
    "change_personnel",
    "change_priority",
    "_normalize_list",
    "_describe_change",
    "_ids_str",
    "supplement_files",
    "permanent_delete_instance",
]
