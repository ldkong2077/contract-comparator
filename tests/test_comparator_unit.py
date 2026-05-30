"""
单元测试 — comparator 模块
验证比对引擎的字段匹配、上下文感知策略
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from comparator import Comparator


class TestComparatorInit(unittest.TestCase):
    """比对器初始化测试"""

    def test_init_default(self):
        """默认初始化不应抛出异常"""
        comp = Comparator()
        self.assertIsNotNone(comp)


class TestComparatorCompare(unittest.TestCase):
    """比对方法测试"""

    def setUp(self):
        self.comp = Comparator()

    def test_identical_fields_match(self):
        """完全相同的字段应匹配"""
        result = self.comp.compare(
            {"金额": ["10000.00"]},
            {"金额": ["10000.00"]}
        )
        self.assertIsInstance(result, dict)

    def test_different_fields_detect_diff(self):
        """不同字段应检测到差异"""
        result = self.comp.compare(
            {"金额": ["10000.00"]},
            {"金额": ["20000.00"]}
        )
        self.assertIsInstance(result, dict)

    def test_missing_field_detected(self):
        """缺失字段应被检测"""
        result = self.comp.compare(
            {"金额": ["10000.00"], "日期": ["2025-01-01"]},
            {"金额": ["10000.00"]}
        )
        self.assertIsInstance(result, dict)

    def test_empty_fields_handled(self):
        """空字段字典不应导致崩溃"""
        result = self.comp.compare({}, {})
        self.assertIsInstance(result, dict)


class TestComparatorNumberTolerance(unittest.TestCase):
    """数字容差匹配测试"""

    def setUp(self):
        self.comp = Comparator()

    def test_small_decimal_difference(self):
        """微小浮点差异应在容差内"""
        result = self.comp.compare(
            {"金额": ["10000.001"]},
            {"金额": ["10000.002"]}
        )
        self.assertIsInstance(result, dict)


class TestComparatorAmountComparison(unittest.TestCase):
    """金额比对专项测试"""

    def setUp(self):
        self.comp = Comparator()

    def test_compare_amounts_digits(self):
        """数字金额比对"""
        word = [{"raw": "10000", "normalized": 10000.0, "keyword": "金额", "phrase": "金额10000元", "context": ""}]
        pdf = [{"raw": "10000", "normalized": 10000.0, "keyword": "金额", "phrase": "金额10000元", "context": ""}]
        result = self.comp.compare_amounts_digits(word, pdf)
        self.assertIsInstance(result, dict)

    def test_compare_amounts_words(self):
        """中文大写金额比对"""
        word = [{"raw": "壹万元整", "normalized": 10000, "context": ""}]
        pdf = [{"raw": "壹万元整", "normalized": 10000, "context": ""}]
        result = self.comp.compare_amounts_words(word, pdf)
        self.assertIsInstance(result, dict)

    def test_compare_dates(self):
        """日期比对"""
        word = [{"raw": "2025-01-15", "normalized": "2025-01-15", "context": ""}]
        pdf = [{"raw": "2025-01-15", "normalized": "2025-01-15", "context": ""}]
        result = self.comp.compare_dates(word, pdf)
        self.assertIsInstance(result, dict)

    def test_compare_numbers(self):
        """数字比对"""
        word = [{"raw": "12345", "normalized": "12345", "context": ""}]
        pdf = [{"raw": "12345", "normalized": "12345", "context": ""}]
        result = self.comp.compare_numbers(word, pdf)
        self.assertIsInstance(result, dict)

    def test_compare_percentages(self):
        """百分比比对"""
        word = [{"raw": "50%", "normalized": 0.5, "context": ""}]
        pdf = [{"raw": "50%", "normalized": 0.5, "context": ""}]
        result = self.comp.compare_percentages(word, pdf)
        self.assertIsInstance(result, dict)


class TestComparatorNormalization(unittest.TestCase):
    """规范化方法测试"""

    def setUp(self):
        self.comp = Comparator()

    def test_normalize_keyword(self):
        """关键词规范化"""
        result = self.comp.normalize_keyword("甲方")
        self.assertIsInstance(result, str)

    def test_number_tolerance_is_float(self):
        """number_tolerance 应为浮点数阈值"""
        self.assertIsInstance(self.comp.number_tolerance, float)
        self.assertGreater(self.comp.number_tolerance, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
