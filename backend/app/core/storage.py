"""存储路径工具 —— 统一管理所有文件路径的构建和解析"""

import os
from app.core.config import settings


def resolve_storage_path(file_path: str) -> str:
    """安全解析存储路径为绝对路径

    处理数据库可能存储了 STORAGE_ROOT 前缀的情况，
    避免 os.path.join 产生重复路径段。
    """
    if os.path.isabs(file_path):
        return file_path
    if file_path.startswith(settings.STORAGE_ROOT + os.sep) or file_path.startswith(settings.STORAGE_ROOT + "/"):
        # 已经包含 STORAGE_ROOT 前缀，直接在项目根下拼接
        return os.path.join(os.path.dirname(settings.STORAGE_ROOT), file_path) if os.path.dirname(settings.STORAGE_ROOT) else file_path
    return os.path.join(settings.STORAGE_ROOT, file_path)


def build_archive_path(template_type: str, instance_name: str) -> str:
    """构建实例归档目录完整路径（相对于项目根目录）

    Args:
        template_type: 模板类型 "project" 或 "proposal"
        instance_name: 实例名称

    Returns:
        完整路径如 storage/项目/XX项目/ 或 storage/方案/XX方案/
    """
    archive_dir = settings.get_archive_dir(template_type)
    return os.path.join(settings.STORAGE_ROOT, archive_dir, instance_name)


def build_archive_relative_path(template_type: str, instance_name: str, filename: str = "") -> str:
    """构建存储在数据库中的相对路径（不含 STORAGE_ROOT 前缀）

    Args:
        template_type: 模板类型 "project" 或 "proposal"
        instance_name: 实例名称
        filename: 文件名（可选）

    Returns:
        相对路径如 项目/XX项目/abc.pdf
    """
    archive_dir = settings.get_archive_dir(template_type)
    path = os.path.join(archive_dir, instance_name)
    if filename:
        path = os.path.join(path, filename)
    return path


def get_signatures_dir() -> str:
    """获取用户签名图片存储目录"""
    return os.path.join(settings.STORAGE_ROOT, settings.STORAGE_SIGNATURES_DIR)


def get_document_templates_dir() -> str:
    """获取文件模板存储目录"""
    return os.path.join(settings.STORAGE_ROOT, settings.STORAGE_DOCUMENT_TEMPLATES_DIR)
