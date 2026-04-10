"""ForgeGod onboarding wizard with guided, secure provider setup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.panel import Panel

from forgegod import __version__
from forgegod.cli_ux import build_banner_text, console, print_brand_panel
from forgegod.config import init_project, recommend_model_defaults
from forgegod.i18n import t
from forgegod.native_auth import (
    codex_automation_status,
    codex_login_status_sync,
    find_command,
)


@dataclass(frozen=True)
class ProviderOption:
    choice: str
    provider: str
    label_key: str
    env_var: str = ""
    url: str = ""


PROVIDER_OPTIONS = [
    ProviderOption("1", "ollama", "opt_local"),
    ProviderOption("2", "openai", "opt_openai", "OPENAI_API_KEY", "https://platform.openai.com/api-keys"),
    ProviderOption("3", "openai-codex", "opt_openai_codex"),
    ProviderOption(
        "4",
        "anthropic",
        "opt_anthropic",
        "ANTHROPIC_API_KEY",
        "https://console.anthropic.com/settings/keys",
    ),
    ProviderOption(
        "5",
        "openrouter",
        "opt_openrouter",
        "OPENROUTER_API_KEY",
        "https://openrouter.ai/keys",
    ),
    ProviderOption("6", "gemini", "opt_gemini", "GOOGLE_API_KEY", "https://aistudio.google.com/apikey"),
    ProviderOption(
        "7",
        "deepseek",
        "opt_deepseek",
        "DEEPSEEK_API_KEY",
        "https://platform.deepseek.com/api_keys",
    ),
    ProviderOption(
        "8",
        "kimi",
        "opt_kimi",
        "MOONSHOT_API_KEY",
        "https://platform.moonshot.ai/console/api-keys",
    ),
    ProviderOption(
        "9",
        "zai",
        "opt_zai",
        "ZAI_CODING_API_KEY",
        "https://docs.z.ai/devpack/quick-start",
    ),
    ProviderOption("10", "multi", "opt_multi"),
]


def recommend_provider_choice(
    detected: set[str],
    *,
    ollama_available: bool,
    codex_supported: bool,
    codex_installed: bool,
) -> str:
    """Pick the friendliest default path for the current environment."""
    if "openai-codex" in detected and codex_supported:
        return "3"
    if "zai" in detected:
        return "9"
    if "openai" in detected:
        return "2"
    if ollama_available:
        return "1"
    if codex_installed and codex_supported:
        return "3"
    return "1"


class OnboardingWizard:
    """Interactive guided setup wizard."""

    def __init__(
        self,
        project_path: Path,
        lang: str = "en",
        harness_profile: str = "adversarial",
        preferred_provider: str = "auto",
    ):
        self.project_path = Path(project_path).resolve()
        self.lang = lang
        self._harness_profile = harness_profile
        self._preferred_provider = preferred_provider
        self._providers: list[str] = []
        self._ollama_available = False
        self._ollama_models: list[str] = []
        self._env_vars: dict[str, str] = {}
        self._detected_providers: set[str] = set()
        self._detected_lines: list[str] = []
        self._recommended_choice = "1"
        self._codex_installed = False
        self._codex_supported = False
        self._probed = False

    def run(self) -> dict:
        """Run the full wizard. Returns config dict."""
        self._probe_current_environment()
        self._step_welcome()
        self._step_provider()
        self._step_harness_profile()
        self._step_provider_preference()
        self._step_verify()
        self._step_done()
        return {
            "providers": self._providers,
            "ollama": self._ollama_available,
            "env_vars": self._env_vars,
        }

    def _probe_current_environment(self) -> None:
        """Detect local auth surfaces before prompting the user."""
        if self._probed:
            return

        self._ollama_available, self._ollama_models = self._detect_ollama()
        if self._ollama_available:
            self._detected_lines.append(
                f"Ollama is already running ({len(self._ollama_models)} models)."
            )

        self._codex_installed = find_command("codex") is not None
        self._codex_supported, codex_detail = codex_automation_status()
        codex_logged_in, _ = codex_login_status_sync()
        if codex_logged_in:
            self._detected_providers.add("openai-codex")
            self._detected_lines.append("OpenAI Codex subscription is already linked.")
        elif self._codex_installed:
            self._detected_lines.append(
                "Codex CLI is installed and can be linked from this onboarding flow."
            )
            if not self._codex_supported:
                self._detected_lines.append(codex_detail)

        env_checks = [
            ("openai", "OPENAI_API_KEY", "OpenAI API key already present in this shell."),
            (
                "anthropic",
                "ANTHROPIC_API_KEY",
                "Anthropic API key already present in this shell.",
            ),
            (
                "openrouter",
                "OPENROUTER_API_KEY",
                "OpenRouter API key already present in this shell.",
            ),
            ("gemini", "GOOGLE_API_KEY", "Gemini API key already present in this shell."),
            ("gemini", "GEMINI_API_KEY", "Gemini API key already present in this shell."),
            ("deepseek", "DEEPSEEK_API_KEY", "DeepSeek API key already present in this shell."),
            ("kimi", "MOONSHOT_API_KEY", "Kimi API key already present in this shell."),
            ("zai", "ZAI_CODING_API_KEY", "Z.AI Coding Plan key already present in this shell."),
            ("zai", "ZAI_API_KEY", "Z.AI API key already present in this shell."),
        ]
        for provider, env_var, detail in env_checks:
            if os.environ.get(env_var):
                self._detected_providers.add(provider)
                if detail not in self._detected_lines:
                    self._detected_lines.append(detail)

        self._recommended_choice = recommend_provider_choice(
            self._detected_providers,
            ollama_available=self._ollama_available,
            codex_supported=self._codex_supported,
            codex_installed=self._codex_installed,
        )
        self._probed = True

    def _detect_ollama(self) -> tuple[bool, list[str]]:
        """Return whether Ollama is up and which models it exposes."""
        try:
            import httpx

            resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return True, [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            pass
        return False, []

    def _step_welcome(self) -> None:
        """Step 1: Welcome screen."""
        console.print(build_banner_text(__version__))
        print_brand_panel("Welcome", t("welcome"))

    def _step_provider(self) -> None:
        """Step 2: Provider selection."""
        self._print_provider_guidance()
        console.print(f"[forge.highlight]{t('provider_prompt')}[/forge.highlight]")
        console.print()
        for option in PROVIDER_OPTIONS:
            suffixes: list[str] = []
            if option.choice == self._recommended_choice:
                suffixes.append(t("provider_recommended"))
            if option.provider in self._detected_providers:
                suffixes.append(t("provider_detected"))

            line = f"  [forge.primary]{option.choice}.[/forge.primary] {t(option.label_key)}"
            if suffixes:
                line += (
                    " [forge.muted]("
                    + " | ".join(suffixes)
                    + ")[/forge.muted]"
                )
            console.print(line)
        console.print()

        choice = typer.prompt("Select", default=self._recommended_choice)

        if choice == "1":
            self._setup_ollama()
        elif choice == "2":
            self._setup_api_key("openai", "OPENAI_API_KEY", "https://platform.openai.com/api-keys")
        elif choice == "3":
            self._setup_openai_codex()
        elif choice == "4":
            self._setup_api_key(
                "anthropic",
                "ANTHROPIC_API_KEY",
                "https://console.anthropic.com/settings/keys",
            )
        elif choice == "5":
            self._setup_api_key("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/keys")
        elif choice == "6":
            self._setup_gemini_key()
        elif choice == "7":
            self._setup_api_key(
                "deepseek",
                "DEEPSEEK_API_KEY",
                "https://platform.deepseek.com/api_keys",
            )
        elif choice == "8":
            self._setup_api_key(
                "kimi",
                "MOONSHOT_API_KEY",
                "https://platform.moonshot.ai/console/api-keys",
            )
        elif choice == "9":
            self._setup_api_key("zai", "ZAI_CODING_API_KEY", "https://docs.z.ai/devpack/quick-start")
        elif choice == "10":
            self._setup_multi_provider()

    def _step_harness_profile(self) -> None:
        """Step 3: choose adversarial vs single-model harness."""
        print_brand_panel(
            t("harness_prompt"),
            t("harness_recommended_body"),
            border_style="forge.secondary",
        )
        console.print(
            f"  [forge.primary]1.[/forge.primary] {t('harness_adversarial')} "
            f"[forge.muted]({t('provider_recommended')})[/forge.muted]"
        )
        console.print(
            f"  [forge.primary]2.[/forge.primary] {t('harness_single')}"
        )
        console.print()

        default_choice = "1" if self._harness_profile != "single-model" else "2"
        choice = typer.prompt("Profile", default=default_choice)
        self._harness_profile = "single-model" if choice == "2" else "adversarial"

    def _step_provider_preference(self) -> None:
        """Step 4: choose whether to bias auto-routing toward OpenAI surfaces."""
        print_brand_panel(
            t("provider_pref_prompt"),
            t("provider_pref_body"),
            border_style="forge.secondary",
        )
        console.print(
            f"  [forge.primary]1.[/forge.primary] {t('provider_pref_auto')} "
            f"[forge.muted]({t('provider_recommended')})[/forge.muted]"
        )
        console.print(
            f"  [forge.primary]2.[/forge.primary] {t('provider_pref_openai')}"
        )
        console.print()

        default_choice = "2" if self._preferred_provider == "openai" else "1"
        choice = typer.prompt("Provider preference", default=default_choice)
        self._preferred_provider = "openai" if choice == "2" else "auto"

    def _print_provider_guidance(self) -> None:
        """Show friendly recommendations and what ForgeGod already detected."""
        recommended = next(
            option for option in PROVIDER_OPTIONS if option.choice == self._recommended_choice
        )
        print_brand_panel(
            t("provider_recommended"),
            f"Start here today: {t(recommended.label_key)}",
            border_style="forge.secondary",
        )

        detected_body = (
            "\n".join(f"- {line}" for line in self._detected_lines)
            if self._detected_lines
            else "- No linked providers found yet. That's fine."
        )
        print_brand_panel(
            t("provider_detected"),
            detected_body,
            border_style="forge.primary",
        )
        console.print(f"[forge.muted]{t('provider_storage_note')}[/forge.muted]")
        console.print(f"[forge.muted]{t('provider_friendly_hint')}[/forge.muted]")
        console.print()

    def _setup_multi_provider(self) -> None:
        """Offer multiple providers without dumping the user into manual env setup."""
        self._setup_ollama()
        for option in PROVIDER_OPTIONS[1:9]:
            add = typer.confirm(f"  Add {option.provider}?", default=False)
            if not add:
                continue
            if option.provider == "openai-codex":
                self._setup_openai_codex()
            elif option.provider == "gemini":
                self._setup_gemini_key()
            else:
                self._setup_api_key(option.provider, option.env_var, option.url)

    def _setup_ollama(self) -> None:
        """Check Ollama availability and model list."""
        self._probe_current_environment()
        if self._ollama_available:
            self._providers.append("ollama")
            console.print(
                "  [forge.success]+[/forge.success] "
                f"Ollama running ({len(self._ollama_models)} models)"
            )
            for model_name in self._ollama_models[:5]:
                console.print(f"    [forge.muted]{model_name}[/forge.muted]")
            return

        console.print(f"  [forge.warn]![/forge.warn] {t('error_ollama_down')}")
        console.print()
        console.print("  Install: https://ollama.com/download")
        console.print("  Then run: [forge.highlight]ollama serve[/forge.highlight]")
        console.print(
            "  And pull a model: "
            "[forge.highlight]ollama pull qwen3.5:9b[/forge.highlight]"
        )
        console.print()

    def _setup_openai_codex(self) -> None:
        """Check or start Codex CLI login for ChatGPT-backed access."""
        import subprocess

        logged_in, _ = codex_login_status_sync()
        if logged_in:
            console.print(
                "  [forge.success]+[/forge.success] OpenAI Codex subscription already linked"
            )
            self._providers.append("openai-codex")
            return

        if not self._codex_installed:
            console.print("  [forge.error]-[/forge.error] Codex CLI not found on PATH")
            console.print("  Install Codex CLI first, then rerun onboarding.")
            return

        if not self._codex_supported:
            _, detail = codex_automation_status()
            console.print(f"  [forge.warn]![/forge.warn] {detail}")

        console.print("\n  Opening official Codex login flow...")
        subprocess.run([find_command("codex"), "login"], check=False)
        logged_in, _ = codex_login_status_sync()
        if logged_in:
            self._providers.append("openai-codex")
            console.print("  [forge.success]+[/forge.success] OpenAI Codex subscription linked")
        else:
            console.print("  [forge.warn]![/forge.warn] Codex login not completed")

    def _setup_api_key(self, provider: str, env_var: str, url: str) -> None:
        """Prompt for API key, validate, save to .env."""
        existing = os.environ.get(env_var)
        if existing:
            console.print(
                "  [forge.success]+[/forge.success] "
                f"{provider} is already available in this environment"
            )
            self._providers.append(provider)
            return

        console.print(f"\n  Get your key at: [link]{url}[/link]")
        key = typer.prompt(f"  {t('enter_key')} ({provider})", hide_input=True)

        if not key or len(key) < 10:
            console.print(f"  [forge.error]{t('verify_fail')}[/forge.error] - key too short")
            return

        self._env_vars[env_var] = key
        os.environ[env_var] = key
        self._providers.append(provider)
        console.print(f"  [forge.success]+[/forge.success] {provider} key saved for this repo")

    def _setup_gemini_key(self) -> None:
        """Setup Google Gemini API key."""
        existing = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if existing:
            console.print("  [forge.success]+[/forge.success] Gemini key already available")
            self._providers.append("gemini")
            return

        console.print("\n  Get your key at: [link]https://aistudio.google.com/apikey[/link]")
        key = typer.prompt(f"  {t('enter_key')} (Gemini)", hide_input=True)

        if not key or len(key) < 10:
            console.print(f"  [forge.error]{t('verify_fail')}[/forge.error] - key too short")
            return

        self._env_vars["GOOGLE_API_KEY"] = key
        os.environ["GOOGLE_API_KEY"] = key
        self._providers.append("gemini")
        console.print("  [forge.success]+[/forge.success] Gemini key saved for this repo")

    def _step_verify(self) -> None:
        """Verification smoke test."""
        if not self._providers:
            console.print(f"\n[forge.warn]{t('no_providers')}[/forge.warn]")
            return

        console.print(f"\n[forge.muted]{t('verifying')}[/forge.muted]")

        if self._ollama_available and self._ollama_models:
            try:
                import httpx

                model = self._ollama_models[0]
                resp = httpx.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Say hello in one word."}],
                        "stream": False,
                        "options": {"num_predict": 10},
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    content = resp.json().get("message", {}).get("content", "")
                    if content:
                        preview = content.strip()[:30]
                        console.print(
                            f"  [forge.success]+[/forge.success] {t('verify_ok')} "
                            f"({model}: \"{preview}\")"
                        )
                        return
            except Exception:
                pass

        for provider in self._providers:
            if provider == "ollama":
                continue
            if provider == "openai-codex":
                logged_in, _ = codex_login_status_sync()
                if logged_in:
                    console.print(
                        f"  [forge.success]+[/forge.success] "
                        f"{t('verify_ok')} (OpenAI Codex)"
                    )
                    return
            if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
                try:
                    import httpx

                    resp = httpx.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        console.print(
                            f"  [forge.success]+[/forge.success] "
                            f"{t('verify_ok')} (OpenAI)"
                        )
                        return
                    console.print(
                        f"  [forge.error]-[/forge.error] "
                        f"{t('error_key_invalid', url='https://platform.openai.com/api-keys')}"
                    )
                except Exception:
                    pass
            zai_key = os.environ.get("ZAI_CODING_API_KEY") or os.environ.get("ZAI_API_KEY")
            if provider == "zai" and zai_key:
                try:
                    import httpx

                    url = (
                        "https://api.z.ai/api/coding/paas/v4/models"
                        if os.environ.get("ZAI_CODING_API_KEY")
                        else "https://api.z.ai/api/paas/v4/models"
                    )
                    resp = httpx.get(
                        url,
                        headers={"Authorization": f"Bearer {zai_key}"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        console.print(f"  [forge.success]+[/forge.success] {t('verify_ok')} (Z.AI)")
                        return
                    console.print(
                        f"  [forge.error]-[/forge.error] "
                        f"{t('error_key_invalid', url='https://docs.z.ai/api-reference/introduction')}"
                    )
                except Exception:
                    pass

        console.print(
            f"  [forge.muted]{t('verify_ok')}[/forge.muted] "
            "(skipped - ForgeGod will verify on first use)"
        )

    def _step_done(self) -> None:
        """Save .env and show success."""
        if self._env_vars:
            env_path = self.project_path / ".forgegod" / ".env"
            env_path.parent.mkdir(parents=True, exist_ok=True)

            existing = ""
            if env_path.exists():
                existing = env_path.read_text(encoding="utf-8")

            lines = existing.rstrip().split("\n") if existing.strip() else []
            existing_keys = {line.split("=")[0] for line in lines if "=" in line}

            for key, value in self._env_vars.items():
                if key not in existing_keys:
                    lines.append(f"{key}={value}")

            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            console.print(f"\n  [forge.muted]{t('saving_env')}[/forge.muted]")

        recommended = recommend_model_defaults(
            self._providers,
            ollama_available=self._ollama_available,
            profile=self._harness_profile,
            preferred_provider=self._preferred_provider,
        )
        project_dir = init_project(
            self.project_path,
            model_defaults=recommended,
            harness_profile=self._harness_profile,
            preferred_provider=self._preferred_provider,
        )
        config_path = project_dir / "config.toml"
        try:
            import toml

            data = toml.loads(config_path.read_text(encoding="utf-8"))
            data["models"] = recommended.model_dump()
            data.setdefault("harness", {})["profile"] = self._harness_profile
            data["harness"]["preferred_provider"] = self._preferred_provider
            config_path.write_text(toml.dumps(data), encoding="utf-8")
        except Exception:
            pass

        console.print()
        console.print(
            Panel(
                (
                    f"[forge.success]{t('success')}[/forge.success]\n\n"
                    f"{t('harness_selected', profile=self._harness_profile)}\n"
                    f"{t('provider_pref_selected', provider=self._preferred_provider)}\n"
                    f"{t('try_it')}"
                ),
                border_style="forge.primary",
            )
        )
