"""MySQL 真实 Service 调用测试 —— 完整业务流程 + 边界场景

直接调用真实 service 函数，只 mock 外部依赖（通知/PDF/签名），
数据库操作全部走真实 MySQL，验证每一步的状态转换。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from sqlalchemy import select

from app.models import (
    Organization, User, FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge, Task, CheckRecord, Approval,
    Endorsement, File, OperationLog, Signature,
)
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus, ApprovalStatus,
    EndorsementStatus, Priority, Difficulty,
)
from app.core.exceptions import AppException, ErrorCode
from app.api.deps import CurrentUser
from app.schemas.task import TaskSubmit


# ============================================================
# Mock 工厂 —— 统一 mock 所有外部依赖
# ============================================================

def _setup_service_mocks(mocker):
    """Mock 所有 service 层的外部依赖（通知/PDF/签名/传播）"""
    # 通知（模块级导入，可安全 patch）
    for mod in ["task_service", "check_service", "approval_service", "endorsement_service",
                "flow_engine"]:
        for fn in ["create_notification", "clear_related"]:
            try:
                mocker.patch(f"app.services.{mod}.{fn}", AsyncMock())
            except AttributeError:
                pass  # 该模块未导入此函数

    # PDF 签名（在 pdf_signature 模块，service 函数内部按需导入）
    mocker.patch("app.services.pdf_signature.apply_signatures_to_files", AsyncMock())
    mocker.patch("app.services.pdf_signature.get_role_signature_defaults", return_value={})

    # 流程传播
    for mod in ["approval_service", "endorsement_service"]:
        try:
            mocker.patch(f"app.services.{mod}.propagate_from_node", AsyncMock(return_value=[]))
        except AttributeError:
            pass



# ============================================================
# 辅助函数
# ============================================================

def _cu(uid, username="u", org_id=1, role="manager"):
    """快速构造 CurrentUser"""
    return CurrentUser({"sub": str(uid), "username": username,
                        "roles": [role], "org_id": org_id})


async def _seed_data(db):
    """创建组织 + 发起人(1)/负责人(2)/校验人(3)/审批人(4)/批准人(5)"""
    db.add(Organization(id=1, name="测试所", is_active=True))
    for i, name in [(1, "发起人"), (2, "负责人"), (3, "校验人"), (4, "审批人"), (5, "批准人")]:
        db.add(User(id=i, username=f"u{i}", real_name=name, password_hash="x",
                    organization_id=1, is_active=True))
    await db.flush()


async def _seed_complete_scenario(db, with_checkers=True, with_endorser=False):
    """创建完整测试场景：模板+节点+连线+实例+节点+任务

    返回: (instance, work_node, task)
    """
    await _seed_data(db)

    # 模板
    db.add(FlowTemplate(id=1, name="测试模板", type="project", organization_id=1, created_by=1))
    await db.flush()

    # 构建节点配置
    checker_cfg = [{"user_id": 3, "name": "校验人"}] if with_checkers else []
    approver_cfg = [{"user_id": 4, "name": "审批人"}]
    endorser_id = 5 if with_endorser else None

    # 模板节点
    for n in [
        TemplateNode(id=1, template_id=1, name="开始", is_start=True, is_end=False, sort_order=1),
        TemplateNode(id=2, template_id=1, name="审批节点", is_start=False, is_end=False, sort_order=2,
                    assignee_id=2, checkers=checker_cfg, approvers=approver_cfg,
                    endorser_id=endorser_id, time_limit_days=5),
        TemplateNode(id=3, template_id=1, name="结束", is_start=False, is_end=True, sort_order=3,
                    approvers=[{"user_id": 1, "name": "发起人"}]),
    ]:
        db.add(n)
    await db.flush()

    # 模板连线
    for e in [
        TemplateEdge(id=1, template_id=1, source_node_id=1, target_node_id=2),
        TemplateEdge(id=2, template_id=1, source_node_id=2, target_node_id=3),
    ]:
        db.add(e)
    await db.flush()

    # 实例
    inst = FlowInstance(
        id=1, name="测试项目", template_id=1, template_name="测试模板",
        template_type="project", organization_id=1, initiator_id=1,
        priority=Priority.NORMAL, difficulty=Difficulty.ONE,
        status=InstanceStatus.CREATED, initiated_at=datetime.now(),
    )
    db.add(inst)
    await db.flush()

    # 实例节点（从模板复制）
    tpl_nodes = (await db.execute(
        select(TemplateNode).where(TemplateNode.template_id == 1).order_by(TemplateNode.sort_order)
    )).scalars().all()
    node_map = {}
    for tn in tpl_nodes:
        inode = InstanceNode(
            id=tn.id + 100, instance_id=1,
            name=tn.name, is_start=tn.is_start, is_end=tn.is_end,
            assignee_id=tn.assignee_id, checkers=tn.checkers, approvers=tn.approvers,
            endorser_id=tn.endorser_id,
            status=InstanceNodeStatus.WAITING, sort_order=tn.sort_order,
            round=1, incoming_count=0, arrived_count=0,
        )
        db.add(inode)
        node_map[tn.id] = inode
    await db.flush()

    # 实例连线
    tpl_edges = (await db.execute(
        select(TemplateEdge).where(TemplateEdge.template_id == 1)
    )).scalars().all()
    for te in tpl_edges:
        src, tgt = node_map.get(te.source_node_id), node_map.get(te.target_node_id)
        if src and tgt:
            db.add(InstanceEdge(instance_id=1, source_node_id=src.id, target_node_id=tgt.id))
    await db.flush()

    # 计算 incoming_counts
    from app.engine.flow_engine import calculate_incoming_counts
    await calculate_incoming_counts(db, 1)

    # 激活开始节点 + 创建首个任务
    start_node = node_map[1]
    start_node.status = InstanceNodeStatus.FINISHED
    work_node = node_map[2]
    work_node.arrived_count = 1
    if work_node.arrived_count >= work_node.incoming_count:
        work_node.status = InstanceNodeStatus.RUNNING

    task = Task(id=1, instance_id=1, node_id=work_node.id, assignee_id=2,
               status=TaskStatus.PENDING)
    db.add(task)
    inst.status = InstanceStatus.RUNNING
    await db.flush()

    return inst, work_node, task


# ============================================================
# 完整流程测试
# ============================================================

@pytest.mark.asyncio
class TestSubmitTask:
    """submit_task 真实调用测试"""

    async def test_submit_with_checkers_creates_check_records(self, mysql_session, mocker):
        """有校验人时提交 → 创建 CheckRecord，状态变为 waiting_check"""
        _setup_service_mocks(mocker)
        db = mysql_session
        inst, work_node, task = await _seed_complete_scenario(db, with_checkers=True)

        from app.services.task_service import submit_task
        data = TaskSubmit(assignee_note="已完成设计")

        result = await submit_task(db, task_id=1, current_user_id=2, data=data)

        assert "校验" in result["message"]

        # 验证 DB 状态
        await db.refresh(task)
        assert task.status == TaskStatus.WAITING_CHECK
        assert task.submitted_at is not None

        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.WAITING_CHECK

        # 验证 CheckRecord 已创建
        checks = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == 1)
        )).scalars().all()
        assert len(checks) == 1
        assert checks[0].checker_id == 3
        assert checks[0].status == CheckStatus.PENDING

    async def test_submit_wrong_user_rejected(self, mysql_session, mocker):
        """非负责人提交 → 403"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_complete_scenario(db)

        from app.services.task_service import submit_task
        data = TaskSubmit()

        with pytest.raises(AppException) as exc:
            await submit_task(db, task_id=1, current_user_id=99, data=data)
        assert exc.value.code == ErrorCode.FORBIDDEN

    async def test_submit_already_submitted_rejected(self, mysql_session, mocker):
        """已提交任务再次提交 → 403"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_complete_scenario(db)

        from app.services.task_service import submit_task
        data = TaskSubmit()

        # 第一次提交
        await submit_task(db, task_id=1, current_user_id=2, data=data)
        # 第二次提交应报错
        with pytest.raises(AppException) as exc:
            await submit_task(db, task_id=1, current_user_id=2, data=data)
        assert exc.value.code == ErrorCode.FORBIDDEN

    async def test_submit_with_files_validation(self, mysql_session, mocker):
        """提交时文件校验：require_file=True 但无文件 → 400"""
        _setup_service_mocks(mocker)
        db = mysql_session
        inst, work_node, task = await _seed_complete_scenario(db)

        # 设置节点要求文件
        work_node.require_file = True
        await db.flush()

        from app.services.task_service import submit_task
        data = TaskSubmit()

        # 没有上传文件 → 应报错
        with pytest.raises(AppException) as exc:
            await submit_task(db, task_id=1, current_user_id=2, data=data)
        assert exc.value.code == ErrorCode.BAD_REQUEST


@pytest.mark.asyncio
class TestPassCheck:
    """pass_check 真实调用测试"""

    async def test_pass_check_all_passed_creates_approvals(self, mysql_session, mocker):
        """全部校验通过 → 创建 Approval 记录，状态变为 waiting_approval"""
        _setup_service_mocks(mocker)
        db = mysql_session
        inst, work_node, task = await _seed_complete_scenario(db)

        # 先提交
        from app.services.task_service import submit_task
        await submit_task(db, task_id=1, current_user_id=2, data=TaskSubmit())

        # 获取 CheckRecord
        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == 1)
        )).scalar_one()

        # 校验通过
        from app.services.check_service import pass_check
        result = await pass_check(db, check_id=cr.id, current_user_id=3, opinion="没问题")

        assert "校验通过" in result["message"]

        # 验证状态
        await db.refresh(task)
        assert task.status == TaskStatus.WAITING_APPROVAL

        # 验证 Approval 已创建
        approvals = (await db.execute(
            select(Approval).where(Approval.task_id == 1)
        )).scalars().all()
        assert len(approvals) == 1
        assert approvals[0].approver_id == 4
        assert approvals[0].status == ApprovalStatus.PENDING

    async def test_pass_check_wrong_checker_rejected(self, mysql_session, mocker):
        """非本人校验 → 403"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_complete_scenario(db)

        from app.services.task_service import submit_task
        await submit_task(db, task_id=1, current_user_id=2, data=TaskSubmit())

        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == 1)
        )).scalar_one()

        from app.services.check_service import pass_check
        with pytest.raises(AppException) as exc:
            await pass_check(db, check_id=cr.id, current_user_id=99, opinion="x")
        assert exc.value.code == ErrorCode.FORBIDDEN

    async def test_pass_check_already_passed_rejected(self, mysql_session, mocker):
        """已通过的校验再次操作 → 403"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_complete_scenario(db)

        from app.services.task_service import submit_task
        await submit_task(db, task_id=1, current_user_id=2, data=TaskSubmit())

        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == 1)
        )).scalar_one()

        from app.services.check_service import pass_check
        await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")
        # 再次通过
        with pytest.raises(AppException) as exc:
            await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")
        assert exc.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
class TestApprove:
    """approve 真实调用测试"""

    async def test_approve_node_finished(self, mysql_session, mocker):
        """全部审批通过 → 节点完成"""
        _setup_service_mocks(mocker)
        db = mysql_session
        inst, work_node, task = await _seed_complete_scenario(db)

        # 提交 → 校验通过 → 审批
        from app.services.task_service import submit_task
        await submit_task(db, task_id=1, current_user_id=2, data=TaskSubmit())

        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == 1)
        )).scalar_one()
        from app.services.check_service import pass_check
        await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")

        ap = (await db.execute(
            select(Approval).where(Approval.task_id == 1)
        )).scalar_one()

        from app.services.approval_service import approve
        result = await approve(db, approval_id=ap.id, current_user_id=4, opinion="同意")

        assert result["all_approved"] is True
        assert "通过" in result["message"]

        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.FINISHED

    async def test_approve_wrong_approver_rejected(self, mysql_session, mocker):
        """非本人审批 → 403"""
        _setup_service_mocks(mocker)
        db = mysql_session
        await _seed_complete_scenario(db)

        from app.services.task_service import submit_task
        await submit_task(db, task_id=1, current_user_id=2, data=TaskSubmit())

        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == 1)
        )).scalar_one()
        from app.services.check_service import pass_check
        await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")

        ap = (await db.execute(
            select(Approval).where(Approval.task_id == 1)
        )).scalar_one()

        from app.services.approval_service import approve
        with pytest.raises(AppException) as exc:
            await approve(db, approval_id=ap.id, current_user_id=99, opinion="x")
        assert exc.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
class TestEndorse:
    """endorse 真实调用测试"""

    async def test_endorse_completes_node(self, mysql_session, mocker):
        """批准通过 → 节点完成（difficulty=4 场景）"""
        _setup_service_mocks(mocker)
        db = mysql_session
        inst, work_node, task = await _seed_complete_scenario(db, with_endorser=True)

        # 提交 → 校验 → 审批
        from app.services.task_service import submit_task
        await submit_task(db, task_id=1, current_user_id=2, data=TaskSubmit())

        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == 1)
        )).scalar_one()
        from app.services.check_service import pass_check
        await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")

        ap = (await db.execute(
            select(Approval).where(Approval.task_id == 1)
        )).scalar_one()

        # 模拟 difficulty=4 审批通过后会创建 Endorsement
        from app.services.approval_service import approve
        inst.difficulty = "4"
        await db.flush()

        result = await approve(db, approval_id=ap.id, current_user_id=4, opinion="同意")
        # difficulty=4 + 有 endorser → 强制断言进入批准环节（无条件守卫，防「永远通过」）
        assert result["all_approved"] is True
        # 显式 flush：真实链路由 API 层 commit 落库，此处 flush 后节点状态才可断言
        await db.flush()
        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.WAITING_ENDORSEMENT

        # Endorsement 记录必已创建
        endorsements = (await db.execute(
            select(Endorsement).where(Endorsement.node_id == work_node.id)
        )).scalars().all()
        assert len(endorsements) == 1
        en = endorsements[0]
        assert en.endorser_id == 5
        assert en.status == EndorsementStatus.PENDING

        # 批准通过 → 节点完成
        from app.services.endorsement_service import endorse
        en_result = await endorse(db, endorsement_id=en.id, current_user_id=5,
                                  opinion="批准同意")
        assert "通过" in en_result["message"]
        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.FINISHED
