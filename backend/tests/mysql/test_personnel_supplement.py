"""MySQL 真实换人（change_personnel）与补交（supplement_files）测试

- 换人：真实发起后发起人紧急换负责人/审批人，验证 node/Task 与 Approval 记录更新。
- 补交：真实全流程走完后发起人向已完成节点补交文件（STORAGE_ROOT 指向 tmp_path），
  验证 File 记录 + 操作日志 + 物理文件落盘。
真实 service 驱动，只 mock 外部依赖（通知 / PDF 签名 / 物理文件系统按需）。
"""

import io
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from sqlalchemy import select

from app.models import (
    Organization, User, FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge, Task, CheckRecord, Approval, File,
    OperationLog,
)
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus, ApprovalStatus,
)
from app.api.deps import CurrentUser
from app.schemas.instance import CreateInstanceRequest, ChangePersonnelRequest
from app.schemas.task import TaskSubmit
from app.core.config import settings


# ============================================================
# Mock 工厂 —— mock 通知/签名；物理文件系统按需（补交验证落盘需真实 exists）
# ============================================================

def _setup_mocks(mocker):
    """Mock 通知与 PDF 签名（物理文件系统保持真实，不 mock os.path.exists）"""
    for mod in ["task_service", "check_service", "approval_service", "endorsement_service"]:
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
    """创建组织 + 发起人(1)/负责人(2)/校验人(3)/审批人(4)/新审批人(5)"""
    db.add(Organization(id=1, name="测试所", is_active=True))
    for i, name in [(1, "发起人"), (2, "负责人"), (3, "校验人"), (4, "审批人"), (5, "新审批人")]:
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


async def _run_full_flow_to_completed(db):
    """真实走完全链路（提交→校验→审批→终审）→ 返回工作节点供补交"""
    from app.services.task_service import submit_task
    from app.services.check_service import pass_check
    from app.services.approval_service import approve

    task = (await db.execute(
        select(Task).where(Task.instance_id == 1)
    )).scalars().one()
    work_node = (await db.execute(
        select(InstanceNode).where(InstanceNode.id == task.node_id)
    )).scalar_one()

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
    final_ap = (await db.execute(
        select(Approval).where(
            Approval.node_id == end_node.id, Approval.status == ApprovalStatus.PENDING
        )
    )).scalar_one()
    await approve(db, approval_id=final_ap.id, current_user_id=1, opinion="归档")
    return work_node


def _make_upload(filename="设计说明.pdf", content=b"PDF-COMPLETE-BODY"):
    """构造模拟 UploadFile（PDF，转换状态直接 ready，不入转换队列）"""
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = "application/pdf"
    upload.file = io.BytesIO(content)
    return upload


# ============================================================
# 换人测试
# ============================================================

@pytest.mark.asyncio
class TestChangePersonnel:
    """紧急换人成功路径：负责人 / 审批人"""

    async def test_change_assignee_updates_node_and_task(self, mysql_session, mocker):
        """负责人处理中 → 换负责人 → node.assignee_id + Task.assignee_id 同步更新"""
        _setup_mocks(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)
        await _create_instance(db)

        work_node = (await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == 1,
                InstanceNode.is_start == False, InstanceNode.is_end == False,
            )
        )).scalar_one()
        task = (await db.execute(
            select(Task).where(Task.instance_id == 1)
        )).scalars().one()
        assert work_node.status == InstanceNodeStatus.RUNNING
        assert task.assignee_id == 2

        from app.services.instance.change import change_personnel
        await change_personnel(
            db, instance_id=1, node_id=work_node.id,
            body=ChangePersonnelRequest(assignee_id=3), current_user=_cu(1),
        )

        await db.refresh(work_node)
        await db.refresh(task)
        assert work_node.assignee_id == 3
        assert task.assignee_id == 3

        # 操作日志已记录
        logs = (await db.execute(
            select(OperationLog).where(
                OperationLog.instance_id == 1, OperationLog.operation_type == "personnel_changed"
            )
        )).scalars().all()
        assert len(logs) == 1
        assert "负责人" in logs[0].description

    async def test_change_approver_terminates_old_creates_new(self, mysql_session, mocker):
        """等待审批 → 换审批人 → 旧 Approval 终止 + 新 Approval 创建"""
        _setup_mocks(mocker)
        db = mysql_session
        await _seed_basic_data(db)
        await _seed_template(db)
        await _create_instance(db)

        # 负责人提交 → 校验通过 → 节点进入 waiting_approval + Approval(approver=4)
        from app.services.task_service import submit_task
        from app.services.check_service import pass_check
        task = (await db.execute(
            select(Task).where(Task.instance_id == 1)
        )).scalars().one()
        work_node = (await db.execute(
            select(InstanceNode).where(InstanceNode.id == task.node_id)
        )).scalar_one()
        await submit_task(db, task_id=task.id, current_user_id=2, data=TaskSubmit(assignee_note="完成"))
        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == task.id)
        )).scalar_one()
        await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")
        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.WAITING_APPROVAL

        from app.services.instance.change import change_personnel
        await change_personnel(
            db, instance_id=1, node_id=work_node.id,
            body=ChangePersonnelRequest(approvers=[{"user_id": 5}]), current_user=_cu(1),
        )

        await db.refresh(work_node)
        assert work_node.approvers == [{"user_id": 5}]

        # 旧审批人记录终止、新审批人记录待审
        approvals = (await db.execute(
            select(Approval).where(Approval.node_id == work_node.id)
        )).scalars().all()
        by_user = {a.approver_id: a for a in approvals}
        assert by_user[4].status == ApprovalStatus.TERMINATED
        assert by_user[5].status == ApprovalStatus.PENDING
        assert by_user[5].task_id == task.id


# ============================================================
# 补交测试
# ============================================================

@pytest.mark.asyncio
class TestSupplementFiles:
    """已完成实例的已完成节点补交文件"""

    async def test_supplement_after_completion(self, mysql_session, mocker, tmp_path):
        """流程完成后发起人补交 PDF → File 记录 + 操作日志 + 物理文件落盘"""
        _setup_mocks(mocker)
        db = mysql_session
        # 补交物理写入指向临时目录，测试结束自动清理
        mocker.patch.object(settings, "STORAGE_ROOT", str(tmp_path))

        await _seed_basic_data(db)
        await _seed_template(db)
        await _create_instance(db)
        work_node = await _run_full_flow_to_completed(db)

        inst = (await db.execute(select(FlowInstance).where(FlowInstance.id == 1))).scalar_one()
        assert inst.status == InstanceStatus.COMPLETED

        from app.services.instance.supplement import supplement_files
        result = await supplement_files(
            db, instance_id=1, node_id=work_node.id,
            files=[_make_upload()], current_user=_cu(1),
        )
        assert len(result.files) == 1

        # File 记录创建（补交类型、PDF 直接 ready）
        files = (await db.execute(
            select(File).where(File.instance_id == 1)
        )).scalars().all()
        assert len(files) == 1
        f = files[0]
        assert f.upload_type == "supplement"
        assert f.node_id == work_node.id
        assert f.task_id is None
        assert f.conversion_status == "ready"
        assert f.mime_type == "application/pdf"
        assert f.original_name == "设计说明.pdf"

        # 物理文件已落盘（STORAGE_ROOT = tmp_path，file_path 为相对路径）
        physical = os.path.join(str(tmp_path), f.file_path)
        assert os.path.exists(physical)

        # 操作日志
        logs = (await db.execute(
            select(OperationLog).where(
                OperationLog.instance_id == 1, OperationLog.operation_type == "file_supplement"
            )
        )).scalars().all()
        assert len(logs) == 1
