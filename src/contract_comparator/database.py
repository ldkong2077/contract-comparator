"""
SQLite 存储模块 —— 合同比对工具持久化层

提供比对任务、审计日志、API Key、配置文件、LLM 配置的统一 SQLite 存储，
替代原有 JSON 文件方案，支持线程安全、自动清理、数据迁移及可扩展后端接口。
"""

from __future__ import annotations

import abc
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import stat
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# ============================================================
# 日志
# ============================================================

logger = logging.getLogger(__name__)

# ============================================================
# Fernet 对称加密（可选依赖，不可用时降级为 Base64 编码）
# ============================================================

try:
    from cryptography.fernet import Fernet

    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False
    logger.warning("cryptography 库不可用，LLM API Key 将仅做 Base64 编码存储，建议安装: pip install cryptography")

# ============================================================
# 常量
# ============================================================

# 默认数据库路径
DEFAULT_DB_PATH = os.path.join(".", "data", "contract_comparator.db")

# 加密密钥文件名
_ENCRYPTION_KEY_FILE = ".db_encryption_key"

# 数据库版本号，用于未来迁移
_DB_VERSION = 1

# ============================================================
# 建表 SQL
# ============================================================

_CREATE_TABLES_SQL = """
-- 比对任务表
CREATE TABLE IF NOT EXISTS comparison_tasks (
    task_id       TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'pending',
    word_file     TEXT NOT NULL DEFAULT '',
    pdf_file      TEXT NOT NULL DEFAULT '',
    result_summary TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    completed_at  TEXT,
    user_id       TEXT DEFAULT ''
);

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    user_id     TEXT DEFAULT '',
    details_json TEXT DEFAULT '{}',
    timestamp   TEXT NOT NULL
);

-- API Key 表
CREATE TABLE IF NOT EXISTS api_keys (
    key_id       TEXT PRIMARY KEY,
    key_hash     TEXT NOT NULL,
    role         TEXT NOT NULL,
    label        TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    last_used_at TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1
);

-- 比对配置文件表
CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- LLM 模型配置表
CREATE TABLE IF NOT EXISTS llm_configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider        TEXT NOT NULL DEFAULT '',
    model_name      TEXT NOT NULL DEFAULT '',
    api_key_encrypted TEXT DEFAULT '',
    base_url        TEXT DEFAULT '',
    is_default      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

-- 数据库元信息表
CREATE TABLE IF NOT EXISTS _db_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_tasks_status    ON comparison_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id   ON comparison_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON comparison_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_user_id   ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_role   ON api_keys(role);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_profiles_name   ON profiles(name);
CREATE INDEX IF NOT EXISTS idx_llm_configs_provider ON llm_configs(provider);
"""


# ============================================================
# 加密工具
# ============================================================

class EncryptionHelper:
    """Fernet 对称加密辅助类，用于 LLM API Key 的加密存储。"""

    def __init__(self, db_dir: str) -> None:
        self._key_path = os.path.join(db_dir, _ENCRYPTION_KEY_FILE)
        self._fernet: Any = None
        self._init_encryption()

    def _init_encryption(self) -> None:
        """初始化加密器：优先使用 Fernet，不可用时降级为 Base64。"""
        os.makedirs(os.path.dirname(self._key_path) or ".", exist_ok=True)

        if _FERNET_AVAILABLE:
            key = self._load_or_create_fernet_key()
            self._fernet = Fernet(key)
        else:
            self._fernet = None

    def _load_or_create_fernet_key(self) -> bytes:
        """加载或创建 Fernet 密钥。"""
        if os.path.exists(self._key_path):
            with open(self._key_path, "rb") as f:
                return f.read().strip()
        # 生成新密钥
        key = Fernet.generate_key()
        with open(self._key_path, "wb") as f:
            f.write(key)
        # 限制文件权限
        self._restrict_file_permissions(self._key_path)
        return key

    @staticmethod
    def _restrict_file_permissions(path: str) -> None:
        """限制文件权限为仅所有者可读写。"""
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    def encrypt(self, plaintext: str) -> str:
        """加密明文字符串，返回密文（字符串形式）。"""
        if not plaintext:
            return ""
        if self._fernet is not None:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        # 降级：仅做 Base64 编码（不安全，仅作占位）
        import base64
        return base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """解密密文字符串，返回明文。"""
        if not ciphertext:
            return ""
        if self._fernet is not None:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        # 降级：Base64 解码
        import base64
        return base64.b64decode(ciphertext.encode("utf-8")).decode("utf-8")


# ============================================================
# HMAC 哈希工具（兼容 auth.py）
# ============================================================

class HMACHelper:
    """HMAC-SHA256 哈希辅助类，与 auth.py 的 APIKeyManager 兼容。"""

    def __init__(self, secret_path: str) -> None:
        self._secret_path = secret_path
        self._secret: bytes = self._load_or_create_secret()

    def _load_or_create_secret(self) -> bytes:
        """加载或创建 HMAC 密钥。"""
        if os.path.exists(self._secret_path):
            with open(self._secret_path, "rb") as f:
                return f.read()
        secret = secrets.token_bytes(32)
        os.makedirs(os.path.dirname(self._secret_path) or ".", exist_ok=True)
        with open(self._secret_path, "wb") as f:
            f.write(secret)
        try:
            os.chmod(self._secret_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return secret

    def hash_key(self, plain_key: str) -> str:
        """计算 API Key 的 HMAC-SHA256 哈希。"""
        return hmac.new(self._secret, plain_key.encode(), hashlib.sha256).hexdigest()

    def verify_key(self, plain_key: str, key_hash: str) -> bool:
        """验证 API Key 哈希（防时序攻击）。"""
        computed = self.hash_key(plain_key)
        return hmac.compare_digest(computed, key_hash)


# ============================================================
# 可扩展存储后端接口
# ============================================================

class StorageBackend(abc.ABC):
    """存储后端抽象基类，定义统一接口以支持未来扩展（如 PostgreSQL 等）。"""

    @abc.abstractmethod
    def store(self, table: str, data: dict) -> bool:
        """存储一条记录。"""
        ...

    @abc.abstractmethod
    def retrieve(self, table: str, key: str, key_column: str = "id") -> Optional[dict]:
        """根据主键检索一条记录。"""
        ...

    @abc.abstractmethod
    def delete(self, table: str, key: str, key_column: str = "id") -> bool:
        """根据主键删除一条记录。"""
        ...

    @abc.abstractmethod
    def query(self, table: str, filters: Optional[dict] = None,
              limit: int = 100, offset: int = 0,
              order_by: Optional[str] = None) -> list[dict]:
        """按条件查询记录。"""
        ...


class SQLiteBackend(StorageBackend):
    """基于 SQLite 的存储后端实现。"""

    def __init__(self, db_manager: "DatabaseManager") -> None:
        self._db = db_manager

    def store(self, table: str, data: dict) -> bool:
        """存储一条记录到指定表。"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        try:
            with self._db._connect() as conn:
                conn.execute(sql, list(data.values()))
            return True
        except Exception as e:
            logger.error("存储记录失败: table=%s, error=%s", table, e)
            return False

    def retrieve(self, table: str, key: str, key_column: str = "id") -> Optional[dict]:
        """根据主键检索一条记录。"""
        sql = f"SELECT * FROM {table} WHERE {key_column} = ?"
        try:
            with self._db._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql, (key,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error("检索记录失败: table=%s, key=%s, error=%s", table, key, e)
            return None

    def delete(self, table: str, key: str, key_column: str = "id") -> bool:
        """根据主键删除一条记录。"""
        sql = f"DELETE FROM {table} WHERE {key_column} = ?"
        try:
            with self._db._connect() as conn:
                cursor = conn.execute(sql, (key,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("删除记录失败: table=%s, key=%s, error=%s", table, key, e)
            return False

    def query(self, table: str, filters: Optional[dict] = None,
              limit: int = 100, offset: int = 0,
              order_by: Optional[str] = None) -> list[dict]:
        """按条件查询记录。"""
        sql = f"SELECT * FROM {table}"
        params: list = []

        if filters:
            conditions = []
            for col, val in filters.items():
                conditions.append(f"{col} = ?")
                params.append(val)
            sql += " WHERE " + " AND ".join(conditions)

        if order_by:
            sql += f" ORDER BY {order_by}"

        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            with self._db._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error("查询记录失败: table=%s, error=%s", table, e)
            return []


def get_storage_backend(backend_type: str = "sqlite", **kwargs: Any) -> StorageBackend:
    """存储后端工厂函数。

    Args:
        backend_type: 后端类型，目前仅支持 "sqlite"。
        **kwargs: 传递给后端构造器的额外参数。

    Returns:
        StorageBackend 实例。

    Raises:
        ValueError: 不支持的后端类型。
    """
    if backend_type == "sqlite":
        db_path = kwargs.get("db_path", DEFAULT_DB_PATH)
        manager = DatabaseManager(db_path=db_path)
        return SQLiteBackend(manager)
    raise ValueError(f"不支持的存储后端类型: {backend_type}")


# ============================================================
# DatabaseManager 核心类
# ============================================================

class DatabaseManager:
    """SQLite 数据库管理器，负责建表、连接管理及线程安全。

    使用方式::

        with DatabaseManager() as db:
            db.create_task("t1", "a.docx", "b.pdf", "user1")
            task = db.get_task("t1")
    """

    def __init__(self, db_path: str | None = None) -> None:
        """初始化数据库管理器。

        Args:
            db_path: 数据库文件路径，默认 ``./data/contract_comparator.db``。
        """
        self._db_path = os.path.abspath(db_path or DEFAULT_DB_PATH)
        self._db_dir = os.path.dirname(self._db_path)
        self._lock = threading.Lock()
        self._encryption = EncryptionHelper(self._db_dir)
        self._hmac = HMACHelper(self._db_path + ".secret")

        # 确保目录存在
        os.makedirs(self._db_dir, exist_ok=True)

        # 初始化表结构
        self._init_tables()

        # 限制数据库文件权限
        self._restrict_db_permissions()

    # ----------------------------------------------------------
    # 上下文管理器
    # ----------------------------------------------------------

    def __enter__(self) -> "DatabaseManager":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass  # SQLite 连接按需创建/关闭，无需在此释放

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """创建新的数据库连接（启用 WAL 模式和外键约束）。"""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_tables(self) -> None:
        """创建所有表及索引。"""
        with self._lock:
            with self._connect() as conn:
                conn.executescript(_CREATE_TABLES_SQL)
                conn.executescript(_CREATE_INDEXES_SQL)
                # 写入版本号
                conn.execute(
                    "INSERT OR REPLACE INTO _db_meta (key, value) VALUES (?, ?)",
                    ("version", str(_DB_VERSION)),
                )

    def _restrict_db_permissions(self) -> None:
        """限制数据库文件权限为仅所有者可读写。"""
        try:
            os.chmod(self._db_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    # ----------------------------------------------------------
    # 比对任务（TaskStorage）
    # ----------------------------------------------------------

    def create_task(self, task_id: str, word_file: str, pdf_file: str,
                    user_id: str = "") -> None:
        """创建比对任务记录。

        Args:
            task_id: 任务唯一标识。
            word_file: Word 文件路径。
            pdf_file: PDF 文件路径。
            user_id: 关联用户 ID。
        """
        now = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO comparison_tasks (task_id, status, word_file, pdf_file, created_at, user_id)
            VALUES (?, 'pending', ?, ?, ?, ?)
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute(sql, (task_id, word_file, pdf_file, now, user_id))

    def update_task(self, task_id: str, **kwargs: Any) -> bool:
        """更新比对任务字段。

        Args:
            task_id: 任务唯一标识。
            **kwargs: 需要更新的字段（如 status, result_summary, completed_at）。

        Returns:
            是否更新成功。
        """
        if not kwargs:
            return False

        # 如果状态变为完成，自动设置 completed_at
        if kwargs.get("status") in ("completed", "failed") and "completed_at" not in kwargs:
            kwargs["completed_at"] = datetime.now(timezone.utc).isoformat()

        sets = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [task_id]
        sql = f"UPDATE comparison_tasks SET {sets} WHERE task_id = ?"

        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, values)
                return cursor.rowcount > 0

    def get_task(self, task_id: str) -> Optional[dict]:
        """获取单个比对任务。

        Args:
            task_id: 任务唯一标识。

        Returns:
            任务字典，不存在则返回 None。
        """
        sql = "SELECT * FROM comparison_tasks WHERE task_id = ?"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_tasks(self, limit: int = 50, offset: int = 0,
                   user_id: str | None = None) -> list[dict]:
        """列出比对任务。

        Args:
            limit: 返回数量上限。
            offset: 偏移量。
            user_id: 可选，按用户 ID 过滤。

        Returns:
            任务字典列表。
        """
        if user_id:
            sql = "SELECT * FROM comparison_tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params: tuple = (user_id, limit, offset)
        else:
            sql = "SELECT * FROM comparison_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def delete_task(self, task_id: str) -> bool:
        """删除比对任务。

        Args:
            task_id: 任务唯一标识。

        Returns:
            是否删除成功。
        """
        sql = "DELETE FROM comparison_tasks WHERE task_id = ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, (task_id,))
                return cursor.rowcount > 0

    # ----------------------------------------------------------
    # 审计日志（AuditLogStorage）
    # ----------------------------------------------------------

    def log_event(self, event_type: str, user_id: str = "",
                  details: dict | None = None) -> None:
        """记录审计事件。

        Args:
            event_type: 事件类型（如 login, compare, export）。
            user_id: 关联用户 ID。
            details: 事件详情字典，将序列化为 JSON。
        """
        now = datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(details or {}, ensure_ascii=False)
        sql = "INSERT INTO audit_logs (event_type, user_id, details_json, timestamp) VALUES (?, ?, ?, ?)"
        with self._lock:
            with self._connect() as conn:
                conn.execute(sql, (event_type, user_id, details_json, now))

    def query_logs(self, start_time: str | None = None,
                   end_time: str | None = None,
                   user_id: str | None = None,
                   event_type: str | None = None,
                   limit: int = 100) -> list[dict]:
        """查询审计日志。

        Args:
            start_time: 起始时间（ISO 格式），可选。
            end_time: 结束时间（ISO 格式），可选。
            user_id: 按用户 ID 过滤，可选。
            event_type: 按事件类型过滤，可选。
            limit: 返回数量上限。

        Returns:
            日志字典列表。
        """
        conditions: list[str] = []
        params: list = []

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM audit_logs{where_clause} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            results = [dict(row) for row in cursor.fetchall()]
            # 反序列化 details_json
            for r in results:
                try:
                    r["details"] = json.loads(r.pop("details_json", "{}"))
                except (json.JSONDecodeError, KeyError):
                    r["details"] = {}
            return results

    # ----------------------------------------------------------
    # API Key 存储
    # ----------------------------------------------------------

    def store_api_key(self, key_id: str, plain_key: str, role: str,
                      label: str = "") -> None:
        """存储 API Key（HMAC 哈希，兼容 auth.py）。

        Args:
            key_id: Key 唯一标识。
            plain_key: 明文 API Key。
            role: 角色。
            label: 标签。
        """
        key_hash = self._hmac.hash_key(plain_key)
        now = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT OR REPLACE INTO api_keys (key_id, key_hash, role, label, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute(sql, (key_id, key_hash, role, label, now))

    def verify_api_key(self, plain_key: str) -> Optional[dict]:
        """验证 API Key。

        Args:
            plain_key: 明文 API Key。

        Returns:
            匹配的 Key 信息字典，未匹配返回 None。
        """
        sql = "SELECT * FROM api_keys WHERE is_active = 1"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            for row in cursor.fetchall():
                r = dict(row)
                if self._hmac.verify_key(plain_key, r["key_hash"]):
                    # 更新最后使用时间
                    now = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
                        (now, r["key_id"]),
                    )
                    r["last_used_at"] = now
                    return r
        return None

    def list_api_keys(self) -> list[dict]:
        """列出所有 API Key（不返回哈希值）。"""
        sql = "SELECT key_id, role, label, created_at, last_used_at, is_active FROM api_keys"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    def delete_api_key(self, key_id: str) -> bool:
        """删除 API Key。"""
        sql = "DELETE FROM api_keys WHERE key_id = ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, (key_id,))
                return cursor.rowcount > 0

    def toggle_api_key(self, key_id: str) -> bool:
        """启用/禁用 API Key。"""
        sql = "UPDATE api_keys SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE key_id = ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, (key_id,))
                return cursor.rowcount > 0

    # ----------------------------------------------------------
    # 配置文件（Profile）存储
    # ----------------------------------------------------------

    def save_profile(self, name: str, config: dict) -> None:
        """保存比对配置文件。

        Args:
            name: 配置名称。
            config: 配置字典。
        """
        now = datetime.now(timezone.utc).isoformat()
        config_json = json.dumps(config, ensure_ascii=False)

        # 尝试更新，不存在则插入
        sql_check = "SELECT id FROM profiles WHERE name = ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql_check, (name,))
                existing = cursor.fetchone()
                if existing:
                    conn.execute(
                        "UPDATE profiles SET config_json = ?, updated_at = ? WHERE name = ?",
                        (config_json, now, name),
                    )
                else:
                    conn.execute(
                        "INSERT INTO profiles (name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (name, config_json, now, now),
                    )

    def load_profile(self, name: str) -> Optional[dict]:
        """加载比对配置文件。

        Args:
            name: 配置名称。

        Returns:
            配置字典，不存在返回 None。
        """
        sql = "SELECT config_json FROM profiles WHERE name = ?"
        with self._connect() as conn:
            cursor = conn.execute(sql, (name,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return None
        return None

    def list_profiles(self) -> list[dict]:
        """列出所有配置文件。"""
        sql = "SELECT id, name, created_at, updated_at FROM profiles ORDER BY name"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    def delete_profile(self, name: str) -> bool:
        """删除配置文件。"""
        sql = "DELETE FROM profiles WHERE name = ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, (name,))
                return cursor.rowcount > 0

    # ----------------------------------------------------------
    # LLM 配置存储
    # ----------------------------------------------------------

    def save_llm_config(self, provider: str, model_name: str,
                        api_key: str = "", base_url: str = "",
                        is_default: bool = False) -> int:
        """保存 LLM 模型配置。

        Args:
            provider: 提供商（如 ollama, openai）。
            model_name: 模型名称。
            api_key: API Key 明文（将加密存储）。
            base_url: API 基础 URL。
            is_default: 是否设为默认配置。

        Returns:
            新记录 ID。
        """
        now = datetime.now(timezone.utc).isoformat()
        api_key_encrypted = self._encryption.encrypt(api_key) if api_key else ""

        with self._lock:
            with self._connect() as conn:
                # 如果设为默认，先取消其他默认
                if is_default:
                    conn.execute("UPDATE llm_configs SET is_default = 0 WHERE is_default = 1")

                cursor = conn.execute(
                    """INSERT INTO llm_configs (provider, model_name, api_key_encrypted, base_url, is_default, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (provider, model_name, api_key_encrypted, base_url, int(is_default), now),
                )
                return cursor.lastrowid or 0

    def get_llm_config(self, config_id: int) -> Optional[dict]:
        """获取 LLM 配置（API Key 解密后返回）。"""
        sql = "SELECT * FROM llm_configs WHERE id = ?"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (config_id,))
            row = cursor.fetchone()
            if row:
                r = dict(row)
                # 解密 API Key
                if r.get("api_key_encrypted"):
                    r["api_key"] = self._encryption.decrypt(r["api_key_encrypted"])
                else:
                    r["api_key"] = ""
                return r
        return None

    def get_default_llm_config(self) -> Optional[dict]:
        """获取默认 LLM 配置。"""
        sql = "SELECT * FROM llm_configs WHERE is_default = 1 LIMIT 1"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            row = cursor.fetchone()
            if row:
                r = dict(row)
                if r.get("api_key_encrypted"):
                    r["api_key"] = self._encryption.decrypt(r["api_key_encrypted"])
                else:
                    r["api_key"] = ""
                return r
        return None

    def list_llm_configs(self) -> list[dict]:
        """列出所有 LLM 配置（不返回 API Key 明文）。"""
        sql = "SELECT id, provider, model_name, base_url, is_default, created_at FROM llm_configs ORDER BY id"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    def delete_llm_config(self, config_id: int) -> bool:
        """删除 LLM 配置。"""
        sql = "DELETE FROM llm_configs WHERE id = ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, (config_id,))
                return cursor.rowcount > 0

    # ----------------------------------------------------------
    # 自动清理
    # ----------------------------------------------------------

    def cleanup_expired_tasks(self, max_age_hours: int = 24) -> int:
        """清理过期的比对任务。

        Args:
            max_age_hours: 最大保留小时数，默认 24 小时。

        Returns:
            删除的记录数。
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        sql = "DELETE FROM comparison_tasks WHERE created_at < ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, (cutoff,))
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info("已清理 %d 条过期比对任务（超过 %d 小时）", deleted, max_age_hours)
                return deleted

    def cleanup_expired_audit_logs(self, max_age_days: int = 90) -> int:
        """清理过期的审计日志。

        Args:
            max_age_days: 最大保留天数，默认 90 天。

        Returns:
            删除的记录数。
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        sql = "DELETE FROM audit_logs WHERE timestamp < ?"
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(sql, (cutoff,))
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info("已清理 %d 条过期审计日志（超过 %d 天）", deleted, max_age_days)
                return deleted

    def run_auto_cleanup(self, task_max_age_hours: int = 24,
                         log_max_age_days: int = 90) -> dict[str, int]:
        """执行综合自动清理。

        在非定制模式下调用此方法可确保不留下操作痕迹。

        Args:
            task_max_age_hours: 任务最大保留小时数。
            log_max_age_days: 日志最大保留天数。

        Returns:
            各类清理的删除数量 ``{"tasks": n, "audit_logs": n}``。
        """
        tasks_deleted = self.cleanup_expired_tasks(max_age_hours=task_max_age_hours)
        logs_deleted = self.cleanup_expired_audit_logs(max_age_days=log_max_age_days)
        result = {"tasks": tasks_deleted, "audit_logs": logs_deleted}
        logger.info("自动清理完成: %s", result)
        return result

    # ----------------------------------------------------------
    # 数据迁移
    # ----------------------------------------------------------

    def migrate_from_json(self, json_path: str) -> int:
        """从 JSON 文件迁移数据到 SQLite。

        支持以下 JSON 文件格式：
        - api_keys.json：与 auth.py 的 APIKeyManager 格式兼容
        - profiles.json：与 profiles.py 的 ProfileManager 格式兼容

        Args:
            json_path: JSON 文件路径。

        Returns:
            迁移的记录数。
        """
        if not os.path.isfile(json_path):
            logger.warning("迁移源文件不存在: %s", json_path)
            return 0

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        basename = os.path.basename(json_path).lower()
        count = 0

        with self._lock:
            with self._connect() as conn:
                # 迁移 API Keys
                if "keys" in data or "api_keys" in data or "key" in basename:
                    keys_list = data.get("keys", data.get("api_keys", []))
                    for item in keys_list:
                        try:
                            conn.execute(
                                """INSERT OR REPLACE INTO api_keys
                                   (key_id, key_hash, role, label, created_at, last_used_at, is_active)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    item["key_id"],
                                    item["key_hash"],
                                    item.get("role", "viewer"),
                                    item.get("label", ""),
                                    item.get("created_at", datetime.now(timezone.utc).isoformat()),
                                    item.get("last_used_at"),
                                    int(item.get("is_active", True)),
                                ),
                            )
                            count += 1
                        except Exception as e:
                            logger.warning("迁移 API Key 失败: %s, error=%s", item.get("key_id"), e)

                # 迁移 Profiles
                elif "name" in data or "profile" in basename:
                    # 单个 profile 文件
                    try:
                        name = data.get("name", os.path.splitext(basename)[0])
                        config_json = json.dumps(data, ensure_ascii=False)
                        now = datetime.now(timezone.utc).isoformat()
                        conn.execute(
                            """INSERT OR REPLACE INTO profiles (name, config_json, created_at, updated_at)
                               VALUES (?, ?, ?, ?)""",
                            (
                                name,
                                config_json,
                                data.get("created_at", now),
                                data.get("updated_at", now),
                            ),
                        )
                        count += 1
                    except Exception as e:
                        logger.warning("迁移 Profile 失败: %s, error=%s", json_path, e)

        logger.info("从 %s 迁移了 %d 条记录", json_path, count)
        return count


# ============================================================
# 模块级便捷函数
# ============================================================

_default_db: Optional[DatabaseManager] = None
_db_lock = threading.Lock()


def get_database(db_path: str | None = None) -> DatabaseManager:
    """获取全局 DatabaseManager 实例（单例模式）。

    Args:
        db_path: 数据库路径，仅在首次调用时生效。

    Returns:
        DatabaseManager 实例。
    """
    global _default_db
    if _default_db is None:
        with _db_lock:
            if _default_db is None:
                _default_db = DatabaseManager(db_path=db_path)
    return _default_db


def migrate_from_json(json_path: str, db_path: str | None = None) -> int:
    """从 JSON 文件迁移数据到 SQLite 的便捷函数。

    Args:
        json_path: JSON 文件路径。
        db_path: 数据库路径，可选。

    Returns:
        迁移的记录数。
    """
    db = get_database(db_path=db_path)
    return db.migrate_from_json(json_path)
