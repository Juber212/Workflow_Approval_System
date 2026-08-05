"""项目服务 —— 按功能拆分到子模块

统一从包入口导入：from app.services.instance import xyz（P2-1 已删除 instance_service.py shim）
"""

from app.services.instance._helpers import (
    _get_type_label,
    _batch_get_node_stats,
    _batch_get_active_node_info,
    format_current_handlers,
    enrich_handler_info_with_names,
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
    "_batch_get_active_node_info",
    "format_current_handlers",
    "enrich_handler_info_with_names",
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
