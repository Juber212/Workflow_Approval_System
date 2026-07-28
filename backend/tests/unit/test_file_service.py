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
