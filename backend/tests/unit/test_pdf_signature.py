"""pdf_signature 服务单元测试 —— 配置读取 / 角色默认值"""

import pytest
from unittest.mock import AsyncMock

from app.models import SystemConfig, File
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.services.pdf_signature import (
    _get_signature_configs, get_role_signature_defaults, create_signature_records,
)
from tests.conftest import MockResult


# ============================================================
# 签名配置读取
# ============================================================

class TestGetSignatureConfigs:
    """_get_signature_configs —— 从 DB 读取 + 默认值兜底"""

    @pytest.mark.asyncio
    async def test_all_from_db(self, mock_db):
        """DB 中有配置 → 使用 DB 值"""
        configs = [
            SystemConfig(config_key="pdf_signature_x", config_value="500"),
            SystemConfig(config_key="pdf_signature_y", config_value="80"),
        ]

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=configs),  # 0: SELECT configs
        ]

        result = await _get_signature_configs(mock_db)
        # DB 中有的用 DB 值
        assert result["pdf_signature_x"] == 500
        assert result["pdf_signature_y"] == 80
        # DB 中没有的回退到 settings 默认值
        assert result["pdf_signature_max_width"] == 100

    @pytest.mark.asyncio
    async def test_empty_db_uses_defaults(self, mock_db):
        """DB 中无配置 → 全部使用 settings 默认值"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[]),  # 0: SELECT configs → 空
        ]

        result = await _get_signature_configs(mock_db)
        # 验证关键 key 存在默认值
        assert "pdf_signature_x" in result
        assert "pdf_signature_y" in result
        assert "pdf_signature_approver_x" in result
        assert "pdf_signature_approver_y" in result
        # 默认值来自 settings
        assert result["pdf_signature_x"] == 400  # settings.PDF_SIGNATURE_X


# ============================================================
# 角色签名默认值
# ============================================================

class TestGetRoleSignatureDefaults:
    """get_role_signature_defaults —— 按角色返回 {x, y}"""

    @pytest.mark.asyncio
    async def test_approver_from_db(self, mock_db):
        """DB 中有审批人配置 → 返回自定义坐标"""
        configs = [
            SystemConfig(config_key="pdf_signature_approver_x", config_value="550"),
            SystemConfig(config_key="pdf_signature_approver_y", config_value="60"),
        ]

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=configs),  # 0: SELECT configs
        ]

        result = await get_role_signature_defaults(mock_db, "approver")
        assert result["x"] == 550
        assert result["y"] == 60

    @pytest.mark.asyncio
    async def test_assignee_defaults(self, mock_db):
        """DB 中无负责人配置 → 返回默认 400/100"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[]),  # 0: SELECT configs → 空
        ]

        result = await get_role_signature_defaults(mock_db, "assignee")
        assert result["x"] == 400
        assert result["y"] == 100


# ============================================================
# create_signature_records —— file_id 归属校验（P0-3）
# ============================================================

class TestCreateSignatureRecords:
    """P0-3 修复：签名 file_id 必须属于当前节点，防止签名写入他人 PDF"""

    @pytest.mark.asyncio
    async def test_reject_file_id_not_in_node(self, mock_db):
        """file_id 属于其他节点 → BAD_REQUEST"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[File(id=20, node_id=8)]),  # 其他节点的文件
        ]
        with pytest.raises(AppException) as exc:
            await create_signature_records(
                mock_db, role_type="approver", source_id=1, node_id=5,
                signatures=[{"file_id": 10, "signer_id": 2}],
            )
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_reject_file_id_missing(self, mock_db):
        """file_id 不存在 → BAD_REQUEST"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[]),  # 查不到该文件
        ]
        with pytest.raises(AppException) as exc:
            await create_signature_records(
                mock_db, role_type="approver", source_id=1, node_id=5,
                signatures=[{"file_id": 999, "signer_id": 2}],
            )
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_accept_file_id_in_node(self, mock_db):
        """file_id 属于当前节点 → 正常创建签名记录"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[File(id=10, node_id=5)]),  # 本节点文件
        ]
        sig_ids = await create_signature_records(
            mock_db, role_type="approver", source_id=1, node_id=5,
            signatures=[{"file_id": 10, "signer_id": 2}],
        )
        # 签名记录已创建；file_id=None（旧兼容）时不校验、直接跳过
        assert mock_db.add.called
        assert len(sig_ids) == 1
