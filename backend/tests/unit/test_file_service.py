"""file_service 单元测试 —— 文件上传/删除

覆盖：上传权限校验、删除顺序（先DB后文件）、边界情况
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models.enums import TaskStatus
from app.services.file_service import upload_file, delete_file

from tests.factories import make_task, make_node
from tests.conftest import MockResult


class _FakeUploadFile:
    """模拟 FastAPI UploadFile，避免 MagicMock 属性比较问题"""
    def __init__(self, filename="test.doc", content_type="application/msword", size=1000):
        self.filename = filename
        self.content_type = content_type
        self.size = size  # 真实的 int，支持 > < 比较
        self.file = self   # UploadFile.file 可 seek 获取大小
    async def read(self):
        return b"fake content" * 100
    def seek(self, offset, whence=0):
        pass
    def tell(self):
        return self.size

def _mock_upload_file(filename="test.doc", content_type="application/msword", size=1000):
    return _FakeUploadFile(filename, content_type, size)


# ============================================================
# upload_file —— 文件上传
# ============================================================

class TestUploadFile:
    """文件上传测试"""

    @pytest.mark.asyncio
    async def test_upload_task_not_found(self, mock_db):
        """任务不存在 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await upload_file(mock_db, task_id=999, upload_file_obj=_mock_upload_file(), current_user_id=1)
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_upload_permission_denied(self, mock_db):
        """非任务负责人上传 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=task))

        with pytest.raises(AppException) as exc:
            await upload_file(mock_db, task_id=1, upload_file_obj=_mock_upload_file(), current_user_id=99)
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_upload_task_already_submitted(self, mock_db):
        """已提交任务不能再上传 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.WAITING_CHECK)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=task))

        with pytest.raises(AppException) as exc:
            await upload_file(mock_db, task_id=1, upload_file_obj=_mock_upload_file(), current_user_id=2)
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_upload_invalid_mime_type(self, mock_db):
        """不允许的文件类型 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)
        node = make_node(id=5, require_file=True)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),        # 0: SELECT task
            MockResult(scalar_one=node),        # 1: SELECT node
        ]

        with pytest.raises(AppException) as exc:
            await upload_file(mock_db, task_id=1, upload_file_obj=_mock_upload_file(
                filename="virus.exe", content_type="application/x-msdownload"), current_user_id=2)
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, mock_db):
        """文件超过大小限制 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)
        node = make_node(id=5, require_file=True)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),        # 0: SELECT task
            MockResult(scalar_one=node),        # 1: SELECT node
        ]

        with pytest.raises(AppException) as exc:
            await upload_file(mock_db, task_id=1, upload_file_obj=_mock_upload_file(
                size=60 * 1024 * 1024), current_user_id=2)
        assert exc.value.code == ErrorCode.BAD_REQUEST


# ============================================================
# delete_file —— 文件删除
# ============================================================

class TestDeleteFile:
    """文件删除测试"""

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, mock_db):
        """任务不存在 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await delete_file(mock_db, task_id=999, file_id=10, current_user_id=1)
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_not_task_owner(self, mock_db):
        """非任务负责人删除 → 403"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=task))

        with pytest.raises(AppException) as exc:
            await delete_file(mock_db, task_id=1, file_id=10, current_user_id=99)
        assert exc.value.code == ErrorCode.FORBIDDEN

    @pytest.mark.asyncio
    async def test_delete_file_success(self, mock_db):
        """正常删除 → 先DB后物理文件（防御顺序验证）"""
        from app.models import File
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)
        file_rec = File(id=10, task_id=1, instance_id=1,
                       file_path="storage/uploads/test.pdf",
                       stored_name="abc123.pdf",
                       original_name="test.pdf",
                       mime_type="application/pdf",
                       file_size=1024)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),        # 0: SELECT task
            MockResult(scalar_one=file_rec),    # 1: SELECT file
        ]

        with patch("app.services.file_service.os.path.exists", return_value=True), \
             patch("app.services.file_service.os.remove") as mock_remove, \
             patch("app.services.file_service.resolve_file_path", return_value="/fake/path/test.pdf"):
            await delete_file(mock_db, task_id=1, file_id=10, current_user_id=2)

        # 验证 DB 删除先执行
        mock_db.delete.assert_called_once_with(file_rec)
        # 物理删除也被调用
        mock_remove.assert_called_once()


# ============================================================
# upload_file —— folder_name 路径穿越与白名单校验（P0-2）
# ============================================================

class _EmptyUploadFile:
    """读取立即返回空的假上传文件（用于让写盘循环正常退出）"""
    filename = "test.docx"
    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def __init__(self):
        self.file = self  # 兼容 upload_file 内 upload_file_obj.file.seek/tell 访问

    def seek(self, offset, whence=0):
        pass

    def tell(self):
        return 100

    def read(self, n=-1):
        return b""


class _FakeAIOFile:
    """模拟 aiofiles.open 返回的异步上下文管理器"""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def write(self, data):
        return len(data)


def _make_flow_instance():
    """构造 FlowInstance 最小 mock（upload_file 校验需要 instance 查询）"""
    inst = MagicMock()
    inst.id = 1
    inst.name = "测试项目"
    inst.template_type = "project"
    return inst


class TestUploadFolderNameValidation:
    """P0-2 修复：folder_name 白名单校验 + 穿越防护"""

    @pytest.mark.asyncio
    async def _assert_folder_rejected(self, mock_db, folder_name, node):
        """构造 task+instance+node 查询，断言上传被 BAD_REQUEST 拒绝"""
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),          # 0: SELECT task
            MockResult(scalar_one=_make_flow_instance()),  # 1: SELECT instance
            MockResult(scalar_one=node),          # 2: SELECT node
        ]
        with pytest.raises(AppException) as exc:
            await upload_file(mock_db, task_id=1, upload_file_obj=_mock_upload_file(),
                              current_user_id=2, folder_name=folder_name)
        assert exc.value.code == ErrorCode.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_reject_dotdot_traversal(self, mock_db):
        """folder_name 含 '..' → 拒绝（目录穿越主攻击向量）"""
        node = make_node(id=5, require_file=True)
        node.file_folders = [{"name": "合同", "required": True}]
        await self._assert_folder_rejected(mock_db, "../../..", node)

    @pytest.mark.asyncio
    async def test_reject_path_separator(self, mock_db):
        """folder_name 含 '/' 或 '\\' → 拒绝"""
        node = make_node(id=5, require_file=True)
        node.file_folders = [{"name": "合同", "required": True}]
        await self._assert_folder_rejected(mock_db, "a/b", node)
        await self._assert_folder_rejected(mock_db, "a\\b", node)

    @pytest.mark.asyncio
    async def test_reject_folder_not_in_config(self, mock_db):
        """folder_name 不在节点文件夹配置中 → 拒绝"""
        node = make_node(id=5, require_file=True)
        node.file_folders = [{"name": "合同", "required": True}]
        await self._assert_folder_rejected(mock_db, "其他目录", node)

    @pytest.mark.asyncio
    async def test_reject_when_no_folder_config(self, mock_db):
        """节点未配置文件夹分类时指定 folder_name → 拒绝"""
        node = make_node(id=5, require_file=True)
        node.file_folders = None
        await self._assert_folder_rejected(mock_db, "合同", node)

    @pytest.mark.asyncio
    async def test_allow_folder_in_config(self, mock_db):
        """folder_name ∈ 配置且无穿越 → 通过校验（写盘被 mock）"""
        node = make_node(id=5, require_file=True)
        node.file_folders = [{"name": "合同", "required": True}]
        task = make_task(id=1, assignee_id=2, status=TaskStatus.PROCESSING)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=task),          # 0: SELECT task
            MockResult(scalar_one=_make_flow_instance()),  # 1: SELECT instance
            MockResult(scalar_one=node),          # 2: SELECT node
        ]
        with patch("app.services.file_service.os.makedirs"), \
             patch("app.services.file_service.os.path.exists", return_value=False), \
             patch("aiofiles.open", return_value=_FakeAIOFile()):
            result = await upload_file(mock_db, task_id=1, upload_file_obj=_EmptyUploadFile(),
                                       current_user_id=2, folder_name="合同")
        # 正常路径不抛错，返回文件信息；folder_name 正确写入 File 记录
        assert result["original_name"] == "test.docx"
        file_record = mock_db.add.call_args[0][0]
        assert file_record.folder_name == "合同"
