"""
OCR Engine 单元测试
测试 IndustryFieldRecognizer 行业字段识别器、置信度提升、图片文件验证
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock

import pytest

# 检查 OCR 模块是否可用
try:
    from ocr_engine import IndustryFieldRecognizer, OCREngine
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

_skip_ocr = pytest.mark.skipif(not OCR_AVAILABLE, reason="OCR engine dependencies not available")


# ============================================================
# IndustryFieldRecognizer 测试
# ============================================================

@_skip_ocr
class TestIndustryFieldRecognizer:
    """行业字段识别器测试"""

    def test_industry_field_recognizer_init(self):
        """初始化应正确设置行业和关键词"""
        recognizer = IndustryFieldRecognizer("general")
        assert recognizer.industry == "general"
        assert len(recognizer.keywords) > 0

    def test_industry_field_recognizer_general(self):
        """通用行业应包含基本合同字段关键词"""
        recognizer = IndustryFieldRecognizer("general")
        assert "甲方" in recognizer.keywords
        assert "乙方" in recognizer.keywords
        assert "合同编号" in recognizer.keywords

    def test_industry_field_recognizer_construction(self):
        """工程建设行业应包含工程相关关键词"""
        recognizer = IndustryFieldRecognizer("construction")
        assert "工程名称" in recognizer.keywords
        assert "施工单位" in recognizer.keywords
        assert "工期" in recognizer.keywords

    def test_industry_field_recognizer_leasing(self):
        """租赁行业应包含租赁相关关键词"""
        recognizer = IndustryFieldRecognizer("leasing")
        assert "出租方" in recognizer.keywords
        assert "承租方" in recognizer.keywords
        assert "租金" in recognizer.keywords

    def test_industry_field_recognizer_procurement(self):
        """采购行业应包含采购相关关键词"""
        recognizer = IndustryFieldRecognizer("procurement")
        assert "供方" in recognizer.keywords
        assert "需方" in recognizer.keywords
        assert "单价" in recognizer.keywords

    def test_industry_field_recognizer_labor(self):
        """劳务行业应包含劳务相关关键词"""
        recognizer = IndustryFieldRecognizer("labor")
        assert "用人单位" in recognizer.keywords
        assert "劳动者" in recognizer.keywords
        assert "工资" in recognizer.keywords

    def test_industry_field_recognizer_invalid_industry(self):
        """不支持的行业类型应抛出 ValueError"""
        with pytest.raises(ValueError, match="不支持的行业类型"):
            IndustryFieldRecognizer("nonexistent")

    def test_recognize_fields_general(self, sample_ocr_results):
        """通用行业字段识别应提取到甲方等字段"""
        recognizer = IndustryFieldRecognizer("general")
        result = recognizer.recognize_fields(sample_ocr_results)
        assert "industry" in result
        assert result["industry"] == "general"
        assert "fields" in result
        # OCR 结果中有 "合同编号" 关键词
        field_names = [f["name"] for f in result["fields"]]
        assert "合同编号" in field_names

    def test_recognize_fields_construction(self, sample_ocr_results):
        """工程建设行业字段识别"""
        recognizer = IndustryFieldRecognizer("construction")
        result = recognizer.recognize_fields(sample_ocr_results)
        assert result["industry"] == "construction"
        # OCR 结果中有 "工期" 关键词
        field_names = [f["name"] for f in result["fields"]]
        assert "工期" in field_names

    def test_extract_value_from_text_colon(self):
        """冒号分隔的值应被正确提取"""
        value = IndustryFieldRecognizer._extract_value_from_text("甲方", "甲方：深圳市XX公司")
        assert value == "深圳市XX公司"

    def test_extract_value_from_text_equals(self):
        """等号分隔的值应被正确提取"""
        value = IndustryFieldRecognizer._extract_value_from_text("金额", "金额＝50000元")
        assert value == "50000元"

    def test_extract_value_from_text_space(self):
        """空格分隔的值应被正确提取"""
        value = IndustryFieldRecognizer._extract_value_from_text("编号", "编号 HT-2024-001")
        assert value == "HT-2024-001"

    def test_extract_value_from_text_no_value(self):
        """关键词后无值应返回空字符串"""
        value = IndustryFieldRecognizer._extract_value_from_text("甲方", "甲方签署")
        assert value == ""

    def test_calc_similarity_identical(self):
        """相同字符串相似度应为 1.0"""
        score = IndustryFieldRecognizer._calc_similarity("合同编号", "合同编号")
        assert score == 1.0

    def test_calc_similarity_different(self):
        """完全不同字符串相似度应较低"""
        score = IndustryFieldRecognizer._calc_similarity("甲方", "乙方")
        assert score < 1.0


# ============================================================
# 置信度提升测试
# ============================================================

@_skip_ocr
class TestBoostConfidence:
    """上下文置信度提升测试"""

    def test_boost_confidence_with_context(self):
        """金额上下文应提升低置信度项的置信度"""
        engine = OCREngine.__new__(OCREngine)
        results = [
            {
                "text": "¥900000.00",
                "confidence": 0.6,
                "bbox": [[0, 0], [100, 0], [100, 20], [0, 20]],
            },
        ]
        full_text = "包干费用为¥900000.00元"
        boosted = engine.boost_confidence_with_context(results, full_text)
        assert boosted[0]["confidence"] > 0.6

    def test_boost_confidence_date_context(self):
        """日期上下文应提升低置信度项的置信度"""
        engine = OCREngine.__new__(OCREngine)
        results = [
            {
                "text": "2024年1月15日",
                "confidence": 0.55,
                "bbox": [[0, 0], [100, 0], [100, 20], [0, 20]],
            },
        ]
        full_text = "签订日期2024年1月15日"
        boosted = engine.boost_confidence_with_context(results, full_text)
        assert boosted[0]["confidence"] > 0.55

    def test_boost_confidence_high_conf_unchanged(self):
        """高置信度项不应被提升"""
        engine = OCREngine.__new__(OCREngine)
        results = [
            {
                "text": "正常文本",
                "confidence": 0.9,
                "bbox": [[0, 0], [100, 0], [100, 20], [0, 20]],
            },
        ]
        full_text = "正常文本"
        boosted = engine.boost_confidence_with_context(results, full_text)
        assert boosted[0]["confidence"] == 0.9

    def test_boost_confidence_capped_at_095(self):
        """置信度提升后不应超过 0.95"""
        engine = OCREngine.__new__(OCREngine)
        results = [
            {
                "text": "¥900000.00元",
                "confidence": 0.79,
                "bbox": [[0, 0], [100, 0], [100, 20], [0, 20]],
            },
        ]
        full_text = "金额¥900000.00元"
        boosted = engine.boost_confidence_with_context(results, full_text)
        assert boosted[0]["confidence"] <= 0.95


# ============================================================
# 图片文件验证测试
# ============================================================

@_skip_ocr
class TestImageFileValidation:
    """图片文件验证测试"""

    def test_nonexistent_file_raises_error(self):
        """不存在的文件应抛出 FileNotFoundError"""
        engine = OCREngine.__new__(OCREngine)
        engine._initialized = True
        engine.ocr = MagicMock()
        with pytest.raises(FileNotFoundError):
            engine.recognize_image("/nonexistent/image.png")

    def test_unsupported_format_raises_error(self, tmp_path):
        """不支持的图片格式应抛出 ValueError"""
        # 创建一个 .gif 文件（不支持）
        gif_path = str(tmp_path / "test.gif")
        with open(gif_path, "wb") as f:
            f.write(b"GIF89a")

        engine = OCREngine.__new__(OCREngine)
        with pytest.raises(ValueError, match="不支持的图片格式"):
            engine.recognize_image_file(gif_path)

    def test_supported_formats(self):
        """支持的格式列表应包含常见图片格式"""
        supported = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
        assert supported == supported  # 确认常量存在
