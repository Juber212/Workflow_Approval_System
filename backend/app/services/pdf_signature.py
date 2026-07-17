"""PDF 签名服务 —— 使用 pypdf 将用户签名图片插入 PDF 指定位置

实现方案：
  1. Pillow 将 PNG 签名图片转为临时 PDF 页（图片=页面尺寸）
  2. pypdf.Transformation 定位签名位置
  3. page.merge_page() 将签名叠加到目标 PDF

依赖：pypdf, Pillow
"""

import os
from io import BytesIO

from pypdf import PdfReader, PdfWriter, Transformation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import SystemConfig, Approval, User, File


# ─── 签名配置默认值 ────────────────────────────────────────────
_SIG_DEFAULTS = {
    "pdf_signature_x": 400,         # 签名起始 X 坐标（距左边）
    "pdf_signature_y": 100,         # 签名 Y 坐标（距底部）
    "pdf_signature_offset": 150,    # 多签名水平偏移量
    "pdf_signature_page": -1,       # 签名页码，-1 = 最后一页
    "pdf_signature_max_width": 150, # 签名图片最大宽度
}


async def _get_signature_configs(db: AsyncSession) -> dict:
    """从 system_configs 表读取签名位置配置，缺失时使用默认值"""
    keys = list(_SIG_DEFAULTS.keys())
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(keys))
    )
    configs = {c.config_key: c.config_value for c in result.scalars().all()}

    parsed = {}
    for key, default in _SIG_DEFAULTS.items():
        val = configs.get(key)
        if val is not None:
            try:
                parsed[key] = int(val)
            except (ValueError, TypeError):
                parsed[key] = default
        else:
            parsed[key] = default
    return parsed


async def apply_signatures_to_node_pdfs(
    db: AsyncSession,
    node_id: int,
) -> int:
    """
    为指定节点的所有 PDF 文件插入审批人签名。

    调用时机：节点全部审批通过后（所有 Approval 均已 approved）

    返回：实际插入签名的文件数
    """

    # 1. 查询该节点所有已通过审批（按审批时间排序，保证签名顺序一致）
    approvals_result = await db.execute(
        select(Approval)
        .where(Approval.node_id == node_id, Approval.status == "approved")
        .order_by(Approval.decided_at.asc())
    )
    approvals = approvals_result.scalars().all()
    if not approvals:
        return 0

    # 2. 获取审批人签名图片（保持审批顺序）
    approver_ids = [a.approver_id for a in approvals]
    users_result = await db.execute(select(User).where(User.id.in_(approver_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    signature_paths: list[str] = []
    for a in approvals:
        user = users_map.get(a.approver_id)
        if user and user.signature_image:
            abs_path = (
                os.path.join(settings.STORAGE_ROOT, user.signature_image)
                if not os.path.isabs(user.signature_image)
                else user.signature_image
            )
            if os.path.exists(abs_path):
                signature_paths.append(abs_path)

    if not signature_paths:
        return 0  # 无有效签名图片，跳过

    # 3. 读取签名位置配置
    cfg = await _get_signature_configs(db)

    # 4. 获取节点 PDF 文件
    files_result = await db.execute(select(File).where(File.node_id == node_id))
    pdf_files = files_result.scalars().all()

    # 5. 逐个 PDF 插入签名
    signed_count = 0
    for file_record in pdf_files:
        abs_path = os.path.join(settings.STORAGE_ROOT, file_record.file_path) if not os.path.isabs(file_record.file_path) else file_record.file_path
        if not os.path.exists(abs_path):
            continue
        if not file_record.mime_type or "pdf" not in file_record.mime_type.lower():
            continue

        try:
            _insert_signatures(
                pdf_path=abs_path,
                signature_paths=signature_paths,
                sig_x=cfg["pdf_signature_x"],
                sig_y=cfg["pdf_signature_y"],
                sig_offset=cfg["pdf_signature_offset"],
                sig_page=cfg["pdf_signature_page"],
                max_width=cfg["pdf_signature_max_width"],
            )
            signed_count += 1
        except Exception:
            # 单文件失败不中断其他文件
            continue

    return signed_count


def _insert_signatures(
    pdf_path: str,
    signature_paths: list[str],
    sig_x: int,
    sig_y: int,
    sig_offset: int,
    sig_page: int,
    max_width: int,
) -> None:
    """
    将多个签名图片插入 PDF 指定位置（同步 I/O）。
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    total_pages = len(reader.pages)

    # 确定目标页码（0-indexed）
    target_page = total_pages - 1 if sig_page < 0 else sig_page
    if target_page < 0 or target_page >= total_pages:
        target_page = total_pages - 1

    # 获取目标页尺寸（用于坐标转换）
    page = reader.pages[target_page]
    page_w = float(page.mediabox.width)
    page_h = float(page.mediabox.height)

    # 复制所有页面
    for p in reader.pages:
        writer.add_page(p)

    # 依次插入每个签名图片
    for idx, sig_path in enumerate(signature_paths):
        if not os.path.exists(sig_path):
            continue

        # 计算该签名的 X 位置
        current_x = sig_x + idx * sig_offset

        # 创建签名叠印页
        stamp_page = _create_signature_stamp(sig_path, max_width)

        if stamp_page is None:
            continue

        # PDF 坐标原点在左下角，将 Y 转换为 PDF 坐标
        stamp_w = float(stamp_page.mediabox.width)
        stamp_h = float(stamp_page.mediabox.height)
        pdf_y = page_h - sig_y - stamp_h

        # 应用位移变换，将签名定位到目标位置
        stamp_page.add_transformation(
            Transformation().translate(tx=current_x, ty=pdf_y)
        )

        # 叠印到目标页
        writer.pages[target_page].merge_page(stamp_page)

    # 先写入临时文件，成功后再原子替换，防止写入失败损坏原 PDF
    tmp_path = pdf_path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            writer.write(f)
        os.replace(tmp_path, pdf_path)  # 原子替换（跨平台）
    except Exception:
        # 清理残留临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _create_signature_stamp(sig_path: str, max_width: int = 150):
    """
    将 PNG 签名图片转为 pypdf 可用的叠印页。

    流程：PNG → Pillow 缩放 → 保存为 PDF → pypdf 读取为 stamp page
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        img = Image.open(sig_path)

        # 转为 RGB（去除 alpha 通道，pypdf merge 时不需透明）
        if img.mode in ("RGBA", "LA", "P"):
            # 创建白色背景，将 RGBA 合成到白底上
            if img.mode == "RGBA":
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # alpha 通道作为 mask
                img = background
            elif img.mode == "P":
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            else:
                img = img.convert("RGB")

        # 缩放到最大宽度（保持宽高比）
        w, h = img.size
        if w > max_width:
            ratio = max_width / w
            w = int(w * ratio)
            h = int(h * ratio)
            img = img.resize((w, h), Image.LANCZOS)

        # 保存为 PDF 字节流
        pdf_bytes = BytesIO()
        img.save(pdf_bytes, format="PDF")
        pdf_bytes.seek(0)

        # 用 pypdf 读取为叠印页
        stamp_reader = PdfReader(pdf_bytes)
        return stamp_reader.pages[0]

    except Exception:
        return None
