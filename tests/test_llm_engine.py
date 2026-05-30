"""
LLM Engine 单元测试
测试 OllamaProvider、ClaudeProvider 初始化及可用性检测，LLMEngine 门面类功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock

import pytest

from llm_engine import OllamaProvider, ClaudeProvider, LLMEngine


class TestOllamaProvider:
    """Ollama Provider 测试"""

    def test_ollama_provider_init(self):
        """OllamaProvider 初始化应正确设置属性"""
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="qwen3.5-0.8b",
            timeout=30,
        )
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "qwen3.5-0.8b"
        assert provider.timeout == 30

    def test_ollama_provider_init_defaults(self):
        """OllamaProvider 默认参数应从配置读取"""
        provider = OllamaProvider()
        assert provider.base_url is not None
        assert provider.model is not None
        assert provider.timeout > 0

    def test_ollama_provider_not_available(self):
        """Ollama 服务未运行时 is_available 应返回 False"""
        provider = OllamaProvider(base_url="http://localhost:19999")
        # 连接不存在的端口，应返回 False
        assert provider.is_available() is False

    def test_ollama_provider_name(self):
        """get_provider_name 应返回 'ollama'"""
        provider = OllamaProvider()
        assert provider.get_provider_name() == "ollama"

    def test_ollama_analyze_semantic_diff_failure(self):
        """Ollama 不可用时 analyze_semantic_diff 应返回错误结果"""
        provider = OllamaProvider(base_url="http://localhost:19999", timeout=2)
        result = provider.analyze_semantic_diff("Word文本", "PDF文本")
        assert result["confidence"] == 0.0
        assert "失败" in result["analysis"] or "异常" in result["summary"]

    def test_ollama_build_prompt(self):
        """_build_prompt 应生成包含用户文本的 prompt"""
        prompt = OllamaProvider._build_prompt("Word内容", "PDF内容")
        assert "Word内容" in prompt
        assert "PDF内容" in prompt
        assert "合同审查" in prompt

    def test_ollama_parse_response_valid_json(self):
        """_parse_response 应正确解析合法 JSON"""
        json_str = '{"analysis": "测试分析", "risk_items": [], "summary": "测试", "confidence": 0.8}'
        result = OllamaProvider._parse_response(json_str)
        assert result["analysis"] == "测试分析"
        assert result["confidence"] == 0.8

    def test_ollama_parse_response_markdown_block(self):
        """_parse_response 应处理 markdown 代码块包裹的 JSON"""
        json_str = '```json\n{"analysis": "测试", "risk_items": [], "summary": "测试", "confidence": 0.5}\n```'
        result = OllamaProvider._parse_response(json_str)
        assert result["analysis"] == "测试"

    def test_ollama_parse_response_invalid_json(self):
        """_parse_response 对无效 JSON 应返回降级结果"""
        result = OllamaProvider._parse_response("这不是JSON")
        assert result["confidence"] == 0.0
        assert result["summary"] == "解析失败"


class TestClaudeProvider:
    """Claude Provider 测试"""

    def test_claude_provider_init(self):
        """ClaudeProvider 初始化应正确设置属性"""
        provider = ClaudeProvider(
            api_key="sk-test-key",
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            timeout=60,
        )
        assert provider.api_key == "sk-test-key"
        assert provider.model == "claude-sonnet-4-20250514"
        assert provider.max_tokens == 4096
        assert provider.timeout == 60

    def test_claude_provider_init_defaults(self):
        """ClaudeProvider 默认参数应从配置读取"""
        provider = ClaudeProvider()
        assert provider.model is not None
        assert provider.max_tokens > 0
        assert provider.timeout > 0

    def test_claude_provider_not_available(self):
        """无 API Key 时 is_available 应返回 False"""
        provider = ClaudeProvider(api_key="")
        assert provider.is_available() is False

    def test_claude_provider_name(self):
        """get_provider_name 应返回 'claude'"""
        provider = ClaudeProvider()
        assert provider.get_provider_name() == "claude"

    def test_claude_friendly_http_error_401(self):
        """401 错误应返回认证失败提示"""
        import urllib.error
        mock_err = urllib.error.HTTPError(
            url="http://test", code=401, msg="Unauthorized",
            hdrs=None, fp=None,
        )
        msg = ClaudeProvider._friendly_http_error(mock_err)
        assert "认证失败" in msg

    def test_claude_friendly_http_error_429(self):
        """429 错误应返回限流提示"""
        import urllib.error
        mock_err = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests",
            hdrs=None, fp=None,
        )
        msg = ClaudeProvider._friendly_http_error(mock_err)
        assert "频率超限" in msg

    def test_claude_analyze_semantic_diff_with_mock(self):
        """使用 mock 测试 Claude analyze_semantic_diff"""
        provider = ClaudeProvider(api_key="sk-test-key")
        # mock _raw_call 返回合法 JSON
        with patch.object(provider, '_raw_call', return_value='{"analysis": "测试", "risk_items": [], "summary": "测试", "confidence": 0.9}'):
            result = provider.analyze_semantic_diff("Word文本", "PDF文本")
            assert result["analysis"] == "测试"
            assert result["confidence"] == 0.9


class TestLLMEngine:
    """LLM Engine 门面类测试"""

    def test_llm_engine_default_provider(self):
        """默认 Provider 应从配置读取"""
        engine = LLMEngine()
        assert engine._provider is not None
        assert isinstance(engine._provider, (OllamaProvider, ClaudeProvider))

    def test_llm_engine_set_provider(self):
        """set_provider 应切换当前 Provider"""
        engine = LLMEngine(provider="ollama")
        assert isinstance(engine._provider, OllamaProvider)
        engine.set_provider("claude", api_key="sk-test")
        assert isinstance(engine._provider, ClaudeProvider)

    def test_llm_engine_set_provider_invalid(self):
        """设置不存在的 Provider 应抛出 ValueError"""
        engine = LLMEngine()
        with pytest.raises(ValueError, match="未知的 LLM Provider"):
            engine.set_provider("nonexistent")

    def test_llm_engine_list_providers(self):
        """list_available_providers 应返回所有已注册 Provider"""
        engine = LLMEngine()
        providers = engine.list_available_providers()
        assert isinstance(providers, list)
        names = [p["name"] for p in providers]
        assert "ollama" in names
        assert "claude" in names

    def test_llm_engine_backward_compat(self):
        """LLMEngine() 无参数调用应正常工作（向后兼容）"""
        engine = LLMEngine()
        assert engine._provider is not None
        assert engine.enabled is not None

    def test_llm_engine_with_provider_instance(self):
        """直接传入 Provider 实例应正常工作"""
        ollama = OllamaProvider()
        engine = LLMEngine(provider=ollama)
        assert engine.provider is ollama

    def test_llm_engine_analyze_disabled(self):
        """LLM 未启用时 analyze_semantic_diff 应返回不可用提示"""
        engine = LLMEngine()
        # 强制禁用
        engine.enabled = False
        result = engine.analyze_semantic_diff("Word", "PDF")
        assert result["confidence"] == 0.0
        assert "未启用" in result["analysis"] or "不可用" in result["analysis"]

    def test_llm_engine_generate_text_disabled(self):
        """LLM 未启用时 generate_text 应返回空字符串"""
        engine = LLMEngine()
        engine.enabled = False
        result = engine.generate_text("测试提示")
        assert result == ""

    def test_llm_engine_generate_risk_report_html(self):
        """generate_risk_report_html 应生成 HTML"""
        engine = LLMEngine()
        analysis = {
            "analysis": "测试分析",
            "risk_items": [
                {
                    "description": "测试风险",
                    "severity": "high",
                    "word_text": "原文",
                    "pdf_text": "扫描件",
                    "risk_type": "同义词替换",
                }
            ],
            "summary": "总体评估",
            "confidence": 0.8,
        }
        html = engine.generate_risk_report_html(analysis)
        assert "测试分析" in html
        assert "测试风险" in html

    def test_llm_engine_generate_risk_report_html_empty(self):
        """空分析结果应返回默认提示"""
        engine = LLMEngine()
        html = engine.generate_risk_report_html({})
        assert "未启用" in html or "不可用" in html
