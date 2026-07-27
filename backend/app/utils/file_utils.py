"""文件工具 —— 路径解析、安全校验（统一项目中分散的文件路径处理逻辑）"""
import os

from app.core.config import settings


def resolve_file_path(file_path: str) -> str:
    """统一解析文件绝对路径

    处理两种存储格式：
    - 相对路径（推荐）：相对于 STORAGE_ROOT 拼接
    - 绝对路径（兼容旧数据）：直接返回

    所有文件操作（上传、删除、下载、签名）统一使用此函数，
    避免各处拼接逻辑不一致导致的路径错误。
    """
    if os.path.isabs(file_path):
        return file_path
    return os.path.join(settings.STORAGE_ROOT, file_path)


def is_safe_path(file_path: str) -> bool:
    """安全检查：确保解析后的路径在 STORAGE_ROOT 范围内（防路径遍历）"""
    real_path = os.path.realpath(resolve_file_path(file_path))
    real_root = os.path.realpath(settings.STORAGE_ROOT)
    return real_path.startswith(real_root + os.sep) or real_path == real_root
