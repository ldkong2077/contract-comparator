"""
Config 配置模块单元测试
测试各配置段的存在性、默认值、多 Provider 配置、图片格式、行业配置、Excel 配置
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from config import (
    OCR_CONFIG,
    PDF_CONFIG,
    FIELD_CONFIG,
    COMPARATOR_CONFIG,
    DATABASE_CONFIG,
    LLM_CONFIG,
    IMAGE_CONFIG,
    INDUSTRY_CONFIG,
    EXCEL_CONFIG,
    AUTH_CONFIG,
    OUTPUT_CONFIG,
    UPLOAD_CONFIG,
    LOG_CONFIG,
)


class TestConfigSectionsExist:
    """配置段存在性测试"""

    def test_ocr_config_exists(self):
        """OCR_CONFIG 应存在且为字典"""
        assert isinstance(OCR_CONFIG, dict)

    def test_pdf_config_exists(self):
        """PDF_CONFIG 应存在且为字典"""
        assert isinstance(PDF_CONFIG, dict)

    def test_field_config_exists(self):
        """FIELD_CONFIG 应存在且为字典"""
        assert isinstance(FIELD_CONFIG, dict)

    def test_comparator_config_exists(self):
        """COMPARATOR_CONFIG 应存在且为字典"""
        assert isinstance(COMPARATOR_CONFIG, dict)

    def test_database_config_exists(self):
        """DATABASE_CONFIG 应存在且为字典"""
        assert isinstance(DATABASE_CONFIG, dict)

    def test_llm_config_exists(self):
        """LLM_CONFIG 应存在且为字典"""
        assert isinstance(LLM_CONFIG, dict)

    def test_image_config_exists(self):
        """IMAGE_CONFIG 应存在且为字典"""
        assert isinstance(IMAGE_CONFIG, dict)

    def test_industry_config_exists(self):
        """INDUSTRY_CONFIG 应存在且为字典"""
        assert isinstance(INDUSTRY_CONFIG, dict)

    def test_excel_config_exists(self):
        """EXCEL_CONFIG 应存在且为字典"""
        assert isinstance(EXCEL_CONFIG, dict)

    def test_auth_config_exists(self):
        """AUTH_CONFIG 应存在且为字典"""
        assert isinstance(AUTH_CONFIG, dict)

    def test_output_config_exists(self):
        """OUTPUT_CONFIG 应存在且为字典"""
        assert isinstance(OUTPUT_CONFIG, dict)

    def test_upload_config_exists(self):
        """UPLOAD_CONFIG 应存在且为字典"""
        assert isinstance(UPLOAD_CONFIG, dict)

    def test_log_config_exists(self):
        """LOG_CONFIG 应存在且为字典"""
        assert isinstance(LOG_CONFIG, dict)


class TestDatabaseConfigDefaults:
    """数据库配置默认值测试"""

    def test_database_enabled_default(self):
        """数据库默认应启用"""
        assert "enabled" in DATABASE_CONFIG
        assert isinstance(DATABASE_CONFIG["enabled"], bool)

    def test_database_db_path_default(self):
        """数据库路径应有默认值"""
        assert "db_path" in DATABASE_CONFIG
        assert DATABASE_CONFIG["db_path"] != ""

    def test_database_auto_cleanup_tasks_hours(self):
        """任务自动清理时间应有默认值"""
        assert "auto_cleanup_tasks_hours" in DATABASE_CONFIG
        assert DATABASE_CONFIG["auto_cleanup_tasks_hours"] > 0

    def test_database_auto_cleanup_audit_days(self):
        """审计日志自动清理天数应有默认值"""
        assert "auto_cleanup_audit_days" in DATABASE_CONFIG
        assert DATABASE_CONFIG["auto_cleanup_audit_days"] > 0

    def test_database_wal_mode(self):
        """WAL 模式应默认启用"""
        assert "wal_mode" in DATABASE_CONFIG
        assert DATABASE_CONFIG["wal_mode"] is True


class TestLLMConfigMultiProvider:
    """LLM 多 Provider 配置测试"""

    def test_llm_enabled_default(self):
        """LLM 默认应禁用"""
        assert "enabled" in LLM_CONFIG
        assert isinstance(LLM_CONFIG["enabled"], bool)

    def test_llm_default_provider(self):
        """应有默认 Provider 设置"""
        assert "default_provider" in LLM_CONFIG
        assert LLM_CONFIG["default_provider"] in ("ollama", "claude")

    def test_llm_ollama_config(self):
        """Ollama 配置段应存在"""
        assert "ollama" in LLM_CONFIG
        ollama = LLM_CONFIG["ollama"]
        assert "base_url" in ollama
        assert "model" in ollama
        assert "timeout" in ollama
        assert ollama["timeout"] > 0

    def test_llm_claude_config(self):
        """Claude 配置段应存在"""
        assert "claude" in LLM_CONFIG
        claude = LLM_CONFIG["claude"]
        assert "model" in claude
        assert "max_tokens" in claude
        assert "timeout" in claude
        assert claude["max_tokens"] > 0
        assert claude["timeout"] > 0

    def test_llm_ollama_base_url_format(self):
        """Ollama base_url 应为 HTTP URL"""
        base_url = LLM_CONFIG["ollama"]["base_url"]
        assert base_url.startswith("http")


class TestImageConfigFormats:
    """图片配置格式测试"""

    def test_supported_formats_not_empty(self):
        """支持的图片格式列表不应为空"""
        assert "supported_formats" in IMAGE_CONFIG
        assert len(IMAGE_CONFIG["supported_formats"]) > 0

    def test_supported_formats_common_types(self):
        """应包含常见图片格式"""
        formats = IMAGE_CONFIG["supported_formats"]
        assert ".png" in formats
        assert ".jpg" in formats
        assert ".jpeg" in formats

    def test_max_image_size_mb(self):
        """最大图片大小应有默认值"""
        assert "max_image_size_mb" in IMAGE_CONFIG
        assert IMAGE_CONFIG["max_image_size_mb"] > 0


class TestIndustryConfig:
    """行业配置测试"""

    def test_default_industry(self):
        """默认行业应为 general"""
        assert "default_industry" in INDUSTRY_CONFIG
        assert INDUSTRY_CONFIG["default_industry"] == "general"

    def test_available_industries(self):
        """可用行业列表应包含所有支持的行业"""
        assert "available_industries" in INDUSTRY_CONFIG
        industries = INDUSTRY_CONFIG["available_industries"]
        assert "general" in industries
        assert "construction" in industries
        assert "leasing" in industries
        assert "procurement" in industries
        assert "labor" in industries

    def test_available_industries_is_list(self):
        """可用行业列表应为列表类型"""
        assert isinstance(INDUSTRY_CONFIG["available_industries"], list)


class TestExcelConfig:
    """Excel 配置测试"""

    def test_excel_enabled(self):
        """Excel 比对应默认启用"""
        assert "enabled" in EXCEL_CONFIG
        assert EXCEL_CONFIG["enabled"] is True

    def test_numeric_tolerance(self):
        """数值容差应有默认值"""
        assert "numeric_tolerance" in EXCEL_CONFIG
        assert EXCEL_CONFIG["numeric_tolerance"] > 0

    def test_fuzzy_column_match_threshold(self):
        """模糊列匹配阈值应在合理范围"""
        assert "fuzzy_column_match_threshold" in EXCEL_CONFIG
        threshold = EXCEL_CONFIG["fuzzy_column_match_threshold"]
        assert 0 < threshold <= 1.0

    def test_key_column_uniqueness_threshold(self):
        """关键列唯一性阈值应在合理范围"""
        assert "key_column_uniqueness_threshold" in EXCEL_CONFIG
        threshold = EXCEL_CONFIG["key_column_uniqueness_threshold"]
        assert 0 < threshold <= 1.0
