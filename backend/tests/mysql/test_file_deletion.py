"""MySQL 真实物理文件删除测试 —— terminate 与终审 reject

与 mock 测试不同：本文件用 tmp_path 创建真实物理文件 + File 记录，
真实调用 terminate_instance / reject，验证「DB 记录 + 物理文件」都被删除。
关键：不 mock os.path.exists，保留 batch_delete_files_with_physical 的真实删除行为。
"""

import pytest
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.models import (
    Organization, User, FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge, Task, CheckRecord, Approval, File,
)
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus, ApprovalStatus,
)
from app.api.deps import CurrentUser
from app.schemas.instance import CreateInstanceRequest
from app.schemas.task import TaskSubmit


# ============================================================
# Mock 工厂 —— 只 mock 通知/签名，保留 os.path.exists（物理删除需真实）
# ============================================================

def _mock_external(mocker):
    """Mock 通知与 PDF 签名，但保留 os.path.exists / 文件删除的真实行为"""
    for mod in ["task_service", "check_service", "approval_service",
                "endorsement_service", "instance.terminate"]:
        for fn in ["create_notification", "clear_related"]:
            mocker.patch(f"app.services.{mod}.{fn}", AsyncMock())
    for mod in ["approval_service", "endorsement_service"]:
        mocker.patch(f"app.services.{mod}.clear_related_for_users", AsyncMock())
    mocker.patch("app.engine.flow_engine.create_notification", AsyncMock())
    mocker.patch("app.services.pdf_signature.apply_signatures_to_files", AsyncMock())
    mocker.patch("app.services.pdf_signature.get_role_signature_defaults", return_value={})


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


async def _seed_template(db):
    """创建简单三节点模板：开始 → 设计 → 终审"""
    db.add(FlowTemplate(id=1, name="测试流程模板", type="project",
                        organization_id=1, description="测试用", created_by=1))
    nodes = [
        TemplateNode(id=101, template_id=1, name="发起", is_start=True, is_end=False, sort_order=1),
        TemplateNode(id=102, template_id=1, name="设计", is_start=False, is_end=False, sort_order=2,
                    assignee_id=2, checkers=[{"user_id": 3, "name": "校验人"}],
                    approvers=[{"user_id": 4, "name": "审批人"}], time_limit_days=5),
        TemplateNode(id=103, template_id=1, name="终审", is_start=False, is_end=True, sort_order=3,
                    approvers=[{"user_id": 1, "name": "发起人"}]),
    ]
    for n in nodes:
        db.add(n)
    await db.flush()  # 节点先落库，edges 的 FK 引用才能通过

    for e in [
        TemplateEdge(id=201, template_id=1, source_node_id=101, target_node_id=102),
        TemplateEdge(id=202, template_id=1, source_node_id=102, target_node_id=103),
    ]:
        db.add(e)
    await db.flush()


async def _create_instance(db, name="测试项目"):
    """真实调用 create_instance 发起"""
    from app.services.instance.create import create_instance
    request = CreateInstanceRequest(template_id=1, name=name, priority="normal", difficulty="1")
    return await create_instance(db, request=request, current_user=_cu(1, "initiator"))


async def _get_work_node(db):
    """查询实例的工作节点"""
    return (await db.execute(
        select(InstanceNode).where(
            InstanceNode.instance_id == 1,
            InstanceNode.is_start == False,
            InstanceNode.is_end == False,
        )
    )).scalar_one()


def _make_real_file(tmp_path, filename="设计.pdf", content=b"PDF-CONTENT"):
    """在 tmp_path 创建真实物理文件，返回 (path, content)"""
    path = tmp_path / filename
    path.write_bytes(content)
    return path


# ============================================================
# 测试
# ============================================================

@pytest.mark.asyncio
class TestTerminateFileDeletion:
    """终止流程 → 实例文件（DB 记录 + 物理文件）全部删除"""

    async def test_terminate_deletes_files(self, mysql_session, mocker, tmp_path):
        """真实终止 → File 记录清空 + 物理文件不存在"""
        _mock_external(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)
        await _create_instance(db)

        work_node = await _get_work_node(db)
        pdf = _make_real_file(tmp_path)
        db.add(File(
            instance_id=1, node_id=work_node.id, round=1, uploader_id=2,
            upload_type="normal", original_name="设计.pdf", stored_name="design.pdf",
            file_path=str(pdf), file_size=pdf.stat().st_size, mime_type="application/pdf",
        ))
        await db.flush()
        assert pdf.exists()  # 物理文件已就位

        from app.services.instance.terminate import terminate_instance
        await terminate_instance(db, instance_id=1, reason="测试终止", current_user=_cu(1))

        # DB 记录删除
        files = (await db.execute(
            select(File).where(File.instance_id == 1)
        )).scalars().all()
        assert files == []

        # 物理文件删除
        assert not pdf.exists()

        inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == 1))).scalar_one()
        assert inst.status == InstanceStatus.TERMINATED


@pytest.mark.asyncio
class TestFinalRejectFileDeletion:
    """终审总驳回 → 目标节点及其下游文件（DB 记录 + 物理文件）删除"""

    async def test_final_reject_deletes_target_files(self, mysql_session, mocker, tmp_path):
        """真实终审驳回 → 目标节点文件删除 + 节点回滚重跑"""
        _mock_external(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)
        await _create_instance(db)

        task = (await db.execute(
            select(Task).where(Task.instance_id == 1)
        )).scalars().one()
        work_node = await _get_work_node(db)

        # ── 工作节点走完：提交 → 校验 → 审批 → 传播到终审 ──
        from app.services.task_service import submit_task
        from app.services.check_service import pass_check
        from app.services.approval_service import approve
        await submit_task(db, task_id=task.id, current_user_id=2, data=TaskSubmit(assignee_note="完成"))
        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == task.id)
        )).scalar_one()
        await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")
        ap = (await db.execute(
            select(Approval).where(Approval.task_id == task.id)
        )).scalar_one()
        await approve(db, approval_id=ap.id, current_user_id=4, opinion="同意")

        end_node = (await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == 1, InstanceNode.is_end == True
            )
        )).scalar_one()
        assert end_node.status == InstanceNodeStatus.WAITING_APPROVAL

        # 目标节点（工作节点）添加真实物理文件
        pdf = _make_real_file(tmp_path)
        db.add(File(
            instance_id=1, node_id=work_node.id, round=1, uploader_id=2,
            upload_type="normal", original_name="设计.pdf", stored_name="design.pdf",
            file_path=str(pdf), file_size=pdf.stat().st_size, mime_type="application/pdf",
        ))
        await db.flush()
        assert pdf.exists()

        # ── 终审总驳回 → 目标节点 ──
        final_ap = (await db.execute(
            select(Approval).where(
                Approval.node_id == end_node.id, Approval.status == ApprovalStatus.PENDING
            )
        )).scalar_one()
        from app.services.approval_service import reject
        result = await reject(db, approval_id=final_ap.id, current_user_id=1,
                              opinion="驳回重做", target_node_id=work_node.id)
        assert "驳回至" in result["message"] and "设计" in result["message"]

        # 目标节点 DB 记录删除 + 物理文件删除
        files = (await db.execute(
            select(File).where(File.node_id == work_node.id)
        )).scalars().all()
        assert files == []
        assert not pdf.exists()

        # 目标节点回滚：round+1、running、生成新 Task 待重做
        # （旧 Task 保留为 completed 历史，断言存在一条新的 pending 活跃 Task）
        await db.refresh(work_node)
        assert work_node.round == 2
        assert work_node.status == InstanceNodeStatus.RUNNING
        pending_tasks = (await db.execute(
            select(Task).where(
                Task.node_id == work_node.id, Task.status == TaskStatus.PENDING
            )
        )).scalars().all()
        assert len(pending_tasks) == 1
