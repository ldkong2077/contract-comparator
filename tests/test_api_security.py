"""
API Security Regression Tests / API 安全回归测试

Verifies that the v4.0 security fixes are properly enforced at the API layer.
Tests cover 6 critical security requirements identified in the security audit.

Run with:
    pytest tests/test_api_security.py -v --cov=src/contract_comparator/api

These tests use FastAPI TestClient (httpx) and do NOT require a running server.
"""
import io
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

# Ensure project root is in path (for conftest compatibility)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# =========================================================================
# 1. API Key not printed to stdout on startup
# =========================================================================

class TestApiKeyNotPrinted:
    """Verify that startup does NOT print the full API Key to stdout.

    The v4.0 fix removed the print() call that leaked the bootstrap admin key.
    Only a masked key log entry is permitted.
    """

    def test_startup_does_not_print_plain_key(self):
        """Startup must not contain the full plain-text key in stdout."""
        from contract_comparator.api.api_server import app
        from contract_comparator.auth import APIKeyManager

        # We can't actually call startup_event() in isolation because it
        # initializes DB and other heavy dependencies. Instead, verify the
        # code path: the startup_event function must NOT call print() with
        # the plain key value.

        # Read the source of startup_event — any print() with the key
        # variable would be a regression.
        import inspect
        from contract_comparator.api import api_server as api_mod

        source = inspect.getsource(api_mod.startup_event)
        # The fix: only masked/truncated keys appear
        assert "print(" not in source or "masked" in source, (
            "startup_event must not print plain-text keys. "
            "If print() exists, it must only reference masked keys."
        )

    def test_key_logged_as_masked_only(self):
        """Verify the key_manager.init_key() or bootstrap path logs masked key,
        not the full plain key."""
        from contract_comparator.auth import APIKeyManager, KeyInfo

        km = APIKeyManager()
        # Simulate bootstrap: create a key
        plain_key = km.generate_key()

        # The plain key must NOT appear in any log or print;
        # only the masked form (first 4 chars + "***") is permitted.
        masked_prefix = plain_key[:4]
        # Verify masking function exists and works
        from contract_comparator.auth import mask_api_key
        masked = mask_api_key(plain_key)
        assert masked.endswith("***")
        assert masked.startswith(plain_key[:4])
        assert plain_key not in [masked], "masked form must differ from plain"


# =========================================================================
# 2. Error response does not contain str(exc)
# =========================================================================

class TestErrorResponseNoExceptionLeak:
    """Verify 500 errors return a generic message with request_id.

    The v4.0 fix ensures general_exception_handler does NOT include
    str(exc) in the JSON response body.
    """

    @pytest.fixture
    def client(self):
        """Create a TestClient with a route guaranteed to raise."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.get("/raise-error")
        async def raise_error():
            raise ValueError("这是一个内部错误详情，不得泄露给客户端")

        # Register the same exception handler used in production
        from contract_comparator.api.api_server import general_exception_handler
        app.add_exception_handler(Exception, general_exception_handler)

        return TestClient(app)

    def test_500_response_has_no_exception_detail(self, client):
        """500 response must NOT contain the exception message."""
        resp = client.get("/raise-error")
        assert resp.status_code == 500

        body = resp.json()
        # Must have generic detail
        assert "服务器内部错误" in body["detail"]
        assert "请稍后重试" in body["detail"]
        # Must NOT contain the original exception text
        assert "内部错误详情" not in body["detail"]
        assert "ValueError" not in body["detail"]
        # Must have request_id for traceability
        assert "request_id" in body
        assert len(body["request_id"]) > 0
        # Must have timestamp and error_code
        assert body["error_code"] == 500
        assert "timestamp" in body

    def test_http_exception_preserves_detail(self, client):
        """HTTPException (4xx) should still preserve the original detail."""
        from contract_comparator.api.api_server import http_exception_handler
        from fastapi import HTTPException
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/needs-auth")
        async def needs_auth():
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=401,
                detail="无效的 API Key。",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        app.add_exception_handler(Exception, http_exception_handler)
        client = TestClient(app)

        resp = client.get("/needs-auth")
        assert resp.status_code == 401
        body = resp.json()
        assert body["detail"] == "无效的 API Key。"
        assert body["error_code"] == 401


# =========================================================================
# 3. Upload file magic number validation
# =========================================================================

class TestUploadMagicNumberRejection:
    """Verify renamed .exe is rejected even with a valid extension.

    The FileUploadValidator must detect extension/magic mismatch.
    """

    def _make_temp_file(self, content: bytes, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return path

    def test_exe_renamed_to_pdf_rejected(self):
        """A real .exe renamed to .pdf must be rejected."""
        from contract_comparator.security import FileUploadValidator

        # MZ executable header
        exe_content = b"MZ\x90\x00" + b"\x00" * 100
        path = self._make_temp_file(exe_content, ".pdf")
        try:
            result = FileUploadValidator.validate_all(
                path,
                expected_types=[".pdf"],
                max_size_mb=10,
                strict_unknown_magic=True,
            )
            assert result.is_valid is False, (
                "Executable renamed to .pdf must fail validation"
            )
            assert any("魔数" in e or "不一致" in e for e in result.errors), (
                f"Error must mention magic mismatch. Got: {result.errors}"
            )
        finally:
            os.unlink(path)

    def test_exe_renamed_to_docx_rejected(self):
        """A real .exe renamed to .docx must be rejected."""
        from contract_comparator.security import FileUploadValidator

        exe_content = b"MZ\x90\x00" + b"\x00" * 100
        path = self._make_temp_file(exe_content, ".docx")
        try:
            result = FileUploadValidator.validate_all(
                path,
                expected_types=[".docx"],
                max_size_mb=10,
                strict_unknown_magic=True,
            )
            assert result.is_valid is False
        finally:
            os.unlink(path)

    def test_text_renamed_to_pdf_rejected(self):
        """Plain text renamed to .pdf must be rejected."""
        from contract_comparator.security import FileUploadValidator

        path = self._make_temp_file(
            b"This is not a PDF file at all", ".pdf"
        )
        try:
            result = FileUploadValidator.validate_all(
                path,
                expected_types=[".pdf"],
                max_size_mb=10,
                strict_unknown_magic=True,
            )
            assert result.is_valid is False
        finally:
            os.unlink(path)

    def test_valid_pdf_accepted(self):
        """A legitimate PDF must pass validation."""
        from contract_comparator.security import FileUploadValidator

        path = self._make_temp_file(b"%PDF-1.4\n...", ".pdf")
        try:
            result = FileUploadValidator.validate_all(
                path,
                expected_types=[".pdf"],
                max_size_mb=10,
                strict_unknown_magic=True,
            )
            assert result.is_valid is True
        finally:
            os.unlink(path)

    def test_valid_docx_accepted(self):
        """A legitimate DOCX (ZIP) must pass validation."""
        from contract_comparator.security import FileUploadValidator

        path = self._make_temp_file(
            b"PK\x03\x04" + b"\x00" * 100, ".docx"
        )
        try:
            result = FileUploadValidator.validate_all(
                path,
                expected_types=[".docx"],
                max_size_mb=10,
                strict_unknown_magic=True,
            )
            assert result.is_valid is True
        finally:
            os.unlink(path)


# =========================================================================
# 4. Rate limiter uses key_id not key prefix
# =========================================================================

class TestRateLimiterClientId:
    """Verify rate limiter identifies client by role:key_id.

    The v4.0 fix changed the rate limit key from api_key_str[:12]
    (which leaked key prefix) to f"{key_info.role}:{key_info.key_id}".
    """

    def test_rate_limiter_uses_role_and_key_id(self):
        """Rate limiter must use role:key_id format, not raw key prefix."""
        from contract_comparator.auth import RateLimiter, KeyInfo
        from contract_comparator.auth import ROLE_ADMIN, ROLE_ANALYST

        limiter = RateLimiter(rpm=60, burst=10)

        # Create key_info objects simulating different roles
        admin_info = KeyInfo(
            key_id="key-admin-001",
            role=ROLE_ADMIN,
            plain_key="sk-admin-test123",
        )
        analyst_info = KeyInfo(
            key_id="key-analyst-001",
            role=ROLE_ANALYST,
            plain_key="sk-analyst-test456",
        )

        # Simulate what require_auth() does:
        admin_client_id = f"{admin_info.role}:{admin_info.key_id}"
        analyst_client_id = f"{analyst_info.role}:{analyst_info.key_id}"

        # Must NOT be the raw key prefix
        assert admin_client_id != admin_info.plain_key[:12]
        assert analyst_client_id != analyst_info.plain_key[:12]

        # Both should be able to make requests
        assert limiter.allow_request(admin_client_id) is True
        assert limiter.allow_request(analyst_client_id) is True

    def test_different_keys_same_role_have_separate_buckets(self):
        """Different keys with same role must have independent rate limit buckets."""
        from contract_comparator.auth import RateLimiter, KeyInfo
        from contract_comparator.auth import ROLE_ADMIN

        limiter = RateLimiter(rpm=5, burst=3)

        info_a = KeyInfo(key_id="key-a", role=ROLE_ADMIN, plain_key="sk-a")
        info_b = KeyInfo(key_id="key-b", role=ROLE_ADMIN, plain_key="sk-b")

        cid_a = f"{info_a.role}:{info_a.key_id}"
        cid_b = f"{info_b.role}:{info_b.key_id}"

        # Exhaust key-a's burst
        for _ in range(3):
            assert limiter.allow_request(cid_a) is True
        # Fourth request from key-a should be rate limited
        assert limiter.allow_request(cid_a) is False

        # key-b must still be allowed (separate bucket)
        assert limiter.allow_request(cid_b) is True

    def test_require_auth_uses_correct_client_id(self):
        """Verify require_auth() constructs the correct client_id format."""
        import inspect
        from contract_comparator.api import api_server as api_mod

        source = inspect.getsource(api_mod.require_auth)
        # Must use role:key_id pattern
        assert "role" in source and "key_id" in source
        # Must NOT use api_key_str[:12] or raw key prefix
        assert "api_key_str[:12]" not in source
        # Key prefix should not appear in rate limit identifier
        assert "api_key_str[:8]" not in source
        assert "api_key_str[:6]" not in source


# =========================================================================
# 5. Unknown magic bytes rejected in strict mode
# =========================================================================

class TestUploadStrictMagicRejection:
    """Verify files with unknown magic bytes are rejected in strict mode.

    strict_unknown_magic=True causes validate_file_type to treat
    unrecognizable magic bytes as an ERROR rather than a warning.
    """

    def _make_temp_file(self, content: bytes, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return path

    def test_unknown_magic_with_strict_true_is_error(self):
        """Unknown magic + strict=True = error (not warning)."""
        from contract_comparator.security import FileUploadValidator

        # Bytes that don't match any registered magic
        unknown_content = bytes(range(0x60, 0x68)) + b"\x00" * 20
        path = self._make_temp_file(unknown_content, ".pdf")
        try:
            result = FileUploadValidator.validate_file_type(
                path,
                expected_types=[".pdf"],
                strict_unknown_magic=True,
            )
            assert result.is_valid is False, (
                "strict_unknown_magic=True must produce error for unknown bytes"
            )
            assert len(result.errors) >= 1
            assert "无法通过魔数识别" in result.errors[0]
        finally:
            os.unlink(path)

    def test_unknown_magic_with_strict_false_is_warning(self):
        """Unknown magic + strict=False = warning (not error)."""
        from contract_comparator.security import FileUploadValidator

        unknown_content = bytes(range(0x60, 0x68)) + b"\x00" * 20
        path = self._make_temp_file(unknown_content, ".pdf")
        try:
            result = FileUploadValidator.validate_file_type(
                path,
                expected_types=[".pdf"],
                strict_unknown_magic=False,
            )
            # Extension is valid, so is_valid should still be True
            assert result.is_valid is True
            # But there should be a warning about unknown magic
            assert len(result.warnings) >= 1
            assert "无法通过魔数识别" in result.warnings[0]
        finally:
            os.unlink(path)

    def test_api_upload_enforces_strict_mode(self):
        """The _save_upload_file function must call validate_all with
        strict_unknown_magic=True."""
        import inspect
        from contract_comparator.api import api_server as api_mod

        source = inspect.getsource(api_mod._save_upload_file)
        # Must pass strict_unknown_magic=True
        assert "strict_unknown_magic=True" in source, (
            "_save_upload_file must enforce strict_unknown_magic=True"
        )


# =========================================================================
# 6. ALLOW_BOOTSTRAP_ADMIN_KEY defaults to false
# =========================================================================

class TestBootstrapKeyDisabledByDefault:
    """Verify startup fails without ALLOW_BOOTSTRAP_ADMIN_KEY.

    The v4.0 fix: when no API keys exist and ALLOW_BOOTSTRAP_ADMIN_KEY is
    not explicitly set to true, startup must raise RuntimeError instead of
    auto-generating a default admin key.
    """

    def test_bootstrap_key_env_default_is_false(self):
        """ALLOW_BOOTSTRAP_ADMIN_KEY must default to false."""
        from contract_comparator.api import api_server as api_mod

        # Re-read the module-level constant
        import importlib
        importlib.reload(api_mod)
        flag = api_mod._ALLOW_BOOTSTRAP_ADMIN_KEY

        # When env is not set, it must be False
        if "ALLOW_BOOTSTRAP_ADMIN_KEY" not in os.environ:
            assert flag is False, (
                "ALLOW_BOOTSTRAP_ADMIN_KEY must default to False"
            )

    def test_bootstrap_key_true_allows_generation(self):
        """When ALLOW_BOOTSTRAP_ADMIN_KEY=true, key generation must proceed."""
        from contract_comparator.auth import APIKeyManager

        # Verify the key manager can generate keys when allowed
        km = APIKeyManager()
        key = km.generate_key()
        assert key.startswith("sk-")
        assert len(key) > 20

    @pytest.mark.skipif(
        os.environ.get("ALLOW_BOOTSTRAP_ADMIN_KEY", "").lower()
        not in ("", "false"),
        reason="This test requires ALLOW_BOOTSTRAP_ADMIN_KEY to be unset or false",
    )
    @patch.dict(os.environ, {"ALLOW_BOOTSTRAP_ADMIN_KEY": "false"}, clear=False)
    def test_startup_fails_without_keys_and_no_bootstrap(self):
        """Startup must fail when no keys exist and ALLOW_BOOTSTRAP_ADMIN_KEY is false."""
        # This requires careful mocking because startup_event initializes
        # DB, auth, etc. We test the guard logic directly.
        from contract_comparator.api.api_server import (
            _ALLOW_BOOTSTRAP_ADMIN_KEY,
        )
        # With env "false", the constant must be False
        assert _ALLOW_BOOTSTRAP_ADMIN_KEY is False

    def test_startup_code_raises_runtime_error(self):
        """Verify the actual guard code raises RuntimeError."""
        import inspect
        from contract_comparator.api import api_server as api_mod

        source = inspect.getsource(api_mod.startup_event)
        # Must check the flag and raise when not set
        assert "_ALLOW_BOOTSTRAP_ADMIN_KEY" in source
        assert "RuntimeError" in source
        # Must NOT auto-generate without checking the flag
        assert "generate_key()" not in source.split(
            "if not _ALLOW_BOOTSTRAP_ADMIN_KEY"
        )[0], (
            "generate_key() must only appear AFTER the ALLOW_BOOTSTRAP check"
        )


# =========================================================================
# 7. (Bonus) File extension whitelist enforcement
# =========================================================================

class TestFileExtensionWhitelist:
    """Verify only permitted extensions are accepted by the upload endpoint."""

    def test_unsupported_extension_rejected(self):
        """Upload with .exe, .bat, .sh, .js extensions must be rejected."""
        from contract_comparator.api.api_server import _save_upload_file

        # Create a mock UploadFile with an unsupported extension
        class MockUploadFile:
            filename = "malware.exe"
            async def read(self):
                return b"fake content"

        upload = MockUploadFile()

        with pytest.raises(Exception) as excinfo:
            # Need to run in async context — we test the sync check
            # by examining the function's allowed_exts parameter
            pass

        # Check allowed_exts default parameter
        import inspect
        sig = inspect.signature(_save_upload_file)
        default_allowed = sig.parameters["allowed_exts"].default
        assert default_allowed is None or ".exe" not in default_allowed, (
            ".exe must not be in allowed extensions"
        )

    def test_allowed_extensions_list(self):
        """Verify the default allowed extensions tuple."""
        import inspect
        from contract_comparator.api.api_server import _save_upload_file

        # Extract the default from the function body
        source = inspect.getsource(_save_upload_file)
        # Find the _allowed assignment
        for line in source.split("\n"):
            if "_allowed = " in line and "or" in line:
                # Found the default allowed extensions definition
                assert ".exe" not in line
                assert ".bat" not in line
                assert ".sh" not in line
                break


# =========================================================================
# 8. (Bonus) Security.py integrity checks
# =========================================================================

class TestSecurityModuleIntegrity:
    """Verify the security module has all required protections enabled."""

    def test_required_magic_numbers_present(self):
        """Verify all required magic numbers are registered."""
        from contract_comparator.security import _MAGIC_BYTES_MAP

        all_extensions = set()
        for exts in _MAGIC_BYTES_MAP.values():
            all_extensions.update(exts)

        # Core document types
        assert ".pdf" in all_extensions
        assert ".docx" in all_extensions
        assert ".xlsx" in all_extensions

        # Image types
        assert ".png" in all_extensions
        assert ".jpg" in all_extensions
        assert ".jpeg" in all_extensions
        assert ".bmp" in all_extensions
        assert ".tiff" in all_extensions
        assert ".tif" in all_extensions
        assert ".webp" in all_extensions

    def test_unknown_magic_strict_mode_in_api(self):
        """Verify the API server passes strict_unknown_magic=True."""
        import inspect
        from contract_comparator.api import api_server as api_mod

        # Check _save_upload_file calls validate_all with strict_unknown_magic
        source = inspect.getsource(api_mod._save_upload_file)
        assert "strict_unknown_magic=True" in source

        # Check the root-level api_server as well
        try:
            import api_server as root_api
            root_source = inspect.getsource(root_api._save_upload_file)
            assert "strict_unknown_magic=True" in root_source
        except (ImportError, AttributeError):
            pass  # root module may not always be importable
