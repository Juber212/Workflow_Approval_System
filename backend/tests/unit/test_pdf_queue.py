"""pdf_queue 单元测试 —— PDF 转换聚合检查任务重试上限（P1-15）

覆盖：convert_all_files_job 在未达上限时重新入队、达上限时标记超时文件 failed 并通知前端。
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.pdf_queue import convert_all_files_job, _CONVERT_ALL_MAX_ATTEMPTS

from tests.conftest import MockResult


def _mk_file(fid: int, status: str):
    """构造带转换状态的 mock 文件对象"""
    f = MagicMock()
    f.id = fid
    f.conversion_status = status
    f.conversion_error = None
    return f


def _setup_db(files: list, mocker):
    """mock async_session_factory，返回可 async with 的 db，execute 返回 files"""
    mock_factory = mocker.patch("app.services.pdf_queue.async_session_factory")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MockResult(scalars_all=files))
    db.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = cm
    return db


class TestConvertAllFilesJob:
    """聚合检查任务 —— 重试上限（P1-15）"""

    @pytest.mark.asyncio
    async def test_reenqueue_before_max_attempts(self, mocker):
        """未达上限时重新入队，attempt+1，不通知前端"""
        files = [_mk_file(1, "ready"), _mk_file(2, "converting")]
        _setup_db(files, mocker)
        ctx = {"redis": AsyncMock()}

        result = await convert_all_files_job(ctx, [1, 2], task_id=10, user_id=5, attempt=1)

        assert result["status"] == "checking"
        assert result["pending"] == 1
        # 重新入队且 attempt+1
        ctx["redis"].enqueue_job.assert_called_once()
        call_args = ctx["redis"].enqueue_job.call_args
        assert call_args.args[0] == "convert_all_files_job"
        assert call_args.args[4] == 2  # attempt + 1

    @pytest.mark.asyncio
    async def test_timeout_marks_failed_and_notifies(self, mocker):
        """达上限时停止重试，标记超时文件 failed，通知前端 partial_failed"""
        files = [_mk_file(1, "ready"), _mk_file(2, "converting")]
        _setup_db(files, mocker)
        ctx = {"redis": AsyncMock()}
        # mock Pub/Sub redis（转换完成后通知前端）
        fake_pub = AsyncMock()
        mocker.patch("app.services.pdf_queue.AsyncRedis.from_url", return_value=fake_pub)

        result = await convert_all_files_job(
            ctx, [1, 2], task_id=10, user_id=5, attempt=_CONVERT_ALL_MAX_ATTEMPTS,
        )

        # 不再重新入队
        ctx["redis"].enqueue_job.assert_not_called()
        # 超时文件被标记 failed
        assert files[1].conversion_status == "failed"
        assert files[1].conversion_error
        # 通知前端
        assert result["status"] == "partial_failed"
        assert result["failed"] == 1
        fake_pub.publish.assert_called_once()
        msg = json.loads(fake_pub.publish.call_args[0][1])
        assert msg["type"] == "conversion_all_done"
        assert msg["status"] == "partial_failed"
        assert msg["failed"] == 1

    @pytest.mark.asyncio
    async def test_all_ready_no_reenqueue(self, mocker):
        """全部转换完成 → 直接通知，不入队"""
        files = [_mk_file(1, "ready"), _mk_file(2, "ready")]
        _setup_db(files, mocker)
        ctx = {"redis": AsyncMock()}
        fake_pub = AsyncMock()
        mocker.patch("app.services.pdf_queue.AsyncRedis.from_url", return_value=fake_pub)

        result = await convert_all_files_job(ctx, [1, 2], task_id=10, user_id=5)

        assert result["status"] == "all_ready"
        ctx["redis"].enqueue_job.assert_not_called()
        fake_pub.publish.assert_called_once()
