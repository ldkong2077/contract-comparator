"""
PDF 转图片模块
使用 PyMuPDF 将 PDF 扫描件转换为高分辨率图片
"""
import logging
import os
import fitz  # PyMuPDF
from contract_comparator.config import PDF_CONFIG

logger = logging.getLogger(__name__)


def pdf_to_images(pdf_path: str, output_dir: str | None = None) -> list[str]:
    """
    将 PDF 每一页转换为图片
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（默认在 PDF 同目录下创建 images 文件夹）
    
    Returns:
        图片路径列表
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    
    # 设置输出目录
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(pdf_path), "images")
    os.makedirs(output_dir, exist_ok=True)
    
    # 打开 PDF
    image_paths = []

    # 缩放参数
    zoom = PDF_CONFIG["zoom"]
    mat = fitz.Matrix(zoom, zoom)

    with fitz.open(pdf_path) as doc:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # 渲染图片
            pix = page.get_pixmap(matrix=mat)

            # 保存图片
            img_path = os.path.join(output_dir, f"page_{page_num + 1:03d}.png")
            pix.save(img_path)
            image_paths.append(img_path)

            logger.info(f"第 {page_num + 1}/{len(doc)} 页 → {img_path}")

    logger.info(f"共转换 {len(image_paths)} 页")
    
    return image_paths


def get_pdf_page_count(pdf_path: str) -> int:
    """获取 PDF 页数"""
    with fitz.open(pdf_path) as doc:
        return len(doc)
