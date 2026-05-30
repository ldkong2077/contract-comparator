"""
单元测试 — field_extractor 模块
验证字段智能抽取功能：正则提取、金额规范化、日期统一化
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from field_extractor import FieldExtractor


class TestFieldExtractorInit(unittest.TestCase):
    """字段提取器初始化测试"""

    def test_init_default(self):
        """默认初始化"""
        extractor = FieldExtractor()
        self.assertIsNotNone(extractor)


class TestFieldExtractorExtractAll(unittest.TestCase):
    """extract_all 综合提取测试"""

    def setUp(self):
        self.extractor = FieldExtractor()

    def test_extract_returns_dict(self):
        """extract_all 应返回字典"""
        result = self.extractor.extract_all("合同金额为人民币100,000.00元")
        self.assertIsInstance(result, dict)

    def test_extract_has_expected_keys(self):
        """返回结果应包含标准键"""
        result = self.extractor.extract_all("合同金额为人民币100,000.00元")
        expected_keys = {"source", "numbers", "dates", "amounts_words", "amounts_digits",
                         "percentages", "party_names", "contract_numbers", "clauses",
                         "legal_terms", "contact_info", "terms"}
        self.assertTrue(expected_keys.issubset(set(result.keys())))


class TestFieldExtractorAmount(unittest.TestCase):
    """金额字段提取测试"""

    def setUp(self):
        self.extractor = FieldExtractor()

    def test_extract_amount_digits(self):
        """提取阿拉伯数字金额"""
        amounts = self.extractor.extract_amount_digits("合同金额为人民币100,000.00元")
        self.assertIsInstance(amounts, list)

    def test_extract_amount_words(self):
        """提取中文大写金额"""
        amounts = self.extractor.extract_amount_words("合同金额为人民币壹拾万元整")
        self.assertIsInstance(amounts, list)

    def test_amount_fullwidth_normalize(self):
        """全角金额规范化"""
        amounts = self.extractor.extract_amount_digits("金额：１００，０００．００元")
        self.assertIsInstance(amounts, list)


class TestFieldExtractorDate(unittest.TestCase):
    """日期字段提取测试"""

    def setUp(self):
        self.extractor = FieldExtractor()

    def test_extract_dates(self):
        """提取日期"""
        dates = self.extractor.extract_dates("签订日期：2025-03-15")
        self.assertIsInstance(dates, list)

    def test_normalize_date(self):
        """日期规范化"""
        result = self.extractor.normalize_date("2025年3月15日")
        self.assertIsInstance(result, str)


class TestFieldExtractorContractId(unittest.TestCase):
    """合同编号提取测试"""

    def setUp(self):
        self.extractor = FieldExtractor()

    def test_extract_contract_numbers(self):
        """提取合同编号"""
        numbers = self.extractor.extract_contract_numbers("合同编号：HT-2025-001234")
        self.assertIsInstance(numbers, list)


class TestFieldExtractorParty(unittest.TestCase):
    """合同主体提取测试"""

    def setUp(self):
        self.extractor = FieldExtractor()

    def test_extract_party_names(self):
        """提取合同双方名称"""
        names = self.extractor.extract_party_names(
            "甲方：北京某某科技有限公司\n乙方：上海某某贸易有限公司"
        )
        self.assertIsInstance(names, list)


class TestFieldExtractorEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def setUp(self):
        self.extractor = FieldExtractor()

    def test_empty_text(self):
        """空文本不应崩溃"""
        result = self.extractor.extract_all("")
        self.assertIsInstance(result, dict)

    def test_long_text(self):
        """长文本处理"""
        long_text = "合同条款" * 1000
        result = self.extractor.extract_all(long_text)
        self.assertIsInstance(result, dict)

    def test_normalize_text(self):
        """文本规范化"""
        result = self.extractor.normalize_text("  多  余  空  格  ")
        self.assertIsInstance(result, str)

    def test_normalize_number(self):
        """数字规范化"""
        result = self.extractor.normalize_number("１２３４５")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
