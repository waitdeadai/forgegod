"""ForgeGod CLI - Typer entry point."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from forgegod import __version__
from forgegod.cli_ux import (
    LoopNarrator,
    RunNarrator,
    build_banner_text,
    configure_cli_logging,
    console,
)
from forgegod.cli_ux import (
    safe_console_text as _ux_safe_console_text,
)

app = typer.Typer(
    name="forgegod",
    help=(
        "Conversational multi-model coding engine. Run `forgegod` to talk "
        "naturally, or use explicit subcommands for scripts and automation."
    ),
    no_args_is_help=False,
)
design_app = typer.Typer(help="Manage DESIGN.md presets and imports.")
auth_app = typer.Typer(help="Manage native provider auth surfaces and login status.")

app.add_typer(design_app, name="design")
app.add_typer(auth_app, name="auth")

# -- Mascot - The One-Eyed Triangle --
_VER = __version__


def _safe_console_text(text: str) -> str:
    """Best-effort console-safe text for legacy Windows encodings."""
    return _ux_safe_console_text(text, active_console=console)


def _build_banner():
    """Build the full mascot banner using Rich Text (avoids markup escaping)."""
    return build_banner_text(_VER)


def _cli_is_interactive() -> bool:
    """Return whether ForgeGod is attached to an interactive stdin."""
    return sys.stdin.isatty()


def _print_banner(mini: bool = False):
    """Print the ForgeGod mascot banner."""
    if mini:
        console.print(f"[cyan]^[/cyan] [bold cyan]ForgeGod[/bold cyan] [dim]v{_VER}[/dim]")
    else:
        console.print(_build_banner())


def _build_tool_approver():
    """Return a CLI approval callback for blocked tool calls."""

    def _approver(name: str, arguments: dict, reason: str) -> bool:
        payload = json.dumps(arguments, ensure_ascii=False)[:400]
        console.print(
            Panel(
                _safe_console_text(
                    f"[yellow]Approval required[/yellow]\n"
                    f"Tool: {name}\n"
                    f"Reason: {reason}\n"
                    f"Arguments: {payload}"
                ),
                border_style="yellow",
            )
        )
        return typer.confirm("Approve this tool call?", default=False)

    return _approver


def _detect_runtime_model_defaults(
    project_path: Path | None = None,
    *,
    profile: str = "adversarial",
    preferred_provider: str = "auto",
    openai_surface: str = "auto",
):
    """Detect usable auth surfaces and return recommended model defaults."""
    from forgegod.benchmark import detect_available_models
    from forgegod.config import ForgeGodConfig, _load_dotenv, recommend_model_defaults

    root = Path(project_path or ".").resolve()
    _load_dotenv(root / ".forgegod" / ".env")
    config = ForgeGodConfig()
    config.project_dir = root / ".forgegod"
    models = detect_available_models(config)
    providers = sorted({model.split(":", 1)[0] for model in models})
    ollama_available = any(model.startswith("ollama:") for model in models)
    recommended = recommend_model_defaults(
        providers,
        ollama_available=ollama_available,
        profile=profile,
        preferred_provider=preferred_provider,
        openai_surface=openai_surface,
    )
    return models, providers, ollama_available, recommended


def _project_has_config(project_path: Path | None = None) -> bool:
    root = Path(project_path or ".").resolve()
    return (root / ".forgegod" / "config.toml").exists()


def _ensure_project_bootstrap(
    project_path: Path | None = None,
    *,
    profile: str = "adversarial",
    preferred_provider: str = "auto",
    openai_surface: str = "auto",
    announce: bool = True,
) -> bool:
    from forgegod.config import init_project

    root = Path(project_path or ".").resolve()
    if _project_has_config(root):
        return False

    _, providers, ollama_available, recommended = _detect_runtime_model_defaults(
        root,
        profile=profile,
        preferred_provider=preferred_provider,
        openai_surface=openai_surface,
    )
    project_dir = init_project(
        root,
        model_defaults=recommended,
        harness_profile=profile,
        preferred_provider=preferred_provider,
        openai_surface=openai_surface,
    )

    if announce:
        if providers or ollama_available:
            console.print(
                "[forge.primary]ForgeGod[/forge.primary] "
                "bootstrapped this project with auth-aware defaults."
            )
        else:
            console.print(
                "[forge.primary]ForgeGod[/forge.primary] "
                "created local project config so you can start talking right away."
            )
            console.print(
                "[forge.warn]No provider auth was detected yet.[/forge.warn] "
                "Run [cyan]forgegod doctor[/cyan] or [cyan]forgegod auth status[/cyan] "
                "if you need to connect models."
            )
        console.print(f"[forge.muted]Project config: {project_dir}[/forge.muted]")
    return True


def _build_run_config(
    *,
    model: str | None = None,
    review: bool = True,
    permission_mode: str | None = None,
    approval_mode: str | None = None,
    allowed_tool: list[str] | None = None,
    verbose: bool = False,
    terse: bool = False,
):
    from forgegod.config import load_config

    _ensure_project_bootstrap(announce=False)
    config = load_config()
    configure_cli_logging(
        verbose=verbose,
        log_file=config.project_dir / "logs" / "run.log",
        stream=verbose,
    )
    if model:
        config.models.coder = model
    config.review.always_review_run = review
    if permission_mode:
        config.security.permission_mode = permission_mode
    if approval_mode:
        config.security.approval_mode = approval_mode
    if allowed_tool is not None:
        config.security.allowed_tools = list(allowed_tool)
    if terse:
        config.terse.enabled = True
    return config


async def _execute_run_task(
    task: str,
    *,
    config,
    review: bool,
    show_banner: bool,
) -> int:
    from forgegod.agent import Agent
    from forgegod.models import ReviewVerdict
    from forgegod.reviewer import Reviewer
    from forgegod.router import ModelRouter

    if show_banner:
        _print_banner(mini=True)
        if config.terse.enabled:
            console.print("[dim]Caveman mode enabled - ultra-terse prompts[/dim]")

    router = ModelRouter(config)
    narrator = RunNarrator()
    try:
        approver = _build_tool_approver() if config.security.approval_mode == "prompt" else None
        agent = Agent(
            router=router,
            config=config,
            tool_approver=approver,
            event_callback=narrator,
        )
        result = await agent.run(task)

        if not result.success:
            failure = _safe_console_text(result.error or result.output or "Unknown failure")
            console.print(f"[red]Task failed:[/red] {failure}")
            if result.completion_blockers:
                console.print("[yellow]Completion blockers:[/yellow]")
                for blocker in result.completion_blockers:
                    console.print(f"  - {_safe_console_text(blocker)}")
            return 1

        if review and result.files_modified:
            reviewer = Reviewer(config=config, router=router)
            review_code = result.output[:6000]
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "diff", "HEAD",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(config.project_dir.parent),
                )
                stdout, _ = await proc.communicate()
                if stdout:
                    review_code = stdout.decode("utf-8", errors="replace")[:6000]
            except Exception:
                pass

            review_result = await reviewer.review(
                task=task,
                code=review_code,
                files_changed=result.files_modified,
            )
            if review_result.verdict != ReviewVerdict.APPROVE:
                color = "yellow" if review_result.verdict == ReviewVerdict.REVISE else "red"
                console.print(
                    Panel(
                        _safe_console_text(
                            f"[{color}]Reviewer blocked completion: "
                            f"{review_result.verdict.value}[/{color}]\n"
                            f"{review_result.reasoning}"
                        ),
                        border_style=color,
                    )
                )
                if review_result.issues:
                    for issue in review_result.issues:
                        console.print(f"  - {_safe_console_text(issue)}")
                return 1

        console.print(
            Panel(
                _safe_console_text(f"[green]Task completed[/green]\n{result.output[:500]}")
            )
        )
        if result.files_modified:
            console.print(f"Files modified: {', '.join(result.files_modified)}")
        if result.verification_commands:
            console.print(f"Verification: {', '.join(result.verification_commands)}")
        console.print(
            f"Cost: ${result.total_usage.cost_usd:.4f} | "
            f"Tokens: {result.total_usage.input_tokens + result.total_usage.output_tokens:,}"
        )
        return 0
    finally:
        await router.close()


def _run_task_entrypoint(
    task: str,
    *,
    model: str | None = None,
    review: bool = True,
    permission_mode: str | None = None,
    approval_mode: str | None = None,
    allowed_tool: list[str] | None = None,
    verbose: bool = False,
    terse: bool = False,
    show_banner: bool = True,
) -> int:
    config = _build_run_config(
        model=model,
        review=review,
        permission_mode=permission_mode,
        approval_mode=approval_mode,
        allowed_tool=allowed_tool,
        verbose=verbose,
        terse=terse,
    )
    return asyncio.run(
        _execute_run_task(
            task,
            config=config,
            review=review,
            show_banner=show_banner,
        )
    )


def _interactive_task_session(
    *,
    model: str | None = None,
    review: bool = True,
    permission_mode: str | None = None,
    approval_mode: str | None = None,
    allowed_tool: list[str] | None = None,
    verbose: bool = False,
    terse: bool = False,
) -> int:
    _print_banner()
    console.print(
        "[dim]Talk to ForgeGod in natural language. "
        "Each message becomes a task against the current workspace.[/dim]"
    )
    if terse:
        console.print("[dim]Caveman mode enabled - ultra-terse prompts[/dim]")
    console.print(
        "[dim]Type /exit to leave, or use slash commands like /help for quick tips.[/dim]\n"
    )

    while True:
        try:
            task = console.input("[bold cyan]forgegod>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session closed.[/dim]")
            return 0

        if not task:
            continue
        lowered = task.lower()
        if lowered in {"/exit", "/quit", "exit", "quit"}:
            console.print("[dim]Session closed.[/dim]")
            return 0
        if lowered in {"/help", "help"}:
            console.print(
                "[dim]Try a plain request like:[/dim] "
                '[cyan]build a /health endpoint with tests[/cyan]'
            )
            console.print(
                "[dim]Use explicit commands for setup and control:[/dim] "
                "[cyan]forgegod init[/cyan], [cyan]forgegod plan[/cyan], "
                "[cyan]forgegod loop[/cyan], [cyan]forgegod doctor[/cyan]"
            )
            continue
        if task.startswith("/"):
            console.print(
                "[yellow]Slash commands are limited here.[/yellow] "
                "Use the full CLI command when you need setup, planning, or loop control."
            )
            continue

        exit_code = _run_task_entrypoint(
            task,
            model=model,
            review=review,
            permission_mode=permission_mode,
            approval_mode=approval_mode,
            allowed_tool=allowed_tool,
            verbose=verbose,
            terse=terse,
            show_banner=False,
        )
        if exit_code != 0:
            console.print("[yellow]ForgeGod needs another try or a different instruction.[/yellow]")
        console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override coder model"),
    review: bool = typer.Option(
        True,
        "--review/--no-review",
        help="Review output with frontier",
    ),
    permission_mode: Optional[str] = typer.Option(
        None,
        "--permission-mode",
        help="Permission mode: read-only, workspace-write, danger-full-access",
    ),
    approval_mode: Optional[str] = typer.Option(
        None,
        "--approval-mode",
        help="Approval mode: deny, prompt, approve",
    ),
    allowed_tool: list[str] | None = typer.Option(
        None,
        "--allow-tool",
        help="Repeat to allow only specific tools for this session",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging"),
    terse: bool = typer.Option(False, "--terse", help="Caveman mode - terse prompts"),
):
    if version:
        _print_banner()
        raise typer.Exit()
    if ctx.invoked_subcommand is not None:
        return

    if not _cli_is_interactive():
        _print_banner(mini=True)
        console.print(
            "[dim]Run [cyan]forgegod[/cyan] in a real terminal to open a "
            "natural-language session.[/dim]"
        )
        console.print(
            "[dim]Use [cyan]forgegod run[/cyan] when you need scripted, "
            "non-interactive execution.[/dim]"
        )
        raise typer.Exit()

    _ensure_project_bootstrap(announce=True)
    raise typer.Exit(
        _interactive_task_session(
            model=model,
            review=review,
            permission_mode=permission_mode,
            approval_mode=approval_mode,
            allowed_tool=allowed_tool,
            verbose=verbose,
            terse=terse,
        )
    )


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project root directory"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Skip wizard, auto-detect only"),
    lang: str = typer.Option("auto", "--lang", "-l", help="Language: en, es, auto"),
    profile: str = typer.Option(
        "adversarial",
        "--profile",
        help="Harness profile: adversarial or single-model",
    ),
    prefer_provider: str = typer.Option(
        "auto",
        "--prefer-provider",
        help="Provider preference: auto or openai",
    ),
    openai_surface: str = typer.Option(
        "auto",
        "--openai-surface",
        help="OpenAI surface: auto, api-only, codex-only, api+codex",
    ),
):
    """Initialize a ForgeGod project - interactive wizard or quick auto-detect."""
    from forgegod.i18n import set_lang

    set_lang(lang)

    if not quick:
        # Interactive wizard (default for new users)
        from forgegod.onboarding import OnboardingWizard

        wizard = OnboardingWizard(
            project_path=path,
            lang=lang,
            harness_profile=profile,
            preferred_provider=prefer_provider,
            openai_surface=openai_surface,
        )
        wizard.run()
        return

    # Quick mode: silent auto-detect (original behavior)
    import os

    from forgegod.config import init_project, recommend_model_defaults
    from forgegod.native_auth import codex_login_status_sync

    _print_banner()
    console.print("[bold]Initializing project...[/bold]")
    console.print()

    providers: list[str] = []
    codex_logged_in, _ = codex_login_status_sync()
    if codex_logged_in:
        providers.append("openai-codex")
        console.print("  [green]+[/green] OpenAI Codex subscription detected")
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
        console.print("  [green]+[/green] OpenAI API key detected")
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
        console.print("  [green]+[/green] Anthropic API key detected")
    if os.environ.get("OPENROUTER_API_KEY"):
        providers.append("openrouter")
        console.print("  [green]+[/green] OpenRouter API key detected")
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        providers.append("gemini")
        console.print("  [green]+[/green] Google Gemini API key detected")
    if os.environ.get("DEEPSEEK_API_KEY"):
        providers.append("deepseek")
        console.print("  [green]+[/green] DeepSeek API key detected")
    if os.environ.get("MOONSHOT_API_KEY"):
        providers.append("kimi")
        console.print("  [green]+[/green] Moonshot / Kimi API key detected")
    if os.environ.get("ZAI_CODING_API_KEY"):
        providers.append("zai")
        console.print("  [green]+[/green] Z.AI Coding Plan key detected")
    elif os.environ.get("ZAI_API_KEY"):
        providers.append("zai")
        console.print("  [green]+[/green] Z.AI / GLM API key detected")

    ollama_available = False
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            ollama_available = True
            models_data = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models_data]
            console.print(f"  [green]+[/green] Ollama running ({len(model_names)} models)")
            for m in model_names[:5]:
                console.print(f"    [dim]{m}[/dim]")
    except Exception:
        console.print("  [dim]-[/dim] Ollama not detected (optional - install for $0 local mode)")

    if not providers and not ollama_available:
        console.print()
        console.print("[yellow]No API keys or Ollama found.[/yellow]")
        console.print("Set at least one:")
        console.print("  forgegod auth login openai-codex")
        console.print("  export OPENAI_API_KEY=sk-...")
        console.print("  export ANTHROPIC_API_KEY=sk-ant-...")
        console.print("  export MOONSHOT_API_KEY=sk-...")
        console.print("  export ZAI_CODING_API_KEY=...")
        console.print("  export ZAI_API_KEY=...")
        console.print("  or: ollama serve  (for free local mode)")
        console.print()

    recommended_models = recommend_model_defaults(
        providers,
        ollama_available=ollama_available,
        profile=profile,
        preferred_provider=prefer_provider,
        openai_surface=openai_surface,
    )
    project_dir = init_project(
        path,
        model_defaults=recommended_models,
        harness_profile=profile,
        preferred_provider=prefer_provider,
        openai_surface=openai_surface,
    )

    console.print()
    console.print(f"[green]Initialized at {project_dir}[/green]")
    console.print("[dim]Applied auth-aware model defaults for detected providers.[/dim]")
    console.print(f"[dim]Provider preference: {prefer_provider}[/dim]")
    console.print(f"[dim]OpenAI surface: {openai_surface}[/dim]")
    console.print()
    console.print("[bold]Quick start:[/bold]")
    console.print('  forgegod run "Describe your task here"')
    console.print()
    console.print("[dim]Config: .forgegod/config.toml | Memory: .forgegod/memory.db[/dim]")
    if ollama_available and not providers:
        console.print("[dim]Running in local-only mode ($0). Add API keys for cloud models.[/dim]")


@design_app.command("list")
def design_list(
    query: str = typer.Option("", "--query", "-q", help="Filter presets by substring"),
    limit: int = typer.Option(30, "--limit", "-n", help="Max presets to show"),
):
    """List available DESIGN.md presets from awesome-design-md."""
    from forgegod.design import fetch_design_presets

    presets = fetch_design_presets()
    if query:
        q = query.lower()
        presets = [p for p in presets if q in p.lower()]
    shown = presets[:limit]

    table = Table(title="DESIGN.md Presets")
    table.add_column("Preset", style="cyan")
    table.add_column("Usage", style="dim")
    for preset in shown:
        table.add_row(preset, f"forgegod design pull {preset}")
    console.print(table)
    if len(presets) > len(shown):
        console.print(f"[dim]Showing {len(shown)} of {len(presets)} presets[/dim]")


@design_app.command("pull")
def design_pull(
    preset: str = typer.Argument(..., help="Preset slug or raw DESIGN.md URL"),
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project root"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing DESIGN.md"),
):
    """Install DESIGN.md into a project from awesome-design-md."""
    from forgegod.design import install_design_md

    installed = install_design_md(path, preset, force=force)
    console.print(f"[green]Installed[/green] {installed}")
    console.print("[dim]ForgeGod will load DESIGN.md automatically for frontend tasks.[/dim]")


@auth_app.command("status")
def auth_status():
    """Show which provider auth surfaces are currently usable."""
    import os
    from pathlib import Path

    from forgegod.config import _load_dotenv
    from forgegod.native_auth import codex_automation_status, codex_login_status_sync

    _load_dotenv(Path.cwd() / ".forgegod" / ".env")

    table = Table(title="ForgeGod Auth Status")
    table.add_column("Surface", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    codex_logged_in, codex_status = codex_login_status_sync()
    codex_supported, codex_env_detail = codex_automation_status()
    if codex_logged_in and codex_supported:
        codex_state = "[green]ready[/green]"
        codex_detail = codex_status or codex_env_detail
        if codex_detail:
            codex_detail = (
                f"{codex_detail} (quota can still block live runs; "
                "use `forgegod evals --matrix openai-live` to verify)"
            )
    elif codex_logged_in:
        codex_state = "[yellow]needs setup[/yellow]"
        codex_detail = codex_env_detail
    else:
        codex_state = "[yellow]not ready[/yellow]"
        codex_detail = codex_status or "Run `codex login`"
    table.add_row(
        "openai-codex",
        codex_state,
        codex_detail,
    )
    table.add_row(
        "openai-api",
        (
            "[green]ready[/green]"
            if os.environ.get("OPENAI_API_KEY")
            else "[yellow]not ready[/yellow]"
        ),
        "OPENAI_API_KEY" if os.environ.get("OPENAI_API_KEY") else "Set OPENAI_API_KEY",
    )
    table.add_row(
        "zai-coding-plan",
        (
            "[green]ready[/green]"
            if os.environ.get("ZAI_CODING_API_KEY") or os.environ.get("ZAI_API_KEY")
            else "[yellow]not ready[/yellow]"
        ),
        (
            "ZAI_CODING_API_KEY"
            if os.environ.get("ZAI_CODING_API_KEY")
            else "ZAI_API_KEY" if os.environ.get("ZAI_API_KEY") else "Set ZAI_CODING_API_KEY"
        ),
    )
    table.add_row(
        "openrouter",
        (
            "[green]ready[/green]"
            if os.environ.get("OPENROUTER_API_KEY")
            else "[yellow]not ready[/yellow]"
        ),
        (
            "OPENROUTER_API_KEY"
            if os.environ.get("OPENROUTER_API_KEY")
            else "OAuth/API support planned; key works today"
        ),
    )
    console.print(table)


@auth_app.command("login")
def auth_login(
    provider: str = typer.Argument(..., help="Provider auth surface, e.g. openai-codex"),
):
    """Start an official login flow when ForgeGod can delegate to it."""
    import subprocess

    from forgegod.native_auth import codex_login_argv

    if provider != "openai-codex":
        raise typer.BadParameter(
            "Only `openai-codex` login is wired today. "
            "Z.AI uses Coding Plan API keys inside ForgeGod."
        )

    try:
        argv = codex_login_argv()
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    subprocess.run(argv, check=False)


@auth_app.command("sync")
def auth_sync(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project root"),
    profile: str = typer.Option(
        "adversarial",
        "--profile",
        help="Harness profile: adversarial or single-model",
    ),
    prefer_provider: str = typer.Option(
        "auto",
        "--prefer-provider",
        help="Provider preference: auto or openai",
    ),
    openai_surface: str = typer.Option(
        "auto",
        "--openai-surface",
        help="OpenAI surface: auto, api-only, codex-only, api+codex",
    ),
):
    """Rewrite model defaults based on detected native auth surfaces."""
    import toml

    from forgegod.config import init_project, openai_surface_label, resolve_openai_surface
    from forgegod.native_auth import codex_automation_status

    _, providers, ollama_available, recommended = _detect_runtime_model_defaults(
        path,
        profile=profile,
        preferred_provider=prefer_provider,
        openai_surface=openai_surface,
    )
    project_dir = init_project(
        path,
        model_defaults=recommended,
        harness_profile=profile,
        preferred_provider=prefer_provider,
        openai_surface=openai_surface,
    )
    config_path = project_dir / "config.toml"
    data = toml.loads(config_path.read_text(encoding="utf-8"))
    data["models"] = recommended.model_dump()
    data.setdefault("harness", {})["profile"] = profile
    data["harness"]["preferred_provider"] = prefer_provider
    data["harness"]["openai_surface"] = openai_surface
    budget = data.setdefault("budget", {})
    if providers and not ollama_available:
        if budget.get("mode") in {"local-only", "halt"}:
            budget["mode"] = "normal"
        if float(budget.get("daily_limit_usd", 0) or 0) <= 0:
            budget["daily_limit_usd"] = 5.0
    config_path.write_text(toml.dumps(data), encoding="utf-8")
    codex_supported, _ = codex_automation_status()
    effective_surface = resolve_openai_surface(
        openai_surface,
        providers,
        codex_automation_supported=codex_supported,
    )

    table = Table(title=f"ForgeGod Model Sync ({Path(path).resolve()})")
    table.add_column("Role", style="cyan")
    table.add_column("Model", style="dim")
    for role, model in recommended.model_dump().items():
        table.add_row(role, model)
    console.print(table)
    console.print(f"[dim]Harness profile:[/dim] {profile}")
    console.print(f"[dim]Provider preference:[/dim] {prefer_provider}")
    console.print(f"[dim]Requested OpenAI surface:[/dim] {openai_surface_label(openai_surface)}")
    console.print(f"[dim]Effective OpenAI surface:[/dim] {openai_surface_label(effective_surface)}")
    if providers and not ollama_available:
        console.print(
            "[dim]Budget sync:[/dim] cloud-ready config ensured "
            f"(mode={budget.get('mode')}, daily_limit_usd={budget.get('daily_limit_usd')})."
        )
    if openai_surface != "auto" and effective_surface != openai_surface:
        console.print(
            "[yellow]OpenAI surface fallback:[/yellow] "
            f"requested {openai_surface_label(openai_surface)}, "
            f"but ForgeGod only detected {openai_surface_label(effective_surface)} today."
        )
    if (
        openai_surface == "auto"
        and "openai-codex" in providers
        and "openai" not in providers
    ):
        console.print(
            "[yellow]Note:[/yellow] Only Codex subscription was detected. "
            "ForgeGod will default to codex-only for OpenAI roles. "
            "Use --openai-surface codex-only to make that explicit."
        )

    if "openai-codex" in providers and recommended.coder.startswith("openai-codex"):
        console.print(
            "[yellow]Note:[/yellow] OpenAI Codex subscription is now a production-ready "
            "ForgeGod surface when the Codex CLI is installed and logged in. "
            "Benchmark codex-only versus api+codex on your workload before making it "
            "the default remote coder."
        )
    elif "openai-codex" in providers:
        console.print(
            "[yellow]Note:[/yellow] OpenAI Codex login was detected, but ForgeGod "
            "did not choose it as a default automation backend in this environment."
        )
    elif not providers and not ollama_available:
        console.print("[yellow]No providers or Ollama detected.[/yellow]")


@auth_app.command("explain")
def auth_explain(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project root"),
    profile: str = typer.Option(
        "adversarial",
        "--profile",
        help="Harness profile: adversarial or single-model",
    ),
    prefer_provider: str = typer.Option(
        "auto",
        "--prefer-provider",
        help="Provider preference: auto or openai",
    ),
    openai_surface: str = typer.Option(
        "auto",
        "--openai-surface",
        help="OpenAI surface: auto, api-only, codex-only, api+codex",
    ),
):
    """Explain how ForgeGod will map roles from the currently available auth surfaces."""
    from forgegod.config import openai_surface_label, resolve_openai_surface
    from forgegod.native_auth import codex_automation_status

    _, providers, ollama_available, recommended = _detect_runtime_model_defaults(
        path,
        profile=profile,
        preferred_provider=prefer_provider,
        openai_surface=openai_surface,
    )
    codex_supported, _ = codex_automation_status()
    effective_surface = resolve_openai_surface(
        openai_surface,
        providers,
        codex_automation_supported=codex_supported,
    )

    summary = Table(title=f"ForgeGod Harness Explain ({Path(path).resolve()})")
    summary.add_column("Setting", style="cyan")
    summary.add_column("Value", style="dim")
    summary.add_row("Profile", profile)
    summary.add_row("Provider preference", prefer_provider)
    summary.add_row("Requested OpenAI surface", openai_surface_label(openai_surface))
    summary.add_row("Effective OpenAI surface", openai_surface_label(effective_surface))
    summary.add_row("Detected providers", ", ".join(providers) if providers else "none")
    summary.add_row("Ollama ready", "yes" if ollama_available else "no")
    console.print(summary)

    roles = Table(title="Role Mapping")
    roles.add_column("Role", style="cyan")
    roles.add_column("Model", style="dim")
    for role, model in recommended.model_dump().items():
        roles.add_row(role, model)
    console.print(roles)

    if openai_surface != "auto" and effective_surface != openai_surface:
        console.print(
            "[yellow]OpenAI surface fallback:[/yellow] "
            f"requested {openai_surface_label(openai_surface)}, "
            f"but ForgeGod only detected {openai_surface_label(effective_surface)} today."
        )
    if (
        openai_surface == "auto"
        and "openai-codex" in providers
        and "openai" not in providers
    ):
        console.print(
            "[yellow]Note:[/yellow] Only Codex subscription was detected. "
            "ForgeGod will default to codex-only for OpenAI roles. "
            "Use --openai-surface codex-only to make that explicit."
        )


@app.command()
def permissions(
    permission_mode: Optional[str] = typer.Option(
        None,
        "--permission-mode",
        help="Preview a specific permission mode: read-only, workspace-write, danger-full-access",
    ),
    approval_mode: Optional[str] = typer.Option(
        None,
        "--approval-mode",
        help="Preview approval mode: deny, prompt, approve",
    ),
    allowed_tool: list[str] | None = typer.Option(
        None,
        "--allowed-tool",
        help="Repeat to preview a restricted allowlist",
    ),
):
    """Show the effective ForgeGod tool-permission policy for this workspace."""
    from forgegod.config import load_config
    from forgegod.tools import load_all_tools, permission_policy_snapshot

    config = load_config()
    if permission_mode:
        config.security.permission_mode = permission_mode
    if approval_mode:
        config.security.approval_mode = approval_mode
    if allowed_tool is not None:
        config.security.allowed_tools = list(allowed_tool)

    load_all_tools()
    snapshot = permission_policy_snapshot(config)

    summary = Table(title="ForgeGod Permissions")
    summary.add_column("Setting", style="cyan")
    summary.add_column("Value", style="dim")
    summary.add_row("Mode", snapshot["mode"])
    summary.add_row("Approval mode", snapshot["approval_mode"])
    summary.add_row("Allowed-tool override", ", ".join(snapshot["allowed_tools"]) or "(none)")
    summary.add_row("Effective allowed tools", str(len(snapshot["effective_allowed_tools"])))
    summary.add_row("Blocked tools", str(len(snapshot["blocked_tools"])))
    console.print(summary)

    if snapshot["blocked_tools"]:
        blocked = Table(title="Blocked Tools")
        blocked.add_column("Tool", style="red")
        for tool in snapshot["blocked_tools"]:
            blocked.add_row(tool)
        console.print(blocked)

    if snapshot["mode"] == "read-only":
        preview = ", ".join(snapshot["read_only_bash_prefixes"][:8])
        console.print(
            "[dim]Read-only bash is prefix-based. Examples:[/dim] "
            f"{preview}"
        )


@app.command()
def run(
    task: str = typer.Argument(..., help="Task description"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override coder model"),
    review: bool = typer.Option(True, "--review/--no-review", help="Review output with frontier"),
    permission_mode: Optional[str] = typer.Option(
        None,
        "--permission-mode",
        help="Permission mode: read-only, workspace-write, danger-full-access",
    ),
    approval_mode: Optional[str] = typer.Option(
        None,
        "--approval-mode",
        help="Approval mode: deny, prompt, approve",
    ),
    allowed_tool: list[str] | None = typer.Option(
        None,
        "--allowed-tool",
        help="Repeat to allow only specific tools for this run",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    terse: bool = typer.Option(
        False, "--terse", help="Caveman mode - terse prompts"
    ),
):
    """Execute a single coding task."""
    raise typer.Exit(
        _run_task_entrypoint(
            task,
            model=model,
            review=review,
            permission_mode=permission_mode,
            approval_mode=approval_mode,
            allowed_tool=allowed_tool,
            verbose=verbose,
            terse=terse,
        )
    )


@app.command()
def loop(
    prd: Path = typer.Option(
        Path(".forgegod/prd.json"), "--prd", "-p", help="PRD file path"
    ),
    workers: int = typer.Option(1, "--workers", "-w", help="Parallel workers"),
    max_iterations: Optional[int] = typer.Option(None, "--max", help="Max iterations"),
    permission_mode: Optional[str] = typer.Option(
        None,
        "--permission-mode",
        help="Permission mode: read-only, workspace-write, danger-full-access",
    ),
    approval_mode: Optional[str] = typer.Option(
        None,
        "--approval-mode",
        help="Approval mode: deny, prompt, approve",
    ),
    allowed_tool: list[str] | None = typer.Option(
        None,
        "--allowed-tool",
        help="Repeat to allow only specific tools during the loop",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Print story order, don't run"
    ),
    terse: bool = typer.Option(
        False, "--terse", help="Caveman mode - terse prompts"
    ),
):
    """Run 24/7 Ralph loop - autonomous coding from PRD."""
    from forgegod.config import load_config

    config = load_config()
    if terse:
        config.terse.enabled = True
    if workers > 1:
        config.loop.parallel_workers = workers
    if max_iterations is not None:
        config.loop.max_iterations = max_iterations
    if permission_mode:
        config.security.permission_mode = permission_mode
    if approval_mode:
        config.security.approval_mode = approval_mode
    if allowed_tool is not None:
        config.security.allowed_tools = list(allowed_tool)
    if config.security.approval_mode == "prompt" and workers > 1:
        console.print("[red]Prompt approval mode is only supported with --workers 1.[/red]")
        raise typer.Exit(1)

    if not prd.exists():
        console.print(f"[red]PRD not found at {prd}[/red]")
        console.print("Create one with: forgegod plan <task>")
        raise typer.Exit(1)

    log_file = config.project_dir / "logs" / "loop.log"
    configure_cli_logging(
        verbose=verbose,
        log_file=log_file,
        stream=verbose,
    )

    async def _loop():
        from forgegod.loop import RalphLoop
        from forgegod.router import ModelRouter

        router = ModelRouter(config)
        approver = _build_tool_approver() if config.security.approval_mode == "prompt" else None
        narrator = LoopNarrator()
        try:
            ralph = RalphLoop.from_prd_file(
                prd,
                config,
                router=router,
                tool_approver=approver,
                event_callback=narrator,
            )

            if dry_run:
                state = await ralph.run(dry_run=True)
                return

            _print_banner()
            console.print(
                "[bold green]Ralph Loop started.[/bold green]"
                " Press Ctrl+C to stop.\n"
            )
            try:
                state = await ralph.run()
            except KeyboardInterrupt:
                await ralph.stop()
                state = ralph.state
                console.print("\n[yellow]Loop stopped by user.[/yellow]")

            console.print(
                f"Completed: {state.stories_completed} | "
                f"Failed: {state.stories_failed} | "
                f"Cost: ${state.total_cost_usd:.4f}"
            )
        finally:
            await router.close()

    asyncio.run(_loop())


@app.command()
def plan(
    task: str = typer.Argument(..., help="High-level project description"),
    output: Path = typer.Option(
        Path(".forgegod/prd.json"), "--output", "-o", help="Output PRD path"
    ),
    terse: bool = typer.Option(
        False, "--terse", help="Caveman mode - terse prompts"
    ),
):
    """Generate a PRD (task decomposition) from a description."""
    from forgegod.config import load_config

    config = load_config()
    if terse:
        config.terse.enabled = True

    async def _plan():
        from forgegod.planner import Planner
        from forgegod.router import ModelRouter

        router = ModelRouter(config)
        planner = Planner(config=config, router=router)
        prd = await planner.decompose(task)

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(prd.model_dump(), indent=2))
        console.print(f"[green]PRD generated with {len(prd.stories)} stories -> {output}[/green]")
        for story in prd.stories:
            console.print(f"  [{story.id}] {story.title}")

    asyncio.run(_plan())


@app.command()
def recon(
    task: str = typer.Argument(..., help="What to build"),
    output: Path = typer.Option(
        Path(".forgegod/prd.json"), "--output", "-o", help="Output PRD path"
    ),
    searches: int = typer.Option(15, "--searches", "-s", help="Max web searches"),
    rounds: int = typer.Option(3, "--rounds", "-r", help="Max debate rounds"),
    provider: str = typer.Option(
        "searxng", "--provider", help="Search provider: searxng, brave, exa"
    ),
    min_score: float = typer.Option(7.0, "--min-score", help="Min approval score (0-10)"),
):
    """Research-grounded planning - web research + adversarial debate.

    The only coding agent that researches before it codes.
    Phase 1: RECON - searches the web for best libraries, CVEs, patterns.
    Phase 2: ARCHITECT - generates PRD using research findings.
    Phase 3: ADVERSARY - hostile critic debates the plan until score >= min_score.
    """
    from forgegod.config import load_config

    config = load_config()
    config.recon.enabled = True
    config.recon.max_searches = searches
    config.recon.debate_rounds = rounds
    config.recon.search_provider = provider
    config.recon.min_approval_score = min_score

    async def _recon():
        from forgegod.planner import Planner
        from forgegod.router import ModelRouter

        router = ModelRouter(config)
        planner = Planner(config=config, router=router)

        console.print(Panel(
            "[cyan]RECON MODE[/cyan] - Research-grounded planning\n"
            f"Task: {task[:80]}{'...' if len(task) > 80 else ''}\n"
            f"Provider: {provider} | Searches: {searches} | Debate rounds: {rounds}",
            title="[bold cyan]ForgeGod Recon[/bold cyan]",
            border_style="cyan",
        ))

        prd, brief, debate = await planner.research_and_decompose(task)

        # Save artifacts
        output.parent.mkdir(parents=True, exist_ok=True)
        recon_dir = output.parent / "recon"
        recon_dir.mkdir(exist_ok=True)

        output.write_text(json.dumps(prd.model_dump(), indent=2))
        (recon_dir / "brief.json").write_text(json.dumps(brief.model_dump(), indent=2))
        (recon_dir / "debate.json").write_text(json.dumps(debate.model_dump(), indent=2))

        # Display results
        console.print()

        # Research Brief summary
        if brief.libraries:
            table = Table(title="Research: Recommended Libraries", border_style="cyan")
            table.add_column("Library", style="green")
            table.add_column("Version", style="cyan")
            table.add_column("Why")
            table.add_column("Alternatives", style="dim")
            for lib in brief.libraries:
                table.add_row(
                    lib.name, lib.version, lib.why[:60],
                    ", ".join(lib.alternatives[:3]) if lib.alternatives else "-",
                )
            console.print(table)

        if brief.security_warnings:
            console.print(Panel(
                "\n".join(f"[red]![/red] {w}" for w in brief.security_warnings),
                title="Security Warnings", border_style="red",
            ))

        # Debate summary
        console.print()
        verdict_color = "green" if debate.converged else "yellow"
        console.print(Panel(
            f"Rounds: {debate.rounds} | "
            f"Converged: [{'green' if debate.converged else 'red'}]{debate.converged}[/] | "
            f"Final Score: [{verdict_color}]{debate.final_score:.1f}/10[/]",
            title="Adversarial Debate", border_style=verdict_color,
        ))

        if debate.critiques:
            last = debate.critiques[-1]
            scores = Table(title="Dimension Scores", border_style="dim")
            scores.add_column("Dimension")
            scores.add_column("Score", justify="right")
            for name, val in [
                ("SOTA", last.sota_score),
                ("Security", last.security_score),
                ("Architecture", last.architecture_score),
                ("Completeness", last.completeness_score),
            ]:
                color = "green" if val >= 7 else "yellow" if val >= 5 else "red"
                scores.add_row(name, f"[{color}]{val:.1f}[/]")
            console.print(scores)

        # PRD summary
        console.print()
        console.print(f"[green]PRD generated with {len(prd.stories)} stories -> {output}[/green]")
        for story in prd.stories:
            console.print(f"  [{story.id}] {story.title}")

        console.print(f"\n[dim]Artifacts: {recon_dir}/[/dim]")

    asyncio.run(_recon())


@app.command()
def contribute(
    target: str = typer.Argument(
        ".",
        help="Local repository path or GitHub URL (https://github.com/owner/repo)",
    ),
    goal: Optional[str] = typer.Option(
        None, "--goal", "-g", help="Specific contribution goal or improvement area"
    ),
    issue: Optional[int] = typer.Option(
        None, "--issue", help="Prefer this issue number when planning"
    ),
    checkout: Optional[Path] = typer.Option(
        None, "--checkout", help="Clone destination when target is a GitHub URL"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write contribution PRD JSON here"
    ),
    autonomous: bool = typer.Option(
        False,
        "--autonomous",
        help="After planning, execute the first proposed contribution story",
    ),
):
    """Contribution mode - read CONTRIBUTING.md, inspect the repo, plan, then optionally act."""
    from forgegod.config import init_project, load_config
    from forgegod.contributing import (
        build_contribution_task,
        collect_contribution_context,
        ensure_target_checkout,
        fetch_issue_candidates,
        parse_github_repo,
    )

    _print_banner(mini=True)
    repo_path, repo_url = ensure_target_checkout(target, checkout)
    parsed = parse_github_repo(repo_url or target)

    issues = []
    if parsed:
        owner, repo = parsed
        try:
            issues = fetch_issue_candidates(owner, repo)
        except Exception as e:
            console.print(f"[yellow]Issue discovery skipped:[/yellow] {e}")

    context = collect_contribution_context(
        repo_path,
        repo_url=repo_url,
        issue_candidates=issues,
    )
    task = build_contribution_task(context, goal=goal or "", issue_number=issue)

    async def _contribute():
        from forgegod.agent import Agent
        from forgegod.planner import Planner
        from forgegod.router import ModelRouter

        _, _, _, recommended = _detect_runtime_model_defaults(repo_path)
        init_project(repo_path, model_defaults=recommended)
        config = load_config(repo_path)
        out_path = output or (repo_path / ".forgegod" / "contribute_prd.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        router = ModelRouter(config)
        try:
            planner = Planner(config=config, router=router)
            prd = await planner.decompose(task, project_name=repo_path.name)
            out_path.write_text(json.dumps(prd.model_dump(), indent=2), encoding="utf-8")

            console.print(
                Panel(
                    f"Target: {repo_path}\n"
                    f"Stories proposed: {len(prd.stories)}\n"
                    f"Issue candidates: {len(issues)}\n"
                    f"Saved plan: {out_path}",
                    title="[bold cyan]Contribution Mode[/bold cyan]",
                    border_style="cyan",
                )
            )
            for story in prd.stories[:8]:
                console.print(f"  [{story.id}] {story.title}")

            if not autonomous:
                return

            selected = prd.stories[0] if prd.stories else None
            if not selected:
                console.print("[yellow]No stories proposed, nothing to run.[/yellow]")
                return

            agent = Agent(config=config, router=router)
            exec_task = (
                f"{task}\n\n"
                f"## Selected Contribution Story\n"
                f"ID: {selected.id}\n"
                f"Title: {selected.title}\n"
                f"Description: {selected.description}\n"
                f"Acceptance Criteria: {selected.acceptance_criteria}\n"
            )
            result = await agent.run(exec_task)
            if result.success:
                console.print(
                    Panel(
                        f"[green]Contribution task completed[/green]\n"
                        f"{result.output[:700]}",
                        border_style="green",
                    )
                )
                if result.files_modified:
                    console.print(f"Files modified: {', '.join(result.files_modified)}")
            else:
                failure = result.error or result.output
                console.print(f"[red]Contribution task failed:[/red] {failure}")
        finally:
            await router.close()

    asyncio.run(_contribute())


@app.command()
def review(
    path: str = typer.Argument(".", help="Path to review"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override reviewer model"),
):
    """Review code with a frontier model."""
    from forgegod.config import load_config

    config = load_config()
    if model:
        config.models.reviewer = model

    async def _review():
        from forgegod.reviewer import Reviewer
        from forgegod.router import ModelRouter

        router = ModelRouter(config)
        reviewer = Reviewer(config=config, router=router)
        result = await reviewer.review_path(path)

        color = {"approve": "green", "revise": "yellow", "reject": "red"}
        console.print(
            f"[{color[result.verdict.value]}]"
            f"Verdict: {result.verdict.value.upper()}[/{color[result.verdict.value]}]"
        )
        console.print(f"Reasoning: {result.reasoning}")
        if result.issues:
            for issue in result.issues:
                console.print(f"  [red]- {issue}[/red]")
        if result.suggestions:
            for suggestion in result.suggestions:
                console.print(f"  [blue]+ {suggestion}[/blue]")

    asyncio.run(_review())


@app.command()
def cost():
    """Show cost breakdown."""
    from forgegod.budget import BudgetTracker
    from forgegod.config import load_config

    config = load_config()
    tracker = BudgetTracker(config)

    status = tracker.get_status()
    table = Table(title="ForgeGod Cost Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Budget Mode", status.mode.value)
    table.add_row("Daily Limit", f"${status.daily_limit_usd:.2f}")
    table.add_row("Spent Today", f"${status.spent_today_usd:.4f}")
    table.add_row("Remaining Today", f"${status.remaining_today_usd:.4f}")
    table.add_row("Total Spent", f"${status.spent_total_usd:.4f}")
    table.add_row("Calls Today", str(status.calls_today))

    console.print(table)

    # Per-model breakdown
    breakdown = tracker.get_model_breakdown()
    if breakdown:
        model_table = Table(title="Per-Model Breakdown (Today)")
        model_table.add_column("Model", style="cyan")
        model_table.add_column("Calls", style="white")
        model_table.add_column("Cost", style="green")
        for model, data in breakdown.items():
            model_table.add_row(model, str(data["calls"]), f"${data['cost']:.4f}")
        console.print(model_table)


@app.command()
def status():
    """Show current ForgeGod status."""
    from forgegod.config import load_config

    config = load_config()
    state_path = config.project_dir / "state.json"

    if not state_path.exists():
        console.print("[yellow]No active loop. Run 'forgegod loop' to start.[/yellow]")
        return

    from forgegod.models import LoopState

    state = LoopState(**json.loads(state_path.read_text()))

    table = Table(title="ForgeGod Status")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", state.status.value)
    table.add_row("Current Story", state.current_story_id or "-")
    table.add_row("Completed", str(state.stories_completed))
    table.add_row("Failed", str(state.stories_failed))
    table.add_row("Iterations", str(state.total_iterations))
    table.add_row("Cost", f"${state.total_cost_usd:.4f}")
    table.add_row("Context Rotations", str(state.context_rotations))
    table.add_row("Started", state.started_at or "-")

    console.print(table)


@app.command()
def memory():
    """Show memory system health and top learnings."""
    from forgegod.config import load_config

    _print_banner(mini=True)
    config = load_config()

    async def _memory():
        from forgegod.memory import Memory

        mem = Memory(config)
        report = await mem.health()

        table = Table(title="ForgeGod Memory Health")
        table.add_column("Tier", style="cyan")
        table.add_column("Count", style="green")

        table.add_row("Episodic (task records)", str(report["episodes"]))
        table.add_row("Semantic (principles)", str(report["semantic_memories"]))
        table.add_row("Procedural (patterns)", str(report["procedural_memories"]))
        table.add_row("Error-Solution pairs", str(report["error_solutions"]))
        table.add_row("Graph entities", str(report["entities"]))
        table.add_row("Causal edges", str(report["causal_edges"]))

        console.print(table)
        console.print(
            f"Avg confidence: {report['avg_confidence']:.1%} | "
            f"Strong: {report['strong_memories']} | Weak: {report['weak_memories']} | "
            f"Health: {report['health_score']:.0%}"
        )

        # Show top learnings
        learnings = await mem.get_learnings_text(limit=5)
        if learnings:
            console.print()
            console.print(Panel(learnings, title="Top Learnings"))

    asyncio.run(_memory())


@app.command()
def doctor():
    """Check ForgeGod installation health."""
    from forgegod.doctor import print_doctor_results, run_doctor

    _print_banner(mini=True)
    checks = run_doctor()
    print_doctor_results(checks)


@app.command()
def evals(
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Optional JSON manifest path. Defaults to ForgeGod's built-in harness evals.",
    ),
    matrix: Optional[str] = typer.Option(
        None,
        "--matrix",
        help=(
            "Built-in eval matrix to run. Supported today: "
            "openai-surfaces, openai-live, openai-live-compare"
        ),
    ),
    case: list[str] | None = typer.Option(
        None,
        "--case",
        help="Repeat to run only specific eval case IDs.",
    ),
    tag: list[str] | None = typer.Option(
        None,
        "--tag",
        help="Repeat to run only cases that include one of these tags.",
    ),
    output: Path = typer.Option(
        Path(".forgegod/evals/harness_evals_report.json"),
        "--output",
        "-o",
        help="Output JSON report path.",
    ),
    traces_dir: Path = typer.Option(
        Path(".forgegod/evals/traces"),
        "--traces-dir",
        help="Directory for per-case mock request traces.",
    ),
    list_cases: bool = typer.Option(
        False,
        "--list",
        help="List available eval cases without running them.",
    ),
    list_matrices: bool = typer.Option(
        False,
        "--list-matrices",
        help="List built-in eval matrices without running them.",
    ),
):
    """Run deterministic harness evals for CLI surfaces and guardrails."""
    from forgegod.config import load_config
    from forgegod.evals import HarnessEvalRunner, load_eval_manifest

    _print_banner(mini=True)
    eval_manifest = load_eval_manifest(manifest)

    if list_matrices:
        typer.echo("Harness eval matrices")
        matrix_table = Table(title="Harness eval matrices")
        matrix_table.add_column("Matrix", style="cyan")
        matrix_table.add_column("Purpose", style="dim")
        matrix_table.add_row(
            "openai-surfaces",
            "Compare adversarial vs single-model across OpenAI API/Codex surfaces",
        )
        matrix_table.add_row(
            "openai-live",
            "Run cheap live probes against real OpenAI API/Codex auth surfaces",
        )
        matrix_table.add_row(
            "openai-live-compare",
            "Rank runnable live OpenAI surfaces and recommend the best current harness row",
        )
        typer.echo(
            "openai-surfaces\t"
            "Compare adversarial vs single-model across OpenAI API/Codex surfaces"
        )
        typer.echo(
            "openai-live\t"
            "Run cheap live probes against real OpenAI API/Codex auth surfaces"
        )
        typer.echo(
            "openai-live-compare\t"
            "Rank runnable live OpenAI surfaces and recommend the best current harness row"
        )
        console.print(matrix_table)
        raise typer.Exit()

    if list_cases:
        typer.echo(f"Harness eval cases - {eval_manifest.name}")
        table = Table(title=f"Harness eval cases - {eval_manifest.name}")
        table.add_column("Case", style="cyan")
        table.add_column("Surface", style="white")
        table.add_column("Tags", style="yellow")
        table.add_column("Description", style="dim")
        for eval_case in eval_manifest.cases:
            table.add_row(
                eval_case.id,
                eval_case.surface,
                ", ".join(eval_case.tags) or "-",
                eval_case.description,
            )
            typer.echo(
                f"{eval_case.id}\t{eval_case.surface}\t"
                f"{', '.join(eval_case.tags) or '-'}\t{eval_case.description}"
            )
        console.print(table)
        console.print(
            "[dim]Available IDs:[/dim] "
            + ", ".join(eval_case.id for eval_case in eval_manifest.cases)
        )
        raise typer.Exit()

    runner = HarnessEvalRunner(load_config())
    if matrix:
        if matrix == "openai-live":
            live_report = runner.run_openai_live_surface_matrix(output_path=output)
            summary = Table(title=f"ForgeGod eval matrix - {live_report.matrix_name}")
            summary.add_column("Row", style="cyan")
            summary.add_column("Profile", style="white")
            summary.add_column("Requested", style="yellow")
            summary.add_column("Effective", style="yellow")
            summary.add_column("Status", justify="center")
            summary.add_column("Score", justify="right")
            for row in live_report.rows:
                summary.add_row(
                    row.id,
                    row.profile,
                    row.requested_openai_surface,
                    row.effective_openai_surface,
                    row.status,
                    "-" if row.status == "skipped" else f"{row.score:.3f}",
                )
            console.print(summary)
            probes = Table(title="Live probe summary")
            probes.add_column("Row", style="cyan")
            probes.add_column("Detail", style="dim")
            for row in live_report.rows:
                if row.probe_results:
                    rendered = ", ".join(
                        f"{probe.role}:{'pass' if probe.passed else 'fail'}"
                        for probe in row.probe_results
                    )
                    probes.add_row(row.id, f"{rendered} | cost=${row.total_cost_usd:.4f}")
                else:
                    probes.add_row(row.id, row.detail or "-")
            console.print(probes)
            typer.echo(
                f"Live OpenAI eval matrix complete ("
                f"{live_report.passed_rows}/{live_report.total_rows} rows passed, "
                f"{live_report.failed_rows} failed, "
                f"{live_report.skipped_rows} skipped, "
                f"score={live_report.score:.3f})"
            )
            typer.echo(f"Report: {output}")
            typer.echo("Live probe summary")
            console.print(
                f"\n[bold green]Live OpenAI eval matrix complete[/bold green] "
                f"({live_report.passed_rows}/{live_report.total_rows} rows passed, "
                f"{live_report.failed_rows} failed, {live_report.skipped_rows} skipped, "
                f"score={live_report.score:.3f})"
            )
            console.print(f"[dim]Report: {output}[/dim]")
            if live_report.failed_rows > 0:
                raise typer.Exit(1)
            raise typer.Exit()
        if matrix == "openai-live-compare":
            comparison_report = runner.run_openai_live_surface_comparison(output_path=output)
            summary = Table(title=f"ForgeGod eval matrix - {comparison_report.matrix_name}")
            summary.add_column("Rank", justify="right")
            summary.add_column("Row", style="cyan")
            summary.add_column("Profile", style="white")
            summary.add_column("Requested", style="yellow")
            summary.add_column("Effective", style="yellow")
            summary.add_column("Status", justify="center")
            summary.add_column("Score", justify="right")
            summary.add_column("Cost", justify="right")
            for row in comparison_report.rows:
                summary.add_row(
                    str(row.rank),
                    row.id,
                    row.profile,
                    row.requested_openai_surface,
                    row.effective_openai_surface,
                    row.status,
                    f"{row.score:.3f}",
                    f"${row.total_cost_usd:.4f}",
                )
            console.print(summary)
            if comparison_report.recommended_row_id:
                typer.echo(f"Recommended harness row: {comparison_report.recommended_row_id}")
                typer.echo(f"Reason: {comparison_report.recommendation_reason}")
                console.print(
                    f"[bold green]Recommended harness row:[/bold green] "
                    f"{comparison_report.recommended_row_id}"
                )
                console.print(f"[dim]{comparison_report.recommendation_reason}[/dim]")
            else:
                typer.echo("Recommended harness row: none")
                typer.echo(f"Reason: {comparison_report.recommendation_reason}")
                console.print("[yellow]No runnable live OpenAI rows were available.[/yellow]")
                console.print(f"[dim]{comparison_report.recommendation_reason}[/dim]")
            typer.echo(
                f"Live OpenAI comparison complete ("
                f"{comparison_report.runnable_rows} runnable, "
                f"{comparison_report.passed_rows} passed, "
                f"{comparison_report.failed_rows} failed, "
                f"{comparison_report.skipped_rows} skipped)"
            )
            typer.echo(f"Report: {output}")
            console.print(
                f"\n[bold green]Live OpenAI comparison complete[/bold green] "
                f"({comparison_report.runnable_rows} runnable, "
                f"{comparison_report.passed_rows} passed, "
                f"{comparison_report.failed_rows} failed, "
                f"{comparison_report.skipped_rows} skipped)"
            )
            console.print(f"[dim]Report: {output}[/dim]")
            if comparison_report.failed_rows > 0:
                raise typer.Exit(1)
            raise typer.Exit()
        if matrix != "openai-surfaces":
            raise typer.BadParameter(
                "Unknown eval matrix. Supported today: "
                "openai-surfaces, openai-live, openai-live-compare"
            )
        matrix_report = runner.run_openai_surface_matrix(
            eval_manifest,
            selected_case_ids=set(case or []),
            selected_tags=set(tag or []),
            output_path=output,
            traces_dir=traces_dir,
        )
        summary = Table(title=f"ForgeGod eval matrix - {matrix_report.matrix_name}")
        summary.add_column("Row", style="cyan")
        summary.add_column("Profile", style="white")
        summary.add_column("OpenAI surface", style="yellow")
        summary.add_column("Score", justify="right")
        summary.add_column("Pass", justify="center")
        for row in matrix_report.rows:
            summary.add_row(
                row.id,
                row.profile,
                row.effective_openai_surface,
                f"{row.score:.3f}",
                "yes" if row.passed else "no",
            )
        console.print(summary)
        graders = Table(title="Trace grader summary")
        graders.add_column("Row", style="cyan")
        graders.add_column("Trace graders", style="dim")
        for row in matrix_report.rows:
            rendered = ", ".join(
                f"{name}={score:.3f}" for name, score in row.trace_grade_scores.items()
            ) or "-"
            graders.add_row(row.id, rendered)
        console.print(graders)
        typer.echo(
            f"Harness eval matrix complete ({matrix_report.passed_rows}/{matrix_report.total_rows} "
            f"rows passing, score={matrix_report.score:.3f})"
        )
        typer.echo(f"Report: {output}")
        typer.echo(f"Traces root: {traces_dir}")
        typer.echo("Trace grader summary")
        console.print(
            f"\n[bold green]Harness eval matrix complete[/bold green] "
            f"({matrix_report.passed_rows}/{matrix_report.total_rows} rows passing, "
            f"score={matrix_report.score:.3f})"
        )
        console.print(f"[dim]Report: {output}[/dim]")
        console.print(f"[dim]Traces root: {traces_dir}[/dim]")
        if matrix_report.passed_rows != matrix_report.total_rows:
            raise typer.Exit(1)
        raise typer.Exit()

    report = runner.run_manifest(
        eval_manifest,
        selected_case_ids=set(case or []),
        selected_tags=set(tag or []),
        output_path=output,
        traces_dir=traces_dir,
    )
    typer.echo(
        f"Harness evals complete ({report.passed_cases}/{report.total_cases} passing, "
        f"score={report.score:.3f})"
    )
    typer.echo(f"Report: {output}")
    typer.echo(f"Traces: {traces_dir}")
    if report.dimension_scores:
        typer.echo(
            "Dimensions: "
            + ", ".join(
                f"{name}={score:.3f}" for name, score in report.dimension_scores.items()
            )
        )
    if report.trace_grade_scores:
        typer.echo(
            "Trace graders: "
            + ", ".join(
                f"{name}={score:.3f}" for name, score in report.trace_grade_scores.items()
            )
        )
    console.print(
        f"\n[bold green]Harness evals complete[/bold green] "
        f"({report.passed_cases}/{report.total_cases} passing, score={report.score:.3f})"
    )
    if report.dimension_scores:
        console.print(
            "[dim]Dimensions:[/dim] "
            + ", ".join(
                f"{name}={score:.3f}" for name, score in report.dimension_scores.items()
            )
        )
    if report.trace_grade_scores:
        console.print(
            "[dim]Trace graders:[/dim] "
            + ", ".join(
                f"{name}={score:.3f}" for name, score in report.trace_grade_scores.items()
            )
        )
    console.print(f"[dim]Report: {output}[/dim]")
    console.print(f"[dim]Traces: {traces_dir}[/dim]")
    if report.passed_cases != report.total_cases:
        raise typer.Exit(1)


@app.command()
def benchmark(
    models: Optional[str] = typer.Option(
        None, "--models", "-m",
        help="Comma-separated models (e.g. 'ollama:qwen3.5:9b,openai:gpt-5.4-mini')",
    ),
    tiers: Optional[str] = typer.Option(
        None, "--tiers", "-t",
        help="Tier filter: 1,2,3,4 or comma-separated",
    ),
    output: Path = typer.Option(
        Path(".forgegod/benchmark_results.json"), "--output", "-o",
        help="Output JSON path",
    ),
    update_readme: bool = typer.Option(
        False, "--update-readme",
        help="Auto-insert leaderboard table into README.md",
    ),
    runs: int = typer.Option(1, "--runs", "-r", help="Runs per task (Pass@k)"),
    lang: str = typer.Option("auto", "--lang", "-l", help="Language: en, es, auto"),
):
    """Benchmark models - compare speed, quality, cost, and self-repair."""
    from forgegod.benchmark import BenchmarkRunner, detect_available_models
    from forgegod.config import load_config
    from forgegod.i18n import set_lang
    from forgegod.i18n import t as tr

    set_lang(lang)
    _print_banner(mini=True)
    config = load_config()

    # Parse models
    if models:
        model_list = [m.strip() for m in models.split(",") if m.strip()]
    else:
        console.print(f"[dim]{tr('bench_detecting')}[/dim]")
        model_list = detect_available_models(config)
        if not model_list:
            console.print(f"[red]{tr('bench_no_models')}[/red]")
            raise typer.Exit(1)
        console.print(f"  Found: {', '.join(model_list)}")

    # Parse tier filter
    tier_filter: set[int] | None = None
    if tiers:
        tier_filter = set()
        for t_val in tiers.split(","):
            t_val = t_val.strip().lower()
            if t_val in ("1", "trivial"):
                tier_filter.add(1)
            elif t_val in ("2", "easy"):
                tier_filter.add(2)
            elif t_val in ("3", "medium"):
                tier_filter.add(3)
            elif t_val in ("4", "hard"):
                tier_filter.add(4)

    console.print(f"\n[bold cyan]{tr('bench_running')}[/bold cyan]")

    async def _bench():
        runner = BenchmarkRunner(config, model_list)
        await runner.run_all(tier_filter=tier_filter, runs_per_task=runs)
        runner.print_results()
        runner.save_results(output)

        if update_readme:
            readme = Path("README.md")
            runner.update_readme(readme)

        console.print(f"\n[bold green]{tr('bench_done')}[/bold green]")

    asyncio.run(_bench())


if __name__ == "__main__":
    app()
