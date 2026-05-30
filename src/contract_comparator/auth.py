"""
认证与权限模块：API Key 管理 + RBAC 角色权限控制

为合同比对 API 提供轻量级认证机制，适用于企业内部局域网部署。
全部使用 Python 标准库，无外部认证依赖。
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ============================================================
# 常量
# ============================================================

# 角色定义
ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_VIEWER = "viewer"

# 权限定义
PERMISSION_COMPARE = "compare"
PERMISSION_EXPORT = "export"
PERMISSION_MANAGE_KEYS = "manage_keys"
PERMISSION_MANAGE_PROFILES = "manage_profiles"
PERMISSION_VIEW_AUDIT = "view_audit"

# 角色 → 权限映射
ROLE_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ADMIN: [
        PERMISSION_COMPARE,
        PERMISSION_EXPORT,
        PERMISSION_MANAGE_KEYS,
        PERMISSION_MANAGE_PROFILES,
        PERMISSION_VIEW_AUDIT,
    ],
    ROLE_ANALYST: [
        PERMISSION_COMPARE,
        PERMISSION_EXPORT,
        PERMISSION_MANAGE_PROFILES,
    ],
    ROLE_VIEWER: [
        PERMISSION_EXPORT,
    ],
}

# API Key 前缀
KEY_PREFIX = "cc"


# ============================================================
# 数据类
# ============================================================

@dataclass
class APIKeyInfo:
    """API Key 信息"""
    key_id: str
    key_hash: str  # HMAC-SHA256 哈希
    role: str
    label: str
    created_at: str
    last_used_at: Optional[str] = None
    is_active: bool = True


# ============================================================
# APIKeyManager
# ============================================================

class APIKeyManager:
    """
    API Key 管理器：生成、验证、存储 API Key。

    安全设计：
    - 存储时使用 HMAC-SHA256 哈希，不存储明文
    - 验证时使用 hmac.compare_digest 防止时序攻击
    - Key 格式：cc_{role}_{32位随机hex}
    """

    def __init__(self, keys_file: str):
        self._keys_file = os.path.abspath(keys_file)
        self._lock = threading.Lock()
        self._keys: dict[str, APIKeyInfo] = {}  # key_id → APIKeyInfo
        self._secret = self._load_or_create_secret()
        self._load()

    def _load_or_create_secret(self) -> bytes:
        """加载或创建 HMAC 密钥（用于 Key 哈希）"""
        secret_file = self._keys_file + ".secret"
        if os.path.exists(secret_file):
            with open(secret_file, "rb") as f:
                return f.read()
        else:
            secret = secrets.token_bytes(32)
            os.makedirs(os.path.dirname(self._keys_file) or ".", exist_ok=True)
            with open(secret_file, "wb") as f:
                f.write(secret)
            # 限制文件权限（仅所有者可读）
            try:
                os.chmod(secret_file, 0o600)
            except OSError:
                pass
            return secret

    def _load(self) -> None:
        """从文件加载 API Key 列表"""
        try:
            if os.path.exists(self._keys_file):
                with open(self._keys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("keys", []):
                    key_id = item["key_id"]
                    self._keys[key_id] = APIKeyInfo(
                        key_id=item["key_id"],
                        key_hash=item["key_hash"],
                        role=item["role"],
                        label=item.get("label", ""),
                        created_at=item["created_at"],
                        last_used_at=item.get("last_used_at"),
                        is_active=item.get("is_active", True),
                    )
        except Exception:
            self._keys = {}

    def _save(self) -> None:
        """保存 API Key 列表到文件"""
        os.makedirs(os.path.dirname(self._keys_file) or ".", exist_ok=True)
        data = {
            "keys": [
                {
                    "key_id": k.key_id,
                    "key_hash": k.key_hash,
                    "role": k.role,
                    "label": k.label,
                    "created_at": k.created_at,
                    "last_used_at": k.last_used_at,
                    "is_active": k.is_active,
                }
                for k in self._keys.values()
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self._keys_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _hash_key(self, plain_key: str) -> str:
        """计算 API Key 的 HMAC-SHA256 哈希"""
        return hmac.new(self._secret, plain_key.encode(), hashlib.sha256).hexdigest()

    def generate_key(self, role: str, label: str = "") -> tuple[str, str]:
        """
        生成新的 API Key。

        Returns:
            (plain_key, key_id) - 明文 Key（仅返回一次）和 Key ID
        """
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"无效的角色: {role}（可选: {', '.join(ROLE_PERMISSIONS.keys())})")

        key_id = secrets.token_hex(8)
        random_part = secrets.token_hex(16)
        plain_key = f"{KEY_PREFIX}_{role}_{random_part}"

        key_info = APIKeyInfo(
            key_id=key_id,
            key_hash=self._hash_key(plain_key),
            role=role,
            label=label or f"{role}_key_{key_id[:6]}",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        with self._lock:
            self._keys[key_id] = key_info
            self._save()

        return plain_key, key_id

    def validate_key(self, plain_key: str) -> Optional[APIKeyInfo]:
        """
        验证 API Key。

        Returns:
            APIKeyInfo 如果验证成功，否则 None
        """
        if not plain_key:
            return None

        key_hash = self._hash_key(plain_key)

        with self._lock:
            for key_info in self._keys.values():
                if not key_info.is_active:
                    continue
                if hmac.compare_digest(key_info.key_hash, key_hash):
                    # 更新最后使用时间
                    key_info.last_used_at = datetime.now(timezone.utc).isoformat()
                    self._save()
                    return key_info

        return None

    def list_keys(self) -> list[dict]:
        """列出所有 API Key（不返回哈希值）"""
        with self._lock:
            return [
                {
                    "key_id": k.key_id,
                    "role": k.role,
                    "label": k.label,
                    "created_at": k.created_at,
                    "last_used_at": k.last_used_at,
                    "is_active": k.is_active,
                }
                for k in self._keys.values()
            ]

    def delete_key(self, key_id: str) -> bool:
        """删除 API Key"""
        with self._lock:
            if key_id in self._keys:
                del self._keys[key_id]
                self._save()
                return True
            return False

    def toggle_key(self, key_id: str) -> bool:
        """启用/禁用 API Key"""
        with self._lock:
            if key_id in self._keys:
                self._keys[key_id].is_active = not self._keys[key_id].is_active
                self._save()
                return True
            return False


# ============================================================
# RBACManager
# ============================================================

class RBACManager:
    """基于角色的访问控制管理器"""

    @staticmethod
    def has_permission(role: str, permission: str) -> bool:
        """检查角色是否有指定权限"""
        return permission in ROLE_PERMISSIONS.get(role, [])

    @staticmethod
    def get_role_permissions(role: str) -> list[str]:
        """获取角色的所有权限"""
        return ROLE_PERMISSIONS.get(role, []).copy()

    @staticmethod
    def get_all_roles() -> list[str]:
        """获取所有可用角色"""
        return list(ROLE_PERMISSIONS.keys())


# ============================================================
# 速率限制器（简单内存实现）
# ============================================================

class RateLimiter:
    """
    简单令牌桶速率限制器。

    适用于单机部署，多机部署需使用 Redis。
    """

    def __init__(self, requests_per_minute: int = 30, burst: int = 5):
        self._rpm = requests_per_minute
        self._burst = burst
        self._tokens: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._interval = 60.0 / requests_per_minute  # 每个请求的最小间隔

    def allow_request(self, client_id: str) -> bool:
        """
        检查是否允许请求。

        Returns:
            True 如果允许，False 如果超出限制
        """
        now = time.time()

        with self._lock:
            if client_id not in self._tokens:
                self._tokens[client_id] = []

            # 清理 1 分钟前的记录
            self._tokens[client_id] = [
                t for t in self._tokens[client_id] if now - t < 60
            ]

            tokens = self._tokens[client_id]

            # 检查突发限制
            if len(tokens) >= self._burst:
                # 检查最早请求是否超过 1 秒
                if now - tokens[0] < 1.0:
                    return False

            # 检查每分钟限制
            if len(tokens) >= self._rpm:
                return False

            tokens.append(now)
            return True

    def reset(self, client_id: str) -> None:
        """重置客户端的速率限制"""
        with self._lock:
            self._tokens.pop(client_id, None)


# ============================================================
# 模块级便捷函数
# ============================================================

_default_key_manager: Optional[APIKeyManager] = None
_default_rate_limiter: Optional[RateLimiter] = None


def init_auth(keys_file: str, rate_limit_enabled: bool = True,
              rpm: int = 30, burst: int = 5) -> tuple[APIKeyManager, Optional[RateLimiter]]:
    """初始化认证模块"""
    global _default_key_manager, _default_rate_limiter
    _default_key_manager = APIKeyManager(keys_file)
    _default_rate_limiter = RateLimiter(rpm, burst) if rate_limit_enabled else None
    return _default_key_manager, _default_rate_limiter


def get_key_manager() -> APIKeyManager:
    if _default_key_manager is None:
        raise RuntimeError("认证模块未初始化，请先调用 init_auth()")
    return _default_key_manager


def get_rate_limiter() -> Optional[RateLimiter]:
    return _default_rate_limiter
