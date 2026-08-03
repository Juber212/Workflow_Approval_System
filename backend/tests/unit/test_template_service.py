"""template_service 单元测试 —— 模板 CRUD + 组织卡片

测试策略：使用 mock_db 验证 service 层的 guard 逻辑和核心流程。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import FlowTemplate, Organization, TemplateNode, User
from app.services.template_service import (
    create_template, get_template_detail, update_template, delete_template,
    get_organization_summaries, _node_to_dict,
)
from tests.conftest import MockResult


# ============================================================
# 组织卡片
# ============================================================

class TestGetOrganizationSummaries:
    """组织卡片列表"""

    @pytest.mark.asyncio
    async def test_returns_all_active_orgs(self, mock_db):
        """有活跃组织 → 返回所有组织卡片"""
        org = Organization(id=1, name="测试所", is_active=True)

        from app.models.enums import InstanceStatus
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            # 0: SELECT orgs → 返回活跃组织
            MockResult(scalars_all=[org]),
            # 1: 批量模板数（使用 .all()）
            MockResult(rows_all=[]),
            # 2: 批量实例状态统计（使用 .all() 返回元组列表）
            MockResult(rows_all=[
                (1, InstanceStatus.RUNNING, 3),
                (1, InstanceStatus.COMPLETED, 5),
                (1, InstanceStatus.TERMINATED, 1),
            ]),
            # 3: 模板最近更新时间（使用 .all()）
            MockResult(rows_all=[]),
            # 4: 实例最近更新时间（使用 .all()）
            MockResult(rows_all=[]),
            # 5: 当前用户所属组织（使用 scalar_one_or_none）
            MockResult(scalar_one=None),
        ]

        result, total = await get_organization_summaries(mock_db, current_user_id=1)
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "测试所"
        assert result[0].running_instance_count == 3
        assert result[0].completed_instance_count == 5
        assert result[0].terminated_instance_count == 1

    @pytest.mark.asyncio
    async def test_no_active_orgs(self, mock_db):
        """无活跃组织 → 返回空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalars_all=[]),  # SELECT orgs → 空
        ]

        result, total = await get_organization_summaries(mock_db)
        assert result == []
        assert total == 0


# ============================================================
# 创建模板
# ============================================================

class TestCreateTemplate:
    """创建模板"""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_db):
        """正常创建模板 → 返回模板对象"""
        org = Organization(id=1, name="测试所")
        tpl = FlowTemplate(id=1, name="新模板", organization_id=1, type="project")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=org),       # 0: SELECT org → 存在
            MockResult(scalar_one=None),       # 1: 同名检查 → 无重复
        ]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        from app.schemas.template import TemplateCreate
        data = TemplateCreate(name="新模板", organization_id=1)

        result = await create_template(mock_db, data, user_id=1)
        assert result is not None
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_org_not_found(self, mock_db):
        """所属组织不存在 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # SELECT org → 不存在
        ]

        from app.schemas.template import TemplateCreate
        data = TemplateCreate(name="新模板", organization_id=999)

        with pytest.raises(AppException) as exc:
            await create_template(mock_db, data, user_id=1)
        assert exc.value.code == ErrorCode.NOT_FOUND


# ============================================================
# 查询模板详情
# ============================================================

class TestGetTemplateDetail:
    """查询模板详情"""

    @pytest.mark.asyncio
    async def test_get_existing_template(self, mock_db):
        """查询存在的模板 → 返回完整详情"""
        tpl = FlowTemplate(id=1, name="审批模板", description="描述",
                           organization_id=1, type="project", created_by=1)
        node = TemplateNode(id=100, template_id=1, name="节点1", is_start=False,
                            is_end=False, sort_order=2, approval_strategy="all_approve")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=tpl),          # 0: SELECT template
            MockResult(scalars_all=[node]),       # 1: SELECT nodes
            MockResult(scalars_all=[]),           # 2: SELECT edges
            # 3: user_ids 为空，跳过 users 查询
            MockResult(scalar_one="测试所"),      # 3: SELECT org name
            MockResult(scalar_one="创建人"),      # 4: SELECT creator name
            MockResult(scalar_value=0),          # 5: SELECT instance count
        ]

        result = await get_template_detail(mock_db, template_id=1)
        assert result.id == 1
        assert result.name == "审批模板"
        assert result.node_count == 1
        assert result.organization_name == "测试所"

    @pytest.mark.asyncio
    async def test_template_not_found(self, mock_db):
        """查询不存在的模板 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # SELECT template → 不存在
        ]

        with pytest.raises(AppException) as exc:
            await get_template_detail(mock_db, template_id=999)
        assert exc.value.code == ErrorCode.NOT_FOUND

    def test_node_to_dict_includes_endorser_signature(self):
        """加载模板节点序列化返回批准人签批开关 + 批准人（此前缺失前端读不到）"""
        node = TemplateNode(id=100, name="节点1", is_start=False, is_end=False,
                            require_endorser_signature=False, endorser_id=3)
        d = _node_to_dict(node, {})
        assert d["require_endorser_signature"] is False
        assert d["endorser_id"] == 3


# ============================================================
# 更新模板
# ============================================================

class TestUpdateTemplate:
    """更新模板"""

    @pytest.mark.asyncio
    async def test_update_success(self, mock_db):
        """正常更新 → 返回更新后的模板"""
        tpl = FlowTemplate(id=1, name="旧名称", organization_id=1, type="project")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=tpl),    # 0: SELECT template
        ]
        mock_db.flush = AsyncMock()

        from app.schemas.template import TemplateUpdate
        data = TemplateUpdate(name="新名称", description="新描述")

        result = await update_template(mock_db, template_id=1, data=data)
        assert result is not None
        assert result.name == "新名称"

    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_db):
        """更新不存在的模板 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # SELECT template → 不存在
        ]

        from app.schemas.template import TemplateUpdate
        data = TemplateUpdate(name="不存在")

        with pytest.raises(AppException) as exc:
            await update_template(mock_db, template_id=999, data=data)
        assert exc.value.code == ErrorCode.NOT_FOUND


# ============================================================
# 删除模板
# ============================================================

class TestDeleteTemplate:
    """删除模板"""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_db):
        """正常删除 → 成功"""
        tpl = FlowTemplate(id=1, name="待删除", organization_id=1, type="project")

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=tpl),  # 0: SELECT template
            MockResult(scalar_value=0),  # 1: SELECT COUNT(*) active instances → 0
        ]
        mock_db.flush = AsyncMock()

        await delete_template(mock_db, template_id=1)
        mock_db.delete.assert_called_once_with(tpl)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_db):
        """删除不存在的模板 → 404"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=None),  # SELECT template → 不存在
        ]

        with pytest.raises(AppException) as exc:
            await delete_template(mock_db, template_id=999)
        assert exc.value.code == ErrorCode.NOT_FOUND
