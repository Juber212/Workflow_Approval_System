"""集成测试 —— 审批流转全链路（API → Service 端到端）

使用 FastAPI TestClient + 依赖注入覆盖：
- get_db → mock AsyncSession
- get_current_active_user → mock CurrentUser
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_active_user, get_db, CurrentUser
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus, ApprovalStatus,
)
from tests.factories import make_instance, make_node, make_task, make_check, make_approval
from tests.conftest import MockResult


# ============================================================
# 测试夹具 —— mock 认证 + 数据库
# ============================================================

def _make_current_user(user_id=1, role="user", org_id=1):
    """创建 mock CurrentUser"""
    return CurrentUser({
        "sub": str(user_id),
        "username": f"user{user_id}",
        "roles": [role],
        "org_id": org_id,
    })


@pytest.fixture
def client_with_mocks():
    """TestClient + mock get_db + mock get_current_active_user"""
    mock_db = AsyncMock()
    # SQLAlchemy 同步方法用 MagicMock（非 AsyncMock），避免 coroutine 未 await 警告
    mock_db.add = MagicMock()
    mock_db.delete = MagicMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    # 不 override get_current_active_user —— 让它正常走 JWT 解析
    # 但 get_current_active_user 内部调用了 db.execute 查 User，
    # 所以 mock_db.execute 也必须能处理那个 User 查询

    client = TestClient(app)
    client.mock_db = mock_db
    yield client
    app.dependency_overrides.clear()


def _setup_user_query(mock_db, user_id=1, role="user", org_id=1):
    """配置 mock_db 以支持 get_current_active_user 的 User 查询"""
    from app.models import User
    user = User(
        id=user_id, username=f"user{user_id}",
        real_name=f"用户{user_id}", password_hash="x",
        organization_id=org_id, is_active=True,
    )
    # get_current_active_user 会查 User + 再查 User（查角色信息）
    # 还有 db.execute(select(User)...) 返回 scalar_one_or_none
    mock_db.execute = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_one=user),  # get_current_active_user 的 User 查询
    ]
    return user


# ============================================================
# 校验流转集成测试
# ============================================================

class TestCheckFlowIntegration:
    """校验流程 API 集成测试"""

    def test_pass_check_all_passed(self, client_with_mocks):
        """POST /api/v1/checks/1/pass → 全部通过 → 进入审批"""
        client = client_with_mocks
        db = client.mock_db

        # 模拟 JWT 中的用户（校验人）
        user = _setup_user_query(db, user_id=3, role="user")

        check = make_check(id=1, task_id=10, node_id=5, checker_id=3, status=CheckStatus.PENDING)
        node = make_node(id=5, require_checker_signature=False,
                         checkers=[{"user_id": 3}], approvers=[{"user_id": 4}])
        task = make_task(id=10, node_id=5)

        # pass_check 中的 execute 调用链
        db.execute.side_effect = [
            MockResult(scalar_one=user),        # 0: get_current_active_user → User
            MockResult(scalar_one=check),       # 1: SELECT check FOR UPDATE
            MagicMock(),                         # 2: lock other pending
            MockResult(scalars_all=[]),          # 3: all pending → 空
            MockResult(scalar_one=node),         # 4: SELECT node
            MockResult(scalar_one=task),         # 5: SELECT task
        ]

        # 生成一个有效 JWT token
        from app.core.security import create_access_token
        token = create_access_token({"sub": "3", "username": "user3", "roles": ["user"], "org_id": 1})

        resp = client.post(
            "/api/v1/checks/1/pass",
            json={"opinion": "通过"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"

    def test_pass_check_wrong_user(self, client_with_mocks):
        """非校验人操作 → 403"""
        client = client_with_mocks
        db = client.mock_db

        user = _setup_user_query(db, user_id=999)  # 不是校验人

        check = make_check(id=1, checker_id=3, status=CheckStatus.PENDING)

        db.execute.side_effect = [
            MockResult(scalar_one=user),        # 0: get_current_active_user
            MockResult(scalar_one=check),       # 1: SELECT check
        ]

        from app.core.security import create_access_token
        token = create_access_token({"sub": "999", "username": "other", "roles": ["user"], "org_id": 1})

        resp = client.post(
            "/api/v1/checks/1/pass",
            json={"opinion": "通过"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    def test_return_check_success(self, client_with_mocks):
        """POST /api/v1/checks/1/return → 退回"""
        client = client_with_mocks
        db = client.mock_db

        user = _setup_user_query(db, user_id=3)

        check = make_check(id=1, task_id=10, node_id=5, checker_id=3, status=CheckStatus.PENDING)
        node = make_node(id=5, round=1)
        task = make_task(id=10, node_id=5, status=TaskStatus.WAITING_CHECK)

        db.execute.side_effect = [
            MockResult(scalar_one=user),        # 0: get_current_active_user
            MockResult(scalar_one=check),       # 1: check FOR UPDATE
            MagicMock(),                         # 2: update other checks
            MockResult(scalar_one=node),         # 3: get node
            MockResult(scalars_all=[]),          # 4: get files
            MockResult(scalar_one=task),         # 5: get task
        ]

        from app.core.security import create_access_token
        token = create_access_token({"sub": "3", "username": "user3", "roles": ["user"], "org_id": 1})

        resp = client.post(
            "/api/v1/checks/1/return",
            json={"opinion": "格式错误"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ============================================================
# 审批流转集成测试
# ============================================================

class TestApprovalFlowIntegration:
    """审批流程 API 集成测试"""

    def test_approve_all_approved(self, client_with_mocks, mocker):
        """POST /api/v1/approvals/1/approve → 全部通过"""
        mocker.patch("app.services.approval_service.propagate_from_node", new=AsyncMock())

        client = client_with_mocks
        db = client.mock_db

        user = _setup_user_query(db, user_id=4)

        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, require_approver_signature=False, endorser_id=None)
        inst = make_instance(id=1, difficulty="1")

        db.execute.side_effect = [
            MockResult(scalar_one=user),        # 0: get_current_active_user
            MockResult(scalar_one=approval),    # 1: approval FOR UPDATE
            MagicMock(),                         # 2: lock other pending
            MockResult(scalars_all=[]),          # 3: remaining → 空
            MagicMock(),                         # 4: UPDATE task
            MockResult(scalar_one=node),         # 5: get node
            MockResult(scalar_one=inst),         # 6: get FlowInstance
            MockResult(scalar_one=None),         # 7: get FlowTemplate
        ]

        from app.core.security import create_access_token
        token = create_access_token({"sub": "4", "username": "user4", "roles": ["user"], "org_id": 1})

        resp = client.post(
            "/api/v1/approvals/1/approve",
            json={"opinion": "同意"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"

    def test_approve_wrong_user(self, client_with_mocks):
        """非审批人操作 → 403"""
        client = client_with_mocks
        db = client.mock_db

        user = _setup_user_query(db, user_id=999)

        approval = make_approval(id=1, approver_id=4, status=ApprovalStatus.PENDING)

        db.execute.side_effect = [
            MockResult(scalar_one=user),        # 0: get_current_active_user
            MockResult(scalar_one=approval),    # 1: approval
        ]

        from app.core.security import create_access_token
        token = create_access_token({"sub": "999", "username": "other", "roles": ["user"], "org_id": 1})

        resp = client.post(
            "/api/v1/approvals/1/approve",
            json={"opinion": "同意"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    def test_reject_mid_node(self, client_with_mocks):
        """POST /api/v1/approvals/1/reject → 中间节点退回"""
        client = client_with_mocks
        db = client.mock_db

        user = _setup_user_query(db, user_id=4)

        approval = make_approval(id=1, task_id=10, node_id=5, approver_id=4, status=ApprovalStatus.PENDING)
        node = make_node(id=5, is_end=False, round=2)
        task = make_task(id=10, node_id=5, status=TaskStatus.WAITING_APPROVAL)

        db.execute.side_effect = [
            MockResult(scalar_one=user),        # 0: get_current_active_user
            MockResult(scalar_one=approval),    # 1: approval FOR UPDATE
            MockResult(scalar_one=node),         # 2: get node
            MagicMock(),                         # 3: clear_related delete
            MagicMock(),                         # 4: update other approvals
            MagicMock(),                         # 5: update pending checks
            MockResult(scalars_all=[]),          # 6: get files
            MockResult(scalar_one=task),         # 7: get task
        ]

        from app.core.security import create_access_token
        token = create_access_token({"sub": "4", "username": "user4", "roles": ["user"], "org_id": 1})

        resp = client.post(
            "/api/v1/approvals/1/reject",
            json={"opinion": "数据有误"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
