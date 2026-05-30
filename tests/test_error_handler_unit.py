"""
单元测试 — error_handler 模块
验证错误类型、审计追踪、降级装饰器
"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from error_handler import (
    ContractComparatorError,
    ComparisonError,
    ConfigurationError,
    ExportError,
    ExtractionError,
    FileValidationError,
    OCRError,
    AuditTrail,
    Severity,
    fallback_on_error,
)


class TestErrorTypes(unittest.TestCase):
    """错误类型测试"""

    def test_base_error_inheritance(self):
        """所有自定义错误应继承自 ContractComparatorError"""
        self.assertTrue(issubclass(ComparisonError, ContractComparatorError))
        self.assertTrue(issubclass(ConfigurationError, ContractComparatorError))
        self.assertTrue(issubclass(ExportError, ContractComparatorError))
        self.assertTrue(issubclass(ExtractionError, ContractComparatorError))
        self.assertTrue(issubclass(FileValidationError, ContractComparatorError))
        self.assertTrue(issubclass(OCRError, ContractComparatorError))

    def test_error_message(self):
        """错误消息应包含原始信息"""
        err = ComparisonError("比对失败")
        self.assertIn("比对失败", str(err))

    def test_error_with_severity(self):
        """错误应支持严重程度参数"""
        err = ComparisonError("比对失败", severity=Severity.ERROR)
        self.assertIsNotNone(err)

    def test_error_with_error_code(self):
        """错误应支持错误码"""
        err = ComparisonError("比对失败", error_code="E004")
        self.assertIsNotNone(err)


class TestSeverity(unittest.TestCase):
    """严重程度枚举测试"""

    def test_severity_has_critical(self):
        """验证 CRITICAL 级别"""
        self.assertIsNotNone(Severity.CRITICAL)

    def test_severity_has_error(self):
        """验证 ERROR 级别"""
        self.assertIsNotNone(Severity.ERROR)

    def test_severity_has_warning(self):
        """验证 WARNING 级别"""
        self.assertIsNotNone(Severity.WARNING)


class TestAuditTrail(unittest.TestCase):
    """审计追踪测试（AuditTrail 为单例）"""

    def test_audit_trail_singleton(self):
        """AuditTrail 应为单例模式"""
        trail1 = AuditTrail()
        trail2 = AuditTrail()
        self.assertIs(trail1, trail2)

    def test_audit_trail_start_operation(self):
        """审计追踪开始操作"""
        trail = AuditTrail()
        op_id = trail.start_operation("test_op", {"key": "value"})
        self.assertIsNotNone(op_id)

    def test_audit_trail_complete_operation(self):
        """审计追踪完成操作"""
        trail = AuditTrail()
        op_id = trail.start_operation("test_op", {"key": "value"})
        trail.complete_operation(op_id, {"result": "success"})

    def test_audit_trail_fail_operation(self):
        """审计追踪失败操作"""
        trail = AuditTrail()
        op_id = trail.start_operation("test_op", {"key": "value"})
        trail.fail_operation(op_id, "测试错误")

    def test_audit_trail_get_summary(self):
        """审计追踪摘要"""
        trail = AuditTrail()
        op_id = trail.start_operation("test_op", {"key": "value"})
        trail.complete_operation(op_id, {"result": "success"})
        summary = trail.get_summary()
        self.assertIsNotNone(summary)


class TestFallbackOnError(unittest.TestCase):
    """降级装饰器测试"""

    def test_fallback_on_error_returns_default(self):
        """fallback_on_error 应在异常时返回默认值"""
        @fallback_on_error(fallback_value="fallback")
        def failing_function():
            raise ValueError("测试错误")

        result = failing_function()
        self.assertEqual(result, "fallback")

    def test_fallback_on_error_success(self):
        """fallback_on_error 在正常执行时应返回原值"""
        @fallback_on_error(fallback_value="fallback")
        def success_function():
            return "success"

        result = success_function()
        self.assertEqual(result, "success")


if __name__ == "__main__":
    unittest.main(verbosity=2)
