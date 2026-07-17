"""PDF 转换服务 —— LibreOffice 无头模式 + Pillow 图片转 PDF

使用 asyncio.Semaphore 限流 2 并发，超时 60 秒，失败重试 1 次。
转换成功后删除源文件保留 PDF。
"""
import asyncio
import os

from PIL import Image

# 限流信号量（全局，2 并发）
_semaphore = asyncio.Semaphore(2)

# 最大超时秒数
CONVERT_TIMEOUT = 60


async def convert_to_pdf(file_path: str) -> str | None:
    """将文件转换为 PDF，返回 PDF 路径或 None（失败时）

    支持的格式：
    - doc/docx → PDF（LibreOffice）
    - xls/xlsx → PDF（LibreOffice）
    - png/jpg/jpeg → PDF（Pillow）
    - pdf → 跳过转换，直接返回原路径
    """
    ext = os.path.splitext(file_path)[1].lower()

    # PDF 无需转换
    if ext == ".pdf":
        return file_path

    async with _semaphore:
        try:
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                return await _image_to_pdf(file_path)
            elif ext in (".doc", ".docx", ".xls", ".xlsx"):
                return await _libreoffice_convert(file_path)
            else:
                return None  # 不支持的类型
        except Exception:
            return None


async def _image_to_pdf(image_path: str) -> str | None:
    """图片转 PDF（Pillow）"""
    try:
        img = Image.open(image_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        pdf_path = os.path.splitext(image_path)[0] + ".pdf"
        img.save(pdf_path, "PDF", resolution=100.0)

        # 删除源文件
        os.remove(image_path)
        return pdf_path
    except Exception:
        return None


async def _libreoffice_convert(input_path: str) -> str | None:
    """LibreOffice 无头模式转换 → PDF

    重试 1 次，超时 60 秒。
    """
    output_dir = os.path.dirname(input_path)

    for attempt in range(2):
        try:
            proc = await asyncio.create_subprocess_exec(
                "libreoffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                input_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=CONVERT_TIMEOUT)

            # 查找生成的 PDF
            base = os.path.splitext(os.path.basename(input_path))[0]
            pdf_path = os.path.join(output_dir, f"{base}.pdf")

            if os.path.exists(pdf_path):
                # 删除源文件
                os.remove(input_path)
                return pdf_path

            if attempt == 0:
                # 重试前等一会
                await asyncio.sleep(2)

        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            if attempt == 0:
                await asyncio.sleep(2)

    return None
