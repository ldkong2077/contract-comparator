"""
StructuredLogger — 为 OCR 流水线提供带上下文字段的结构化日志
"""

import logging


class StructuredLogger:
    """为 OCR 流水线提供带上下文字段的结构化日志"""

    def __init__(self, base_logger: logging.Logger):
        self._logger = base_logger

    def _log(self, level: int, msg: str, **fields):
        parts = [msg]
        if fields:
            parts.append(" | " + " | ".join(f"{k}={v}" for k, v in fields.items()))
        self._logger.log(level, "".join(parts))

    def debug(self, msg: str, **fields):
        self._log(logging.DEBUG, msg, **fields)

    def info(self, msg: str, **fields):
        self._log(logging.INFO, msg, **fields)

    def warning(self, msg: str, **fields):
        self._log(logging.WARNING, msg, **fields)

    def error(self, msg: str, **fields):
        self._log(logging.ERROR, msg, **fields)
