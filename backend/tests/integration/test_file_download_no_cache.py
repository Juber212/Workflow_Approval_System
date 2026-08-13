"""文件下载缓存控制 —— 签名/驳回会更新 PDF，下载接口必须禁用缓存（Cache-Control: no-store）

背景：download_file 无缓存头时，浏览器启发式缓存签名前的 PDF，
签名写入后预览（pdfjs 用同一 URL 请求）拿到缓存的旧文件 → 预览看不到签名
（用户报告 bug：PDF 文件里有签名，但在线预览没有）。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.responses import Response
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.models import File
from tests.conftest import MockResult


@pytest.fixture
def client():
    """TestClient + mock get_db（非 with 模式，避免 lifespan 触发全局 DB）"""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.mock_db = mock_db
    yield c
    app.dependency_overrides.clear()


def _make_token(user_id=1):
    """签发 JWT（roles 带 user）"""
    from app.core.security import create_access_token
    return create_access_token({"sub": str(user_id), "username": f"u{user_id}",
                                "roles": ["user"], "org_id": 1})


def _make_user(user_id=1):
    """构造当前登录用户"""
    from app.models import User
    return User(id=user_id, username=f"u{user_id}", real_name="用户", password_hash="x",
                organization_id=1, is_active=True)


class TestDownloadFileNoCache:
    """GET /files/{file_id}/download 必须禁用缓存"""

    def test_download_response_has_no_cache(self, client, mocker):
        """文件下载响应带 Cache-Control: no-store（文件会被签名/驳回更新，禁止缓存）"""
        # 用透传 headers 的 fake FileResponse，验证 download_file 传入的缓存头
        def _fake_file_response(**kwargs):
            return Response(content=b"pdf-data", headers=kwargs.get("headers", {}))

        mocker.patch("app.api.tasks.FileResponse", side_effect=_fake_file_response)
        mocker.patch("os.path.exists", return_value=True)

        db = client.mock_db
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),   # 0: 当前用户
            MockResult(scalars_all=['user']),       # 1: 角色查询
            MockResult(scalar_one=File(
                id=1, file_path="项目/x.pdf",
                mime_type="application/pdf", original_name="x.pdf",
            )),  # 2: 文件记录
        ]

        resp = client.get(
            "/api/v1/files/1/download",
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("Cache-Control") == "no-store"
