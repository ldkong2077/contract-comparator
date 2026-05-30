"""
错误处理与日志框架

提供自定义异常层级、结构化日志、审计追踪、优雅降级和系统健康检查功能。
"""
import functools
import json
import logging
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

# ============================================================================
# 1. 自定义异常层级体系
# ============================================================================


class Severity(Enum):
    """严重程度枚举"""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


class ContractComparatorError(Exception):
    """
    合约比对工具基础异常类。

    Attributes:
        error_code: 错误码（如 "E001"）
        message: 错误描述信息
        severity: 严重程度
        recoverable: 是否可恢复（默认不可恢复）
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        severity: Severity = Severity.ERROR,
        recoverable: bool = False,
        original_exception: Optional[Exception] = None,
    ) -> None:
        self.error_code = error_code
        self.severity = severity
        self.recoverable = recoverable
        self.original_exception = original_exception
        self.timestamp = datetime.now(timezone.utc)
        super().__init__(message)

    def __str__(self) -> str:
        return (
            f"[{self.error_code}][{self.severity.value.upper()}] {self.args[0]}"
            f"{' (可恢复)' if self.recoverable else ''}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """将异常信息导出为字典。"""
        return {
            "error_code": self.error_code,
            "message": self.args[0],
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat(),
            "original_exception": str(self.original_exception) if self.original_exception else None,
        }


class FileValidationError(ContractComparatorError):
    """文件校验异常：格式无效、文件损坏、空文件等。"""

    def __init__(
        self,
        message: str,
        error_code: str = "E001",
        file_path: Optional[str] = None,
        reason: str = "",
        severity: Severity = Severity.ERROR,
        recoverable: bool = False,
    ) -> None:
        self.file_path = file_path
        self.reason = reason
        super().__init__(
            error_code=error_code,
            message=self._build_message(message),
            severity=severity,
            recoverable=recoverable,
        )

    def _build_message(self, base_message: str) -> str:
        parts = [base_message]
        if self.file_path:
            parts.append(f"文件: {self.file_path}")
        if self.reason:
            parts.append(f"原因: {self.reason}")
        return "; ".join(parts)


class OCRError(ContractComparatorError):
    """OCR 引擎异常：模型未找到、超时、识别失败等。"""

    def __init__(
        self,
        message: str,
        error_code: str = "E002",
        engine: str = "RapidOCR",
        severity: Severity = Severity.ERROR,
        recoverable: bool = False,
    ) -> None:
        self.engine = engine
        super().__init__(
            error_code=error_code,
            message=f"[{engine}] {message}",
            severity=severity,
            recoverable=recoverable,
        )


class ExtractionError(ContractComparatorError):
    """字段抽取异常：正则编译失败、字段提取错误等。"""

    def __init__(
        self,
        message: str,
        error_code: str = "E003",
        field_type: str = "",
        severity: Severity = Severity.ERROR,
        recoverable: bool = True,
    ) -> None:
        self.field_type = field_type
        super().__init__(
            error_code=error_code,
            message=self._build_message(message),
            severity=severity,
            recoverable=recoverable,
        )

    def _build_message(self, base_message: str) -> str:
        if self.field_type:
            return f"[{self.field_type}] {base_message}"
        return base_message


class ComparisonError(ContractComparatorError):
    """比对逻辑异常。"""

    def __init__(
        self,
        message: str,
        error_code: str = "E004",
        severity: Severity = Severity.ERROR,
        recoverable: bool = False,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            severity=severity,
            recoverable=recoverable,
        )


class ExportError(ContractComparatorError):
    """报告导出异常。"""

    def __init__(
        self,
        message: str,
        error_code: str = "E005",
        output_path: Optional[str] = None,
        severity: Severity = Severity.ERROR,
        recoverable: bool = False,
    ) -> None:
        self.output_path = output_path
        super().__init__(
            error_code=error_code,
            message=self._build_message(message),
            severity=severity,
            recoverable=recoverable,
        )

    def _build_message(self, base_message: str) -> str:
        if self.output_path:
            return f"{base_message}（输出路径: {self.output_path}）"
        return base_message


class ConfigurationError(ContractComparatorError):
    """配置异常：无效配置、缺少必要字段等。"""

    def __init__(
        self,
        message: str,
        error_code: str = "E006",
        config_key: str = "",
        severity: Severity = Severity.ERROR,
        recoverable: bool = False,
    ) -> None:
        self.config_key = config_key
        super().__init__(
            error_code=error_code,
            message=self._build_message(message),
            severity=severity,
            recoverable=recoverable,
        )

    def _build_message(self, base_message: str) -> str:
        if self.config_key:
            return f"[配置项: {self.config_key}] {base_message}"
        return base_message


# ============================================================================
# 2. 结构化日志类
# ============================================================================


class StructuredLogger:
    """
    结构化日志记录器，以 key=value 格式输出日志。

    封装标准 Python logging，自动附加时间戳、模块名、操作名和耗时。

    用法::

        logger = StructuredLogger("ocr_engine")
        op_id = logger.log_operation_start("recognize", file="scan.pdf")
        # ... 执行操作 ...
        logger.log_operation_end(op_id, status="ok", text_blocks=42)
        # 输出: [2025-01-15 10:30:00] [INFO] ocr_engine.recognize: 操作完成 | file=scan.pdf status=ok text_blocks=42 duration=1.23s
    """

    def __init__(
        self,
        module_name: str,
        level: int = logging.INFO,
    ) -> None:
        self.module_name = module_name
        self._logger = logging.getLogger(module_name)
        self._logger.setLevel(level)
        # 存储操作开始时间
        self._operation_starts: Dict[str, float] = {}

    @staticmethod
    def _format_time(timestamp: float) -> str:
        """格式化时间戳。"""
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _format_kv_pairs(kwargs: Dict[str, Any]) -> str:
        """将关键字参数格式化为 key=val 字符串。"""
        parts = []
        for key, val in kwargs.items():
            if isinstance(val, float):
                parts.append(f"{key}={val:.2f}")
            else:
                parts.append(f"{key}={val}")
        return " ".join(parts)

    def _log(self, level: int, operation: str, message: str, **kwargs: Any) -> None:
        """底层日志输出方法。"""
        if not self._logger.isEnabledFor(level):
            return

        ts = self._format_time(time.time())
        level_name = logging.getLevelName(level)
        prefix = f"[{ts}] [{level_name}] {self.module_name}.{operation}"

        kv_part = self._format_kv_pairs(kwargs)
        if kv_part:
            full_message = f"{prefix}: {message} | {kv_part}"
        else:
            full_message = f"{prefix}: {message}"

        self._logger.log(level, full_message)

    def log_operation_start(
        self, operation: str, message: str = "操作开始", **kwargs: Any
    ) -> str:
        """
        记录操作开始，返回操作 ID 供 log_operation_end 使用。

        Args:
            operation: 操作名称
            message: 日志消息
            **kwargs: 附加键值对

        Returns:
            操作 ID（UUID 字符串）
        """
        op_id = str(uuid.uuid4())
        self._operation_starts[op_id] = time.time()
        self._log(logging.INFO, operation, message, op_id=op_id, **kwargs)
        return op_id

    def log_operation_end(
        self, operation: str, message: str = "操作完成", *, op_id: Optional[str] = None, **kwargs: Any
    ) -> None:
        """
        记录操作结束，自动计算耗时。

        Args:
            operation: 操作名称
            message: 日志消息
            op_id: 操作 ID（来自 log_operation_start）
            **kwargs: 附加键值对（如 status=ok）
        """
        duration = None
        if op_id and op_id in self._operation_starts:
            duration = time.time() - self._operation_starts.pop(op_id)
        if duration is not None:
            kwargs["duration"] = f"{duration:.2f}s"
        self._log(logging.INFO, operation, message, **kwargs)

    def log_warning(self, operation: str, message: str, **kwargs: Any) -> None:
        """记录警告日志。"""
        self._log(logging.WARNING, operation, message, **kwargs)

    def log_error(self, operation: str, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """
        记录错误日志。

        Args:
            operation: 操作名称
            message: 错误消息
            exc_info: 是否包含异常堆栈
            **kwargs: 附加键值对
        """
        if exc_info:
            kwargs["traceback"] = traceback.format_exc().replace("\n", "\\n")
        self._log(logging.ERROR, operation, message, **kwargs)

    def log_metric(self, operation: str, metric_name: str, value: Any, **kwargs: Any) -> None:
        """
        记录指标数据。

        Args:
            operation: 操作名称
            metric_name: 指标名称
            value: 指标值
            **kwargs: 附加维度标签
        """
        self._log(logging.INFO, operation, f"指标记录: {metric_name}", metric_name=metric_name, value=value, **kwargs)


# ============================================================================
# 3. 审计追踪
# ============================================================================


class AuditTrail:
    """
    线程安全的审计追踪单例，以环形缓冲区存储最近 1000 条操作记录。

    用法::

        audit = AuditTrail()
        op_id = audit.start_operation("ocr_recognize", details={"file": "scan.pdf"})
        # ... 执行操作 ...
        audit.complete_operation(op_id, details={"text_blocks": 42})
        # 获取摘要
        summary = audit.get_summary()
        # 导出为 JSON
        audit.export_audit_log("audit_log.json")
    """

    _instance: Optional["AuditTrail"] = None
    _lock: threading.Lock = threading.Lock()
    MAX_RECORDS: int = 1000

    def __new__(cls) -> "AuditTrail":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._records: OrderedDict[str, Dict[str, Any]] = OrderedDict()
                    instance._lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    def start_operation(
        self,
        operation_type: str,
        details: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
    ) -> str:
        """
        开始记录一个操作。

        Args:
            operation_type: 操作类型标识
            details: 操作详情
            user: 执行用户

        Returns:
            操作 ID
        """
        op_id = str(uuid.uuid4())
        record: Dict[str, Any] = {
            "operation_id": op_id,
            "operation_type": operation_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "in_progress",
            "details": details or {},
            "user": user,
        }

        with self._lock:
            if len(self._records) >= self.MAX_RECORDS:
                # 弹出最早插入的记录（FIFO 环形缓冲）
                self._records.popitem(last=False)
            self._records[op_id] = record

        return op_id

    def complete_operation(
        self, operation_id: str, details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        标记操作完成。

        Args:
            operation_id: 操作 ID
            details: 附加详情（会合并到已有 details）

        Returns:
            是否成功更新
        """
        with self._lock:
            if operation_id not in self._records:
                return False
            record = self._records[operation_id]
            record["status"] = "completed"
            record["completed_at"] = datetime.now(timezone.utc).isoformat()
            if details:
                record["details"].update(details)
        return True

    def fail_operation(
        self,
        operation_id: str,
        error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        标记操作失败。

        Args:
            operation_id: 操作 ID
            error: 异常对象
            details: 附加详情

        Returns:
            是否成功更新
        """
        with self._lock:
            if operation_id not in self._records:
                return False
            record = self._records[operation_id]
            record["status"] = "failed"
            record["failed_at"] = datetime.now(timezone.utc).isoformat()
            if error:
                record["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            if details:
                record["details"].update(details)
        return True

    def get_summary(self) -> Dict[str, Any]:
        """
        获取审计追踪摘要。

        Returns:
            包含总数、各状态计数、最近记录列表的字典
        """
        with self._lock:
            total = len(self._records)
            completed = sum(1 for r in self._records.values() if r["status"] == "completed")
            failed = sum(1 for r in self._records.values() if r["status"] == "failed")
            in_progress = sum(1 for r in self._records.values() if r["status"] == "in_progress")
            # 最近 10 条记录
            recent = list(self._records.values())[-10:]

        return {
            "total_operations": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "recent_operations": recent,
        }

    def export_audit_log(self, filepath: str) -> str:
        """
        导出审计日志为 JSON 文件。

        Args:
            filepath: 输出文件路径

        Returns:
            输出文件路径

        Raises:
            ExportError: 导出失败时抛出
        """
        with self._lock:
            records_list = list(self._records.values())

        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(records_list),
            "records": records_list,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        except (OSError, IOError) as exc:
            raise ExportError(
                f"导出审计日志失败: {exc}",
                output_path=filepath,
            ) from exc

        return filepath

    def clear(self) -> None:
        """清空所有审计记录。"""
        with self._lock:
            self._records.clear()


# ============================================================================
# 4. 优雅降级 —— 装饰器 / 上下文管理器
# ============================================================================

F = TypeVar("F", bound=Callable[..., Any])


def fallback_on_error(
    fallback_value: Any = None,
    log_level: int = logging.WARNING,
    module_name: str = "graceful",
) -> Callable[[F], F]:
    """
    装饰器：捕获函数中的异常并返回回退值。

    Args:
        fallback_value: 异常发生时的回退返回值
        log_level: 日志级别
        module_name: 日志模块名

    用法::

        @fallback_on_error(fallback_value={}, log_level=logging.ERROR)
        def parse_config(path):
            # 可能抛出异常
            ...

    Returns:
        装饰后的函数
    """

    def decorator(func: F) -> F:
        logger = StructuredLogger(module_name)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                func_name = getattr(func, "__qualname__", func.__name__)
                logger._log(
                    level=log_level,
                    operation="fallback",
                    message=f"{func_name} 执行失败，使用回退值",
                    function=func_name,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    fallback_value=str(fallback_value),
                )
                return fallback_value

        return wrapper  # type: ignore[return-value]

    return decorator


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    module_name: str = "retry",
) -> Callable[[F], F]:
    """
    装饰器：在指定异常上自动重试，采用指数退避策略。

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff_factor: 退避因子（每次重试延迟 = delay * backoff_factor^attempt）
        exceptions: 需要重试的异常类型元组
        module_name: 日志模块名

    用法::

        @retry_on_error(max_retries=5, delay=0.5, exceptions=(ConnectionError, TimeoutError))
        def call_api():
            ...

    Returns:
        装饰后的函数
    """

    def decorator(func: F) -> F:
        logger = StructuredLogger(module_name)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = getattr(func, "__qualname__", func.__name__)
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger._log(
                            logging.INFO,
                            "retry",
                            f"{func_name} 在第 {attempt} 次重试后成功",
                            function=func_name,
                            attempts=attempt + 1,
                        )
                    return result
                except exceptions as exc:
                    last_exception = exc
                    if attempt < max_retries:
                        wait_time = delay * (backoff_factor ** attempt)
                        logger.log_warning(
                            "retry",
                            f"{func_name} 第 {attempt + 1}/{max_retries} 次重试",
                            function=func_name,
                            attempts=attempt + 1,
                            max_retries=max_retries,
                            wait=f"{wait_time:.2f}s",
                            error=str(exc),
                        )
                        time.sleep(wait_time)
                    else:
                        logger.log_error(
                            "retry",
                            f"{func_name} 重试 {max_retries} 次后仍然失败",
                            function=func_name,
                            max_retries=max_retries,
                            error=str(exc),
                            exc_info=True,
                        )

            # 所有重试已耗尽，重新抛出最后一个异常
            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


@contextmanager
def graceful_operation(
    operation_name: str,
    module_name: str = "graceful",
    raise_on_error: bool = False,
    **context_kwargs: Any,
):
    """
    上下文管理器：自动记录操作开始/结束/失败。

    用法::

        with graceful_operation("ocr_recognize", module_name="ocr", file="scan.pdf"):
            result = ocr.recognize("scan.pdf")

    Args:
        operation_name: 操作名称
        module_name: 日志模块名
        raise_on_error: 是否在异常时重新抛出（默认 False 即吞掉异常）
        **context_kwargs: 附加上下文键值对
    """
    logger = StructuredLogger(module_name)
    op_id = logger.log_operation_start(operation_name, **context_kwargs)

    try:
        yield
    except Exception as exc:
        logger.log_error(
            operation_name,
            f"操作失败: {exc}",
            op_id=op_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )
        if raise_on_error:
            raise
    else:
        logger.log_operation_end(
            operation_name,
            "操作完成",
            op_id=op_id,
            status="ok",
            **context_kwargs,
        )


# ============================================================================
# 5. 系统健康检查
# ============================================================================


# 需要检查的核心依赖及对应的 import 路径
_CRITICAL_DEPENDENCIES: Dict[str, str] = {
    "rapidocr": "rapidocr",
    "onnxruntime": "onnxruntime",
    "cv2": "cv2",
    "numpy": "numpy",
    "fitz": "fitz",           # PyMuPDF
    "docx": "docx",           # python-docx
    "jinja2": "jinja2",
}

_OPTIONAL_DEPENDENCIES: Dict[str, str] = {
    "ollama": "ollama",
    "diff_match_patch": "diff_match_patch",
    "dateutil": "dateutil",
    "regex": "regex",
}

_ADDITIONAL_CHECKS: Dict[str, str] = {
    "json": "json",
    "uuid": "uuid",
    "logging": "logging",
    "threading": "threading",
    "functools": "functools",
    "traceback": "traceback",
    "os": "os",
    "time": "time",
}


def _check_import(import_path: str) -> Dict[str, Any]:
    """检查单个模块是否可导入。"""
    try:
        __import__(import_path)
        return {"status": "ok", "error": None}
    except ImportError as exc:
        return {"status": "unavailable", "error": str(exc)}


def check_system_health() -> Dict[str, Any]:
    """
    检查所有依赖是否可导入，返回系统健康状态。

    Returns:
        {
            "overall_status": "healthy" | "degraded" | "unhealthy",
            "timestamp": "ISO时间戳",
            "components": {
                "critical": {
                    "rapidocr": {"status": "ok", "error": None},
                    ...
                },
                "optional": {
                    "ollama": {"status": "unavailable", "error": "No module named 'ollama'"},
                    ...
                },
                "stdlib": { ... }
            },
            "summary": {
                "total_critical": 7,
                "available_critical": 6,
                "total_optional": 4,
                "available_optional": 3
            }
        }
    """
    critical_results: Dict[str, Dict[str, Any]] = {}
    for name, import_path in _CRITICAL_DEPENDENCIES.items():
        critical_results[name] = _check_import(import_path)

    optional_results: Dict[str, Dict[str, Any]] = {}
    for name, import_path in _OPTIONAL_DEPENDENCIES.items():
        optional_results[name] = _check_import(import_path)

    stdlib_results: Dict[str, Dict[str, Any]] = {}
    for name, import_path in _ADDITIONAL_CHECKS.items():
        stdlib_results[name] = _check_import(import_path)

    all_components = {**critical_results, **optional_results, **stdlib_results}

    critical_available = sum(1 for r in critical_results.values() if r["status"] == "ok")
    critical_total = len(critical_results)
    optional_available = sum(1 for r in optional_results.values() if r["status"] == "ok")
    optional_total = len(optional_results)

    # 判定总体状态
    if critical_available == critical_total:
        overall_status = "healthy"
    elif critical_available > 0:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "overall_status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "critical": critical_results,
            "optional": optional_results,
            "stdlib": stdlib_results,
        },
        "summary": {
            "total_critical": critical_total,
            "available_critical": critical_available,
            "total_optional": optional_total,
            "available_optional": optional_available,
        },
    }


# ============================================================================
# 便捷函数：快速记录异常到审计追踪
# ============================================================================


def record_exception(
    exc: Exception,
    operation_type: str = "unhandled_error",
    details: Optional[Dict[str, Any]] = None,
    logger_module: str = "error_handler",
) -> str:
    """
    记录异常到审计追踪并输出结构化日志。

    Args:
        exc: 异常对象
        operation_type: 操作类型
        details: 附加详情
        logger_module: 日志模块名

    Returns:
        审计操作 ID

    用法::

        try:
            ...
        except Exception as e:
            record_exception(e, "pdf_processing", details={"file": path})
    """
    logger = StructuredLogger(logger_module)
    audit = AuditTrail()

    details = details or {}
    if isinstance(exc, ContractComparatorError):
        details.update(exc.to_dict())
    else:
        details.update({
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "error_code": "UNKNOWN",
            "severity": "error",
            "recoverable": False,
        })

    op_id = audit.start_operation(operation_type, details=details)
    audit.fail_operation(op_id, error=exc, details=details)

    logger.log_error(
        operation_type,
        str(exc),
        op_id=op_id,
        error_type=type(exc).__name__,
        exc_info=True,
    )

    return op_id