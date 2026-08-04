"""MySQL 真实流程端到端测试 —— 从真实发起（create_instance）开始的全链路

与 test_service_flows.py 的分工：
- test_service_flows.py：各 service 的单元级调用 + 边界场景（403/400）
- 本文件：真实发起实例（create_instance 含节点复制、incoming 计算、开始节点激活、
  首个 Task 传播、deadline 链式推算）→ 全链路状态流转 → 完成/终止。

所有状态转换都由真实 service 驱动，不手工改状态、不手工模拟发起逻辑。
只 mock 外部依赖（通知 / PDF 签名 / 物理文件系统）。
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime, date as date_type

from sqlalchemy import select

from app.models import (
    Organization, User, FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge, Task, CheckRecord, Approval,
)
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus, ApprovalStatus,
)
from app.api.deps import CurrentUser
from app.schemas.instance import CreateInstanceRequest
from app.schemas.task import TaskSubmit


# ============================================================
# Mock 工厂 —— 统一 mock 所有外部依赖（通知 / PDF 签名 / 物理文件）
# ============================================================

def _setup_service_mocks(mocker):
    """Mock 所有 service 层的外部依赖，让真实流程专注状态流转"""
    # 通知（各 service 模块级 import，可安全 patch）
    for mod in ["task_service", "check_service", "approval_service",
                "endorsement_service", "instance.terminate"]:
        for fn in ["create_notification", "clear_related"]:
            mocker.patch(f"app.services.{mod}.{fn}", AsyncMock())
    for mod in ["approval_service", "endorsement_service"]:
        mocker.patch(f"app.services.{mod}.clear_related_for_users", AsyncMock())
    # flow_engine 模块级 import 的通知（create_instance / propagate 真实调用时用）
    mocker.patch("app.engine.flow_engine.create_notification", AsyncMock())
    # PDF 签名（service 内部按需导入，本测试不涉及真实 PDF）
    mocker.patch("app.services.pdf_signature.apply_signatures_to_files", AsyncMock())
    mocker.patch("app.services.pdf_signature.get_role_signature_defaults", return_value={})
    # 物理文件系统：mock 为「文件不存在」，batch_delete_files_with_physical 跳过物理删除
    mocker.patch("os.path.exists", return_value=False)


# ============================================================
# 辅助函数
# ============================================================

def _cu(uid, username="u", org_id=1, role="manager"):
    """快速构造 CurrentUser"""
    return CurrentUser({"sub": str(uid), "username": username,
                        "roles": [role], "org_id": org_id})


async def _seed_basic_data(db):
    """创建组织 + 发起人(1)/负责人(2)/校验人(3)/审批人(4)"""
    db.add(Organization(id=1, name="测试所", is_active=True))
    for i, name in [(1, "发起人"), (2, "负责人"), (3, "校验人"), (4, "审批人")]:
        db.add(User(id=i, username=f"u{i}", real_name=name, password_hash="x",
                    organization_id=1, is_active=True))
    await db.flush()


async def _seed_template(db, tpl_id=1):
    """创建模板 + 开始/工作/结束节点 + 连线（工作节点含负责人/校验人/审批人）"""
    db.add(FlowTemplate(id=tpl_id, name="测试流程模板", type="project",
                        organization_id=1, description="测试用", created_by=1))
    nodes = [
        TemplateNode(id=101, template_id=tpl_id, name="发起", is_start=True, is_end=False, sort_order=1),
        TemplateNode(id=102, template_id=tpl_id, name="设计", is_start=False, is_end=False, sort_order=2,
                    assignee_id=2, checkers=[{"user_id": 3, "name": "校验人"}],
                    approvers=[{"user_id": 4, "name": "审批人"}], time_limit_days=5),
        TemplateNode(id=103, template_id=tpl_id, name="终审", is_start=False, is_end=True, sort_order=3,
                    approvers=[{"user_id": 1, "name": "发起人"}]),
    ]
    for n in nodes:
        db.add(n)
    await db.flush()  # 节点先落库，edges 的 FK 引用才能通过

    edges = [
        TemplateEdge(id=201, template_id=tpl_id, source_node_id=101, target_node_id=102),
        TemplateEdge(id=202, template_id=tpl_id, source_node_id=102, target_node_id=103),
    ]
    for e in edges:
        db.add(e)
    await db.flush()


async def _create_instance(db, name="测试项目"):
    """真实调用 create_instance 发起实例（含节点复制/激活/首个 Task 传播/deadline 推算）

    返回 InstanceResponse。create_instance 内部只 flush，测试同事务可见，无需 commit。
    """
    from app.services.instance.create import create_instance
    request = CreateInstanceRequest(
        template_id=1,
        name=name,
        priority="normal",
        difficulty="1",
    )
    return await create_instance(db, request=request, current_user=_cu(1, "initiator"))


async def _query_nodes(db):
    """查询实例全部节点（按 sort_order 排序）"""
    return (await db.execute(
        select(InstanceNode).where(InstanceNode.instance_id == 1).order_by(InstanceNode.sort_order)
    )).scalars().all()


# ============================================================
# 发起实例测试
# ============================================================

@pytest.mark.asyncio
class TestCreateInstance:
    """真实发起实例：节点复制 / 激活 / 首个 Task / deadline 链式推算"""

    async def test_create_instance_generates_full_snapshot(self, mysql_session, mocker):
        """发起 → 实例 running、3 节点复制、开始 finished、工作节点 running + Task、deadline 推算"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)

        resp = await _create_instance(db)

        # 实例已创建为 running
        assert resp.id == 1
        assert resp.status == InstanceStatus.RUNNING
        inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == 1))).scalar_one()
        assert inst.template_type == "project"
        assert inst.organization_id == 1
        assert inst.initiator_id == 1

        # 模板节点 + 连线复制为实例快照
        nodes = await _query_nodes(db)
        assert len(nodes) == 3
        assert len((await db.execute(
            select(InstanceEdge).where(InstanceEdge.instance_id == 1)
        )).scalars().all()) == 2
        start, work, end = nodes
        assert start.is_start and not start.is_end
        assert not work.is_start and not work.is_end
        assert end.is_end and not end.is_start

        # 开始节点激活 finished；工作节点 running；结束节点 waiting
        assert start.status == InstanceNodeStatus.FINISHED
        assert work.status == InstanceNodeStatus.RUNNING
        assert end.status == InstanceNodeStatus.WAITING

        # 真实 propagate 已生成工作节点的首个 Task
        task = (await db.execute(
            select(Task).where(Task.instance_id == 1)
        )).scalars().one()
        assert task.node_id == work.id
        assert task.assignee_id == 2
        assert task.status == TaskStatus.PENDING

        # deadline 链式推算：首个工作节点从发起日起算 time_limit_days 工作日，应为未来日期
        assert work.deadline is not None
        assert work.deadline.date() >= date_type.today()

        # 结束节点 approvers 保持模板配置（发起人终审）
        assert end.approvers == [{"user_id": 1, "name": "发起人"}]


# ============================================================
# 全链路测试
# ============================================================

@pytest.mark.asyncio
class TestFullFlow:
    """完整流程：真实发起 → 提交 → 校验 → 审批 → 终审 → 完成"""

    async def test_full_flow_to_completed(self, mysql_session, mocker):
        """黄金路径：实例从发起一路真实流转到 completed（propagate 真实传播）"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)

        await _create_instance(db)

        # 发起后首个 Task 由真实 propagate 生成
        task = (await db.execute(
            select(Task).where(Task.instance_id == 1)
        )).scalars().one()
        work_node = (await db.execute(
            select(InstanceNode).where(InstanceNode.id == task.node_id)
        )).scalar_one()
        assert not work_node.is_start and not work_node.is_end

        # ── 负责人提交（真实 service）──
        from app.services.task_service import submit_task
        result = await submit_task(db, task_id=task.id, current_user_id=2,
                                   data=TaskSubmit(assignee_note="已完成设计"))
        assert "提交" in result["message"]
        await db.refresh(task)
        assert task.status == TaskStatus.WAITING_CHECK
        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.WAITING_CHECK

        # 校验记录由真实 submit 创建
        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == task.id)
        )).scalar_one()
        assert cr.checker_id == 3
        assert cr.status == CheckStatus.PENDING

        # ── 校验通过（真实 service）→ 创建审批记录 ──
        from app.services.check_service import pass_check
        result = await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")
        assert "校验通过" in result["message"]
        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.WAITING_APPROVAL

        ap = (await db.execute(
            select(Approval).where(Approval.task_id == task.id)
        )).scalar_one()
        assert ap.approver_id == 4
        assert ap.status == ApprovalStatus.PENDING

        # ── 工作节点审批通过 → 真实 propagate 传播到结束节点（终审）──
        from app.services.approval_service import approve
        result = await approve(db, approval_id=ap.id, current_user_id=4, opinion="同意")
        assert result["all_approved"] is True
        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.FINISHED

        # 结束节点已激活为 waiting_approval，并生成终审 Approval（发起人）
        end_node = (await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == 1, InstanceNode.is_end == True
            )
        )).scalar_one()
        assert end_node.status == InstanceNodeStatus.WAITING_APPROVAL
        final_ap = (await db.execute(
            select(Approval).where(
                Approval.node_id == end_node.id, Approval.status == ApprovalStatus.PENDING
            )
        )).scalar_one()
        assert final_ap.approver_id == 1

        # ── 终审通过 → 实例 completed ──
        result = await approve(db, approval_id=final_ap.id, current_user_id=1, opinion="归档")
        assert result.get("instance_completed") is True
        inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == 1))).scalar_one()
        assert inst.status == InstanceStatus.COMPLETED
        assert inst.completed_at is not None


# ============================================================
# 终止流程测试
# ============================================================

@pytest.mark.asyncio
class TestInstanceTerminate:
    """真实发起后终止：实例 + 待办任务全部关闭"""

    async def test_terminate_closes_pending_records(self, mysql_session, mocker):
        """终止流程 → 实例 terminated + 运行中 Task 关闭"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)

        await _create_instance(db)
        task = (await db.execute(
            select(Task).where(Task.instance_id == 1)
        )).scalars().one()
        assert task.status == TaskStatus.PENDING

        from app.services.instance.terminate import terminate_instance
        result = await terminate_instance(db, instance_id=1, reason="测试终止",
                                          current_user=_cu(1, "initiator"))
        assert result["status"] == "terminated"

        inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == 1))).scalar_one()
        assert inst.status == InstanceStatus.TERMINATED
        await db.refresh(task)
        assert task.status == TaskStatus.TERMINATED


# ============================================================
# 同名实例测试
# ============================================================

@pytest.mark.asyncio
class TestDuplicateInstanceName:
    """同名实例可重复发起（name 非唯一约束）"""

    async def test_same_name_instances_both_created(self, mysql_session, mocker):
        """同名发起两次 → 两个实例并存"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)

        resp1 = await _create_instance(db, name="同名项目")
        resp2 = await _create_instance(db, name="同名项目")

        assert resp1.id != resp2.id
        insts = (await db.execute(
            select(FlowInstance).where(FlowInstance.name == "同名项目")
        )).scalars().all()
        assert len(insts) == 2
