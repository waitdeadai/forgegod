"""ForgeGod Onboarding Wizard — interactive setup for new users.

SOTA pattern (2026): 2-3 steps to first value, masked API key input,
verification smoke test, .env file storage. No manual env var editing.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from forgegod.i18n import t

console = Console()


class OnboardingWizard:
    """Interactive 4-step setup wizard."""

    def __init__(self, project_path: Path, lang: str = "en"):
        self.project_path = Path(project_path).resolve()
        self.lang = lang
        self._providers: list[str] = []
        self._ollama_available = False
        self._ollama_models: list[str] = []
        self._env_vars: dict[str, str] = {}

    def run(self) -> dict:
        """Run the full wizard. Returns config dict."""
        self._step_welcome()
        self._step_provider()
        self._step_verify()
        self._step_done()
        return {
            "providers": self._providers,
            "ollama": self._ollama_available,
            "env_vars": self._env_vars,
        }

    def _step_welcome(self) -> None:
        """Step 1: Welcome screen."""
        from forgegod.cli import _build_banner

        console.print(_build_banner())
        console.print(f"[bold]{t('welcome')}[/bold]")
        console.print()

    def _step_provider(self) -> None:
        """Step 2: Provider selection."""
        console.print(f"[bold]{t('provider_prompt')}[/bold]")
        console.print()
        console.print(f"  [cyan]1.[/cyan] {t('opt_local')}")
        console.print(f"  [cyan]2.[/cyan] {t('opt_openai')}")
        console.print(f"  [cyan]3.[/cyan] {t('opt_anthropic')}")
        console.print(f"  [cyan]4.[/cyan] {t('opt_openrouter')}")
        console.print(f"  [cyan]5.[/cyan] {t('opt_multi')}")
        console.print()

        choice = typer.prompt("Select", default="1")

        if choice == "1":
            self._setup_ollama()
        elif choice == "2":
            self._setup_api_key("openai", "OPENAI_API_KEY", "https://platform.openai.com/api-keys")
        elif choice == "3":
            self._setup_api_key("anthropic", "ANTHROPIC_API_KEY", "https://console.anthropic.com/settings/keys")
        elif choice == "4":
            self._setup_api_key("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/keys")
        elif choice == "5":
            self._setup_ollama()
            for provider, env_var, url in [
                ("openai", "OPENAI_API_KEY", "https://platform.openai.com/api-keys"),
                ("anthropic", "ANTHROPIC_API_KEY", "https://console.anthropic.com/settings/keys"),
                ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/keys"),
            ]:
                add = typer.confirm(f"  Add {provider}?", default=False)
                if add:
                    self._setup_api_key(provider, env_var, url)

    def _setup_ollama(self) -> None:
        """Check Ollama availability and model list."""
        try:
            import httpx

            resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                self._ollama_available = True
                models = resp.json().get("models", [])
                self._ollama_models = [m.get("name", "") for m in models]
                self._providers.append("ollama")
                console.print(f"  [green]+[/green] Ollama running ({len(self._ollama_models)} models)")
                for m in self._ollama_models[:5]:
                    console.print(f"    [dim]{m}[/dim]")
                return
        except Exception:
            pass

        console.print(f"  [yellow]![/yellow] {t('error_ollama_down')}")
        console.print()
        console.print("  Install: https://ollama.com/download")
        console.print("  Then run: [bold]ollama serve[/bold]")
        console.print("  And pull a model: [bold]ollama pull qwen3.5:9b[/bold]")
        console.print()

    def _setup_api_key(self, provider: str, env_var: str, url: str) -> None:
        """Prompt for API key, validate, save to .env."""
        # Check if already set
        existing = os.environ.get(env_var)
        if existing:
            console.print(f"  [green]+[/green] {provider} key already set")
            self._providers.append(provider)
            return

        console.print(f"\n  Get your key at: [link]{url}[/link]")
        key = typer.prompt(f"  {t('enter_key')} ({provider})", hide_input=True)

        if not key or len(key) < 10:
            console.print(f"  [red]{t('verify_fail')}[/red] — key too short")
            return

        # Save to .env
        self._env_vars[env_var] = key
        os.environ[env_var] = key
        self._providers.append(provider)
        console.print(f"  [green]+[/green] {provider} key saved")

    def _step_verify(self) -> None:
        """Step 3: Verification smoke test."""
        if not self._providers:
            console.print(f"\n[yellow]{t('no_providers')}[/yellow]")
            return

        console.print(f"\n[dim]{t('verifying')}[/dim]")

        # Quick test: if Ollama, check a model responds
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
                        console.print(f"  [green]+[/green] {t('verify_ok')} ({model}: \"{content.strip()[:30]}\")")
                        return
            except Exception:
                pass

        # Test cloud provider
        for provider in self._providers:
            if provider == "ollama":
                continue
            if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
                try:
                    import httpx

                    resp = httpx.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        console.print(f"  [green]+[/green] {t('verify_ok')} (OpenAI)")
                        return
                    else:
                        console.print(f"  [red]-[/red] {t('error_key_invalid', url='https://platform.openai.com/api-keys')}")
                except Exception:
                    pass

        console.print(f"  [dim]{t('verify_ok')}[/dim] (skipped — will verify on first use)")

    def _step_done(self) -> None:
        """Step 4: Save .env and show success."""
        if self._env_vars:
            env_path = self.project_path / ".forgegod" / ".env"
            env_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to existing .env
            existing = ""
            if env_path.exists():
                existing = env_path.read_text(encoding="utf-8")

            lines = existing.rstrip().split("\n") if existing.strip() else []
            existing_keys = {l.split("=")[0] for l in lines if "=" in l}

            for key, value in self._env_vars.items():
                if key not in existing_keys:
                    lines.append(f"{key}={value}")

            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            console.print(f"\n  [dim]{t('saving_env')}[/dim]")

        # Write config.toml if it doesn't exist
        config_path = self.project_path / ".forgegod" / "config.toml"
        if not config_path.exists():
            from forgegod.config import init_project

            init_project(self.project_path)

        console.print()
        console.print(Panel(
            f"[bold green]{t('success')}[/bold green]\n\n{t('try_it')}",
            border_style="green",
        ))
