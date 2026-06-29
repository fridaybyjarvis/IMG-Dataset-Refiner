"""Tests for ai_backends.py — backend classification, URL normalization,
timeout clamping, token estimation, and API key env-var fallback."""

import os
import sys

import ai_backends


# ── _backend_kind ──────────────────────────────────────────────

class TestBackendKind:
    def test_ollama(self):
        assert ai_backends._backend_kind("Ollama") == "ollama"

    def test_ollama_case_insensitive(self):
        assert ai_backends._backend_kind("OLLAMA") == "ollama"

    def test_anthropic(self):
        assert ai_backends._backend_kind("Anthropic Claude") == "anthropic"

    def test_anthropic_by_claude(self):
        assert ai_backends._backend_kind("Claude 3.5") == "anthropic"

    def test_gemini(self):
        assert ai_backends._backend_kind("Google Gemini") == "gemini"

    def test_gemini_by_google(self):
        assert ai_backends._backend_kind("Google AI") == "gemini"

    def test_openai_compat_lm_studio(self):
        assert ai_backends._backend_kind("API OpenAI / LM Studio (GGUF locaux)") == "openai_compat"

    def test_openai_compat_openrouter(self):
        assert ai_backends._backend_kind("OpenRouter") == "openai_compat"

    def test_empty_defaults_to_ollama(self):
        assert ai_backends._backend_kind("") == "ollama"

    def test_none_defaults_to_ollama(self):
        assert ai_backends._backend_kind(None) == "ollama"


# ── _normalize_api_url ─────────────────────────────────────────

class TestNormalizeApiUrl:
    def test_adds_http_prefix(self):
        assert ai_backends._normalize_api_url("localhost:1234", "http://default") == "http://localhost:1234"

    def test_strips_trailing_slash(self):
        assert ai_backends._normalize_api_url("http://localhost:1234/", "http://default") == "http://localhost:1234"

    def test_empty_uses_default(self):
        assert ai_backends._normalize_api_url("", "http://default") == "http://default"

    def test_none_uses_default(self):
        assert ai_backends._normalize_api_url(None, "http://default") == "http://default"

    def test_whitespace_stripped(self):
        assert ai_backends._normalize_api_url("  http://localhost:1234  ", "http://default") == "http://localhost:1234"

    def test_https_preserved(self):
        assert ai_backends._normalize_api_url("https://api.openai.com", "http://default") == "https://api.openai.com"


# ── _safe_timeout ──────────────────────────────────────────────

class TestSafeTimeout:
    def test_valid_value(self):
        assert ai_backends._safe_timeout(30) == 30

    def test_string_value(self):
        assert ai_backends._safe_timeout("60") == 60

    def test_clamps_to_1800(self):
        assert ai_backends._safe_timeout(99999) == 1800

    def test_clamps_to_15(self):
        assert ai_backends._safe_timeout(1) == 15

    def test_invalid_defaults_to_180(self):
        assert ai_backends._safe_timeout("abc") == 180

    def test_none_defaults_to_180(self):
        assert ai_backends._safe_timeout(None) == 180

    def test_float_truncated(self):
        assert ai_backends._safe_timeout(45.9) == 45


# ── _safe_output_tokens ────────────────────────────────────────

class TestSafeOutputTokens:
    def test_valid_value(self):
        assert ai_backends._safe_output_tokens(500) == 500

    def test_clamps_to_hard_cap(self):
        assert ai_backends._safe_output_tokens(99999) == 2048

    def test_clamps_to_64(self):
        assert ai_backends._safe_output_tokens(1) == 64

    def test_zero_uses_default(self):
        assert ai_backends._safe_output_tokens(0) == 1024

    def test_negative_uses_default(self):
        assert ai_backends._safe_output_tokens(-5) == 1024

    def test_invalid_uses_default(self):
        assert ai_backends._safe_output_tokens("abc") == 1024


# ── _safe_context_tokens ───────────────────────────────────────

class TestSafeContextTokens:
    def test_valid_value(self):
        assert ai_backends._safe_context_tokens(8192) == 8192

    def test_clamps_to_1024(self):
        assert ai_backends._safe_context_tokens(512) == 1024

    def test_zero_uses_default(self):
        assert ai_backends._safe_context_tokens(0) == 4096

    def test_negative_uses_default(self):
        assert ai_backends._safe_context_tokens(-1) == 4096


# ── estimate_text_tokens ───────────────────────────────────────

class TestEstimateTextTokens:
    def test_empty_string(self):
        assert ai_backends.estimate_text_tokens("") == 0

    def test_none(self):
        assert ai_backends.estimate_text_tokens(None) == 0

    def test_non_empty_positive(self):
        assert ai_backends.estimate_text_tokens("hello world") > 0

    def test_longer_text_more_tokens(self):
        short = ai_backends.estimate_text_tokens("a")
        long_ = ai_backends.estimate_text_tokens("a" * 100)
        assert long_ > short


# ── _env_api_key ───────────────────────────────────────────────

class TestEnvApiKey:
    def test_ollama_returns_empty(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert ai_backends._env_api_key("ollama") == ""

    def test_gemini_from_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        assert ai_backends._env_api_key("gemini") == "test-gemini-key"

    def test_gemini_google_alias(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
        assert ai_backends._env_api_key("gemini") == "test-google-key"

    def test_anthropic_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        assert ai_backends._env_api_key("anthropic") == "test-anthropic-key"

    def test_openai_compat_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        assert ai_backends._env_api_key("openai_compat") == "test-openai-key"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "  spaced-key  ")
        assert ai_backends._env_api_key("gemini") == "spaced-key"

    def test_no_env_var_returns_empty(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        assert ai_backends._env_api_key("gemini") == ""


# ── _format_http_error ─────────────────────────────────────────

class TestFormatHttpError:
    def test_without_response_detail(self):
        result = ai_backends._format_http_error("Erreur", None, Exception("boom"))
        assert "Erreur" in result
        assert "boom" in result

    def test_with_response_detail(self):
        class FakeResp:
            text = "Internal Server Error"
        result = ai_backends._format_http_error("Erreur", FakeResp(), Exception("500"))
        assert "Erreur" in result
        assert "Internal Server Error" in result


# ── call_ai_api (error paths only — no network) ────────────────

class TestCallAiApiErrors:
    def test_gemini_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        result = ai_backends.call_ai_api("hi", "gemini-2.5-flash", None, "Gemini",
                                         ai_backends.DEFAULT_GEMINI_URL, 0.5, 256, "",
                                         api_key="", timeout=5)
        assert "manquante" in result

    def test_anthropic_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
        result = ai_backends.call_ai_api("hi", "claude-sonnet-4-5", None, "Anthropic",
                                         ai_backends.DEFAULT_ANTHROPIC_URL, 0.5, 256, "",
                                         api_key="", timeout=5)
        assert "manquante" in result

    def test_openai_compat_no_model_returns_error(self):
        result = ai_backends.call_ai_api("hi", "", None, "OpenAI",
                                         ai_backends.DEFAULT_LM_STUDIO_URL, 0.5, 256, "",
                                         api_key="", timeout=5)
        assert "modèle" in result.lower() or "model" in result.lower()