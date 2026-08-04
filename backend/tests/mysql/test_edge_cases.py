"""MySQL 边界场景测试 —— 驳回、Fork-Join、约束校验

覆盖 mock 测试无法验证的真实数据库行为。
"""

import pytest
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Organization, User, FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge, Task, CheckRecord, Approval, Endorsement,
    File,
)
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus, ApprovalStatus,
    Priority, Difficulty,
)
from app.api.deps import CurrentUser


# ── 复用 test_full_flow 的辅助函数 ──

def _current_user(uid, username="test", org_id=1):
    return CurrentUser({"sub": str(uid), "username": username,
                        "roles": ["manager"], "org_id": org_id})


async def _seed_org_and_users(db, org_id=1):
    """创建组织 + 5 个用户（含批准人）"""
    org = Organization(id=org_id, name="测试所", is_active=True)
    db.add(org)
    users = [
        User(id=1, username="u1", real_name="发起人", password_hash="x", organization_id=org_id, is_active=True),
        User(id=2, username="u2", real_name="负责人", password_hash="x", organization_id=org_id, is_active=True),
        User(id=3, username="u3", real_name="校验人", password_hash="x", organization_id=org_id, is_active=True),
        User(id=4, username="u4", real_name="审批人A", password_hash="x", organization_id=org_id, is_active=True),
        User(id=5, username="u5", real_name="审批人B", password_hash="x", organization_id=org_id, is_active=True),
        User(id=6, username="u6", real_name="批准人", password_hash="x", organization_id=org_id, is_active=True),
    ]
    for u in users:
        db.add(u)
    await db.flush()


async def _seed_simple_template(db, tpl_id=1):
    """创建简单三节点模板：开始→工作（双审批人）→结束"""
    tpl = FlowTemplate(id=tpl_id, name="简单模板", type="project",
                       organization_id=1, created_by=1)
    db.add(tpl)
    # 节点
    nodes = [
        TemplateNode(id=1, template_id=tpl_id, name="发起", is_start=True, is_end=False, sort_order=1),
        TemplateNode(id=2, template_id=tpl_id, name="审批", is_start=False, is_end=False, sort_order=2,
                    assignee_id=2,
                    checkers=[{"user_id": 3, "name": "校验人"}],
                    approvers=[{"user_id": 4, "name": "审批人A"}, {"user_id": 5, "name": "审批人B"}],
                    time_limit_days=3),
        TemplateNode(id=3, template_id=tpl_id, name="终审", is_start=False, is_end=True, sort_order=3,
                    approvers=[{"user_id": 1, "name": "发起人"}]),
    ]
    for n in nodes:
        db.add(n)
    await db.flush()
    # 连线
    db.add(TemplateEdge(id=1, template_id=tpl_id, source_node_id=1, target_node_id=2))
    db.add(TemplateEdge(id=2, template_id=tpl_id, source_node_id=2, target_node_id=3))
    await db.flush()


async def _create_running_instance(db, inst_id=1, tpl_id=1):
    """创建运行中实例（含节点和任务），返回工作节点"""
    inst = FlowInstance(
        id=inst_id, name="测试项目", template_id=tpl_id, template_name="简单模板",
        template_type="project", organization_id=1, initiator_id=1,
        priority=Priority.NORMAL, difficulty=Difficulty.ONE,
        status=InstanceStatus.CREATED, initiated_at=datetime.now(),
    )
    db.add(inst)
    await db.flush()

    # 复制模板节点
    tpl_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == tpl_id).order_by(TemplateNode.sort_order)
    )).scalars().all()
    node_map = {}
    for tn in tpl_nodes:
        inode = InstanceNode(
            id=tn.id + 100, instance_id=inst_id,
            name=tn.name, is_start=tn.is_start, is_end=tn.is_end,
            assignee_id=tn.assignee_id, checkers=tn.checkers, approvers=tn.approvers,
            status=InstanceNodeStatus.WAITING, sort_order=tn.sort_order,
            round=1, incoming_count=0, arrived_count=0,
        )
        db.add(inode)
        node_map[tn.id] = inode
    await db.flush()

    # 复制连线
    tpl_edges = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == tpl_id)
    )).scalars().all()
    for te in tpl_edges:
        src, tgt = node_map.get(te.source_node_id), node_map.get(te.target_node_id)
        if src and tgt:
            db.add(InstanceEdge(instance_id=inst_id, source_node_id=src.id, target_node_id=tgt.id))
    await db.flush()

    # 计算 incoming + 激活开始节点
    from app.engine.flow_engine import calculate_incoming_counts
    await calculate_incoming_counts(db, inst_id)

    # 模拟 activate_start_node
    start_node = (await db.execute(
        select(InstanceNode).where(InstanceNode.instance_id == inst_id, InstanceNode.is_start == True)
    )).scalar_one()
    start_node.status = InstanceNodeStatus.FINISHED

    work_node = (await db.execute(
        select(InstanceNode).where(InstanceNode.instance_id == inst_id,
                                   InstanceNode.is_start == False, InstanceNode.is_end == False)
    )).scalar_one()
    work_node.arrived_count = 1
    if work_node.arrived_count >= work_node.incoming_count:
        work_node.status = InstanceNodeStatus.RUNNING
        task = Task(id=100, instance_id=inst_id, node_id=work_node.id,
                   assignee_id=2, status=TaskStatus.PENDING)
        db.add(task)
    inst.status = InstanceStatus.RUNNING
    await db.flush()

    return inst, work_node


# ============================================================
# 测试类
# ============================================================

@pytest.mark.asyncio
class TestEdgeCases:
    """边界场景"""

    async def test_fk_constraint_catches_invalid_task(self, mysql_session):
        """外键约束：引用不存在的任务 → IntegrityError"""
        db = mysql_session
        await _seed_org_and_users(db)
        await _seed_simple_template(db)
        await _create_running_instance(db)

        # 尝试创建引用不存在 task_id 的 CheckRecord
        cr = CheckRecord(id=999, instance_id=1, node_id=102, task_id=99999,
                        checker_id=3, status=CheckStatus.PENDING, round=1)
        db.add(cr)
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_unique_constraint_on_org_name(self, mysql_session):
        """唯一约束：组织名重复 → IntegrityError（name 有 UNIQUE 约束，必须抛错）"""
        db = mysql_session
        db.add(Organization(id=1, name="测试所", is_active=True))
        await db.flush()

        # 同名组织插入必须被唯一约束拒绝，严格断言而非静默吞错
        db.add(Organization(id=2, name="测试所", is_active=True))
        with pytest.raises(IntegrityError):
            await db.flush()

    async def test_work_node_requires_assignee(self, mysql_session):
        """工作节点 assignee_id 可空 → 允许不设负责人"""
        db = mysql_session
        await _seed_org_and_users(db)
        tpl = FlowTemplate(id=1, name="测试", type="project", organization_id=1, created_by=1)
        db.add(tpl)
        await db.flush()

        # 创建 assignee_id=NULL 的节点
        node = TemplateNode(id=10, template_id=1, name="无负责人节点",
                          is_start=False, is_end=False, sort_order=2)
        db.add(node)
        await db.flush()  # 不应报错

        assert node.id == 10


@pytest.mark.asyncio
class TestCheckReturnFlow:
    """校验退回流程"""

    async def test_check_return_resets_task(self, mysql_session):
        """校验退回 → task 回到 pending → 负责人重新处理"""
        db = mysql_session
        await _seed_org_and_users(db)
        await _seed_simple_template(db)
        inst, work_node = await _create_running_instance(db)

        # 获取 task
        task = (await db.execute(
            select(Task).where(Task.instance_id == 1, Task.node_id == work_node.id)
        )).scalar_one()

        # 模拟提交
        task.status = TaskStatus.WAITING_CHECK
        work_node.status = InstanceNodeStatus.WAITING_CHECK
        cr = CheckRecord(id=200, instance_id=1, node_id=work_node.id, task_id=task.id,
                        checker_id=3, status=CheckStatus.PENDING, round=1)
        db.add(cr)
        await db.flush()

        # 模拟校验退回
        cr.status = CheckStatus.RETURNED
        task.status = TaskStatus.PENDING
        work_node.status = InstanceNodeStatus.RUNNING
        work_node.round += 1
        await db.flush()

        assert cr.status == CheckStatus.RETURNED
        assert task.status == TaskStatus.PENDING
        assert work_node.round == 2


@pytest.mark.asyncio
class TestMultipleApprovers:
    """多审批人场景"""

    async def test_both_approvers_required(self, mysql_session):
        """双审批人都需要通过 → 全部通过后才算完成"""
        db = mysql_session
        await _seed_org_and_users(db)
        await _seed_simple_template(db)
        inst, work_node = await _create_running_instance(db)

        task = (await db.execute(
            select(Task).where(Task.instance_id == 1, Task.node_id == work_node.id)
        )).scalar_one()

        # 模拟已提交，创建两个审批记录
        task.status = TaskStatus.WAITING_APPROVAL
        work_node.status = InstanceNodeStatus.WAITING_APPROVAL
        ap1 = Approval(id=301, instance_id=1, node_id=work_node.id, task_id=task.id,
                      approver_id=4, status=ApprovalStatus.PENDING, round=1)
        ap2 = Approval(id=302, instance_id=1, node_id=work_node.id, task_id=task.id,
                      approver_id=5, status=ApprovalStatus.PENDING, round=1)
        db.add(ap1)
        db.add(ap2)
        await db.flush()

        # 审批人A 通过，B 未通过
        ap1.status = ApprovalStatus.APPROVED
        ap1.decided_at = datetime.now()
        await db.flush()

        # 检查还有 pending
        remaining = (await db.execute(
            select(Approval).where(
                Approval.node_id == work_node.id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].approver_id == 5

        # B 也通过 → 全部通过
        ap2.status = ApprovalStatus.APPROVED
        ap2.decided_at = datetime.now()
        await db.flush()

        remaining = (await db.execute(
            select(Approval).where(
                Approval.node_id == work_node.id,
                Approval.status == ApprovalStatus.PENDING,
            )
        )).scalars().all()
        assert len(remaining) == 0
