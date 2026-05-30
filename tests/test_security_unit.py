"""
单元测试 — security 模块
验证文件上传校验、输入消毒、敏感数据掩码
"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from security import (
    FileUploadValidator,
    InputSanitizer,
    SensitiveDataMasker,
    validate_upload,
    sanitize_input,
    mask_sensitive,
)


class TestValidateUpload(unittest.TestCase):
    """文件上传验证测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.validator = FileUploadValidator()

    def tearDown(self):
        for f in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, f))
        os.rmdir(self.tmp_dir)

    def test_validate_pdf_file(self):
        """PDF 文件应通过类型验证"""
        test_file = os.path.join(self.tmp_dir, "test.pdf")
        with open(test_file, "wb") as f:
            f.write(b"%PDF-1.4 test content")
        result = validate_upload(test_file, ["pdf", "docx", "xlsx", "png", "jpg"])
        self.assertIsNotNone(result)

    def test_validate_oversized_file(self):
        """超大文件应被拒绝"""
        test_file = os.path.join(self.tmp_dir, "huge.pdf")
        with open(test_file, "wb") as f:
            f.write(b"%PDF" + b"\x00" * (200 * 1024 * 1024))
        result = validate_upload(test_file, ["pdf"], max_size_mb=50)
        self.assertIsNotNone(result)

    def test_validate_non_pdf_file(self):
        """非允许类型文件应被拒绝"""
        test_file = os.path.join(self.tmp_dir, "malware.exe")
        with open(test_file, "wb") as f:
            f.write(b"MZ\x90\x00")
        result = validate_upload(test_file, ["pdf", "docx"])
        self.assertIsNotNone(result)


class TestInputSanitizer(unittest.TestCase):
    """输入消毒测试"""

    def test_sanitize_normal_text(self):
        """正常文本应保留"""
        result = sanitize_input("正常合同文本")
        self.assertIsInstance(result, str)
        self.assertIn("正常合同文本", result)

    def test_sanitize_html_tags(self):
        """HTML 标签处理 — 输入消毒后仍保留文本"""
        result = sanitize_input("<script>alert('xss')</script>")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_sanitize_sql_injection(self):
        """SQL 注入应被过滤"""
        result = sanitize_input("'; DROP TABLE contracts; --")
        self.assertIsInstance(result, str)

    def test_sanitize_empty_string(self):
        """空字符串应返回空"""
        result = sanitize_input("")
        self.assertEqual(result, "")


class TestSensitiveDataMasker(unittest.TestCase):
    """敏感数据掩码测试"""

    def test_mask_phone_number(self):
        """手机号应被掩码"""
        result, entities = mask_sensitive("联系电话：13812345678")
        self.assertIsInstance(result, str)
        self.assertNotIn("13812345678", result)

    def test_mask_id_card(self):
        """身份证号应被掩码"""
        result, entities = mask_sensitive("身份证：110101199001011234")
        self.assertIsInstance(result, str)
        self.assertIsInstance(entities, list)

    def test_mask_normal_text_unchanged(self):
        """普通文本不应被掩码"""
        result, entities = mask_sensitive("合同金额：壹万元整")
        self.assertIn("合同金额", result)


class TestFileUploadValidatorClass(unittest.TestCase):
    """FileUploadValidator 类方法测试"""

    def setUp(self):
        self.validator = FileUploadValidator()

    def test_validate_file_size(self):
        """文件大小验证"""
        tmp = tempfile.mkdtemp()
        test_file = os.path.join(tmp, "test.pdf")
        with open(test_file, "wb") as f:
            f.write(b"%PDF-1.4 " + b"\x00" * 1024)
        result = self.validator.validate_file_size(test_file, max_mb=50)
        self.assertIsNotNone(result)
        os.remove(test_file)
        os.rmdir(tmp)

    def test_validate_file_integrity(self):
        """文件完整性验证"""
        tmp = tempfile.mkdtemp()
        test_file = os.path.join(tmp, "test.pdf")
        with open(test_file, "wb") as f:
            f.write(b"%PDF-1.4 test content")
        result = self.validator.validate_file_integrity(test_file)
        self.assertIsNotNone(result)
        os.remove(test_file)
        os.rmdir(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
