"""designer_service 单元测试 —— 设计器数据保存/节点/连线操作

覆盖：save_design_data、add_node、update_node、delete_node、add_edge、delete_edge
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.services.designer_service import (
    save_design_data, add_node, update_node, delete_node,
    add_edge, delete_edge,
)
from app.models import FlowTemplate

from tests.conftest import MockResult


# ============================================================
# save_design_data —— 批量保存
# ============================================================

class TestSaveDesignData:
    """批量保存设计器数据"""

    @pytest.mark.asyncio
    async def test_template_not_found(self, mock_db):
        """模板不存在 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await save_design_data(mock_db, template_id=999, nodes_data=[], edges_data=[])
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_save_new_nodes_and_edges(self, mock_db, mocker):
        """全新保存 → 创建节点和连线"""
        mocker.patch("app.services.designer_service._topological_sort", new=AsyncMock())
        tpl = FlowTemplate(id=1, name="测试模板", type="project", organization_id=1)

        nodes_data = [
            {"id": "node_1", "type": "start", "name": "开始", "is_start": True, "is_end": False, "position_x": 0, "position_y": 0},
            {"id": "node_2", "type": "work", "name": "审批", "is_start": False, "is_end": False, "position_x": 200, "position_y": 0,
             "assignee_id": 2, "approvers": [{"user_id": 3}], "checkers": []},
            {"id": "node_3", "type": "end", "name": "结束", "is_start": False, "is_end": True, "position_x": 400, "position_y": 0},
        ]
        edges_data = [{"id": "edge_1", "source_node_id": "node_1", "target_node_id": "node_2"},
                      {"id": "edge_2", "source_node_id": "node_2", "target_node_id": "node_3"}]

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MockResult(scalar_one=tpl),                              # 0: SELECT template (FOR UPDATE)
            MockResult(scalars_all=[]),                              # 1: existing nodes → empty
            MockResult(scalars_all=[]),                              # 2: existing edges → empty
            MockResult(scalar_one=None),                             # 3: create node_1 → check existing
            MagicMock(),                                              # 4: add node_1
            MagicMock(),                                              # 5: flush
            MockResult(scalar_one=None),                             # 6: create node_2 → check existing
            MagicMock(),                                              # 7: add node_2
            MagicMock(),                                              # 8: flush
            MockResult(scalar_one=None),                             # 9: create node_3 → check existing
            MagicMock(),                                              # 10: add node_3
            MagicMock(),                                              # 11: flush
            MockResult(scalar_one=None),                             # 12: create edge_1 → check existing
            MagicMock(),                                              # 13: add edge_1
            MagicMock(),                                              # 14: flush
            MockResult(scalar_one=None),                             # 15: create edge_2 → check existing
            MagicMock(),                                              # 16: add edge_2
            MagicMock(),                                              # 17: flush
            # topological sort
            MockResult(scalars_all=[]),                              # 18: SELECT nodes for topo
        ]

        result = await save_design_data(mock_db, template_id=1,
                                       nodes_data=nodes_data, edges_data=edges_data)

        assert result["template_id"] == 1
        assert "node_count" in result
        assert "edge_count" in result


# ============================================================
# add_node / update_node / delete_node
# ============================================================

class TestNodeOperations:
    """节点 CRUD 测试"""

    @pytest.mark.asyncio
    async def test_add_node_template_not_found(self, mock_db):
        """添加节点 → 模板不存在"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await add_node(mock_db, template_id=999, data={"name": "新节点"})
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_node_not_found(self, mock_db):
        """删除不存在的节点 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await delete_node(mock_db, node_id=999)
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_node_not_found(self, mock_db):
        """更新不存在的节点 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await update_node(mock_db, node_id=999, data={})
        assert exc.value.code == ErrorCode.NOT_FOUND


# ============================================================
# add_edge / delete_edge
# ============================================================

class TestEdgeOperations:
    """连线操作测试"""

    @pytest.mark.asyncio
    async def test_add_edge_template_not_found(self, mock_db):
        """添加连线 → 模板不存在"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await add_edge(mock_db, template_id=999, source_node_id="n1", target_node_id="n2")
        assert exc.value.code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_edge_not_found(self, mock_db):
        """删除不存在的连线 → 404"""
        mock_db.execute = AsyncMock(return_value=MockResult(scalar_one=None))

        with pytest.raises(AppException) as exc:
            await delete_edge(mock_db, edge_id=999, template_id=1)
        assert exc.value.code == ErrorCode.NOT_FOUND
