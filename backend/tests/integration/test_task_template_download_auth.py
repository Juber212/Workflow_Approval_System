"""P1-2 集成测试：任务维度模板下载接口归属校验

下载模板包 ZIP / 单文件模板时，包内 doc/category 必须属于该任务对应实例的关联集
（collect_instance_doc_ids），否则 403，防止跨实例枚举下载。
"""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.models import Task, FlowInstance, DocumentTemplate
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


def _make_task():
    """构造任务：负责人=当前用户，归属实例 100"""
    return Task(id=1, instance_id=100, node_id=5, assignee_id=1)


def _make_instance(doc_template_ids=None):
    """构造实例：doc_template_ids 为空时走模板关联查询"""
    return FlowInstance(id=100, template_id=10, doc_template_ids=doc_template_ids)


# ============================================================
# 模板包 ZIP 下载 —— category 内模板必须属于该实例关联集
# ============================================================

class TestDownloadTaskTemplateZip:
    """GET /tasks/{task_id}/document-templates/download-zip"""

    def test_cross_instance_forbidden(self, client):
        """category 包内模板不属于该实例 → 403"""
        db = client.mock_db
        # 实例只关联 doc 1，而包内是 doc 999
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),   # 0: get_current_active_user → User
            MockResult(scalars_all=['user']),       # 1: 角色查询
            MockResult(scalar_one=_make_task()),    # 2: task
            MockResult(scalars_all=[999]),          # 3: category 内 doc_ids
            MockResult(scalar_one=_make_instance([1])),  # 4: instance
            # collect_instance_doc_ids: doc_template_ids=[1] → 直接返回，无额外查询
        ]

        resp = client.get(
            "/api/v1/tasks/1/document-templates/download-zip?category_id=5",
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
        assert resp.status_code == 403

    def test_own_instance_allowed(self, client, mocker):
        """category 包内模板属于该实例 → 200"""
        mocker.patch("app.services.category_service.batch_fill_and_zip",
                     new=AsyncMock(return_value=BytesIO(b"zip")))
        db = client.mock_db
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),
            MockResult(scalars_all=['user']),
            MockResult(scalar_one=_make_task()),
            MockResult(scalars_all=[1]),            # category 内 doc_ids=[1] ∈ {1}
            MockResult(scalar_one=_make_instance([1])),
            MockResult(scalar_one=None),            # 包名查询 → 无 → 用默认名
        ]

        resp = client.get(
            "/api/v1/tasks/1/document-templates/download-zip?category_id=5",
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
        assert resp.status_code == 200


# ============================================================
# 单文件模板下载 —— doc 必须属于该实例关联集
# ============================================================

class TestDownloadDocumentTemplate:
    """GET /tasks/{task_id}/document-templates/{doc_id}/download"""

    def test_cross_instance_forbidden(self, client):
        """doc 不属于该实例 → 403"""
        db = client.mock_db
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),
            MockResult(scalars_all=['user']),
            MockResult(scalar_one=_make_task()),
            MockResult(scalar_one=_make_instance([1])),  # instance（在查 doc 之前校验）
            # collect: doc_template_ids=[1] → {1}；doc_id=999 ∉ {1} → 403
        ]

        resp = client.get(
            "/api/v1/tasks/1/document-templates/999/download",
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
        assert resp.status_code == 403

    def test_own_instance_allowed(self, client, mocker):
        """doc 属于该实例 → 200"""
        mocker.patch("app.api.tasks.resolve_template_variables", new=AsyncMock(return_value={}))
        mocker.patch("app.api.tasks.get_doc_template_abs_path", return_value="/tmp/t.docx")
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("app.api.tasks.fill_template", return_value=BytesIO(b"doc"))

        db = client.mock_db
        doc = DocumentTemplate(id=1, name="合同模板", original_name="合同模板.docx", file_type="docx")
        db.execute = AsyncMock()
        db.execute.side_effect = [
            MockResult(scalar_one=_make_user()),
            MockResult(scalars_all=['user']),
            MockResult(scalar_one=_make_task()),
            MockResult(scalar_one=_make_instance([1])),
            MockResult(scalar_one=doc),             # doc 查询
        ]

        resp = client.get(
            "/api/v1/tasks/1/document-templates/1/download",
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
        assert resp.status_code == 200
