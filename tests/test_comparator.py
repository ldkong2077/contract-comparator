"""
Comparator 单元测试
测试字段比对引擎：数字、日期、金额、百分比比对及关键词归一化
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from comparator import Comparator


class TestCompareIdenticalFields:
    """相同字段比对测试"""

    def test_compare_identical_fields(self):
        """完全相同的字段应无差异"""
        comparator = Comparator()
        word_fields = {
            "numbers": [{"raw": "100000", "normalized": 100000.0, "context": "金额"}],
            "dates": [{"raw": "2024-01-15", "normalized": "2024-01-15", "context": "签订日期"}],
            "amounts_words": [{"raw": "壹拾伍万元整", "normalized": "壹拾伍万元整", "context": "合同金额"}],
            "amounts_digits": [{"raw": "900000", "normalized": 900000.0, "keyword": "包干费用", "phrase": "包干费用为900000元", "context": "包干费用"}],
            "percentages": [{"raw": "5%", "normalized": 0.05, "context": "违约金比例"}],
        }
        pdf_fields = {
            "numbers": [{"raw": "100000", "normalized": 100000.0, "context": "金额"}],
            "dates": [{"raw": "2024-01-15", "normalized": "2024-01-15", "context": "签订日期"}],
            "amounts_words": [{"raw": "壹拾伍万元整", "normalized": "壹拾伍万元整", "context": "合同金额"}],
            "amounts_digits": [{"raw": "900000", "normalized": 900000.0, "keyword": "包干费用", "phrase": "包干费用900000", "context": "包干费用"}],
            "percentages": [{"raw": "5%", "normalized": 0.05, "context": "违约金比例"}],
        }
        result = comparator.compare(word_fields, pdf_fields)
        assert not result["numbers"]["has_diff"]
        assert not result["dates"]["has_diff"]
        assert not result["amounts_words"]["has_diff"]
        assert not result["percentages"]["has_diff"]


class TestCompareDifferentNumbers:
    """数字差异比对测试"""

    def test_compare_different_numbers(self):
        """不同数字应被检测为差异"""
        comparator = Comparator()
        word_nums = [{"raw": "50000", "normalized": 50000.0, "context": "违约金"}]
        pdf_nums = [{"raw": "5000", "normalized": 5000.0, "context": "违约金"}]
        result = comparator.compare_numbers(word_nums, pdf_nums)
        assert result["has_diff"]

    def test_compare_numbers_missing_in_pdf(self):
        """Word 有但 PDF 没有的数字应标记为 missing"""
        comparator = Comparator()
        word_nums = [{"raw": "100000", "normalized": 100000.0, "context": "金额"}]
        pdf_nums = []
        result = comparator.compare_numbers(word_nums, pdf_nums)
        assert len(result["missing_in_pdf"]) == 1

    def test_compare_numbers_extra_in_pdf(self):
        """PDF 有但 Word 没有的数字应标记为 extra"""
        comparator = Comparator()
        word_nums = []
        pdf_nums = [{"raw": "99999", "normalized": 99999.0, "context": "多出"}]
        result = comparator.compare_numbers(word_nums, pdf_nums)
        assert len(result["extra_in_pdf"]) == 1


class TestCompareDates:
    """日期比对测试"""

    def test_compare_dates_match(self):
        """归一化后相同的日期应匹配"""
        comparator = Comparator()
        word_dates = [{"raw": "2024-01-15", "normalized": "2024-01-15"}]
        pdf_dates = [{"raw": "2024年1月15日", "normalized": "2024-01-15"}]
        result = comparator.compare_dates(word_dates, pdf_dates)
        assert len(result["matched"]) == 1
        assert not result["has_diff"]

    def test_compare_dates_different(self):
        """不同日期应标记为差异"""
        comparator = Comparator()
        word_dates = [{"raw": "2024-01-15", "normalized": "2024-01-15"}]
        pdf_dates = [{"raw": "2024-01-16", "normalized": "2024-01-16"}]
        result = comparator.compare_dates(word_dates, pdf_dates)
        assert result["has_diff"]
        assert len(result["missing_in_pdf"]) == 1


class TestCompareAmounts:
    """金额比对测试"""

    def test_compare_amounts_words_match(self):
        """相同大写金额应匹配"""
        comparator = Comparator()
        word = [{"raw": "壹拾伍万元整", "normalized": "壹拾伍万元整"}]
        pdf = [{"raw": "壹拾伍万元整", "normalized": "壹拾伍万元整"}]
        result = comparator.compare_amounts_words(word, pdf)
        assert len(result["matched"]) == 1

    def test_compare_amounts_words_different(self):
        """不同大写金额应标记为差异"""
        comparator = Comparator()
        word = [{"raw": "壹拾伍万元整", "normalized": "壹拾伍万元整"}]
        pdf = [{"raw": "壹拾陆万元整", "normalized": "壹拾陆万元整"}]
        result = comparator.compare_amounts_words(word, pdf)
        assert result["has_diff"]

    def test_compare_amounts_digits_keyword_match(self):
        """关键词相同的金额数字应匹配"""
        comparator = Comparator()
        word = [{"raw": "900000", "normalized": 900000.0, "keyword": "包干费用", "phrase": "包干费用为900000元", "context": "包干费用"}]
        pdf = [{"raw": "900000", "normalized": 900000.0, "keyword": "包干费用", "phrase": "包干费用900000", "context": "包干费用"}]
        result = comparator.compare_amounts_digits(word, pdf)
        assert len(result["matched"]) == 1

    def test_compare_amounts_digits_different_value(self):
        """不同金额数字应标记为差异"""
        comparator = Comparator()
        word = [{"raw": "50000", "normalized": 50000.0, "keyword": "违约金", "phrase": "违约金50000元", "context": "违约金"}]
        pdf = [{"raw": "5000", "normalized": 5000.0, "keyword": "违约金", "phrase": "违约金5000元", "context": "违约金"}]
        result = comparator.compare_amounts_digits(word, pdf)
        assert result["has_diff"]


class TestNormalizeKeyword:
    """关键词归一化测试"""

    def test_normalize_keyword_basic(self):
        """基本归一化：去除标点、空格、统一小写"""
        result = Comparator.normalize_keyword("合同金额")
        assert result == "合同金额"

    def test_normalize_keyword_with_punctuation(self):
        """含标点的关键词应被归一化"""
        result = Comparator.normalize_keyword("合同金额：")
        assert "：" not in result
        assert "合同金额" in result

    def test_normalize_keyword_with_spaces(self):
        """含空格的关键词应被归一化"""
        result = Comparator.normalize_keyword(" 合同 金额 ")
        assert " " not in result

    def test_normalize_keyword_mixed_case(self):
        """大小写混合应统一为小写"""
        result = Comparator.normalize_keyword("RMB")
        assert result == "rmb"

    def test_normalize_keyword_empty(self):
        """空字符串应返回空"""
        result = Comparator.normalize_keyword("")
        assert result == ""

    def test_normalize_keyword_none_like(self):
        """None 类输入（空字符串）应返回空"""
        result = Comparator.normalize_keyword("")
        assert result == ""


class TestComparePercentages:
    """百分比比对测试"""

    def test_compare_percentages_match(self):
        """相同百分比应匹配"""
        comparator = Comparator()
        word = [{"raw": "5%", "normalized": 0.05}]
        pdf = [{"raw": "5%", "normalized": 0.05}]
        result = comparator.compare_percentages(word, pdf)
        assert len(result["matched"]) == 1
        assert not result["has_diff"]

    def test_compare_percentages_different(self):
        """不同百分比应标记为差异"""
        comparator = Comparator()
        word = [{"raw": "5%", "normalized": 0.05}]
        pdf = [{"raw": "3%", "normalized": 0.03}]
        result = comparator.compare_percentages(word, pdf)
        assert result["has_diff"]


class TestGetSummary:
    """比对摘要测试"""

    def test_get_summary_no_diff(self):
        """无差异时摘要应显示 0 差异"""
        comparator = Comparator()
        result = {
            "numbers": {"has_diff": False},
            "dates": {"has_diff": False},
            "amounts_words": {"has_diff": False},
            "amounts_digits": {"has_diff": False},
            "percentages": {"has_diff": False},
        }
        summary = comparator.get_summary(result)
        assert summary["total_diffs"] == 0
        assert not summary["has_critical_diff"]

    def test_get_summary_with_critical_diff(self):
        """金额差异应标记为严重"""
        comparator = Comparator()
        result = {
            "numbers": {"has_diff": False},
            "dates": {"has_diff": False},
            "amounts_words": {"has_diff": True, "missing_in_pdf": [{}], "extra_in_pdf": []},
            "amounts_digits": {"has_diff": False},
            "percentages": {"has_diff": False},
        }
        summary = comparator.get_summary(result)
        assert summary["has_critical_diff"] is True
