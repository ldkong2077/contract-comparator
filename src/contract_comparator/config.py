"""
配置参数
支持环境变量覆盖，支持 pydantic-settings 方式加载
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional


# === 日志配置 ===
def setup_logging(level: int = logging.INFO) -> None:
    """初始化全局日志配置"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


LOG_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),  # DEBUG / INFO / WARNING / ERROR
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
}


# === OCR 配置 ===
OCR_CONFIG = {
    "text_score": float(os.getenv("OCR_TEXT_SCORE", "0.5")),
    "use_det": True,
    "use_cls": True,
    "use_rec": True,
    "lang_type": "ch",
    "rec_score_thresh": float(os.getenv("OCR_SCORE_THRESH", "0.5")),
    "preprocess": {
        "enable": os.getenv("OCR_PREPROCESS_ENABLE", "true").lower() == "true",
        "denoise": True,
        "sharpen": False,
        "contrast_enhance": False,
        "deskew": True,
    },
}

# === PDF 转图片配置 ===
PDF_CONFIG = {
    "dpi": int(os.getenv("PDF_DPI", "300")),
    "zoom": float(os.getenv("PDF_ZOOM", "2.0")),
}

# === 字段抽取配置 ===
FIELD_CONFIG = {
    "number_patterns": [
        r'\d{1,3}(?:,\d{3})*(?:\.\d+)?',
        r'\d+%',
    ],
    "date_patterns": [
        r'\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}[日号]?',
        r'\d{4}年\s*\d{1,2}月\s*\d{1,2}日',
        r'\d{1,2}[-/.月]\d{1,2}[日号]?\s*\d{4}年?',
        r'\d{4}年\d{1,2}月\d{1,2}日',
    ],
    "amount_word_patterns": [
        r'[零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元整角分]+',
    ],
    "amount_keywords": [
        '¥', '￥', '$',
        '金额', '总价', '合计', '总额', '总计',
        '费用', '价款', '报酬', '单价',
        '违约金', '赔偿金', '保证金', '押金', '罚金',
        '包干费用', '合同总价', '合同总额', '合同费用',
        '含税', '不含税', '增值税',
        '元',
    ],
}

# === 比对配置 ===
COMPARATOR_CONFIG = {
    "number_tolerance": float(os.getenv("NUMBER_TOLERANCE", "0.01")),
    "number_rel_tolerance": float(os.getenv("NUMBER_REL_TOLERANCE", "0.00001")),
    "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", "0.85")),
    "min_segment_length": 4,
}

# === SQLite 数据库配置 ===
DATABASE_CONFIG = {
    "enabled": os.getenv("DB_ENABLED", "true").lower() == "true",
    "db_path": os.getenv("DB_PATH", "./data/contract_comparator.db"),
    "auto_cleanup_tasks_hours": int(os.getenv("DB_CLEANUP_TASKS_HOURS", "24")),
    "auto_cleanup_audit_days": int(os.getenv("DB_CLEANUP_AUDIT_DAYS", "90")),
    "auto_cleanup_interval_seconds": int(os.getenv("DB_CLEANUP_INTERVAL", "3600")),
    "wal_mode": True,
}

# === LLM 配置（支持多 Provider：Ollama 本地模型 + Claude API）===
LLM_CONFIG = {
    "enabled": os.getenv("LLM_ENABLED", "false").lower() == "true",
    "default_provider": os.getenv("LLM_DEFAULT_PROVIDER", "ollama"),
    "ollama": {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "model": os.getenv("OLLAMA_MODEL", "qwen3.5-0.8b"),
        "timeout": int(os.getenv("OLLAMA_TIMEOUT", "30")),
    },
    "claude": {
        "api_key": os.getenv("CLAUDE_API_KEY", ""),
        "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        "max_tokens": int(os.getenv("CLAUDE_MAX_TOKENS", "4096")),
        "timeout": int(os.getenv("CLAUDE_TIMEOUT", "60")),
    },
}

# === 图片 OCR 配置 ===
IMAGE_CONFIG = {
    "supported_formats": [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"],
    "max_image_size_mb": int(os.getenv("MAX_IMAGE_SIZE_MB", "20")),
}

# === 行业预设配置 ===
INDUSTRY_CONFIG = {
    "default_industry": os.getenv("DEFAULT_INDUSTRY", "general"),
    "available_industries": ["general", "construction", "leasing", "procurement", "labor"],
}

# === Excel 比对配置 ===
EXCEL_CONFIG = {
    "enabled": True,
    "numeric_tolerance": float(os.getenv("EXCEL_NUMERIC_TOLERANCE", "0.01")),
    "fuzzy_column_match_threshold": 0.7,
    "key_column_uniqueness_threshold": 0.8,
}

# === 认证与权限配置 ===
AUTH_CONFIG = {
    "api_keys_file": os.getenv("API_KEYS_FILE", "./config/api_keys.json"),
    "enabled": os.getenv("AUTH_ENABLED", "true").lower() == "true",
    "rate_limit": {
        "enabled": os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        "requests_per_minute": int(os.getenv("RATE_LIMIT_RPM", "30")),
        "burst": int(os.getenv("RATE_LIMIT_BURST", "5")),
    },
}

# === 输出配置 ===
OUTPUT_CONFIG = {
    "output_dir": os.getenv("OUTPUT_DIR", "./output"),
    "save_preprocessed_images": os.getenv("SAVE_PREPROCESSED", "true").lower() == "true",
    "save_ocr_results": os.getenv("SAVE_OCR_RESULTS", "true").lower() == "true",
    "report_format": os.getenv("REPORT_FORMAT", "text"),
}

# === 上传配置 ===
UPLOAD_CONFIG = {
    "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", "50")),
    "max_batch_pairs": int(os.getenv("MAX_BATCH_PAIRS", "10")),
    "allowed_extensions": [".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"],
}
