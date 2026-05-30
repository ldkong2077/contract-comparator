"""
安全基线测试 — 验证项目中无敏感文件泄露
"""
import json
import os

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSensitiveFiles:
    """验证配置目录不包含运行态密钥"""

    def test_api_keys_json_is_empty_template(self):
        api_keys_path = os.path.join(PROJECT_ROOT, "config", "api_keys.json")
        assert os.path.exists(api_keys_path), "config/api_keys.json must exist"

        with open(api_keys_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "keys" in data, "api_keys.json must have 'keys' field"
        assert isinstance(data["keys"], list), "'keys' must be a list"
        assert len(data["keys"]) == 0, "api_keys.json must not contain any actual keys"

    def test_no_secret_file_exists(self):
        secret_path = os.path.join(PROJECT_ROOT, "config", "api_keys.json.secret")
        assert not os.path.exists(secret_path), (
            "config/api_keys.json.secret must not exist — contains plaintext secrets"
        )

    def test_no_admin_keys_file(self):
        admin_path = os.path.join(PROJECT_ROOT, "config", "admin_keys.json")
        assert not os.path.exists(admin_path), (
            "config/admin_keys.json must not exist in open-source distribution"
        )

    def test_gitignore_excludes_sensitive_files(self):
        gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
        assert os.path.exists(gitignore_path), ".gitignore must exist"

        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "config/api_keys.json" in content, ".gitignore must exclude config/api_keys.json"
        assert "config/api_keys.json.secret" in content, (
            ".gitignore must exclude config/api_keys.json.secret"
        )
        assert "config/admin_keys.json" in content, (
            ".gitignore must exclude config/admin_keys.json"
        )

    def test_env_example_not_real_env(self):
        env_example = os.path.join(PROJECT_ROOT, ".env.example")
        env_real = os.path.join(PROJECT_ROOT, ".env")
        assert os.path.exists(env_example), ".env.example must exist"
        if os.path.exists(env_real):
            with open(env_real, "r", encoding="utf-8") as f:
                content = f.read()
            assert "sk-" not in content.lower(), ".env must not contain real API keys"
            assert content.strip() != "", ".env must not be empty if it exists"
