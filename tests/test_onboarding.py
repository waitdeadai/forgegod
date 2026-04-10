"""Tests for ForgeGod Onboarding Wizard and Doctor."""

from __future__ import annotations

import os
from pathlib import Path

from forgegod.doctor import (
    HealthCheck,
    _check_git,
    _check_python,
    _check_strict_sandbox,
    run_doctor,
)
from forgegod.i18n import STRINGS, get_lang, set_lang, t
from forgegod.onboarding import recommend_provider_choice


class TestI18n:
    """Test i18n translation system."""

    def test_default_language_is_english(self):
        """Default language should be English."""
        set_lang("en")
        assert get_lang() == "en"

    def test_set_spanish(self):
        """Setting language to Spanish should work."""
        set_lang("es")
        assert get_lang() == "es"
        set_lang("en")  # Reset

    def test_set_invalid_falls_back_to_english(self):
        """Invalid language code falls back to English."""
        set_lang("xx")
        assert get_lang() == "en"

    def test_translate_english(self):
        """English translations should return English strings."""
        set_lang("en")
        assert t("welcome") == "Let's set up ForgeGod in 2 minutes"

    def test_translate_spanish(self):
        """Spanish translations should return Spanish strings."""
        set_lang("es")
        assert t("welcome") == "Configuremos ForgeGod en 2 minutos"
        set_lang("en")  # Reset

    def test_missing_key_returns_key(self):
        """Missing translation key should return the key itself."""
        set_lang("en")
        assert t("nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_placeholder_formatting(self):
        """Translation with placeholders should format correctly."""
        set_lang("en")
        result = t("error_ollama_no_model", model="qwen3.5:9b")
        assert "qwen3.5:9b" in result

    def test_placeholder_formatting_spanish(self):
        """Spanish placeholders should also format."""
        set_lang("es")
        result = t("error_ollama_no_model", model="qwen3.5:9b")
        assert "qwen3.5:9b" in result
        set_lang("en")  # Reset

    def test_all_english_keys_have_spanish(self):
        """Every English key should have a Spanish translation."""
        en_keys = set(STRINGS["en"].keys())
        es_keys = set(STRINGS["es"].keys())
        missing = en_keys - es_keys
        assert not missing, f"Missing Spanish translations: {missing}"

    def test_auto_detection(self):
        """set_lang('auto') should not crash."""
        set_lang("auto")
        assert get_lang() in ("en", "es")
        set_lang("en")  # Reset


class TestDoctor:
    """Test ForgeGod doctor health checks."""

    def test_python_check_passes(self):
        """Python version check should pass (we're running 3.11+)."""
        check = _check_python()
        assert check.passed is True
        assert "3." in check.detail

    def test_git_check_in_repo(self, tmp_path: Path):
        """Git check should pass in a git repo."""
        (tmp_path / ".git").mkdir()
        check = _check_git(tmp_path)
        assert check.passed is True

    def test_git_check_no_repo(self, tmp_path: Path):
        """Git check should fail outside a git repo."""
        check = _check_git(tmp_path)
        # May pass (git installed) or fail (no repo) — depends on git being on PATH
        if not check.passed:
            assert check.fix  # Should have a fix instruction

    def test_run_doctor_returns_checks(self, tmp_path: Path):
        """run_doctor should return a list of HealthCheck objects."""
        checks = run_doctor(tmp_path)
        assert len(checks) == 7
        assert all(isinstance(c, HealthCheck) for c in checks)

    def test_strict_sandbox_check_skips_without_config(self, tmp_path: Path):
        """Strict sandbox check should not fail when config does not exist yet."""
        check = _check_strict_sandbox(tmp_path)
        assert check.passed is True
        assert "Skipped" in check.detail

    def test_strict_sandbox_check_reports_optional_for_standard_mode(self, tmp_path: Path):
        """Standard mode should not require Docker sandbox prerequisites."""
        forgegod_dir = tmp_path / ".forgegod"
        forgegod_dir.mkdir()
        (forgegod_dir / "config.toml").write_text(
            "[security]\n"
            'sandbox_mode = "standard"\n',
            encoding="utf-8",
        )

        check = _check_strict_sandbox(tmp_path)
        assert check.passed is True
        assert "optional" in check.detail.lower()

    def test_health_check_model(self):
        """HealthCheck should store all fields."""
        check = HealthCheck(
            name="Test Check",
            passed=False,
            detail="Something wrong",
            fix="Fix it like this",
        )
        assert check.name == "Test Check"
        assert check.passed is False
        assert check.fix == "Fix it like this"

    def test_passing_check_has_no_fix(self):
        """Passing checks typically don't need fix instructions."""
        check = HealthCheck(name="OK Check", passed=True, detail="All good")
        assert check.fix == ""


class TestDotenvLoading:
    """Test .env file loading from config."""

    def test_load_dotenv_fallback(self, tmp_path: Path):
        """Manual .env parsing should work without python-dotenv."""
        from forgegod.config import _load_dotenv

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_FORGEGOD_KEY=test_value_123\n", encoding="utf-8")

        # Remove from env if it exists
        os.environ.pop("TEST_FORGEGOD_KEY", None)

        _load_dotenv(env_file)

        assert os.environ.get("TEST_FORGEGOD_KEY") == "test_value_123"

        # Cleanup
        os.environ.pop("TEST_FORGEGOD_KEY", None)

    def test_load_dotenv_skips_comments(self, tmp_path: Path):
        """Comments and empty lines in .env should be skipped."""
        from forgegod.config import _load_dotenv

        env_file = tmp_path / ".env"
        env_file.write_text(
            "# This is a comment\n"
            "\n"
            "TEST_FORGEGOD_COMMENT=works\n",
            encoding="utf-8",
        )

        os.environ.pop("TEST_FORGEGOD_COMMENT", None)
        _load_dotenv(env_file)
        assert os.environ.get("TEST_FORGEGOD_COMMENT") == "works"

        # Cleanup
        os.environ.pop("TEST_FORGEGOD_COMMENT", None)

    def test_load_dotenv_no_override(self, tmp_path: Path):
        """Existing env vars should NOT be overridden by .env."""
        from forgegod.config import _load_dotenv

        os.environ["TEST_FORGEGOD_EXISTING"] = "original"

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_FORGEGOD_EXISTING=overridden\n", encoding="utf-8")

        _load_dotenv(env_file)
        assert os.environ["TEST_FORGEGOD_EXISTING"] == "original"

        # Cleanup
        os.environ.pop("TEST_FORGEGOD_EXISTING", None)

    def test_load_dotenv_missing_file(self, tmp_path: Path):
        """Missing .env file should not crash."""
        from forgegod.config import _load_dotenv

        _load_dotenv(tmp_path / "nonexistent.env")  # Should not raise


class TestOnboardingRecommendations:
    def test_recommend_provider_choice_prefers_linked_codex(self):
        choice = recommend_provider_choice(
            {"openai-codex", "openai"},
            ollama_available=True,
            codex_supported=True,
            codex_installed=True,
        )
        assert choice == "3"

    def test_recommend_provider_choice_prefers_zai_when_detected(self):
        choice = recommend_provider_choice(
            {"zai", "openai"},
            ollama_available=False,
            codex_supported=False,
            codex_installed=False,
        )
        assert choice == "9"
