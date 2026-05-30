# Contract Document Comparator / 合同扫描件比对工具
# Intelligent document comparison engine — field-level OCR diff, Excel analysis, LLM semantic evaluation

from contract_comparator.config import *
from contract_comparator.security import (
    FileUploadValidator, SensitiveDataMasker, InputSanitizer, AuditLogger,
    SecureTempFileManager, validate_upload, mask_sensitive, sanitize_input,
)
from contract_comparator.auth import APIKeyManager, RBACManager, RateLimiter
from contract_comparator.database import DatabaseManager
from contract_comparator.error_handler import (
    ComparisonError, OCRError, ExtractionError, FileValidationError, ExportError, ConfigurationError,
    StructuredLogger, AuditTrail,
)
from contract_comparator.profiles import ProfileManager

from contract_comparator.engine.pdf_processor import pdf_to_images, get_pdf_page_count
from contract_comparator.engine.word_parser import WordParser
from contract_comparator.engine.ocr.engine import OCREngine
from contract_comparator.engine.ocr.industry import IndustryFieldRecognizer

from contract_comparator.compare.comparator import Comparator
from contract_comparator.compare.field_extractor import FieldExtractor
from contract_comparator.compare.full_text_diff import FullTextDiff
from contract_comparator.compare.excel_comparator import ExcelComparator

from contract_comparator.llm.llm_engine import LLMEngine

from contract_comparator.export.report_generator import ReportGenerator

__version__ = "4.0.0"
__author__ = "Contract Comparator Team"
__license__ = "MIT"
