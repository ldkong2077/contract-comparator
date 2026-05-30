"""
FieldExtractor 单元测试
测试字段抽取器：数字、日期、金额、百分比提取
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from field_extractor import FieldExtractor


class TestExtractNumbers:
    """数字提取测试"""

    def test_extract_numbers_basic(self):
        """基本数字提取"""
        extractor = FieldExtractor()
        text = "合同金额为150000元，期限365天"
        result = extractor.extract_numbers(text)
        values = [r["raw"] for r in result]
        assert "150000" in values
        assert "365" in values

    def test_extract_numbers_with_commas(self):
        """千分位逗号数字应被正确提取"""
        extractor = FieldExtractor()
        text = "总金额为1,000,000元"
        result = extractor.extract_numbers(text)
        values = [r["raw"] for r in result]
        assert "1,000,000" in values

    def test_extract_numbers_with_decimals(self):
        """小数数字应被正确提取"""
        extractor = FieldExtractor()
        text = "单价为99.50元"
        result = extractor.extract_numbers(text)
        # 99.50 可能被过滤（纯1位小数格式数字），但 99.50 > 10 所以应保留
        normalized = [r["normalized"] for r in result]
        assert any(abs(n - 99.5) < 0.01 for n in normalized)

    def test_extract_numbers_exclude_short(self):
        """排除2位以下数字（地块编号）"""
        extractor = FieldExtractor()
        text = "地块编号05-02，金额100000元"
        result = extractor.extract_numbers(text)
        values = [r["raw"] for r in result]
        assert "05" not in values
        assert "02" not in values

    def test_extract_numbers_exclude_very_long(self):
        """排除超长数字（银行账号）"""
        extractor = FieldExtractor()
        text = "银行账号6222021234567890123，金额100000元"
        result = extractor.extract_numbers(text)
        values = [r["raw"] for r in result]
        # 超过12位的数字应被排除
        assert not any(len(v.replace(",", "").replace(".", "")) > 12 for v in values)

    def test_extract_numbers_exclude_alpha_adjacent(self):
        """排除字母相邻的数字（印章编码）"""
        extractor = FieldExtractor()
        text = "印章编码B621JE，金额100000元"
        result = extractor.extract_numbers(text)
        values = [r["raw"] for r in result]
        assert "621" not in values

    def test_extract_numbers_context(self):
        """提取的数字应包含上下文信息"""
        extractor = FieldExtractor()
        text = "合同金额为150000元"
        result = extractor.extract_numbers(text)
        assert len(result) >= 1
        assert "context" in result[0]
        assert "金额" in result[0]["context"]


class TestExtractDates:
    """日期提取测试"""

    def test_extract_dates_chinese_format(self):
        """中文日期格式提取"""
        extractor = FieldExtractor()
        text = "合同签订日期：2024年1月15日"
        result = extractor.extract_dates(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == "2024-01-15"

    def test_extract_dates_hyphen_format(self):
        """连字符日期格式提取"""
        extractor = FieldExtractor()
        text = "签署日期：2024-01-15"
        result = extractor.extract_dates(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == "2024-01-15"

    def test_extract_dates_slash_format(self):
        """斜杠日期格式提取"""
        extractor = FieldExtractor()
        text = "日期：2024/01/15"
        result = extractor.extract_dates(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == "2024-01-15"

    def test_extract_dates_dot_format(self):
        """点号日期格式提取"""
        extractor = FieldExtractor()
        text = "日期：2024.01.15"
        result = extractor.extract_dates(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == "2024-01-15"

    def test_extract_dates_dedup(self):
        """相同归一化日期应去重"""
        extractor = FieldExtractor()
        text = "起始日期2024年1月15日，截止日期2024-01-15"
        result = extractor.extract_dates(text)
        # 两个日期归一化后相同，应去重为1个
        normalized_values = [r["normalized"] for r in result]
        assert normalized_values.count("2024-01-15") == 1

    def test_extract_dates_context(self):
        """提取的日期应包含上下文信息"""
        extractor = FieldExtractor()
        text = "合同签订日期：2024年1月15日生效"
        result = extractor.extract_dates(text)
        assert len(result) >= 1
        assert "context" in result[0]


class TestExtractAmounts:
    """金额提取测试"""

    def test_extract_amount_with_currency_symbol(self):
        """货币符号+数字的金额提取"""
        extractor = FieldExtractor()
        text = "¥900000.00"
        result = extractor.extract_amount_digits(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == 900000.0

    def test_extract_amount_with_keyword_yuan(self):
        """关键词+数字+元的金额提取"""
        extractor = FieldExtractor()
        text = "违约金50000元"
        result = extractor.extract_amount_digits(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == 50000.0

    def test_extract_amount_rmb(self):
        """人民币格式金额提取"""
        extractor = FieldExtractor()
        text = "人民币100000元"
        result = extractor.extract_amount_digits(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == 100000.0

    def test_extract_amount_with_keyword_wei(self):
        """关键词+为+货币符号+数字+元的金额提取"""
        extractor = FieldExtractor()
        text = "包干费用为¥900000.00元"
        result = extractor.extract_amount_digits(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == 900000.0

    def test_extract_amount_small_value_filtered(self):
        """小于100的值不应被识别为金额"""
        extractor = FieldExtractor()
        text = "金额50元"
        result = extractor.extract_amount_digits(text)
        assert len(result) == 0

    def test_extract_amount_words(self):
        """大写金额提取"""
        extractor = FieldExtractor()
        text = "合同总价为壹拾伍万元整"
        result = extractor.extract_amount_words(text)
        assert len(result) >= 1
        assert result[0]["raw"] == "壹拾伍万元整"

    def test_extract_amount_words_short_filtered(self):
        """单个汉字不应被识别为大写金额"""
        extractor = FieldExtractor()
        text = "元"
        result = extractor.extract_amount_words(text)
        assert len(result) == 0

    def test_extract_amount_words_no_valid_chars(self):
        """不含有效数字字符的文本不应被识别为大写金额"""
        extractor = FieldExtractor()
        text = "零零零零元整"
        result = extractor.extract_amount_words(text)
        assert len(result) == 0


class TestExtractPercentages:
    """百分比提取测试"""

    def test_extract_percentages_basic(self):
        """基本百分比提取"""
        extractor = FieldExtractor()
        text = "违约金按5%计算"
        result = extractor.extract_percentages(text)
        assert len(result) >= 1
        assert result[0]["normalized"] == 0.05

    def test_extract_percentages_decimal(self):
        """小数百分比提取"""
        extractor = FieldExtractor()
        text = "税率为3.5%"
        result = extractor.extract_percentages(text)
        assert len(result) >= 1
        assert abs(result[0]["normalized"] - 0.035) < 0.001

    def test_extract_percentages_multiple(self):
        """多个百分比提取"""
        extractor = FieldExtractor()
        text = "甲方占60%，乙方占40%"
        result = extractor.extract_percentages(text)
        assert len(result) >= 2

    def test_extract_percentages_context(self):
        """提取的百分比应包含上下文信息"""
        extractor = FieldExtractor()
        text = "违约金按5%计算"
        result = extractor.extract_percentages(text)
        assert len(result) >= 1
        assert "context" in result[0]
