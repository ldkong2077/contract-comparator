"""
ErrorHandler 单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import logging
import tempfile
import time
import pytest
from error_handler import (
    ContractComparatorError,
    FileValidationError,
    OCRError,
    ExtractionError,
    ComparisonError,
    ExportError,
    ConfigurationError,
    Severity,
    StructuredLogger,
    AuditTrail,
    fallback_on_error,
    retry_on_error,
    graceful_operation,
    check_system_health,
    record_exception,
)


class TestSeverityEnum:
    """严重程度枚举测试"""

    def test_critical_value(self):
        assert Severity.CRITICAL.value == "critical"

    def test_error_value(self):
        assert Severity.ERROR.value == "error"

    def test_warning_value(self):
        assert Severity.WARNING.value == "warning"


class TestContractComparatorError:
    """基础异常类测试"""

    def test_basic_creation(self):
        exc = ContractComparatorError("E000", "测试错误")
        assert exc.error_code == "E000"
        assert str(exc) == "[E000][ERROR] 测试错误"
        assert exc.severity == Severity.ERROR
        assert exc.recoverable is False
        assert exc.original_exception is None
        assert exc.timestamp is not None

    def test_with_severity_and_recoverable(self):
        exc = ContractComparatorError(
            "E000", "可恢复警告",
            severity=Severity.WARNING, recoverable=True
        )
        assert exc.severity == Severity.WARNING
        assert exc.recoverable is True
        assert "(可恢复)" in str(exc)

    def test_chaining_with_original_exception(self):
        original = ValueError("原始错误")
        exc = ContractComparatorError(
            "E000", "包装错误",
            original_exception=original
        )
        assert exc.original_exception is original

    def test_to_dict(self):
        exc = ContractComparatorError("E000", "测试错误")
        d = exc.to_dict()
        assert d["error_code"] == "E000"
        assert d["message"] == "测试错误"
        assert d["severity"] == "error"
        assert d["recoverable"] is False
        assert "timestamp" in d
        assert d["original_exception"] is None

    def test_to_dict_with_chained_exception(self):
        exc = ContractComparatorError(
            "E000", "包装错误",
            original_exception=ValueError("inner")
        )
        d = exc.to_dict()
        assert "inner" in d["original_exception"]


class TestFileValidationError:
    """文件校验异常测试"""

    def test_basic(self):
        exc = FileValidationError("文件格式无效")
        assert exc.error_code == "E001"
        assert "文件格式无效" in str(exc)

    def test_with_file_path(self):
        exc = FileValidationError("文件不存在", file_path="/tmp/test.pdf")
        assert "/tmp/test.pdf" in str(exc)

    def test_with_reason(self):
        exc = FileValidationError("文件无效", reason="扩展名不匹配")
        assert "扩展名不匹配" in str(exc)


class TestOCRError:
    """OCR异常测试"""

    def test_basic(self):
        exc = OCRError("识别超时")
        assert exc.error_code == "E002"
        assert "[RapidOCR]" in str(exc)

    def test_custom_engine(self):
        exc = OCRError("引擎异常", engine="Tesseract")
        assert "[Tesseract]" in str(exc)


class TestExtractionError:
    """字段抽取异常测试"""

    def test_basic(self):
        exc = ExtractionError("正则编译失败")
        assert exc.error_code == "E003"
        assert exc.recoverable is True

    def test_with_field_type(self):
        exc = ExtractionError("提取失败", field_type="dates")
        assert "dates" in exc.field_type
        assert "[dates]" in str(exc)


class TestComparisonError:
    """比对逻辑异常测试"""

    def test_basic(self):
        exc = ComparisonError("比对失败")
        assert exc.error_code == "E004"


class TestExportError:
    """报告导出异常测试"""

    def test_basic(self):
        exc = ExportError("导出失败")
        assert exc.error_code == "E005"

    def test_with_output_path(self):
        exc = ExportError("写入失败", output_path="/tmp/report.pdf")
        assert "/tmp/report.pdf" in str(exc)


class TestConfigurationError:
    """配置异常测试"""

    def test_basic(self):
        exc = ConfigurationError("无效配置")
        assert exc.error_code == "E006"

    def test_with_config_key(self):
        exc = ConfigurationError("配置缺失", config_key="ocr.text_score")
        assert "ocr.text_score" in str(exc)


class TestExceptionChaining:
    """异常链测试"""

    def test_base_error_chaining(self):
        """Only ContractComparatorError supports original_exception in __init__"""
        inner = FileNotFoundError("no such file")
        exc = ContractComparatorError(
            "E999", "包装错误",
            original_exception=inner
        )
        assert exc.original_exception is inner
        d = exc.to_dict()
        assert "no such file" in d["original_exception"]

    def test_file_validation_error_with_cause(self):
        """FileValidationError doesn't accept original_exception; use raise from"""
        try:
            raise FileNotFoundError("inner cause")
        except FileNotFoundError as inner:
            exc = FileValidationError("文件不存在")
            exc.__cause__ = inner
        assert exc.__cause__ is not None

    def test_export_error_with_cause(self):
        try:
            raise PermissionError("denied")
        except PermissionError as inner:
            exc = ExportError("无法写入")
            exc.__cause__ = inner
        assert exc.__cause__ is not None


class TestStructuredLogger:
    """结构化日志器测试"""

    @pytest.fixture
    def logger(self):
        return StructuredLogger("test_module", level=logging.DEBUG)

    def test_log_operation_start(self, logger):
        op_id = logger.log_operation_start(
            "test_op", "开始测试", key1="val1"
        )
        assert isinstance(op_id, str)
        assert len(op_id) > 0
        # op_id should be a UUID
        assert len(op_id) == 36  # standard UUID

    def test_log_operation_end_with_duration(self, logger):
        op_id = logger.log_operation_start("test_op", "开始")
        time.sleep(0.01)
        logger.log_operation_end(
            "test_op", "完成", op_id=op_id, status="ok"
        )
        # No exception means success

    def test_log_operation_end_without_op_id(self, logger):
        logger.log_operation_end("test_op", "完成", status="ok")
        # Should not crash

    def test_log_warning(self, logger):
        logger.log_warning("test_op", "这是一个警告", reason="测试")

    def test_log_error(self, logger):
        logger.log_error("test_op", "发生错误", error_type="ValueError")

    def test_log_error_with_exc_info(self, logger):
        try:
            raise ValueError("test exception")
        except ValueError:
            logger.log_error("test_op", "捕获错误", exc_info=True)

    def test_log_metric(self, logger):
        logger.log_metric("test_op", "cpu_usage", 0.85, unit="percent")

    def test_log_respects_level_filter(self):
        # Logger with WARNING level should not log INFO
        logger = StructuredLogger("silent", level=logging.WARNING)
        op_id = logger.log_operation_start("test_op", "should be silent")
        logger.log_operation_end("test_op", "done", op_id=op_id)
        # Should not crash (just silently skip)


class TestAuditTrailSingleton:
    """审计追踪单例测试"""

    def teardown_method(self):
        audit = AuditTrail()
        audit.clear()

    def test_same_instance_returned(self):
        a1 = AuditTrail()
        a2 = AuditTrail()
        assert a1 is a2

    def test_start_operation(self):
        audit = AuditTrail()
        op_id = audit.start_operation("ocr_recognize", details={"file": "scan.pdf"})
        assert isinstance(op_id, str)

    def test_start_operation_with_user(self):
        audit = AuditTrail()
        op_id = audit.start_operation("upload", user="admin")
        assert isinstance(op_id, str)

    def test_start_complete_cycle(self):
        audit = AuditTrail()
        op_id = audit.start_operation("test_op")
        result = audit.complete_operation(op_id, details={"items": 42})
        assert result is True

    def test_start_fail_cycle(self):
        audit = AuditTrail()
        op_id = audit.start_operation("test_op")
        result = audit.fail_operation(
            op_id, error=ValueError("test"), details={"step": 3}
        )
        assert result is True

    def test_complete_nonexistent_op(self):
        audit = AuditTrail()
        result = audit.complete_operation("nonexistent-id")
        assert result is False

    def test_fail_nonexistent_op(self):
        audit = AuditTrail()
        result = audit.fail_operation("nonexistent-id")
        assert result is False

    def test_get_summary_empty(self):
        audit = AuditTrail()
        summary = audit.get_summary()
        assert summary["total_operations"] == 0
        assert summary["completed"] == 0
        assert summary["failed"] == 0
        assert summary["in_progress"] == 0
        assert summary["recent_operations"] == []

    def test_get_summary_with_operations(self):
        audit = AuditTrail()
        op1 = audit.start_operation("op1")
        op2 = audit.start_operation("op2")
        op3 = audit.start_operation("op3")
        audit.complete_operation(op1)
        audit.fail_operation(op2)
        # op3 remains in_progress

        summary = audit.get_summary()
        assert summary["total_operations"] == 3
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["in_progress"] == 1
        assert len(summary["recent_operations"]) == 3


class TestAuditTrailRingBuffer:
    """审计追踪环形缓冲区测试"""

    def teardown_method(self):
        audit = AuditTrail()
        audit.clear()

    def test_ring_buffer_overflow(self):
        audit = AuditTrail()
        # Add more than MAX_RECORDS (default 1000)
        for i in range(1100):
            audit.start_operation(f"op_{i}")

        summary = audit.get_summary()
        assert summary["total_operations"] <= 1000


class TestAuditTrailExport:
    """审计追踪导出测试"""

    def teardown_method(self):
        audit = AuditTrail()
        audit.clear()

    def test_export_audit_log(self):
        audit = AuditTrail()
        audit.start_operation("test_op")
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("{}")
            tmp_path = f.name

        try:
            result = audit.export_audit_log(tmp_path)
            assert result == tmp_path
            # Verify content
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "exported_at" in data
            assert "total_records" in data
            assert "records" in data
        finally:
            os.unlink(tmp_path)


class TestFallbackOnError:
    """优雅降级装饰器测试"""

    def test_successful_call_returns_value(self):
        @fallback_on_error(fallback_value=42)
        def good_func():
            return 100

        assert good_func() == 100

    def test_failed_call_returns_fallback(self):
        @fallback_on_error(fallback_value="default")
        def bad_func():
            raise RuntimeError("boom")

        assert bad_func() == "default"

    def test_fallback_with_none(self):
        @fallback_on_error(fallback_value=None)
        def bad_func():
            raise ValueError("error")

        assert bad_func() is None

    def test_fallback_with_dict(self):
        @fallback_on_error(fallback_value={})
        def bad_func():
            raise Exception("fail")

        assert bad_func() == {}

    def test_preserves_function_metadata(self):
        @fallback_on_error(fallback_value=None)
        def my_func():
            """Docstring here"""
            pass

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "Docstring here"


class TestRetryOnError:
    """重试装饰器测试"""

    def test_successful_call_no_retry(self):
        call_count = [0]

        @retry_on_error(max_retries=3, delay=0.01, exceptions=(ValueError,))
        def good_func():
            call_count[0] += 1
            return 42

        result = good_func()
        assert result == 42
        assert call_count[0] == 1

    def test_retry_and_succeed(self):
        call_count = [0]

        @retry_on_error(max_retries=3, delay=0.01, exceptions=(ValueError,))
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("temp error")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count[0] == 3

    def test_exhausted_retries_raises(self):
        call_count = [0]

        @retry_on_error(max_retries=2, delay=0.01, exceptions=(ValueError,))
        def always_fails():
            call_count[0] += 1
            raise ValueError("always fail")

        with pytest.raises(ValueError, match="always fail"):
            always_fails()
        assert call_count[0] == 3  # 1 initial + 2 retries

    def test_non_matching_exception_not_retried(self):
        call_count = [0]

        @retry_on_error(max_retries=3, delay=0.01, exceptions=(ValueError,))
        def raises_type_error():
            call_count[0] += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            raises_type_error()
        assert call_count[0] == 1


class TestGracefulOperation:
    """优雅操作上下文管理器测试"""

    def test_successful_operation(self):
        with graceful_operation("test_op", module_name="test"):
            x = 1 + 1

        assert x == 2

    def test_failed_operation_swallowed(self):
        # raise_on_error=False (default) swallows exception
        with graceful_operation("test_op", module_name="test"):
            raise ValueError("handled")

    def test_failed_operation_raised(self):
        with pytest.raises(ValueError, match="re-raised"):
            with graceful_operation("test_op", module_name="test", raise_on_error=True):
                raise ValueError("re-raised")

    def test_operation_with_context_kwargs(self):
        with graceful_operation("test_op", module_name="test", file="scan.pdf", page=1):
            pass


class TestCheckSystemHealth:
    """系统健康检查测试"""

    def test_returns_expected_structure(self):
        result = check_system_health()
        assert "overall_status" in result
        assert "timestamp" in result
        assert "components" in result
        assert "summary" in result

    def test_components_have_critical(self):
        result = check_system_health()
        assert "critical" in result["components"]

    def test_components_have_optional(self):
        result = check_system_health()
        assert "optional" in result["components"]

    def test_components_have_stdlib(self):
        result = check_system_health()
        assert "stdlib" in result["components"]

    def test_summary_counts(self):
        result = check_system_health()
        s = result["summary"]
        assert s["total_critical"] > 0
        assert s["available_critical"] <= s["total_critical"]
        assert s["total_optional"] > 0
        assert s["available_optional"] <= s["total_optional"]

    def test_overall_status_is_valid(self):
        result = check_system_health()
        assert result["overall_status"] in ("healthy", "degraded", "unhealthy")

    def test_stdlib_components_all_available(self):
        result = check_system_health()
        for name, info in result["components"]["stdlib"].items():
            assert info["status"] == "ok", f"stdlib {name} should be available"


class TestRecordException:
    """异常记录函数测试"""

    def teardown_method(self):
        AuditTrail().clear()

    def test_record_contract_comparator_error(self):
        exc = FileValidationError("测试文件错误")
        op_id = record_exception(exc, "file_validation")
        assert isinstance(op_id, str)
        audit = AuditTrail()
        summary = audit.get_summary()
        assert summary["failed"] >= 1

    def test_record_generic_exception(self):
        exc = RuntimeError("运行时错误")
        op_id = record_exception(exc, "generic_error", details={"ctx": "test"})
        assert isinstance(op_id, str)
        audit = AuditTrail()
        summary = audit.get_summary()
        assert summary["failed"] >= 1