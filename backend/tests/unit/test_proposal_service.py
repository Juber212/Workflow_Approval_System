"""proposal_service 单元测试 —— 组织统计/列表/模板/创建方案边界"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import FlowTemplate, FlowInstance, Organization, User
from app.models.enums import InstanceStatus
from app.services.proposal_service import (
    get_organization_summaries, list_proposals,
    ensure_proposal_template, create_proposal,
)
from tests.conftest import MockResult
from tests.factories import make_user


# ============================================================
# 组织方案统计
# ============================================================

class TestGetOrganizationSummaries:
    """get_organization_summaries —— 各所方案卡片"""

    @pytest.mark.asyncio
    async def test_returns_data(self, mock_db):
        """有方案 → 返回分组统计"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[
                type("Row", (), {
                    "organization_id": 1, "org_name": "测试所",
                    "total": 10, "running": 3, "completed": 5,
                    "terminated": 2,
                    "latest_update": datetime.now(),
                }),
            ]),
        ]

        result = await get_organization_summaries(mock_db, user_org_id=1)
        orgs = result["organizations"]
        assert len(orgs) == 1
        assert orgs[0]["id"] == 1
        assert orgs[0]["name"] == "测试所"
        assert orgs[0]["running_count"] == 3
        assert orgs[0]["completed_count"] == 5
        assert orgs[0]["terminated_count"] == 2
        assert orgs[0]["is_current_user_org"] is True

    @pytest.mark.asyncio
    async def test_empty(self, mock_db):
        """无方案 → 空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(rows_all=[]),
        ]

        result = await get_organization_summaries(mock_db, user_org_id=1)
        assert result["organizations"] == []


# ============================================================
# 方案列表
# ============================================================

class TestListProposals:
    """list_proposals —— 分页列表"""

    @pytest.mark.asyncio
    async def test_returns_data(self, mock_db):
        """有方案 → 返回分页列表含发起人"""
        inst = FlowInstance(
            id=1, name="设计方案", organization_id=1,
            template_type="proposal", initiator_id=1,
            status=InstanceStatus.RUNNING, created_at=datetime.now(),
        )
        user = User(id=1, username="zhangsan", real_name="张三", password_hash="x",
                    organization_id=1, is_active=True)
        org = Organization(id=1, name="测试所", is_active=True)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=1),              # 0: count
            MockResult(scalars_all=[inst]),           # 1: list
            MockResult(scalars_all=[user]),            # 2: users
            MockResult(scalars_all=[org]),             # 3: orgs
        ]

        result = await list_proposals(mock_db)
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == 1
        assert result.items[0].name == "设计方案"
        assert result.items[0].initiator_name == "张三"
        assert result.items[0].organization_name == "测试所"

    @pytest.mark.asyncio
    async def test_empty(self, mock_db):
        """无方案 → 空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_value=0),       # 0: count
            MockResult(scalars_all=[]),       # 1: list
        ]

        result = await list_proposals(mock_db)
        assert result.total == 0
        assert result.items == []


# ============================================================
# 确保方案模板
# ============================================================

class TestEnsureProposalTemplate:
    """ensure_proposal_template —— 获取或创建方案内置模板"""

    @pytest.mark.asyncio
    async def test_existing_template(self, mock_db):
        """模板已存在 → 直接返回"""
        tpl = FlowTemplate(
            id=10, name="方案默认模板", organization_id=1,
            type="proposal", created_by=1,
        )

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=tpl),  # 0: SELECT ... FOR UPDATE → 已存在
        ]

        result = await ensure_proposal_template(mock_db, org_id=1, user_id=1)
        assert result is not None
        assert result.id == 10
        assert result.type == "proposal"


# ============================================================
# 创建方案边界
# ============================================================

class TestCreateProposal:
    """create_proposal —— 组织校验边界"""

    @pytest.mark.asyncio
    async def test_org_not_found(self, mock_db):
        """组织不存在 → 404"""
        from app.schemas.proposal import ProposalCreateRequest
        from app.api.deps import CurrentUser

        body = ProposalCreateRequest(
            name="测试方案", organization_id=999,
            designer_id=1, approvers=[{"user_id": 2}],
        )
        current_user = CurrentUser({"sub": "1", "username": "test", "roles": ["manager"], "org_id": 1})

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # 0: 组织查询 → 不存在
        ]

        with pytest.raises(AppException) as exc:
            await create_proposal(mock_db, body, current_user)
        assert exc.value.code == ErrorCode.NOT_FOUND
