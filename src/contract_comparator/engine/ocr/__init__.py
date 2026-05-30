"""
OCR 识别引擎包
==============
从 ocr_engine.py 拆分重组的多模块 OCR 识别引擎。

导出接口（向后兼容）:
    OCREngine              — 主 OCR 引擎
    IndustryFieldRecognizer — 行业字段识别器
    ImageQualityReport     — 图像质量评估报告
    FallbackEngine         — 多引擎回退
    ImagePreprocessor      — 图像预处理器
    OCRPostCorrector       — OCR 后校正器
    LayoutRegion           — 版面区域
    StructuredLogger       — 结构化日志器
    以及各独立函数
"""

from contract_comparator.engine.ocr.logger import StructuredLogger
from contract_comparator.engine.ocr.binarize import adaptive_binarize, _apply_otsu_binarize, _apply_sauvola
from contract_comparator.engine.ocr.layout import LayoutRegion, detect_table_regions, detect_columns, layout_analysis
from contract_comparator.engine.ocr.dewarp import dewarp_document, _order_points
from contract_comparator.engine.ocr.quality import ImageQualityReport, assess_image_quality
from contract_comparator.engine.ocr.fallback import FallbackEngine
from contract_comparator.engine.ocr.postcorrector import OCRPostCorrector
from contract_comparator.engine.ocr.preprocessor import ImagePreprocessor
from contract_comparator.engine.ocr.engine import OCREngine
from contract_comparator.engine.ocr.industry import IndustryFieldRecognizer

__all__ = [
    "OCREngine",
    "IndustryFieldRecognizer",
    "ImageQualityReport",
    "FallbackEngine",
    "ImagePreprocessor",
    "OCRPostCorrector",
    "StructuredLogger",
    "LayoutRegion",
    "adaptive_binarize",
    "dewarp_document",
    "assess_image_quality",
    "layout_analysis",
    "detect_table_regions",
    "detect_columns",
]
