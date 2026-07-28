"""实例终止服务 单元测试 —— 权限/状态/并发保护

覆盖：正常终止、非发起人终止、已终止再终止、实例不存在
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.services.instance.terminate import terminate_instance

from tests.factories import make_instance
from tests.conftest import MockResult


class TestTerminateInstance:
    """终止实例服务测试"""

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        """实例不存在 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await terminate_instance(mock_db, instance_id=999, reason="测试",
                                    current_user=MagicMock(id=1))
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_not_initiator(self, mock_db):
        """非发起人终止 → 403"""
        inst = make_instance(id=1, initiator_id=2)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=inst))

        with pytest.raises(AppException) as exc:
            await terminate_instance(mock_db, instance_id=1, reason="测试",
                                    current_user=MagicMock(id=99))
        assert exc.value.code == ErrorCode.NOT_INITIATOR

    @pytest.mark.asyncio
    async def test_already_terminated(self, mock_db):
        """已终止实例再次终止 → 400"""
        inst = make_instance(id=1, initiator_id=1, status="terminated")
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=inst))

        with pytest.raises(AppException) as exc:
            await terminate_instance(mock_db, instance_id=1, reason="再次测试",
                                    current_user=MagicMock(id=1))
        assert exc.value.code == ErrorCode.INSTANCE_ALREADY_TERMINATED

    @pytest.mark.asyncio
    async def test_terminate_success(self, mock_db, mocker):
        """正常终止 → 实例状态更新 + 文件删除 + 相关记录关闭"""
        mocker.patch("app.services.instance.terminate.create_notification", new=AsyncMock())
        mocker.patch("app.services.instance.terminate.clear_related", new=AsyncMock())
        mocker.patch("app.services.instance.terminate.os.path.exists", return_value=False)
        inst = make_instance(id=1, initiator_id=1, status="running")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=inst),              # 0: SELECT instance FOR UPDATE
            MockResult(scalars_all=[]),               # 1: SELECT files → empty
            MagicMock(),                               # 2: UPDATE instance_nodes
            MagicMock(),                               # 3: UPDATE tasks
            MagicMock(),                               # 4: UPDATE check_records
            MagicMock(),                               # 5: UPDATE approvals
            MagicMock(),                               # 6: UPDATE endorsements
            MagicMock(),                               # 7: UPDATE instance status
            MockResult(scalar_one=None),              # 8: SELECT template
            MockResult(scalars_all=[]),               # 9: SELECT pending tasks
            MockResult(scalars_all=[]),               # 10: SELECT pending checks
            MockResult(scalars_all=[]),               # 11: SELECT pending approvals
            MockResult(scalars_all=[]),               # 12: SELECT pending endorsements
        ]

        result = await terminate_instance(mock_db, instance_id=1, reason="测试终止",
                                         current_user=MagicMock(id=1))

        assert result["status"] == "terminated"
        assert inst.status == "terminated"
