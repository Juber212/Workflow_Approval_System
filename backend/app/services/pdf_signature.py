"""PDF 签名服务 —— 使用 pypdf 将用户签名图片插入 PDF 指定位置

实现方案：
  1. 签名上传时保留 RGBA 透明通道
  2. _create_signature_stamp：用 pypdf 原生 Image XObject + SMask（Alpha 通道）创建 stamp 页
  3. Transformation.scale().translate() 定位签名位置
  4. merge_transformed_page() 将签名叠加到目标 PDF

透明实现：
  - RGBA 图片拆分为 RGB 像素数据 + Alpha 像素数据
  - RGB → /DeviceRGB Image XObject（FlateDecode）
  - Alpha → /DeviceGray Image XObject 作为 /SMask
  - PDF 渲染器自动处理透明合成

依赖：pypdf, Pillow
"""

import asyncio
import logging
import os
import weakref
import uuid
import zlib
from io import BytesIO

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import (
    NameObject,
    DictionaryObject,
    ArrayObject,
    NumberObject,
    DecodedStreamObject,
    FloatObject,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.models import SystemConfig, User, File, Signature

logger = logging.getLogger(__name__)


# ─── M25：同一 PDF 并发签名写入串行化 ──────────────────────────────
# 多审批人几乎同时审批同一文件时，各走各的 apply_signatures_after_commit，
# 若并发写同一 PDF 的临时文件会互相覆盖导致丢签名。按文件路径持进程内锁串行化。
# 低危项：改用弱引用字典——协程 async with 持锁期间强引用存活、并发协程命中同一锁；
# 全部释放后无强引用自动回收，防归档文件增长时锁对象无限累积。
_pdf_locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()


def _get_pdf_lock(pdf_path: str) -> asyncio.Lock:
    """按 PDF 绝对路径获取进程内锁（asyncio 单事件循环，无 await 原子）

    弱引用字典必须持强引用：先 get 到局部变量再赋值——若直接
    `_pdf_locks[pdf_path] = asyncio.Lock()`，锁对象仅存弱引用、临时对象
    引用计数归零立即回收 → 下一行按 key 取值抛 KeyError（WeakValueDictionary 陷阱）。
    """
    lock = _pdf_locks.get(pdf_path)
    if lock is None:
        lock = asyncio.Lock()
        _pdf_locks[pdf_path] = lock
    return lock


# ─── 签名配置默认值 ────────────────────────────────────────────
_SIG_KEYS = [
    "pdf_signature_x", "pdf_signature_y", "pdf_signature_offset",
    "pdf_signature_page", "pdf_signature_max_width", "pdf_signature_max_height",
    # 角色维度签名默认（X/Y，不含 pages——pages 由 PDF 总页数自动决定）
    "pdf_signature_assignee_x", "pdf_signature_assignee_y",
    "pdf_signature_checker_x", "pdf_signature_checker_y",
    "pdf_signature_approver_x", "pdf_signature_approver_y",
    "pdf_signature_endorser_x", "pdf_signature_endorser_y",
]


def _get_sig_default(key: str) -> int | str:
    """从 settings 获取签名的默认值（pages 类 key 返回字符串）"""
    mapping = {
        "pdf_signature_x": settings.PDF_SIGNATURE_X,
        "pdf_signature_y": settings.PDF_SIGNATURE_Y,
        "pdf_signature_offset": settings.PDF_SIGNATURE_OFFSET,
        "pdf_signature_page": settings.PDF_SIGNATURE_PAGE,
        "pdf_signature_max_width": settings.PDF_SIGNATURE_MAX_WIDTH,
        "pdf_signature_max_height": settings.PDF_SIGNATURE_MAX_HEIGHT,
        # 角色维度签名默认值（X/Y 坐标）
        "pdf_signature_assignee_x": settings.PDF_SIGNATURE_ASSIGNEE_X,
        "pdf_signature_assignee_y": settings.PDF_SIGNATURE_ASSIGNEE_Y,
        "pdf_signature_checker_x": settings.PDF_SIGNATURE_CHECKER_X,
        "pdf_signature_checker_y": settings.PDF_SIGNATURE_CHECKER_Y,
        "pdf_signature_approver_x": settings.PDF_SIGNATURE_APPROVER_X,
        "pdf_signature_approver_y": settings.PDF_SIGNATURE_APPROVER_Y,
        "pdf_signature_endorser_x": settings.PDF_SIGNATURE_ENDORSER_X,
        "pdf_signature_endorser_y": settings.PDF_SIGNATURE_ENDORSER_Y,
    }
    return mapping.get(key, 0)


async def _get_signature_configs(db: AsyncSession) -> dict:
    """从 system_configs 表读取签名位置配置，缺失时使用 settings 默认值"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(_SIG_KEYS))
    )
    configs = {c.config_key: c.config_value for c in result.scalars().all()}

    parsed = {}
    for key in _SIG_KEYS:
        default = _get_sig_default(key)
        val = configs.get(key)
        if val is not None:
            try:
                parsed[key] = int(val)
            except (ValueError, TypeError):
                parsed[key] = default
        else:
            parsed[key] = default
    return parsed


async def get_role_signature_defaults(db: AsyncSession, role: str) -> dict:
    """返回指定角色的默认签名坐标 {x, y}

    从 SystemConfig 读取角色维度的签名默认值（X/Y），
    缺失时回退到 settings 默认值（400/100）。

    role 参数: "assignee" | "checker" | "approver" | "endorser"
    """
    cfg = await _get_signature_configs(db)
    prefix = f"pdf_signature_{role}_"
    return {
        "x": cfg.get(f"{prefix}x", 400),
        "y": cfg.get(f"{prefix}y", 100),
    }


async def create_signature_records(
    db: AsyncSession,
    *,
    role_type: str,
    source_id: int,
    node_id: int,
    signatures: list[dict],
    default_signature_x: int = 400,
    default_signature_y: int = 100,
    default_signature_page: int = -1,
    default_date_font_size: int = 14,
) -> list[int]:
    """统一创建签名记录 —— 消除 approval/check/endorse/task 4 个 Service 中的重复代码

    Args:
        db: 数据库会话
        role_type: 签名角色 "assignee" / "checker" / "approver" / "endorser"
        source_id: 关联记录 ID（approval_id / check_id / endorsement_id / task_id）
        node_id: 节点 ID
        signatures: 签名数据列表 [{file_id, signature_x?, signature_y?, ...}]
        default_signature_x/y/page: 未指定时的默认值
        default_date_font_size: 默认日期字体大小

    Returns:
        新创建的签名记录 ID 列表
    """
    from app.models import Signature

    # ===== P0-3 修复：签名 file_id 归属校验 =====
    # file_id 来自前端，若不校验归属，攻击者可枚举 file_id 把自己的签名盖到他人 PDF 上。
    # 统一校验：file_id 对应的文件必须属于当前节点（node_id），否则拒绝。
    real_file_ids = [sig.get("file_id") for sig in signatures if sig.get("file_id") is not None]
    if real_file_ids:
        node_files = (await db.execute(
            select(File).where(File.id.in_(real_file_ids), File.node_id == node_id)
        )).scalars().all()
        valid_ids = {f.id for f in node_files}
        for sig in signatures:
            fid = sig.get("file_id")
            if fid is not None and fid not in valid_ids:
                raise AppException(
                    ErrorCode.BAD_REQUEST,
                    f"签名文件不存在或不属于当前节点（file_id={fid}）",
                )

    sig_records: list[Signature] = []  # 先保存对象引用，等 flush 后再取 ID
    for idx, sig in enumerate(signatures):
        sig_record = Signature(
            file_id=sig["file_id"],
            signer_id=sig.get("signer_id", 0),  # 调用方应传入
            role_type=role_type,
            source_id=source_id,
            node_id=node_id,
            signature_x=sig.get("signature_x", default_signature_x),
            signature_y=sig.get("signature_y", default_signature_y),
            signature_page=sig.get("signature_page", default_signature_page),
            signature_width=sig.get("signature_width"),
            signature_height=sig.get("signature_height"),
            sign_date=sig.get("sign_date"),
            show_date=sig.get("show_date", True),
            date_x=sig.get("date_x"),
            date_y=sig.get("date_y"),
            date_font_size=sig.get("date_font_size", default_date_font_size),
            applied=False,
            sort_order=idx,
        )
        db.add(sig_record)
        sig_records.append(sig_record)
    await db.flush()  # 批量 flush，减少 DB 往返
    # flush 后 SQLAlchemy 自动回填自增 ID，此时取 ID 才是有效值
    return [r.id for r in sig_records]


async def apply_signatures_to_files(
    db: AsyncSession,
    signature_ids: list[int],
) -> int:
    """
    按签名记录 ID 列表，将签名写入对应 PDF 文件。

    用于负责人即时签名和校验/审批批量签名两种场景。
    签名位置直接从 Signature 记录读取。

    返回：实际写入签名的文件数
    """
    if not signature_ids:
        return 0

    # 1. 查询签名记录
    sigs_result = await db.execute(
        select(Signature).where(Signature.id.in_(signature_ids))
    )
    sigs = sigs_result.scalars().all()
    if not sigs:
        return 0

    # 2. 按 file_id 分组签名（一个文件可能有多处签名）
    file_sigs: dict[int, list[Signature]] = {}
    signer_ids = set()
    for s in sigs:
        file_sigs.setdefault(s.file_id, []).append(s)
        signer_ids.add(s.signer_id)

    # 3. 获取签名人信息（签名图片路径）
    users_result = await db.execute(select(User).where(User.id.in_(signer_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    # 4. 获取全局配置
    cfg = await _get_signature_configs(db)

    # 5. 逐个文件处理
    file_ids = list(file_sigs.keys())
    files_result = await db.execute(select(File).where(File.id.in_(file_ids)))
    files_map = {f.id: f for f in files_result.scalars().all()}

    signed_count = 0
    for file_id, sig_list in file_sigs.items():
        file_record = files_map.get(file_id)
        if not file_record:
            continue

        abs_path = os.path.join(settings.STORAGE_ROOT, file_record.file_path) if not os.path.isabs(file_record.file_path) else file_record.file_path
        if not os.path.exists(abs_path):
            continue

        # PDF 判断：mime_type + 后缀名双重检查
        is_pdf = False
        if file_record.mime_type and "pdf" in file_record.mime_type.lower():
            is_pdf = True
        elif file_record.file_path and file_record.file_path.lower().endswith('.pdf'):
            is_pdf = True
        if not is_pdf:
            continue

        # 收集该文件的所有签名路径和位置
        sig_paths: list[str] = []
        sig_positions: list[dict] = []
        for s in sorted(sig_list, key=lambda x: x.sort_order or 0):
            user = users_map.get(s.signer_id)
            if not user or not user.signature_image:
                continue
            sig_path = user.signature_image
            abs_sig = sig_path if os.path.isabs(sig_path) else os.path.join(settings.STORAGE_ROOT, sig_path)
            if sig_path.startswith(settings.STORAGE_ROOT + os.sep) or sig_path.startswith(settings.STORAGE_ROOT + "/"):
                abs_sig = sig_path
            if not os.path.exists(abs_sig):
                continue
            sig_paths.append(abs_sig)
            sig_positions.append({
                "x": s.signature_x if s.signature_x is not None else cfg["pdf_signature_x"],
                "y": s.signature_y if s.signature_y is not None else cfg["pdf_signature_y"],
                "page": s.signature_page if s.signature_page is not None else cfg["pdf_signature_page"],
                "width": s.signature_width,   # NULL → 使用全局兜底
                "height": s.signature_height,
                # 签批日期
                # sign_date 可能是 date 对象或 ISO 字符串
                "sign_date": s.sign_date.isoformat() if hasattr(s.sign_date, 'isoformat') else (str(s.sign_date) if s.sign_date else None),
                "show_date": s.show_date if s.show_date is not None else True,
                "date_x": s.date_x,
                "date_y": s.date_y,
                "date_font_size": s.date_font_size if s.date_font_size else 12,
            })

        if not sig_paths:
            continue

        try:
            # M25：同一 PDF 并发签名写入用进程内锁串行化，防临时文件碰撞/丢签名
            async with _get_pdf_lock(abs_path):
                await asyncio.to_thread(
                    _insert_signatures,
                    pdf_path=abs_path,
                    signature_paths=sig_paths,
                    signature_positions=sig_positions,
                    max_width=cfg["pdf_signature_max_width"],
                    max_height=cfg["pdf_signature_max_height"],
                )
            signed_count += 1

            # 标记这些签名为已应用
            sig_ids = [s.id for s in sig_list]
            await db.execute(
                update(Signature)
                .where(Signature.id.in_(sig_ids))
                .values(applied=True)
            )
        except Exception as e:
            # 安全网：DB 更新失败不中断其他文件的签名标记
            logger.warning(f"[签名] 文件 {file_id} 签名写入失败: {e}", exc_info=True)
            continue

    return signed_count


async def apply_signatures_after_commit(signature_ids: list[int]) -> None:
    """事务提交后异步写入签名到 PDF（独立会话，失败不影响已提交的审批）

    解决 PDF 文件修改在 DB 事务内执行的问题：
    - 若 commit 失败 → 磁盘 PDF 不会残留半截修改
    - 若 commit 成功但 PDF 写入失败 → Signature.applied 保持 False，可重试
    """
    if not signature_ids:
        return
    from app.core.database import async_session_factory
    import logging
    logger = logging.getLogger(__name__)
    try:
        async with async_session_factory() as db:
            await apply_signatures_to_files(db, signature_ids)
            await db.commit()
    except Exception as e:
        logger.error("[签名] post-commit 签名写入失败（重试即可）: %s", e, exc_info=True)


# ─── 中文日期字体查找 ────────────────────────────────────────────

def _get_cjk_font_path() -> str | None:
    """查找系统可用的中文字体路径（Windows / macOS / Linux）"""
    candidates = [
        # Windows
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _create_date_text_stamp(date_text: str, font_size: int = 12):
    """将日期文本渲染为透明底 PNG 图片的 PDF 叠印页

    使用 3 倍超采样渲染，PDF 上缩放后保持清晰锐利。

    返回：(stamp_page, img_w, img_h) 或 (None, 0, 0)
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # 3 倍超采样渲染，避免 PDF 缩放后文字模糊
        render_size = font_size * 3

        font_path = _get_cjk_font_path()
        if font_path:
            font = ImageFont.truetype(font_path, render_size)
        else:
            font = ImageFont.load_default()

        # 测量文本尺寸（用 getbbox 获取精确边界）
        temp_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), date_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if tw <= 0 or th <= 0:
            return None, 0, 0

        # 创建透明底图片并绘制文字（无额外边距，与前端预览对齐）
        img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), date_text, fill=(0, 0, 0, 255), font=font)

        w, h = img.size

        # 创建 PDF stamp 页（与签名图用同一技术路径）
        stamp_writer = PdfWriter()
        stamp_writer.add_blank_page(width=float(w), height=float(h))
        stamp_page = stamp_writer.pages[0]

        # 分离 RGB / Alpha
        alpha = img.split()[3] if img.mode == "RGBA" else None
        rgb_img = img.convert("RGB")
        rgb_raw = rgb_img.tobytes("raw", "RGB")
        rgb_compressed = zlib.compress(rgb_raw, 9)

        # Alpha SMask
        smask_ref = None
        if alpha is not None:
            alpha_raw = alpha.tobytes("raw", "L")
            alpha_compressed = zlib.compress(alpha_raw, 9)
            smask_stream = DecodedStreamObject()
            smask_stream.set_data(alpha_compressed)
            smask_stream.update(DictionaryObject({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(w),
                NameObject("/Height"): NumberObject(h),
                NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                NameObject("/BitsPerComponent"): NumberObject(8),
                NameObject("/Filter"): NameObject("/FlateDecode"),
            }))
            smask_ref = stamp_writer._add_object(smask_stream)

        # RGB Image XObject
        img_dict = DictionaryObject({
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(w),
            NameObject("/Height"): NumberObject(h),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/Filter"): NameObject("/FlateDecode"),
        })
        if smask_ref is not None:
            img_dict[NameObject("/SMask")] = smask_ref

        img_stream = DecodedStreamObject()
        img_stream.set_data(rgb_compressed)
        img_stream.update(img_dict)
        img_ref = stamp_writer._add_object(img_stream)

        # Resources
        resources_dict = DictionaryObject()
        xobj_dict = DictionaryObject()
        xobj_dict[NameObject("/Im0")] = img_ref
        resources_dict[NameObject("/XObject")] = xobj_dict
        stamp_page[NameObject("/Resources")] = resources_dict

        # 内容流
        content_bytes = "q {:.5f} 0 0 {:.5f} 0 0 cm /Im0 Do Q".format(
            float(w), float(h)
        ).encode("ascii")
        content_obj = DecodedStreamObject()
        content_obj.set_data(content_bytes)
        stamp_page[NameObject("/Contents")] = content_obj
        stamp_page.compress_content_streams()

        # 序列化后重新读取
        out = BytesIO()
        stamp_writer.write(out)
        out.seek(0)
        reader = PdfReader(out)
        stamp_page = reader.pages[0]

        return stamp_page, w, h

    except (OSError, ValueError):
        return None, 0, 0


# ─── PDF 签名插入主函数 ──────────────────────────────────────────

def _insert_signatures(
    pdf_path: str,
    signature_paths: list[str],
    signature_positions: list[dict],
    max_width: int,
    max_height: int = 26,
) -> None:
    """
    将多个签名图片插入 PDF 指定位置（同步 I/O）。

    signature_positions: [{"x": float, "y": float, "page": int, "width": float|None, "height": float|None}, ...]
    与 signature_paths 一一对应，每个签名独立指定位置、页码和尺寸。
    width/height 为 None 时使用 max_width/max_height 兜底。
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    total_pages = len(reader.pages)

    # 复制所有页面
    page_heights: list[float] = []
    for p in reader.pages:
        writer.add_page(p)
        page_heights.append(float(p.mediabox.height))

    # 依次插入每个签名图片（每个签名可使用不同页码和尺寸）
    for idx, sig_path in enumerate(signature_paths):
        if not os.path.exists(sig_path):
            continue

        pos = signature_positions[idx] if idx < len(signature_positions) else {"x": 400, "y": 100, "page": -1}
        sig_x = pos.get("x", 400)
        sig_y = pos.get("y", 100)
        sig_page = int(pos.get("page", -1))
        # 使用签名独立宽高，否则用全局配置兜底
        sig_w = pos.get("width") or max_width
        sig_h = pos.get("height") or max_height

        # 确定目标页码（前端 1-based → pypdf 0-based）
        target_page = total_pages - 1 if sig_page < 0 else sig_page - 1
        if target_page < 0 or target_page >= total_pages:
            target_page = total_pages - 1

        page_h = page_heights[target_page]

        # 创建签名叠印页（不缩图，返回原始尺寸供 scale 计算）
        result = _create_signature_stamp(sig_path, sig_w, sig_h)
        if isinstance(result, tuple):
            stamp_page, img_w, img_h = result
        else:
            stamp_page = result
        if stamp_page is None or img_w == 0:
            continue

        # 计算缩放比例：使用签名独立宽度（width）和高度
        scale = min(sig_w / img_w, sig_h / img_h, 1.0)

        # 计算实际渲染尺寸
        actual_w = img_w * scale
        actual_h = img_h * scale

        # 居中偏移（匹配前端 object-fit: contain 的居中行为）
        center_x = (sig_w - actual_w) / 2
        center_y = (sig_h - actual_h) / 2

        # 前端使用 CSS top 坐标系（距页面顶部），这里转换为 PDF 底部坐标系
        stamp_h = float(stamp_page.mediabox.height)
        pdf_y = page_h - sig_y - (stamp_h * scale) - center_y

        # 先缩放再平移：缩小 stamp → 居中 → 定位到目标坐标
        trans = Transformation().scale(sx=scale, sy=scale).translate(
            tx=sig_x + center_x,
            ty=pdf_y,
        )
        writer.pages[target_page].merge_transformed_page(stamp_page, trans)

        # ── 插入签批日期文字（签名下方）──
        sign_date = pos.get("sign_date")
        show_date = pos.get("show_date", False)
        if show_date and sign_date:
            # 解析日期字符串为中文格式
            try:
                from datetime import date as date_type
                if isinstance(sign_date, str):
                    dt = date_type.fromisoformat(sign_date)
                else:
                    dt = sign_date
                date_text = f"{dt.year}年{dt.month}月{dt.day}日"
            except (ValueError, TypeError):
                date_text = str(sign_date)

            date_result = _create_date_text_stamp(date_text, font_size=pos.get("date_font_size", 10))
            if isinstance(date_result, tuple):
                date_stamp, dw, dh = date_result
            else:
                date_stamp = date_result
                dw, dh = 0, 0
            if date_stamp is not None and dw > 0:
                # 日期默认位置：签名正下方 28px + 水平居中于签名
                # _create_date_text_stamp 3x 超采样，还原比例 = target_font_size / dh
                target_font_size = pos.get("date_font_size", 10)
                date_scale = (target_font_size / dh) if dh > 0 else 0.3
                date_stamp_w = dw * date_scale  # 日期 stamp 在 PDF 中的渲染宽度
                # 默认 X：签名中心（sig_x + actual_w/2），可用 date_x 覆盖
                if pos.get("date_x") is not None:
                    date_tx = pos["date_x"] - date_stamp_w / 2  # 居中
                else:
                    date_tx = sig_x + sig_w / 2 - date_stamp_w / 2  # 签名槽位居中（匹配前端预览）
                date_y = pos.get("date_y") if pos.get("date_y") is not None else sig_y + 28
                date_pdf_y = page_h - date_y - (dh * date_scale)  # CSS top → PDF 底部坐标
                date_trans = Transformation().scale(sx=date_scale, sy=date_scale).translate(
                    tx=date_tx,
                    ty=date_pdf_y,
                )
                writer.pages[target_page].merge_transformed_page(date_stamp, date_trans)

    # 先写入临时文件，成功后再原子替换，防止写入失败损坏原 PDF
    # M25：临时文件用唯一后缀，防多线程并发写同一 PDF 时临时文件互相覆盖
    tmp_path = f"{pdf_path}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(tmp_path, "wb") as f:
            writer.write(f)
        os.replace(tmp_path, pdf_path)  # 原子替换（跨平台）
    except OSError:
        # 清理残留临时文件（文件写入失败/磁盘空间不足）
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as e:
                logger.warning(f"文件操作失败: {e}", exc_info=True)
                pass
        raise


def _create_signature_stamp(sig_path: str, max_width: int = 100, max_height: int = 26):
    """
    将签名图片转为 pypdf 可用的叠印页，支持 RGBA 透明通道。

    透明实现：
      - RGBA 图片拆分为 RGB 像素 + Alpha 通道
      - RGB → /DeviceRGB Image XObject（FlateDecode 压缩）
      - Alpha → /DeviceGray Image XObject 作为 /SMask 引用
      - PDF 渲染器自动处理透明合成，无需手动计算

    返回：
      - (stamp_page, img_width, img_height)：成功时返回 pypdf 页面对象和原始尺寸
      - (None, 0, 0)：创建失败
    """
    try:
        img = Image.open(sig_path)
        w, h = img.size
        if w == 0 or h == 0:
            return None, 0, 0

        # ── 统一图片模式 ──
        has_alpha = img.mode == 'RGBA'
        if img.mode == 'P':
            img = img.convert('RGBA')
            has_alpha = True
        elif img.mode == 'L':
            img = img.convert('RGB')
            has_alpha = False
        elif img.mode == 'LA':
            img = img.convert('RGBA')
            has_alpha = True
        elif img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')
            has_alpha = True

        # ── 分离 RGB 和 Alpha 数据 ──
        if has_alpha:
            rgb_img = img.convert('RGB')
            alpha_img = img.split()[3]  # Alpha 通道
        else:
            rgb_img = img if img.mode == 'RGB' else img.convert('RGB')
            alpha_img = None

        # ── 创建 stamp PDF ──
        stamp_writer = PdfWriter()
        stamp_writer.add_blank_page(width=float(w), height=float(h))
        stamp_page = stamp_writer.pages[0]

        # 压缩原始像素数据（级别 9 最大压缩）
        rgb_raw = rgb_img.tobytes('raw', 'RGB')
        rgb_compressed = zlib.compress(rgb_raw, 9)

        # ── SMask（Alpha 通道）XObject ──
        smask_ref = None
        if has_alpha and alpha_img is not None:
            alpha_raw = alpha_img.tobytes('raw', 'L')
            alpha_compressed = zlib.compress(alpha_raw, 9)

            smask_stream = DecodedStreamObject()
            smask_stream.set_data(alpha_compressed)
            smask_stream.update(DictionaryObject({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(w),
                NameObject("/Height"): NumberObject(h),
                NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                NameObject("/BitsPerComponent"): NumberObject(8),
                NameObject("/Filter"): NameObject("/FlateDecode"),
            }))
            smask_ref = stamp_writer._add_object(smask_stream)

        # ── RGB Image XObject（主图像）──
        img_dict = DictionaryObject({
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(w),
            NameObject("/Height"): NumberObject(h),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/Filter"): NameObject("/FlateDecode"),
        })
        if smask_ref is not None:
            img_dict[NameObject("/SMask")] = smask_ref  # PDF 原生透明引用

        img_stream = DecodedStreamObject()
        img_stream.set_data(rgb_compressed)
        img_stream.update(img_dict)
        img_ref = stamp_writer._add_object(img_stream)

        # ── 更新页面 Resources ──
        resources_dict = DictionaryObject()
        xobj_dict = DictionaryObject()
        xobj_dict[NameObject("/Im0")] = img_ref
        resources_dict[NameObject("/XObject")] = xobj_dict
        stamp_page[NameObject("/Resources")] = resources_dict

        # ── 构建内容流：绘制图片填充整页 ──
        # PDF Image XObject 默认映射到 [0,1]×[0,1]，cm 变换扩展到 [0,w]×[0,h]
        content_bytes = "q {:.5f} 0 0 {:.5f} 0 0 cm /Im0 Do Q".format(
            float(w), float(h)
        ).encode("ascii")
        content_obj = DecodedStreamObject()
        content_obj.set_data(content_bytes)
        stamp_page[NameObject("/Contents")] = content_obj
        stamp_page.compress_content_streams()

        # ── 序列化后重新读取（确保 pypdf 内部引用正确解析）──
        out = BytesIO()
        stamp_writer.write(out)
        out.seek(0)
        reader = PdfReader(out)
        stamp_page = reader.pages[0]

        return stamp_page, w, h

    except (OSError, ValueError):
        # PIL 图片处理 / pypdf PDF 操作失败时静默降级
        return None, 0, 0
