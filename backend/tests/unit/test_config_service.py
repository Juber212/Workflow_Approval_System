"""config_service 单元测试 —— 配置缓存读写

覆盖：缓存加载、get/get_int/get_float/get_bool、未加载兜底、get_all
"""

import pytest
from unittest.mock import MagicMock

from app.services.config_service import ConfigService


class TestConfigService:
    """系统配置缓存测试"""

    def test_get_returns_cached_value(self):
        """缓存已加载 → get 返回缓存值"""
        svc = ConfigService()
        svc._loaded = True
        svc._cache["max_file_size"] = MagicMock(config_value="50")

        assert svc.get("max_file_size") == "50"

    def test_get_default_when_not_loaded(self):
        """缓存未加载 → 返回默认值"""
        svc = ConfigService()
        svc._loaded = False

        assert svc.get("max_file_size", "10") == "10"

    def test_get_default_when_key_missing(self):
        """键不存在 → 返回默认值"""
        svc = ConfigService()
        svc._loaded = True

        assert svc.get("nonexistent", "fallback") == "fallback"

    def test_get_int_parses_value(self):
        """get_int 正确解析整数"""
        svc = ConfigService()
        svc._loaded = True
        svc._cache["pool_size"] = MagicMock(config_value="20")

        assert svc.get_int("pool_size") == 20

    def test_get_int_default_on_invalid(self):
        """get_int 值非法时返回默认值"""
        svc = ConfigService()
        svc._loaded = True
        svc._cache["pool_size"] = MagicMock(config_value="not_a_number")

        assert svc.get_int("pool_size", 10) == 10

    def test_get_float_parses_value(self):
        """get_float 正确解析浮点数"""
        svc = ConfigService()
        svc._loaded = True
        svc._cache["ratio"] = MagicMock(config_value="0.75")

        assert svc.get_float("ratio") == 0.75

    def test_get_bool_true_cases(self):
        """get_bool 识别 true/1/yes"""
        svc = ConfigService()
        svc._loaded = True
        svc._cache["enable"] = MagicMock(config_value="true")
        svc._cache["flag1"] = MagicMock(config_value="1")
        svc._cache["flag2"] = MagicMock(config_value="yes")

        assert svc.get_bool("enable") is True
        assert svc.get_bool("flag1") is True
        assert svc.get_bool("flag2") is True

    def test_is_loaded_false_initially(self):
        """新实例初始未加载"""
        svc = ConfigService()
        assert svc.is_loaded is False

    def test_get_all_returns_dict(self):
        """get_all 返回 key→value 映射"""
        svc = ConfigService()
        svc._loaded = True
        svc._cache["k1"] = MagicMock(config_value="v1")
        svc._cache["k2"] = MagicMock(config_value="v2")

        assert svc.get_all() == {"k1": "v1", "k2": "v2"}
