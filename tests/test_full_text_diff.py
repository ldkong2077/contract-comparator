"""
FullTextDiff 单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from full_text_diff import FullTextDiff


class TestNormalizeForDiff:
    """文本预处理测试"""

    def test_empty_text(self):
        result = FullTextDiff.normalize_for_diff("")
        assert result == ""

    def test_whitespace_only(self):
        result = FullTextDiff.normalize_for_diff("   \t  \n  \t  ")
        assert result == ""

    def test_carriage_return(self):
        result = FullTextDiff.normalize_for_diff("line1\r\nline2\rline3")
        assert "\r" not in result
        assert "line1\nline2\nline3" in result

    def test_multiple_spaces_to_single(self):
        result = FullTextDiff.normalize_for_diff("hello    world\t\ttest")
        assert "hello world test" in result

    def test_blank_lines_removed(self):
        result = FullTextDiff.normalize_for_diff("line1\n   \n  \t  \nline2")
        lines = result.split("\n")
        assert len(lines) == 2
        assert "line1" in lines
        assert "line2" in lines

    def test_chinese_text_preserved(self):
        text = "合同金额为壹拾万元整，签订日期2024年1月15日。"
        result = FullTextDiff.normalize_for_diff(text)
        assert "合同金额" in result

    def test_normal_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        result = FullTextDiff.normalize_for_diff(text)
        assert result == text


class TestCompare:
    """全文比对测试"""

    @pytest.fixture
    def differ(self):
        return FullTextDiff()

    def test_empty_input(self, differ):
        result = differ.compare("", "")
        assert result["diffs"] == []
        assert result["summary"]["total_changes"] == 0
        assert result["summary"]["insertions"] == 0
        assert result["summary"]["deletions"] == 0
        assert result["summary"]["has_risk"] is False

    def test_identical_texts(self, differ):
        text = "合同金额为100000元，签订日期2024年1月15日。"
        result = differ.compare(text, text)
        assert result["diffs"] == []
        assert result["summary"]["total_changes"] == 0

    def test_simple_insertion(self, differ):
        word_text = "合同金额为100000元。"
        pdf_text = "合同金额为100000元，另加违约金。"
        result = differ.compare(word_text, pdf_text)
        assert result["summary"]["total_changes"] > 0
        insertions = [d for d in result["diffs"] if d["type"] == "insert"]
        assert len(insertions) >= 1

    def test_simple_deletion(self, differ):
        word_text = "合同金额为100000元，另加违约金50000元。"
        pdf_text = "合同金额为100000元。"
        result = differ.compare(word_text, pdf_text)
        deletions = [d for d in result["diffs"] if d["type"] == "delete"]
        assert len(deletions) >= 1

    def test_diff_has_context(self, differ):
        word_text = "甲方应于2024年1月15日前支付合同金额100000元。"
        pdf_text = "甲方应于2024年1月15日前支付合同金额150000元。"
        result = differ.compare(word_text, pdf_text)
        for d in result["diffs"]:
            assert "context_before" in d
            assert "context_after" in d

    def test_diff_has_type_and_risk(self, differ):
        word_text = "合同金额为100000元。"
        pdf_text = "合同金额为50000元。"
        result = differ.compare(word_text, pdf_text)
        for d in result["diffs"]:
            assert d["type"] in ("insert", "delete")
            assert d["risk_level"] in ("high", "medium", "low")
            assert d["category"] in ("text", "number", "date", "keyword")


class TestClassifyDiff:
    """差异分类测试"""

    def test_number_detected_as_high(self):
        risk, category = FullTextDiff._classify_diff("100000", -1)
        assert risk == "high"
        assert category == "number"

    def test_decimal_number(self):
        risk, category = FullTextDiff._classify_diff("50000.50", 1)
        assert risk == "high"
        assert category == "number"

    def test_comma_number(self):
        risk, category = FullTextDiff._classify_diff("1,000,000", -1)
        assert risk == "high"
        assert category == "number"

    def test_date_detected_as_high(self):
        # Note: number regex fires before date regex in _classify_diff,
        # so dates containing digits are classified as "number" first.
        risk, category = FullTextDiff._classify_diff("2024-01-15", 1)
        assert risk == "high"
        assert category in ("number", "date")

    def test_chinese_date(self):
        risk, category = FullTextDiff._classify_diff("2024年1月15日", -1)
        assert risk == "high"
        assert category in ("number", "date")

    def test_slash_date(self):
        risk, category = FullTextDiff._classify_diff("2024/01/15", 1)
        assert risk == "high"
        assert category in ("number", "date")

    @pytest.mark.parametrize("keyword", [
        "违约金", "赔偿金", "保证金", "押金", "罚金",
        "甲方", "乙方", "违约责任", "不可抗力",
        "解除", "终止", "无效", "撤销",
        "仲裁", "诉讼", "管辖", "保密", "知识产权",
        "生效", "履行", "交付", "验收",
    ])
    def test_legal_keyword_detected_as_high(self, keyword):
        risk, category = FullTextDiff._classify_diff(keyword, -1)
        assert risk == "high"
        assert category == "keyword"

    def test_pure_whitespace_is_low(self):
        risk, category = FullTextDiff._classify_diff("   \t  ", -1)
        assert risk == "low"
        assert category == "text"

    def test_punctuation_only_is_low(self):
        risk, category = FullTextDiff._classify_diff("，。；：！", 1)
        assert risk == "low"
        assert category == "text"

    def test_mixed_punctuation_whitespace_is_low(self):
        risk, category = FullTextDiff._classify_diff("  ...  ", -1)
        assert risk == "low"
        assert category == "text"

    def test_normal_text_is_medium(self):
        risk, category = FullTextDiff._classify_diff("普通文本内容", -1)
        assert risk == "medium"
        assert category == "text"

    def test_english_text_is_medium(self):
        risk, category = FullTextDiff._classify_diff("This is a normal sentence.", 1)
        assert risk == "medium"
        assert category == "text"


class TestSummary:
    """摘要统计测试"""

    @pytest.fixture
    def differ(self):
        return FullTextDiff()

    def test_summary_insertions_count(self, differ):
        word_text = "甲方"
        pdf_text = "甲乙双方"
        result = differ.compare(word_text, pdf_text)
        assert result["summary"]["insertions"] >= 1

    def test_summary_deletions_count(self, differ):
        word_text = "甲乙双方"
        pdf_text = "甲方"
        result = differ.compare(word_text, pdf_text)
        assert result["summary"]["deletions"] >= 1

    def test_has_risk_when_number_diff(self, differ):
        word_text = "金额100000元"
        pdf_text = "金额50000元"
        result = differ.compare(word_text, pdf_text)
        assert result["summary"]["has_risk"] is True

    def test_no_risk_when_only_punctuation_diff(self, differ):
        word_text = "合同条款"
        pdf_text = "合同条款。"
        result = differ.compare(word_text, pdf_text)
        # punctuation-only diffs are "low", so has_risk should be False
        # (has_risk only True when risk_level == "high")
        assert result["summary"]["has_risk"] is False

    def test_total_changes_equals_sum(self, differ):
        word_text = "甲乙双方签订合同，金额100000元。"
        pdf_text = "甲方签订合同，金额150000元，违约金为5%。"
        result = differ.compare(word_text, pdf_text)
        assert result["summary"]["total_changes"] == (
            result["summary"]["insertions"] + result["summary"]["deletions"]
        )


class TestGenerateHighlightedHtml:
    """HTML 生成测试"""

    @pytest.fixture
    def differ(self):
        return FullTextDiff()

    def test_html_contains_diff_structure(self, differ):
        html = differ.generate_highlighted_html("合同金额100000元", "合同金额150000元")
        assert '<div class="full-text-diff">' in html
        assert '</div>' in html

    def test_html_contains_risk_class(self, differ):
        html = differ.generate_highlighted_html("金额100000", "金额999999")
        assert "diff-high" in html or "diff-medium" in html or "diff-low" in html

    def test_html_contains_type_class(self, differ):
        html = differ.generate_highlighted_html("甲方", "甲乙双方")
        assert "diff-insert" in html or "diff-delete" in html

    def test_html_same_text_no_diffs(self, differ):
        html = differ.generate_highlighted_html("相同文本", "相同文本")
        assert '<div class="full-text-diff">' in html

    def test_html_with_chinese_content(self, differ):
        html = differ.generate_highlighted_html(
            "合同金额为壹拾万元整",
            "合同金额为壹拾伍万元整"
        )
        assert isinstance(html, str)
        assert len(html) > 0

    def test_max_diffs_limited(self, differ):
        # Generate many diffs by comparing completely different texts
        word_text = "第一条 第二条 第三条 第四条 第五条 第六条 第七条"
        pdf_text = "第一章 第二章 第三章 第四章 第五章 第六章 第七章"
        html = differ.generate_highlighted_html(word_text, pdf_text, max_diffs=2)
        # Check diff-item count does not exceed max_diffs
        diff_count = html.count('<div class="diff-item')
        assert diff_count <= 2


class TestEscapeHtml:
    """HTML 转义测试"""

    def test_ampersand(self):
        result = FullTextDiff._escape_html("A & B")
        assert result == "A &amp; B"

    def test_lt(self):
        result = FullTextDiff._escape_html("<tag>")
        assert result == "&lt;tag&gt;"

    def test_gt(self):
        result = FullTextDiff._escape_html("a > b")
        assert "&gt;" in result

    def test_normal_text_unchanged(self):
        result = FullTextDiff._escape_html("普通中文文本")
        assert result == "普通中文文本"

    def test_mixed_special_chars(self):
        result = FullTextDiff._escape_html('<div class="test">&copy;</div>')
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result