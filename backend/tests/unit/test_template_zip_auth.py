"""P0-1 单元测试：模板 ZIP 下载接口归属校验

覆盖两个校验 helper：
- _is_instance_participant：发起人 / 负责人 / 校验人(dict) / 审批人(int) / 批准人 判定
- _collect_instance_doc_ids：实例级配置优先，否则继承模板关联 + 分类包展开
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.templates import _is_instance_participant
from app.services.document_service import collect_instance_doc_ids
from app.models import FlowInstance


class _Node:
    """模拟 InstanceNode 的最小对象（只暴露参与人相关字段）"""

    def __init__(self, assignee_id=None, checkers=None, approvers=None, endorser_id=None):
        self.assignee_id = assignee_id
        self.checkers = checkers
        self.approvers = approvers
        self.endorser_id = endorser_id


def _make_instance(initiator_id=1, template_id=10, doc_template_ids=None):
    """构造 FlowInstance mock，仅暴露本校验关心的字段"""
    inst = MagicMock(spec=FlowInstance)
    inst.id = 100
    inst.initiator_id = initiator_id
    inst.template_id = template_id
    inst.doc_template_ids = doc_template_ids
    return inst


def _mock_node_result(nodes: list) -> MagicMock:
    """构造 db.execute 返回结果：.scalars().all() → nodes

    注意：execute 是 async 方法（AsyncMock），但其返回值上的 .scalars().all()
    是同步链，需用 MagicMock，否则 AsyncMock 的方法调用会返回 coroutine。
    """
    result = MagicMock()
    result.scalars.return_value.all.return_value = nodes
    return result


# ────────────────────────────────────────────────
# _is_instance_participant
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_participant_by_initiator():
    """发起人即参与者（无需查节点）"""
    db = AsyncMock()
    inst = _make_instance(initiator_id=5)
    assert await _is_instance_participant(db, inst, 5) is True
    db.execute.assert_not_called()  # 发起人直接命中，不触发节点查询


@pytest.mark.asyncio
async def test_participant_by_assignee():
    """节点负责人判定为参与者"""
    db = AsyncMock()
    db.execute.return_value = _mock_node_result([_Node(assignee_id=7)])
    assert await _is_instance_participant(db, _make_instance(), 7) is True


@pytest.mark.asyncio
async def test_participant_by_dict_checker_and_int_approver():
    """兼容 checkers 为 dict、approvers 为 int 的历史数组格式"""
    db = AsyncMock()
    db.execute.return_value = _mock_node_result([
        _Node(assignee_id=None, checkers=[{"user_id": 8}], approvers=[9], endorser_id=10),
    ])
    inst = _make_instance()
    assert await _is_instance_participant(db, inst, 8) is True   # 校验人(dict)
    assert await _is_instance_participant(db, inst, 9) is True   # 审批人(int)
    assert await _is_instance_participant(db, inst, 10) is True  # 批准人
    assert await _is_instance_participant(db, inst, 99) is False  # 无关用户


# ────────────────────────────────────────────────
# _collect_instance_doc_ids
# ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_uses_instance_level_config_first():
    """实例级 doc_template_ids 优先，无需查库"""
    db = AsyncMock()
    inst = _make_instance(doc_template_ids=[3, 4])
    assert await collect_instance_doc_ids(db, inst) == {3, 4}
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_collect_from_template_links_and_category():
    """无实例级配置时：继承模板单模板关联 + 分类包内模板展开"""
    db = AsyncMock()
    inst = _make_instance(doc_template_ids=None, template_id=10)

    # 第一次 execute：TemplateDocumentLink（一个单模板 + 一个分类）
    link_result = MagicMock()
    link_doc = MagicMock(document_id=5, category_id=None)
    link_cat = MagicMock(document_id=None, category_id=20)
    link_result.scalars.return_value.all.return_value = [link_doc, link_cat]
    # 第二次 execute：TemplateCategoryDocument（分类 20 内文档）
    cat_result = MagicMock()
    cat_result.scalars.return_value.all.return_value = [6, 7]
    db.execute.side_effect = [link_result, cat_result]

    assert await collect_instance_doc_ids(db, inst) == {5, 6, 7}
