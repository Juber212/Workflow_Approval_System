"""MySQL 真实 pypdf 签名全链路测试

本测试不 mock 两个核心路径：
- `propagate_from_node`：真实发起 + 真实传播（首个 Task 由系统生成）
- `apply_signatures_to_files`：真实 pypdf 底层把签名 PNG 插入 PDF

用 Pillow 生成透明签名 PNG + pypdf 生成真实 PDF，审批通过后触发签名，
验证 Signature.applied 置位 + PDF 文件字节真实变化（页数保持不变）。
只 mock 通知（与其余真实流转测试一致）。
"""

import pytest
from unittest.mock import AsyncMock

from sqlalchemy import select
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageDraw

from app.models import (
    Organization, User, FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge, Task, CheckRecord, Approval, File,
    Signature,
)
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus, ApprovalStatus,
)
from app.api.deps import CurrentUser
from app.schemas.instance import CreateInstanceRequest
from app.schemas.task import TaskSubmit


# ============================================================
# Mock 工厂 —— 只 mock 通知；签名/传播/物理文件全部真实
# ============================================================

def _mock_notifications_only(mocker):
    """仅 mock 通知，保留 propagate_from_node / apply_signatures_to_files / os.path.exists 真实"""
    for mod in ["task_service", "check_service", "approval_service", "endorsement_service"]:
        for fn in ["create_notification", "clear_related"]:
            mocker.patch(f"app.services.{mod}.{fn}", AsyncMock())
    for mod in ["approval_service", "endorsement_service"]:
        mocker.patch(f"app.services.{mod}.clear_related_for_users", AsyncMock())
    mocker.patch("app.engine.flow_engine.create_notification", AsyncMock())


# ============================================================
# 辅助函数
# ============================================================

def _cu(uid, username="u", org_id=1, role="manager"):
    """快速构造 CurrentUser"""
    return CurrentUser({"sub": str(uid), "username": username,
                        "roles": [role], "org_id": org_id})


def _make_png(path, size=(200, 60)):
    """生成 RGBA 透明底签名 PNG（Pillow）"""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 画一个蓝色矩形模拟手写签名区域（带透明通道）
    draw.rectangle([10, 10, 190, 50], fill=(30, 80, 200, 255))
    img.save(path, "PNG")


def _make_pdf(path):
    """用 pypdf 生成 1 页 A4 空白 PDF"""
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)


async def _seed_basic_data(db, approver_sig_path: str | None = None):
    """创建组织 + 发起人(1)/负责人(2)/校验人(3)/审批人(4，带签名图片)"""
    db.add(Organization(id=1, name="测试所", is_active=True))
    for i, name in [(1, "发起人"), (2, "负责人"), (3, "校验人"), (4, "审批人")]:
        db.add(User(id=i, username=f"u{i}", real_name=name, password_hash="x",
                    organization_id=1, is_active=True,
                    signature_image=approver_sig_path if i == 4 else None))
    await db.flush()


async def _seed_template(db):
    """创建模板：开始 → 设计（需审批签名）→ 终审"""
    db.add(FlowTemplate(id=1, name="签名模板", type="project",
                        organization_id=1, description="签名测试", created_by=1))
    nodes = [
        TemplateNode(id=101, template_id=1, name="发起", is_start=True, is_end=False, sort_order=1),
        TemplateNode(id=102, template_id=1, name="设计", is_start=False, is_end=False, sort_order=2,
                    assignee_id=2, checkers=[{"user_id": 3, "name": "校验人"}],
                    approvers=[{"user_id": 4, "name": "审批人"}],
                    require_approver_signature=True, signature_x=400, signature_y=100,
                    signature_page=-1, time_limit_days=5),
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


async def _create_instance(db, name="签名项目"):
    """真实调用 create_instance 发起（真实 propagate 生成首个 Task）"""
    from app.services.instance.create import create_instance
    request = CreateInstanceRequest(template_id=1, name=name, priority="normal", difficulty="1")
    return await create_instance(db, request=request, current_user=_cu(1, "initiator"))


# ============================================================
# 测试
# ============================================================

@pytest.mark.asyncio
class TestRealSignature:
    """真实 pypdf 签名全链路：审批通过 → 签名真实插入 PDF"""

    async def test_approval_applies_real_signature_to_pdf(self, mysql_session, mocker, tmp_path):
        """真实签名 PNG 插入真实 PDF，Signature.applied 置位、PDF 字节变化"""
        _mock_notifications_only(mocker)
        db = mysql_session

        # ── 准备真实素材：签名 PNG + 待签 PDF ──
        sig_png = tmp_path / "signature.png"
        _make_png(sig_png)
        design_pdf = tmp_path / "design.pdf"
        _make_pdf(design_pdf)

        await _seed_basic_data(db, approver_sig_path=str(sig_png))
        await _seed_template(db)
        await _create_instance(db)

        work_node = (await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == 1,
                InstanceNode.is_start == False, InstanceNode.is_end == False,
            )
        )).scalar_one()

        # 节点已有真实 PDF 文件（File 记录指向真实文件）
        db.add(File(
            instance_id=1, node_id=work_node.id, round=1, uploader_id=2,
            upload_type="normal", original_name="design.pdf", stored_name="design.pdf",
            file_path=str(design_pdf), file_size=design_pdf.stat().st_size,
            mime_type="application/pdf", conversion_status="ready",
        ))
        await db.flush()
        file_record = (await db.execute(
            select(File).where(File.instance_id == 1)
        )).scalars().one()

        before = design_pdf.read_bytes()

        # ── 负责人提交 → 校验通过 → 审批通过（携带签名位置）──
        from app.services.task_service import submit_task
        from app.services.check_service import pass_check
        from app.services.approval_service import approve
        task = (await db.execute(
            select(Task).where(Task.instance_id == 1)
        )).scalars().one()
        await submit_task(db, task_id=task.id, current_user_id=2, data=TaskSubmit(assignee_note="完成"))
        cr = (await db.execute(
            select(CheckRecord).where(CheckRecord.task_id == task.id)
        )).scalar_one()
        await pass_check(db, check_id=cr.id, current_user_id=3, opinion="通过")
        ap = (await db.execute(
            select(Approval).where(Approval.task_id == task.id)
        )).scalar_one()

        result = await approve(
            db, approval_id=ap.id, current_user_id=4, opinion="同意",
            signatures=[{"file_id": file_record.id, "signature_x": 400, "signature_y": 100}],
        )
        assert result["all_approved"] is True

        # approve 返回待写入的签名 ID（approval_service 返回键为 _pending_sig_ids）
        pending_ids = result["_pending_sig_ids"]
        assert len(pending_ids) == 1

        # ── 真实签名写入 PDF（模拟 API 层 post-commit hook）──
        from app.services.pdf_signature import apply_signatures_to_files
        signed_count = await apply_signatures_to_files(db, pending_ids)
        assert signed_count == 1

        # PDF 被真实修改（字节变化），页数保持不变
        after = design_pdf.read_bytes()
        assert after != before
        assert len(PdfReader(str(design_pdf)).pages) == 1

        # Signature 记录已标记 applied，且角色为审批人
        sigs = (await db.execute(
            select(Signature).where(Signature.id.in_(pending_ids))
        )).scalars().all()
        assert len(sigs) == 1
        assert sigs[0].applied is True
        assert sigs[0].role_type == "approver"
        assert sigs[0].file_id == file_record.id

        # 工作节点完成、流程推进（真实 propagate 传播到终审）
        await db.refresh(work_node)
        assert work_node.status == InstanceNodeStatus.FINISHED
        end_node = (await db.execute(
            select(InstanceNode).where(
                InstanceNode.instance_id == 1, InstanceNode.is_end == True
            )
        )).scalar_one()
        assert end_node.status == InstanceNodeStatus.WAITING_APPROVAL
