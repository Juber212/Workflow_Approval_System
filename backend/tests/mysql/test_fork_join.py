"""MySQL 真实 Fork/Join 汇合测试 —— 分支传播与汇合等待

模板拓扑：开始 → 分支A / 分支B → 汇合 → 结束（DAG，汇合点 incoming_count=2）。
全程真实 service：真实 create_instance 发起 + 真实 propagate_from_node 传播，
验证「所有上游分支到达才激活汇合」这一 fork/join 核心语义在真实 DB 下成立。
只 mock 外部依赖（通知 / PDF 签名 / 物理文件系统）。
"""

import pytest
from unittest.mock import AsyncMock

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
# Mock 工厂（对齐 test_full_flow：真实 propagate，mock 通知/签名/物理文件）
# ============================================================

def _setup_service_mocks(mocker):
    """Mock 外部依赖（通知 / PDF 签名 / 物理文件系统），真实流程专注状态流转"""
    for mod in ["task_service", "check_service", "approval_service", "endorsement_service"]:
        for fn in ["create_notification", "clear_related"]:
            mocker.patch(f"app.services.{mod}.{fn}", AsyncMock())
    for mod in ["approval_service", "endorsement_service"]:
        mocker.patch(f"app.services.{mod}.clear_related_for_users", AsyncMock())
    # flow_engine 模块级 import 的通知（create_instance / propagate 真实调用时用）
    mocker.patch("app.engine.flow_engine.create_notification", AsyncMock())
    mocker.patch("app.services.pdf_signature.apply_signatures_to_files", AsyncMock())
    mocker.patch("app.services.pdf_signature.get_role_signature_defaults", return_value={})
    mocker.patch("os.path.exists", return_value=False)


# ============================================================
# 辅助函数
# ============================================================

def _cu(uid, username="u", org_id=1, role="manager"):
    """快速构造 CurrentUser"""
    return CurrentUser({"sub": str(uid), "username": username,
                        "roles": [role], "org_id": org_id})


async def _seed_basic_data(db):
    """创建组织 + 发起人(1)/分支A负责人(2)/校验人(3)/审批人(4)/分支B负责人(5)"""
    db.add(Organization(id=1, name="测试所", is_active=True))
    for i, name in [(1, "发起人"), (2, "负责人A"), (3, "校验人"), (4, "审批人"), (5, "负责人B")]:
        db.add(User(id=i, username=f"u{i}", real_name=name, password_hash="x",
                    organization_id=1, is_active=True))
    await db.flush()


async def _seed_fork_join_template(db):
    """创建 fork/join 模板：开始 → 分支A/分支B → 汇合 → 结束"""
    tpl = FlowTemplate(id=1, name="并行模板", type="project",
                       organization_id=1, description="fork/join", created_by=1)
    db.add(tpl)
    nodes = [
        TemplateNode(id=1, template_id=1, name="开始", is_start=True, is_end=False, sort_order=1),
        TemplateNode(id=2, template_id=1, name="分支A", is_start=False, is_end=False, sort_order=2,
                    assignee_id=2, checkers=[{"user_id": 3, "name": "校验人"}],
                    approvers=[{"user_id": 4, "name": "审批人"}], time_limit_days=3),
        TemplateNode(id=3, template_id=1, name="分支B", is_start=False, is_end=False, sort_order=3,
                    assignee_id=5, checkers=[{"user_id": 3, "name": "校验人"}],
                    approvers=[{"user_id": 4, "name": "审批人"}], time_limit_days=3),
        TemplateNode(id=4, template_id=1, name="汇合", is_start=False, is_end=False, sort_order=4,
                    assignee_id=2, checkers=[{"user_id": 3, "name": "校验人"}],
                    approvers=[{"user_id": 4, "name": "审批人"}], time_limit_days=3),
        TemplateNode(id=5, template_id=1, name="结束", is_start=False, is_end=True, sort_order=5,
                    approvers=[{"user_id": 1, "name": "发起人"}]),
    ]
    for n in nodes:
        db.add(n)
    await db.flush()  # 节点先落库，edges 的 FK 引用才能通过

    for e in [
        TemplateEdge(id=1, template_id=1, source_node_id=1, target_node_id=2),
        TemplateEdge(id=2, template_id=1, source_node_id=1, target_node_id=3),
        TemplateEdge(id=3, template_id=1, source_node_id=2, target_node_id=4),
        TemplateEdge(id=4, template_id=1, source_node_id=3, target_node_id=4),
        TemplateEdge(id=5, template_id=1, source_node_id=4, target_node_id=5),
    ]:
        db.add(e)
    await db.flush()


async def _create_instance(db, name="并行项目"):
    """真实调用 create_instance 发起（propagate 真实激活分支A/B）"""
    from app.services.instance.create import create_instance
    request = CreateInstanceRequest(template_id=1, name=name, priority="normal", difficulty="1")
    return await create_instance(db, request=request, current_user=_cu(1, "initiator"))


async def _nodes_by_name(db):
    """查询实例全部节点 → name → node 映射"""
    nodes = (await db.execute(
        select(InstanceNode).where(InstanceNode.instance_id == 1).order_by(InstanceNode.sort_order)
    )).scalars().all()
    return {n.name: n for n in nodes}


async def _run_node_to_finish(db, task: Task):
    """把单个工作节点走完：提交 → 校验 → 审批（返回审批结果）"""
    from app.services.task_service import submit_task
    from app.services.check_service import pass_check
    from app.services.approval_service import approve

    result = await submit_task(db, task_id=task.id, current_user_id=task.assignee_id,
                               data=TaskSubmit(assignee_note="已完成"))
    assert result["message"] != ""

    cr = (await db.execute(
        select(CheckRecord).where(CheckRecord.task_id == task.id)
    )).scalar_one()
    await pass_check(db, check_id=cr.id, current_user_id=cr.checker_id, opinion="通过")

    ap = (await db.execute(
        select(Approval).where(Approval.task_id == task.id)
    )).scalar_one()
    return await approve(db, approval_id=ap.id, current_user_id=ap.approver_id, opinion="同意")


# ============================================================
# 测试
# ============================================================

@pytest.mark.asyncio
class TestForkJoin:
    """fork/join 真实汇合：两个分支都完成才激活汇合节点"""

    async def test_fork_join_waits_for_both_branches(self, mysql_session, mocker):
        """分支A/B 任一未完成 → 汇合等待；两分支都完成 → 汇合激活并最终完成"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_fork_join_template(db)

        await _create_instance(db)

        # ── 发起后：分支A/B 都被真实 propagate 激活，各生成一个 Task ──
        nodes = await _nodes_by_name(db)
        branch_a, branch_b, join = nodes["分支A"], nodes["分支B"], nodes["汇合"]
        assert branch_a.status == InstanceNodeStatus.RUNNING
        assert branch_b.status == InstanceNodeStatus.RUNNING
        assert join.status == InstanceNodeStatus.WAITING  # 汇合等待两分支

        task_a = (await db.execute(
            select(Task).where(Task.node_id == branch_a.id)
        )).scalars().one()
        task_b = (await db.execute(
            select(Task).where(Task.node_id == branch_b.id)
        )).scalars().one()
        assert task_a.assignee_id == 2
        assert task_b.assignee_id == 5

        # ── 分支A 走完 → 汇合 arrived=1/2，仍等待，不激活 ──
        await _run_node_to_finish(db, task_a)
        await db.refresh(join)
        assert branch_a.status == InstanceNodeStatus.FINISHED
        assert join.status == InstanceNodeStatus.WAITING  # 分支B 未到，继续等
        assert (await db.execute(
            select(Task).where(Task.node_id == join.id)
        )).scalars().all() == []  # 汇合未激活 → 无 Task

        # ── 分支B 走完 → 汇合 arrived=2/2，激活 running + 生成 Task ──
        await _run_node_to_finish(db, task_b)
        await db.refresh(join)
        assert join.status == InstanceNodeStatus.RUNNING
        task_join = (await db.execute(
            select(Task).where(Task.node_id == join.id)
        )).scalars().one()

        # ── 汇合节点走完 → 传播到结束节点（终审）→ 终审通过 → 实例完成 ──
        await _run_node_to_finish(db, task_join)
        await db.refresh(join)
        assert join.status == InstanceNodeStatus.FINISHED

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

        from app.services.approval_service import approve
        result = await approve(db, approval_id=final_ap.id, current_user_id=1, opinion="归档")
        assert result.get("instance_completed") is True

        inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == 1))).scalar_one()
        assert inst.status == InstanceStatus.COMPLETED
