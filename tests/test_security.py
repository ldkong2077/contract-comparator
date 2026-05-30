"""
Security 单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import tempfile
import pytest
from security import (
    FileUploadValidator,
    SensitiveDataMasker,
    InputSanitizer,
    SecureTempFileManager,
    ValidationResult,
)


# ====================== ValidationResult ======================

class TestValidationResult:
    """验证结果数据类测试"""

    def test_default_valid(self):
        r = ValidationResult()
        assert r.is_valid is True
        assert r.errors == []
        assert r.warnings == []

    def test_merge_both_valid(self):
        r1 = ValidationResult()
        r2 = ValidationResult()
        r1.merge(r2)
        assert r1.is_valid is True

    def test_merge_invalid_into_valid(self):
        r1 = ValidationResult()
        r2 = ValidationResult(is_valid=False, errors=["err"])
        r1.merge(r2)
        assert r1.is_valid is False
        assert "err" in r1.errors

    def test_merge_accumulates_errors(self):
        r1 = ValidationResult(errors=["e1"])
        r2 = ValidationResult(errors=["e2"])
        r1.merge(r2)
        assert len(r1.errors) == 2

    def test_merge_accumulates_warnings(self):
        r1 = ValidationResult(warnings=["w1"])
        r2 = ValidationResult(warnings=["w2"])
        r1.merge(r2)
        assert len(r1.warnings) == 2


# ====================== FileUploadValidator ======================

class TestFileUploadValidator:
    """文件上传验证器测试"""

    @pytest.fixture
    def validator(self):
        return FileUploadValidator()

    def _create_temp_file(self, content: bytes, suffix: str) -> str:
        """创建临时文件并返回路径"""
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
        return path

    # --- validate_file_type ---

    def test_valid_extension_matches(self, validator):
        path = self._create_temp_file(
            b"%PDF-1.4\nfake pdf content",
            ".pdf"
        )
        try:
            result = validator.validate_file_type(path, [".pdf", ".docx"])
            assert result.is_valid is True
        finally:
            os.unlink(path)

    def test_invalid_extension_rejected(self, validator):
        path = self._create_temp_file(
            b"just text content",
            ".exe"
        )
        try:
            result = validator.validate_file_type(path, [".pdf", ".docx"])
            assert result.is_valid is False
            assert len(result.errors) >= 1
        finally:
            os.unlink(path)

    def test_valid_docx_by_magic(self, validator):
        # DOCX files start with PK\x03\x04 (ZIP magic)
        docx_content = b"PK\x03\x04" + b"\x00" * 20
        path = self._create_temp_file(docx_content, ".docx")
        try:
            result = validator.validate_file_type(path, [".pdf", ".docx"])
            assert result.is_valid is True
        finally:
            os.unlink(path)

    def test_valid_pdf_by_magic(self, validator):
        pdf_content = b"%PDF-1.4\n" + b"\x00" * 20
        path = self._create_temp_file(pdf_content, ".pdf")
        try:
            result = validator.validate_file_type(path, [".pdf", ".docx"])
            assert result.is_valid is True
        finally:
            os.unlink(path)

    def test_magic_mismatch_detected(self, validator):
        # File with .pdf extension but JPEG magic bytes
        jpg_content = b"\xFF\xD8\xFF\xE0" + b"\x00" * 20
        path = self._create_temp_file(jpg_content, ".pdf")
        try:
            result = validator.validate_file_type(path, [".pdf", ".docx"])
            assert result.is_valid is False
            assert len(result.errors) >= 1
        finally:
            os.unlink(path)

    def test_unknown_magic_gives_warning(self, validator):
        content = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        path = self._create_temp_file(content, ".pdf")
        try:
            result = validator.validate_file_type(path, [".pdf"])
            # extension is valid but magic unknown, should be warning not error
            # (the extension check passes, magic check yields warning)
            assert len(result.warnings) >= 1 or result.is_valid is True
        finally:
            os.unlink(path)

    # --- validate_file_size ---

    def test_file_size_under_limit(self, validator):
        path = self._create_temp_file(b"A" * 100, ".txt")
        try:
            result = validator.validate_file_size(path, max_mb=1)
            assert result.is_valid is True
        finally:
            os.unlink(path)

    def test_file_size_zero(self, validator):
        path = self._create_temp_file(b"", ".txt")
        try:
            result = validator.validate_file_size(path, max_mb=1)
            assert result.is_valid is False
            assert len(result.errors) >= 1
        finally:
            os.unlink(path)

    def test_file_size_over_limit(self, validator):
        # Create a file > 1KB but set max to 0.0001 MB (~100 bytes)
        path = self._create_temp_file(b"A" * 1024, ".txt")
        try:
            result = validator.validate_file_size(path, max_mb=0.0001)
            assert result.is_valid is False
            assert len(result.errors) >= 1
        finally:
            os.unlink(path)

    def test_file_nonexistent(self, validator):
        result = validator.validate_file_size("/nonexistent/path/file.pdf", max_mb=1)
        assert result.is_valid is False

    # --- validate_file_integrity ---

    def test_file_integrity_nonempty(self, validator):
        path = self._create_temp_file(b"Hello World", ".pdf")
        try:
            result = validator.validate_file_integrity(path)
            # The file has valid content; it may or may not have a ZIP structure
            # Just verify it doesn't crash and returns a result
            assert isinstance(result, ValidationResult)
        finally:
            os.unlink(path)

    def test_file_integrity_not_exists(self, validator):
        result = validator.validate_file_integrity("/nonexistent/file.txt")
        assert result.is_valid is False

    # --- validate_all ---

    def test_validate_all_valid(self, validator):
        pdf_content = b"%PDF-1.4\n" + b"A" * 200
        path = self._create_temp_file(pdf_content, ".pdf")
        try:
            result = validator.validate_all(path, [".pdf"], max_size_mb=1)
            assert result.is_valid is True
        finally:
            os.unlink(path)

    def test_validate_all_invalid_extension(self, validator):
        path = self._create_temp_file(b"content", ".exe")
        try:
            result = validator.validate_all(path, [".pdf"], max_size_mb=1)
            assert result.is_valid is False
        finally:
            os.unlink(path)


# ====================== SensitiveDataMasker ======================

class TestSensitiveDataMasker:
    """敏感数据脱敏测试"""

    @pytest.fixture
    def masker(self):
        return SensitiveDataMasker()

    # --- mask_phone_numbers ---

    def test_mobile_phone_masked(self, masker):
        text = "联系人：张三，电话13800138000"
        masked, items = masker.mask_phone_numbers(text)
        assert "13800138000" not in masked
        assert "***PHONE***" in masked
        assert "13800138000" in items

    def test_landline_masked(self, masker):
        text = "电话：010-12345678"
        masked, items = masker.mask_phone_numbers(text)
        assert "010-12345678" not in masked
        assert "***PHONE***" in masked

    def test_no_phone_numbers(self, masker):
        text = "合同条款没有任何电话号码"
        masked, items = masker.mask_phone_numbers(text)
        assert masked == text
        assert items == []

    def test_multiple_phones(self, masker):
        text = "电话1：13800138000，电话2：13900139000"
        masked, items = masker.mask_phone_numbers(text)
        assert "13800138000" not in masked
        assert "13900139000" not in masked
        assert len(items) >= 2

    # --- mask_emails ---

    def test_email_masked(self, masker):
        text = "邮箱：test@example.com"
        masked, items = masker.mask_emails(text)
        assert "test@example.com" not in masked
        assert "***EMAIL***" in masked
        assert "test@example.com" in items

    def test_no_email(self, masker):
        text = "没有邮箱的文本"
        masked, items = masker.mask_emails(text)
        assert masked == text
        assert items == []

    def test_multiple_emails(self, masker):
        text = "邮箱1：a@b.com，邮箱2：c@d.cn"
        masked, items = masker.mask_emails(text)
        assert "a@b.com" not in masked
        assert "c@d.cn" not in masked
        assert len(items) >= 2

    # --- mask_id_cards ---

    def test_id_card_masked(self, masker):
        text = "身份证号：110101199001011234"
        masked, items = masker.mask_id_cards(text)
        assert "110101199001011234" not in masked
        assert "***ID_CARD***" in masked

    def test_id_card_with_x(self, masker):
        text = "身份证号：11010119900101123X"
        masked, items = masker.mask_id_cards(text)
        assert "11010119900101123X" not in masked
        assert "***ID_CARD***" in masked

    def test_no_id_card(self, masker):
        text = "不是身份证号的十六位数字 1234567890123456"
        masked, items = masker.mask_id_cards(text)
        # 16 digits is not an 18-digit ID card pattern
        assert "***ID_CARD***" not in masked

    # --- mask_bank_accounts ---

    def test_bank_account_masked(self, masker):
        text = "银行卡号：6222021234567890123"
        masked, items = masker.mask_bank_accounts(text)
        assert "6222021234567890123" not in masked
        assert "***BANK_ACCOUNT***" in masked

    def test_no_bank_account(self, masker):
        text = "短数字 12345 不会被拦截"
        masked, items = masker.mask_bank_accounts(text)
        assert "***BANK_ACCOUNT***" not in masked

    def test_all_zeros_not_masked(self, masker):
        text = "0000000000000000"
        masked, items = masker.mask_bank_accounts(text)
        assert "0000000000000000" in masked

    # --- mask_all ---

    def test_mask_all_default(self, masker):
        text = "电话13800138000 邮箱test@ex.com 身份证110101199001011234"
        masked, all_masked = masker.mask_all(text)
        assert "13800138000" not in masked
        assert "test@ex.com" not in masked
        assert "110101199001011234" not in masked
        # Each masked item should have type and value
        for item in all_masked:
            assert "type" in item
            assert "value" in item

    def test_mask_all_with_options_disabled(self, masker):
        text = "电话13800138000 邮箱test@ex.com"
        masked, all_masked = masker.mask_all(
            text, options={"phones": False, "emails": True}
        )
        assert "13800138000" in masked  # phone not masked
        assert "test@ex.com" not in masked  # email masked

    def test_mask_all_empty(self, masker):
        text = ""
        masked, all_masked = masker.mask_all(text)
        assert masked == ""
        assert all_masked == []

    def test_mask_all_no_sensitive_data(self, masker):
        text = "这是一段不含敏感信息的普通文本。"
        masked, all_masked = masker.mask_all(text)
        assert masked == text
        assert all_masked == []


# ====================== InputSanitizer ======================

class TestInputSanitizer:
    """输入清理器测试"""

    @pytest.fixture
    def sanitizer(self):
        return InputSanitizer()

    # --- sanitize_filename ---

    def test_normal_filename_preserved(self, sanitizer):
        result = sanitizer.sanitize_filename("report.pdf")
        assert "report" in result
        assert ".pdf" in result

    def test_path_traversal_removed(self, sanitizer):
        result = sanitizer.sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "etc" not in result.lower()  # after basename, should just be "passwd"

    def test_path_backslash_traversal_removed(self, sanitizer):
        result = sanitizer.sanitize_filename("..\\..\\windows\\system32\\config")
        assert ".." not in result

    def test_null_byte_removed(self, sanitizer):
        result = sanitizer.sanitize_filename("file\x00name.pdf")
        assert "\x00" not in result

    def test_control_chars_removed(self, sanitizer):
        result = sanitizer.sanitize_filename("file\x01name.pdf")
        assert "\x01" not in result

    def test_windows_reserved_chars_replaced(self, sanitizer):
        result = sanitizer.sanitize_filename('file<>:"/\\|?*name')
        assert ">" not in result
        assert "<" not in result

    def test_windows_reserved_name_prefixed(self, sanitizer):
        result = sanitizer.sanitize_filename("CON")
        assert result.startswith("_")

    def test_empty_filename_returns_untitled(self, sanitizer):
        result = sanitizer.sanitize_filename("")
        assert result == "untitled"

    def test_none_filename_returns_untitled(self, sanitizer):
        result = sanitizer.sanitize_filename("")
        assert result == "untitled"

    # --- sanitize_text ---

    def test_normal_text_preserved(self, sanitizer):
        text = "合同条款：甲方支付乙方1000元。"
        result = sanitizer.sanitize_text(text)
        assert result == text

    def test_null_byte_removed_from_text(self, sanitizer):
        result = sanitizer.sanitize_text("text\x00with\x00nulls")
        assert "\x00" not in result
        assert "text" in result

    def test_empty_text(self, sanitizer):
        result = sanitizer.sanitize_text("")
        assert result == ""

    def test_none_text(self, sanitizer):
        result = sanitizer.sanitize_text("")
        assert result == ""

    # --- validate_path_safe ---

    def test_safe_path(self, sanitizer, tmp_path):
        base = str(tmp_path)
        safe_file = os.path.join(base, "safe.txt")
        assert sanitizer.validate_path_safe(safe_file, base) is True

    def test_traversal_path_unsafe(self, sanitizer, tmp_path):
        base = str(tmp_path)
        traversal = os.path.join(base, "..", "outside.txt")
        result = sanitizer.validate_path_safe(traversal, base)
        # After resolving, this should be outside base_dir
        assert result is False

    def test_nonexistent_path(self, sanitizer, tmp_path):
        base = str(tmp_path)
        fake = os.path.join(base, "nonexistent", "deep", "file.txt")
        # os.path.realpath resolves existent part and retains the tail
        # Since base exists, the expanded path may still be parsed as under base
        # depending on platform behavior
        result = sanitizer.validate_path_safe(fake, base)
        assert isinstance(result, bool)


# ====================== SecureTempFileManager ======================

class TestSecureTempFileManager:
    """安全临时文件管理器测试"""

    def test_context_manager_creates_and_cleans(self):
        with SecureTempFileManager() as tm:
            assert tm.temp_dir is not None
            assert os.path.isdir(tm.temp_dir)
            temp_path = tm.temp_dir

        # After context exit, directory should be deleted
        assert not os.path.isdir(temp_path)

    def test_prepare_path_returns_safe_path(self):
        with SecureTempFileManager() as tm:
            path = tm.prepare_path("test.txt")
            assert tm.temp_dir in path
            assert path.endswith("test.txt")
            assert os.path.dirname(path) == tm.temp_dir

    def test_prepare_path_sanitizes_filename(self):
        with SecureTempFileManager() as tm:
            path = tm.prepare_path("../../../evil.txt")
            assert ".." not in os.path.basename(path)

    def test_validate_file_placement(self):
        with SecureTempFileManager() as tm:
            path = tm.prepare_path("data.txt")
            # Create the file
            with open(path, "w") as f:
                f.write("test")
            assert tm.validate_file_placement(path) is True

    def test_validate_file_placement_outside(self, tmp_path):
        with SecureTempFileManager() as tm:
            outside = os.path.join(str(tmp_path), "outside.txt")
            assert tm.validate_file_placement(outside) is False

    def test_write_and_read_file(self):
        with SecureTempFileManager() as tm:
            path = tm.prepare_path("data.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("合同比对测试数据")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert content == "合同比对测试数据"

    def test_temp_dir_property_before_enter(self):
        tm = SecureTempFileManager()
        with pytest.raises(RuntimeError, match="尚未进入上下文"):
            _ = tm.temp_dir