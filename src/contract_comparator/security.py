"""
安全模块：文件验证、敏感数据脱敏、输入清理、审计日志、安全临时文件管理

为合同比对工具提供全面的安全防护能力。
"""

import json
import os
import re
import secrets
import stat
import shutil
import struct
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 文件魔数（magic bytes）→ 对应的扩展名
_MAGIC_BYTES_MAP: dict[bytes, list[str]] = {
    b"\x25\x50\x44\x46": [".pdf"],                          # PDF
    b"\x50\x4B\x03\x04": [".docx", ".zip", ".xlsx"],       # DOCX / ZIP / XLSX
    b"\xD0\xCF\x11\xE0": [".doc", ".xls", ".ppt"],         # OLE2: DOC / XLS / PPT
    b"\xEF\xBB\xBF":  [".txt"],                             # UTF-8 BOM TXT
    b"\x89\x50\x4E\x47": [".png"],                          # PNG
    b"\xFF\xD8\xFF":   [".jpg", ".jpeg"],                   # JPEG
    b"\x42\x4D":       [".bmp"],                            # BMP
    b"\x49\x49\x2A\x00": [".tiff", ".tif"],                 # TIFF (little-endian)
    b"\x4D\x4D\x00\x2A": [".tiff", ".tif"],                 # TIFF (big-endian)
    b"\x52\x49\x46\x46": [".webp"],                         # WebP (RIFF header)
}

# 手机号正则：1 开头，第二位 3-9，后跟 9 位数字
_RE_PHONE_MOBILE = re.compile(r"1[3-9]\d{9}")

# 座机号正则：区号（3-4 位）+ 号码（7-8 位），允许 - 和空格分隔
_RE_PHONE_LANDLINE = re.compile(
    r"\b\d{3,4}[\-\s]?\d{7,8}(?:\s*(?:转|分机)\s*\d{1,6})?\b"
)

# 电子邮箱
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# 18 位身份证号
_RE_ID_CARD = re.compile(r"[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]")

# 银行卡号 16-19 位
_RE_BANK_ACCOUNT = re.compile(r"\b\d{16,19}\b")

# 公章编号：字母开头 + 数字的组合（如 B621JE12345）
_RE_COMPANY_SEAL = re.compile(r"\b[A-Za-z]+\d{3,}[A-Za-z]+\d+\b")

# 零宽字符
_ZERO_WIDTH_RE = re.compile(
    "[\u200B\u200C\u200D\u200E\u200F\uFEFF\u00AD\u2060\u2061\u2062\u2063\u2064\u2066\u2067\u2068\u2069\u206A\u206B\u206C\u206D\u206E\u206F]"
)

# 路径遍历危险模式
_PATH_TRAVERSAL_RE = re.compile(r"\.\.[/\\]|^\.\.[/\\]|[/\\]\.\.\x00?")


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """文件验证结果"""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """合并另一个 ValidationResult 到当前结果"""
        self.is_valid = self.is_valid and other.is_valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        return self


# ---------------------------------------------------------------------------
# FileUploadValidator
# ---------------------------------------------------------------------------

class FileUploadValidator:
    """文件上传验证器，基于魔数、扩展名、大小和完整性进行多层校验。"""

    @staticmethod
    def _read_magic_bytes(file_path: str, n: int = 8) -> bytes:
        """读取文件前 n 个字节作为魔数字节。"""
        with open(file_path, "rb") as f:
            return f.read(n)

    @classmethod
    def _detect_type_by_magic(cls, file_path: str) -> list[str]:
        """通过魔数字节识别文件真实类型，返回匹配的扩展名列表。"""
        try:
            magic = cls._read_magic_bytes(file_path)
        except OSError:
            return []

        results: list[str] = []
        for sig, exts in _MAGIC_BYTES_MAP.items():
            if magic.startswith(sig):
                results.extend(exts)
        return results

    @classmethod
    def validate_file_type(
        cls,
        file_path: str,
        expected_types: list[str],
        strict_unknown_magic: bool = False,
    ) -> ValidationResult:
        """
        验证文件类型，先检查扩展名，再通过魔数确认真实类型。

        Args:
            file_path: 文件路径
            expected_types: 允许的扩展名列表，如 ['.pdf', '.docx']
            strict_unknown_magic: 当为 True 时，无法识别魔数也视为错误（而非警告）

        Returns:
            ValidationResult
        """
        result = ValidationResult()
        ext = os.path.splitext(file_path)[1].lower()

        if ext not in expected_types:
            result.is_valid = False
            result.errors.append(
                f"文件扩展名 {ext} 不在允许列表中: {expected_types}"
            )
            return result

        # 魔数校验
        detected = cls._detect_type_by_magic(file_path)
        if not detected:
            msg = f"无法通过魔数识别文件类型: {file_path}"
            if strict_unknown_magic:
                result.is_valid = False
                result.errors.append(msg)
            else:
                result.warnings.append(msg)
        elif ext not in detected:
            # 扩展名与魔数不匹配，可能是伪装文件
            result.is_valid = False
            result.errors.append(
                f"文件扩展名 {ext} 与魔数检测类型 {detected} 不一致，疑似伪装文件"
            )

        return result

    @staticmethod
    def validate_file_size(
        file_path: str,
        max_mb: float = 50,
    ) -> ValidationResult:
        """
        验证文件大小不超过上限。

        Args:
            file_path: 文件路径
            max_mb: 文件大小上限，单位 MB，默认 50

        Returns:
            ValidationResult
        """
        result = ValidationResult()
        max_bytes = int(max_mb * 1024 * 1024)
        try:
            size = os.path.getsize(file_path)
        except OSError as e:
            result.is_valid = False
            result.errors.append(f"无法获取文件大小: {e}")
            return result

        if size == 0:
            result.is_valid = False
            result.errors.append("文件大小为 0，可能为空文件")
        elif size > max_bytes:
            result.is_valid = False
            result.errors.append(
                f"文件大小 {size / 1024 / 1024:.1f} MB 超过上限 {max_mb} MB"
            )

        return result

    @staticmethod
    def validate_file_integrity(file_path: str) -> ValidationResult:
        """
        基本完整性检查：文件可打开、非空、未截断。

        对于 DOCX/ZIP 格式，额外检查 ZIP 中央目录是否完整。

        Args:
            file_path: 文件路径

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        if not os.path.isfile(file_path):
            result.is_valid = False
            result.errors.append(f"文件不存在或不是普通文件: {file_path}")
            return result

        # 检查是否可读且非空
        try:
            with open(file_path, "rb") as f:
                # 读取首尾少量字节验证文件可正常访问
                head = f.read(1)
                if not head:
                    result.is_valid = False
                    result.errors.append("文件为空")
                    return result

                # 对 ZIP/DOCX 额外校验尾部（EOCD 签名）
                f.seek(-22, os.SEEK_END)
                tail = f.read(22)
                if len(tail) >= 4:
                    # ZIP 的 EOCD 签名为 0x06054b50
                    eocd_sig = struct.unpack("<I", tail[:4])[0]
                    if eocd_sig == 0x06054B50:
                        # 检查注释长度 → 修正偏移
                        comment_len = struct.unpack("<H", tail[20:22])[0]
                        expected_pos = 22 + comment_len
                        f.seek(-expected_pos, os.SEEK_END)
                        eocd = f.read(expected_pos)
                        if len(eocd) < 4 or struct.unpack("<I", eocd[:4])[0] != 0x06054B50:
                            result.is_valid = False
                            result.errors.append("ZIP 归档尾部损坏，文件可能截断")
        except OSError as e:
            result.is_valid = False
            result.errors.append(f"无法读取文件: {e}")

        return result

    @classmethod
    def validate_all(
        cls,
        file_path: str,
        expected_types: list[str],
        max_size_mb: float = 50,
        strict_unknown_magic: bool = False,
    ) -> ValidationResult:
        """
        组合验证：扩展名、魔数、大小、完整性。

        Args:
            file_path: 文件路径
            expected_types: 允许的扩展名列表
            max_size_mb: 最大文件大小，单位 MB
            strict_unknown_magic: 无法识别魔数时视为错误（默认 False）

        Returns:
            ValidationResult
        """
        result = ValidationResult()
        result.merge(cls.validate_file_type(file_path, expected_types, strict_unknown_magic))
        result.merge(cls.validate_file_size(file_path, max_size_mb))
        result.merge(cls.validate_file_integrity(file_path))
        return result


# ---------------------------------------------------------------------------
# SensitiveDataMasker
# ---------------------------------------------------------------------------

class SensitiveDataMasker:
    """敏感数据脱敏器，识别并替换文本中的隐私信息。"""

    @staticmethod
    def mask_phone_numbers(text: str) -> tuple[str, list[str]]:
        """替换手机号和座机号为 ***PHONE***。"""
        masked_items: list[str] = []

        # 先替换手机号
        for m in _RE_PHONE_MOBILE.finditer(text):
            masked_items.append(m.group())

        # 再替换座机号（避免与手机号重叠匹配）
        # 先对剩余区域匹配座机号
        temp = _RE_PHONE_MOBILE.sub("***PHONE***", text)
        for m in _RE_PHONE_LANDLINE.finditer(temp):
            if "***PHONE***" not in m.group():
                masked_items.append(m.group())
        # 统一替换（按长度降序避免部分替换问题）
        sorted_items = sorted(set(masked_items), key=len, reverse=True)
        for item in sorted_items:
            text = text.replace(item, "***PHONE***")
        return text, list(set(masked_items))

    @staticmethod
    def mask_emails(text: str) -> tuple[str, list[str]]:
        """替换电子邮箱为 ***EMAIL***。"""
        masked_items: list[str] = []
        result = re.sub(_RE_EMAIL, lambda m: (masked_items.append(m.group()) or "***EMAIL***"), text)
        return result, masked_items

    @staticmethod
    def mask_id_cards(text: str) -> tuple[str, list[str]]:
        """替换 18 位身份证号为 ***ID_CARD***。"""
        masked_items: list[str] = []

        def _do_mask(m: re.Match) -> str:
            s = m.group()
            # 简单的加权校验：全数字或末位为 X/x
            if s[-1] in ("X", "x") or s.isdigit():
                masked_items.append(s)
                return "***ID_CARD***"
            return s

        result = re.sub(_RE_ID_CARD, _do_mask, text)
        return result, masked_items

    @staticmethod
    def mask_bank_accounts(text: str) -> tuple[str, list[str]]:
        """替换 16-19 位银行卡号为 ***BANK_ACCOUNT***。"""
        masked_items: list[str] = []

        def _do_mask(m: re.Match) -> str:
            s = m.group()
            # 排除 Excel 科学记数法残留、纯 0
            if s == "0" * len(s):
                return s
            masked_items.append(s)
            return "***BANK_ACCOUNT***"

        result = re.sub(_RE_BANK_ACCOUNT, _do_mask, text)
        return result, masked_items

    @staticmethod
    def mask_company_seals(text: str) -> tuple[str, list[str]]:
        """替换公章编号（如 B621JE12345）为 ***SEAL***。"""
        masked_items: list[str] = []
        result = re.sub(_RE_COMPANY_SEAL, lambda m: (masked_items.append(m.group()) or "***SEAL***"), text)
        return result, masked_items

    @classmethod
    def mask_all(
        cls,
        text: str,
        options: dict[str, bool] | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        """
        批量脱敏，根据 options 控制启用哪些脱敏器。

        Args:
            text: 输入文本
            options: 可选字典，控制启用项，支持：
                phones, emails, id_cards, bank_accounts, company_seals
                默认全部启用。

        Returns:
            (脱敏后文本, 被脱敏项列表 [{type, value}])
        """
        default_options = {
            "phones": True,
            "emails": True,
            "id_cards": True,
            "bank_accounts": True,
            "company_seals": True,
        }
        opts = {**default_options, **(options or {})}

        all_masked: list[dict[str, str]] = []
        current = text

        # 按长度/特异性排序：先处理长模式（身份证/银行卡），避免被短模式
        # （手机号）部分匹配
        maskers: list[tuple[str, Any]] = [
            ("emails", cls.mask_emails),
            ("company_seals", cls.mask_company_seals),
            ("id_cards", cls.mask_id_cards),
            ("bank_accounts", cls.mask_bank_accounts),
            ("phones", cls.mask_phone_numbers),
        ]

        for key, masker_fn in maskers:
            if opts.get(key):
                current, items = masker_fn(current)
                for item in items:
                    all_masked.append({"type": key, "value": item})

        return current, all_masked


# ---------------------------------------------------------------------------
# InputSanitizer
# ---------------------------------------------------------------------------

class InputSanitizer:
    """输入清理器，防止路径遍历、空字节、控制字符等注入攻击。"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，去除路径遍历字符、空字节、控制字符。

        Args:
            filename: 原始文件名

        Returns:
            安全文件名
        """
        if not filename:
            return "untitled"

        # 提取纯文件名（去除任何路径部分）
        name = os.path.basename(filename)

        # 去除空字节
        name = name.replace("\x00", "")

        # 去除路径遍历序列
        name = _PATH_TRAVERSAL_RE.sub("", name)
        name = name.replace("../", "").replace("..\\", "")

        # 去除 ASCII 控制字符（保留换行不作为文件名一部分）
        name = re.sub(r"[\x00-\x1F\x7F]", "", name)

        # 去除 Windows 保留字符
        name = re.sub(r'[<>:"/\\|?*]', "_", name)

        # 去除首尾空格和点（Windows 不允许末尾用点）
        name = name.strip(" .")

        # 避免 Windows 保留名（CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9）
        reserved = {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
        stem = os.path.splitext(name)[0].upper()
        if stem in reserved:
            name = f"_{name}"

        if not name:
            name = "untitled"

        return name

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        清理文本，去除空字节、控制字符和零宽字符。

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return ""

        # 去除空字节
        text = text.replace("\x00", "")

        # 去除 ASCII 控制字符（0x00-0x1F 和 DEL），但保留常用空白 \t \n \r
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

        # 去除零宽字符
        text = _ZERO_WIDTH_RE.sub("", text)

        return text

    @staticmethod
    def validate_path_safe(filepath: str, base_dir: str) -> bool:
        """
        确保解析后的路径在 base_dir 内，防止目录遍历攻击。

        Args:
            filepath: 待验证的路径
            base_dir: 基准目录

        Returns:
            是否安全
        """
        try:
            real_path = os.path.realpath(os.path.abspath(filepath))
            real_base = os.path.realpath(os.path.abspath(base_dir))
        except (OSError, ValueError):
            return False

        # Windows 下比较时统一大小写（os.path.realpath 保持原有大小写，但比较时需注意）
        common = os.path.commonpath([real_path, real_base])
        # 在 Windows 下 commonpath 比较不区分大小写
        return common.lower() == real_base.lower()

    @staticmethod
    def clean_temp_files(temp_dir: str, max_age_hours: float = 24) -> int:
        """
        清理超过指定时间的临时文件。

        Args:
            temp_dir: 临时目录路径
            max_age_hours: 文件最大保留时间（小时）

        Returns:
            删除的文件数量
        """
        if not os.path.isdir(temp_dir):
            return 0

        now = time.time()
        cutoff = now - max_age_hours * 3600
        removed = 0

        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    st = os.stat(file_path)
                    if st.st_mtime < cutoff:
                        os.remove(file_path)
                        removed += 1
                except OSError:
                    pass
            # 删除空目录
            for name in dirs:
                dir_path = os.path.join(root, name)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except OSError:
                    pass

        return removed


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    审计日志记录器（独立于 error_handler 的 AuditTrail）。

    以 JSON Lines 格式写入带轮转功能的审计日志文件，记录文件操作、
    比对、导出和错误事件，支持按时间范围和用户 ID 查询。
    """

    _DEFAULT_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
    _DEFAULT_BACKUP_COUNT = 5

    _lock = threading.Lock()

    def __init__(
        self,
        log_path: str = "audit.log",
        max_bytes: int = _DEFAULT_MAX_BYTES,
        backup_count: int = _DEFAULT_BACKUP_COUNT,
    ) -> None:
        """
        初始化审计日志器。

        Args:
            log_path: 日志文件路径
            max_bytes: 单个日志文件最大字节数，超出后轮转
            backup_count: 保留的旧日志文件数量
        """
        self._log_path = os.path.abspath(log_path)
        self._max_bytes = max_bytes
        self._backup_count = backup_count

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def _rotate_if_needed(self) -> None:
        """如果当前日志文件超过大小限制则自动轮转。"""
        try:
            if os.path.isfile(self._log_path) and os.path.getsize(self._log_path) >= self._max_bytes:
                for i in range(self._backup_count - 1, 0, -1):
                    src = f"{self._log_path}.{i}"
                    dst = f"{self._log_path}.{i + 1}"
                    if os.path.isfile(src):
                        if os.path.isfile(dst):
                            os.remove(dst)
                        os.rename(src, dst)
                dst_1 = f"{self._log_path}.1"
                if os.path.isfile(dst_1):
                    os.remove(dst_1)
                os.rename(self._log_path, dst_1)
        except OSError:
            pass

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """写入一条 JSON 行记录（线程安全）。"""
        entry.setdefault("timestamp", datetime.now().isoformat())
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._lock:
            self._rotate_if_needed()
            os.makedirs(os.path.dirname(self._log_path) or ".", exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line)

    # ------------------------------------------------------------------
    # 公共日志方法
    # ------------------------------------------------------------------

    def log_file_access(
        self,
        user_id: str,
        file_name: str,
        action: str,
    ) -> None:
        """记录文件操作（上传 / 读取 / 删除等）。"""
        self._write_entry({
            "event": "file_access",
            "user_id": user_id,
            "file_name": file_name,
            "action": action,
        })

    def log_comparison(
        self,
        user_id: str,
        word_file: str,
        pdf_file: str,
        result_summary: str,
    ) -> None:
        """记录合同比对操作。"""
        self._write_entry({
            "event": "comparison",
            "user_id": user_id,
            "word_file": word_file,
            "pdf_file": pdf_file,
            "result_summary": result_summary,
        })

    def log_export(
        self,
        user_id: str,
        format: str,
        file_path: str,
    ) -> None:
        """记录报告导出操作。"""
        self._write_entry({
            "event": "export",
            "user_id": user_id,
            "format": format,
            "file_path": file_path,
        })

    def log_error(
        self,
        user_id: str,
        error_type: str,
        details: str,
    ) -> None:
        """记录错误事件。"""
        self._write_entry({
            "event": "error",
            "user_id": user_id,
            "error_type": error_type,
            "details": details,
        })

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def _all_log_files(self) -> list[str]:
        """返回所有存在的日志文件路径（主文件 + 轮转文件）。"""
        files: list[str] = []
        if os.path.isfile(self._log_path):
            files.append(self._log_path)
        for i in range(1, self._backup_count + 1):
            path = f"{self._log_path}.{i}"
            if os.path.isfile(path):
                files.append(path)
        return files

    def get_audit_records(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        user_id: str | None = None,
        event: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        按条件查询审计记录。

        Args:
            start_time: 时间范围起点（含）
            end_time: 时间范围终点（含）
            user_id: 按用户 ID 筛选
            event: 按事件类型筛选（file_access / comparison / export / error）

        Returns:
            匹配的审计记录列表，按时间升序排列
        """
        results: list[dict[str, Any]] = []
        for log_file in self._all_log_files():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # 时间过滤
                        ts_str = record.get("timestamp", "")
                        if ts_str:
                            try:
                                ts = datetime.fromisoformat(ts_str)
                            except ValueError:
                                continue
                            if start_time and ts < start_time:
                                continue
                            if end_time and ts > end_time:
                                continue

                        # 用户过滤
                        if user_id and record.get("user_id") != user_id:
                            continue

                        # 事件类型过滤
                        if event and record.get("event") != event:
                            continue

                        results.append(record)
            except OSError:
                continue

        # 按时间升序
        results.sort(key=lambda r: r.get("timestamp", ""))
        return results


# ---------------------------------------------------------------------------
# SecureTempFileManager
# ---------------------------------------------------------------------------

class SecureTempFileManager:
    """
    安全临时文件管理器（上下文管理器）。

    在受限权限的随机命名临时目录中管理文件，退出时自动清理
    （即使发生异常），并校验写入的文件确实位于预期目录内。

    用法:
        with SecureTempFileManager() as tm:
            path = tm.prepare_path("data.txt")
            with open(path, "w") as f:
                f.write("...")
            # ... 使用 path
    """

    def __init__(
        self,
        base_dir: str | None = None,
        prefix: str = "sec_",
    ) -> None:
        """
        初始化。

        Args:
            base_dir: 父目录，默认使用系统临时目录
            prefix: 临时目录名前缀
        """
        self._base_dir = base_dir or tempfile.gettempdir()
        self._prefix = prefix
        self._temp_dir: str | None = None

    @property
    def temp_dir(self) -> str:
        """返回已创建的临时目录路径（需在进入上下文后访问）。"""
        if self._temp_dir is None:
            raise RuntimeError("SecureTempFileManager 尚未进入上下文")
        return self._temp_dir

    def _create_secure_dir(self) -> str:
        """创建带受限权限的随机命名目录。"""
        while True:
            rand_name = self._prefix + secrets.token_hex(8)
            candidate = os.path.join(self._base_dir, rand_name)
            if not os.path.exists(candidate):
                break

        os.makedirs(candidate, exist_ok=False)

        # 在 Windows 上限制目录权限为仅当前用户可访问
        if os.name == "nt":
            # 使用 icacls 设置权限（仅当前用户完全控制）
            try:
                import subprocess
                subprocess.run(
                    ["icacls", candidate, "/inheritance:r", "/grant:r", f"{os.environ.get('USERNAME', 'Everyone')}:(OI)(CI)F"],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass
        else:
            # Unix-like 系统
            os.chmod(candidate, stat.S_IRWXU)  # 0o700

        return candidate

    def prepare_path(self, filename: str) -> str:
        """
        在临时目录中生成安全路径。

        Args:
            filename: 文件名（将经过 sanitize_filename 清理）

        Returns:
            完整的临时文件路径
        """
        safe_name = InputSanitizer.sanitize_filename(filename)
        return os.path.join(self.temp_dir, safe_name)

    def validate_file_placement(self, file_path: str) -> bool:
        """
        校验文件确实在临时目录内，防止符号链接逃逸等攻击。

        Args:
            file_path: 要校验的文件路径

        Returns:
            是否在预期目录内
        """
        return InputSanitizer.validate_path_safe(file_path, self.temp_dir)

    def __enter__(self) -> "SecureTempFileManager":
        self._temp_dir = self._create_secure_dir()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """退出上下文，自动清理临时目录。"""
        if self._temp_dir is not None and os.path.isdir(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None
        # 不抑制异常
        return None


# ---------------------------------------------------------------------------
# 模块级便捷函数
# ---------------------------------------------------------------------------

_default_validator = FileUploadValidator()
_default_masker = SensitiveDataMasker()
_default_sanitizer = InputSanitizer()


def validate_upload(
    file_path: str,
    expected_types: list[str],
    max_size_mb: float = 50,
) -> ValidationResult:
    """便捷函数：完整验证上传文件。"""
    return _default_validator.validate_all(file_path, expected_types, max_size_mb)


def mask_sensitive(
    text: str,
    options: dict[str, bool] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """便捷函数：脱敏敏感信息。"""
    return _default_masker.mask_all(text, options)


def sanitize_input(text: str) -> str:
    """便捷函数：清理用户输入文本。"""
    return _default_sanitizer.sanitize_text(text)