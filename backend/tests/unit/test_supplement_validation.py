"""P1-9 单元测试：补交文件文件夹校验（白名单 + 必填）

补交前校验：
- 节点有文件夹配置时：folder_name 必填且属于白名单；必填文件夹（连同历史）非空
- 节点无文件夹配置时：folder_name 必须为空
"""

from unittest.mock import MagicMock, AsyncMock

import pytest

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models.enums import InstanceStatus, InstanceNodeStatus
from app.services.instance.supplement import supplement_files
from tests.factories import make_instance, make_node
from tests.conftest import MockResult


class FakeUser:
    def __init__(self, id=1):
        self.id = id


def _make_upload(name="a.pdf"):
    """构造模拟上传文件（application/pdf，魔数校验走 OFFICE_EXTS 白名单跳过）"""
    f = MagicMock()
    f.content_type = "application/pdf"
    f.filename = name
    f.file = MagicMock()
    f.file.seek = MagicMock()
    f.file.tell = MagicMock(return_value=1024)
    # 分块读取：先返回数据一次，再返回空结束循环
    f.file.read = MagicMock(side_effect=[b"pdf-data", b""])
    return f


def _make_folders_config():
    """文件夹配置：图纸（必填，恰好2）+ 说明（可选）"""
    return [
        {"name": "图纸", "required": True, "file_count": 2},
        {"name": "说明", "required": False},
    ]


def _enable_id_assignment(mock_db):
    """mock flush 时为 add 的 File 分配自增 id（模拟数据库回填，NodeFileBrief 需要）"""
    counter = 100

    def _assign_ids():
        nonlocal counter
        for call in mock_db.add.call_args_list:
            obj = call.args[0]
            if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                obj.id = counter
                counter += 1

    mock_db.flush = AsyncMock(side_effect=_assign_ids)
    return mock_db


async def _run_supplement(mock_db, node, files, folder_name=None):
    """执行补交（失败时断言抛异常，成功时返回结果）"""
    instance = make_instance(id=1, initiator_id=1, status=InstanceStatus.COMPLETED)
    return await supplement_files(
        mock_db, instance_id=1, node_id=node.id, files=files,
        current_user=FakeUser(id=1), folder_name=folder_name,
    )


class TestSupplementFolderValidation:
    """补交文件文件夹校验"""

    @pytest.mark.asyncio
    async def test_folder_not_in_whitelist(self, mock_db):
        """有文件夹配置但 folder_name 不在白名单 → 400"""
        node = make_node(id=1, instance_id=1, status=InstanceNodeStatus.FINISHED,
                         assignee_id=1, file_folders=_make_folders_config())
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=make_instance(id=1, initiator_id=1, status=InstanceStatus.COMPLETED)),
            MockResult(scalar_one=node),
            MockResult(scalar_value="用户"),  # User.real_name
        ]
        with pytest.raises(AppException) as exc:
            await _run_supplement(mock_db, node, [_make_upload()], folder_name="未知文件夹")
        assert exc.value.code == ErrorCode.BAD_REQUEST
        assert "目标文件夹" in exc.value.message

    @pytest.mark.asyncio
    async def test_folder_required_but_missing(self, mock_db):
        """有文件夹配置但 folder_name 为空 → 400"""
        node = make_node(id=1, instance_id=1, status=InstanceNodeStatus.FINISHED,
                         assignee_id=1, file_folders=_make_folders_config())
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=make_instance(id=1, initiator_id=1, status=InstanceStatus.COMPLETED)),
            MockResult(scalar_one=node),
            MockResult(scalar_value="用户"),
        ]
        with pytest.raises(AppException) as exc:
            await _run_supplement(mock_db, node, [_make_upload()], folder_name=None)
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_required_folder_still_empty(self, mock_db):
        """folder_name 在白名单，但必填文件夹（含历史）仍为空 → 400"""
        node = make_node(id=1, instance_id=1, status=InstanceNodeStatus.FINISHED,
                         assignee_id=1, file_folders=_make_folders_config())
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=make_instance(id=1, initiator_id=1, status=InstanceStatus.COMPLETED)),
            MockResult(scalar_one=node),
            MockResult(scalar_value="用户"),
            MockResult(scalars_all=[]),  # 历史文件 → 空（必填文件夹图纸无文件）
        ]
        with pytest.raises(AppException) as exc:
            # 补交到「说明」文件夹（可选），历史无「图纸」文件 → 必填校验失败
            await _run_supplement(mock_db, node, [_make_upload()], folder_name="说明")
        assert exc.value.code == ErrorCode.BAD_REQUEST
        assert "必须至少提交 1 个文件" in exc.value.message

    @pytest.mark.asyncio
    async def test_no_folder_config_but_passed_folder(self, mock_db):
        """节点无文件夹配置却传了 folder_name → 400"""
        node = make_node(id=1, instance_id=1, status=InstanceNodeStatus.FINISHED,
                         assignee_id=1, file_folders=None)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=make_instance(id=1, initiator_id=1, status=InstanceStatus.COMPLETED)),
            MockResult(scalar_one=node),
            MockResult(scalar_value="用户"),
        ]
        with pytest.raises(AppException) as exc:
            await _run_supplement(mock_db, node, [_make_upload()], folder_name="多余")
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_normal_supplement_without_folder_config(self, mock_db, mocker):
        """无文件夹配置 + 不传 folder_name → 正常补交"""
        node = make_node(id=1, instance_id=1, status=InstanceNodeStatus.FINISHED,
                         assignee_id=1, file_folders=None)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=make_instance(id=1, initiator_id=1, status=InstanceStatus.COMPLETED)),
            MockResult(scalar_one=node),
            MockResult(scalar_value="用户"),
        ]
        # mock 文件写入，避免真实落盘
        mocker.patch("os.makedirs")
        mocker.patch("aiofiles.open", return_value=_AsyncWriteCtx())
        _enable_id_assignment(mock_db)

        result = await _run_supplement(mock_db, node, [_make_upload()], folder_name=None)
        assert len(result.files) == 1

    @pytest.mark.asyncio
    async def test_normal_supplement_with_folder_in_whitelist(self, mock_db, mocker):
        """有文件夹配置 + folder_name 在白名单 + 必填满足（历史已有文件）→ 正常补交"""
        node = make_node(id=1, instance_id=1, status=InstanceNodeStatus.FINISHED,
                         assignee_id=1, file_folders=_make_folders_config())
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=make_instance(id=1, initiator_id=1, status=InstanceStatus.COMPLETED)),
            MockResult(scalar_one=node),
            MockResult(scalar_value="用户"),
            # 历史文件：图纸文件夹已有一份（必填满足）
            MockResult(scalars_all=[type("HistFile", (), {"folder_name": "图纸"})()]),
        ]
        mocker.patch("os.makedirs")
        mocker.patch("aiofiles.open", return_value=_AsyncWriteCtx())
        _enable_id_assignment(mock_db)

        result = await _run_supplement(mock_db, node, [_make_upload()], folder_name="图纸")
        assert len(result.files) == 1


class _AsyncWriteCtx:
    """模拟 aiofiles.open 的异步上下文管理器"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def write(self, data):
        return len(data)
