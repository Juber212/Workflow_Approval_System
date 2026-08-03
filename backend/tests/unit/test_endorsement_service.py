"""endorsement_service 单元测试 —— 批准通过/驳回核心路径

覆盖：正常批准/驳回、权限校验、状态校验、not_found 边界
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models.enums import EndorsementStatus, InstanceNodeStatus
from app.services.endorsement_service import endorse, endorse_reject

from tests.factories import make_endorsement, make_node, make_instance
from tests.conftest import MockResult


# ============================================================
# endorse —— 批准通过
# ============================================================

class TestEndorse:
    """批准通过相关测试"""

    @pytest.mark.asyncio
    async def test_endorse_not_found(self, mock_db):
        """批准记录不存在 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await endorse(mock_db, endorsement_id=999, current_user_id=5, opinion="同意")
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_endorse_wrong_user(self, mock_db):
        """非本人批准 → 403"""
        e = make_endorsement(id=1, endorser_id=5, status=EndorsementStatus.PENDING)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=e))

        with pytest.raises(AppException) as exc:
            await endorse(mock_db, endorsement_id=1, current_user_id=99, opinion="同意")
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_endorse_already_processed(self, mock_db):
        """已批准记录再次操作 → 校验失败"""
        e = make_endorsement(id=1, endorser_id=5, status=EndorsementStatus.APPROVED)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=e))

        with pytest.raises(AppException) as exc:
            await endorse(mock_db, endorsement_id=1, current_user_id=5, opinion="同意")
        assert exc.value.code == ErrorCode.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_endorse_success(self, mock_db, mocker):
        """正常批准通过 → 状态更新 + 节点完成"""
        mocker.patch("app.services.endorsement_service.propagate_from_node", new=AsyncMock())
        mocker.patch("app.services.endorsement_service.get_role_signature_defaults", return_value={})

        e = make_endorsement(id=1, status=EndorsementStatus.PENDING)
        node = make_node(id=5, is_end=False, endorser_id=5, status=InstanceNodeStatus.WAITING_ENDORSEMENT)
        inst = make_instance(id=1, difficulty="4")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=e),           # 0: SELECT endorsement FOR UPDATE
            MagicMock(),                         # 1: clear_related
            MagicMock(),                         # 2: flush/update
            MockResult(scalar_one=node),        # 3: _get_node
            MagicMock(),                         # 4: UPDATE node → finished
            MagicMock(),                         # 5: UPDATE task → completed
            MagicMock(),                         # 6: add operation log
            MagicMock(),                         # 7: flush
            MockResult(scalar_one=inst),        # 8: SELECT FlowInstance
            MockResult(scalar_one=None),        # 9: SELECT FlowTemplate
        ]

        result = await endorse(mock_db, endorsement_id=1, current_user_id=5, opinion="同意")

        assert "批准通过" in result["message"]
        assert e.status == EndorsementStatus.APPROVED

    @pytest.mark.asyncio
    async def test_endorse_legacy_signature_fills_file_id(self, mock_db, mocker):
        """P1-13：旧版单签名兼容分支补 file_id（当前轮次首 PDF），签名待落盘"""
        mocker.patch("app.services.endorsement_service.propagate_from_node", new=AsyncMock())

        e = make_endorsement(id=1, status=EndorsementStatus.PENDING)
        node = make_node(id=5, is_end=False, endorser_id=5, require_endorser_signature=True,
                         status=InstanceNodeStatus.WAITING_ENDORSEMENT)
        inst = make_instance(id=1, difficulty="4")
        pdf = MagicMock()
        pdf.id = 888

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=e),          # 0: SELECT endorsement FOR UPDATE
            MagicMock(),                        # 1: clear_related
            MockResult(scalar_one=node),       # 2: SELECT InstanceNode（旧版分支查轮次）
            MockResult(scalars_all=[pdf]),     # 3: SELECT File（当前轮次 PDF）
            MockResult(scalar_one=node),       # 4: _get_node
            MockResult(scalar_one=inst),       # 5: SELECT FlowInstance
            MagicMock(),                        # 6: UPDATE task → completed
            MockResult(scalar_one=None),       # 7: SELECT FlowTemplate（非 proposal）
        ]

        result = await endorse(mock_db, endorsement_id=1, current_user_id=5, opinion="同意", signature_x=300)

        # 旧版分支创建的签名记录：file_id 指向当前轮次 PDF，applied=False（待落盘）
        created = next((a.args[0] for a in mock_db.add.call_args_list
                        if a.args and a.args[0].__class__.__name__ == "Signature"), None)
        assert created is not None, "未创建签名记录"
        assert created.file_id == 888
        assert created.applied is False
        # 签名 ID 进入待落盘列表，signature_applied 按实际落盘结果置 True
        assert len(result["_pending_sig_ids"]) == 1
        assert e.signature_applied is True

    @pytest.mark.asyncio
    async def test_endorse_without_signature_not_applied(self, mock_db, mocker):
        """P1-13：未签名时 signature_applied 保持 False（不假报已签名）"""
        mocker.patch("app.services.endorsement_service.propagate_from_node", new=AsyncMock())

        e = make_endorsement(id=1, status=EndorsementStatus.PENDING)
        node = make_node(id=5, is_end=False, endorser_id=5, require_endorser_signature=True,
                         status=InstanceNodeStatus.WAITING_ENDORSEMENT)
        inst = make_instance(id=1, difficulty="4")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=e),          # 0: SELECT endorsement FOR UPDATE
            MagicMock(),                        # 1: clear_related
            MockResult(scalar_one=node),       # 2: _get_node
            MockResult(scalar_one=inst),       # 3: SELECT FlowInstance
            MagicMock(),                        # 4: UPDATE task → completed
            MockResult(scalar_one=None),       # 5: SELECT FlowTemplate（非 proposal）
        ]

        result = await endorse(mock_db, endorsement_id=1, current_user_id=5, opinion="同意")

        assert e.signature_applied is False
        assert result["_pending_sig_ids"] == []


# ============================================================
# endorse_reject —— 批准驳回
# ============================================================

class TestEndorseReject:
    """批准驳回相关测试"""

    @pytest.mark.asyncio
    async def test_reject_not_found(self, mock_db):
        """驳回不存在的记录 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await endorse_reject(mock_db, endorsement_id=999, current_user_id=5, opinion="不同意")
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_reject_wrong_user(self, mock_db):
        """非本人驳回 → 403"""
        e = make_endorsement(id=1, endorser_id=5, status=EndorsementStatus.PENDING)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=e))

        with pytest.raises(AppException) as exc:
            await endorse_reject(mock_db, endorsement_id=1, current_user_id=99, opinion="不同意")
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_reject_already_processed(self, mock_db):
        """已驳回记录再次操作 → 校验失败"""
        e = make_endorsement(id=1, endorser_id=5, status=EndorsementStatus.REJECTED)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=e))

        with pytest.raises(AppException) as exc:
            await endorse_reject(mock_db, endorsement_id=1, current_user_id=5, opinion="不同意")
        assert exc.value.code == ErrorCode.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_reject_success(self, mock_db, mocker):
        """正常批准驳回 → 节点回到 running + task 回到 pending"""
        e = make_endorsement(id=1, instance_id=1, node_id=5, status=EndorsementStatus.PENDING)
        node = make_node(id=5, is_end=False, endorser_id=5, status=InstanceNodeStatus.WAITING_ENDORSEMENT,
                        round=1)

        # endorse_reject 有多步 DB 查询，用 lambda 无限返回 MockResult
        call_count = [0]
        def _side_effect(*args, **kwargs):
            call_count[0] += 1
            idx = call_count[0]
            if idx == 1:
                return MockResult(scalar_one=e)       # SELECT endorsement FOR UPDATE
            if idx == 2:
                return MagicMock()                     # clear_related
            if idx == 3:
                return MockResult(scalar_one=node)    # _get_node
            if idx == 4:
                return MagicMock()                     # UPDATE approvals
            if idx == 5:
                return MagicMock()                     # UPDATE check_records
            if idx == 6:
                return MockResult(scalars_all=[])      # SELECT files → empty
            if idx == 7:
                return MagicMock()                     # UPDATE task
            if idx == 8:
                return MagicMock()                     # UPDATE node / add log
            return MagicMock()

        mock_db.execute = AsyncMock(side_effect=_side_effect)
        mocker.patch("app.services.endorsement_service.create_notification", new=AsyncMock())
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("os.path.isabs", return_value=False)
        mocker.patch("os.remove")

        result = await endorse_reject(mock_db, endorsement_id=1, current_user_id=5, opinion="需修改")

        assert "驳回" in result["message"]
        assert e.status == EndorsementStatus.REJECTED
