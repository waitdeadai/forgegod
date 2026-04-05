"""ForgeGod CLI — Typer entry point."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from forgegod import __version__

app = typer.Typer(
    name="forgegod",
    help="Multi-model autonomous coding engine. Local + Cloud. 24/7.",
    no_args_is_help=True,
)
console = Console()

# ── Mascot — The One-Eyed Triangle ──
_VER = __version__


def _build_banner():
    """Build the full mascot banner using Rich Text (avoids markup escaping)."""
    from rich.text import Text

    t = Text()
    t.append("         ___\n", style="yellow")
    t.append("        (   )\n", style="yellow")
    t.append("         ---\n", style="yellow")
    t.append("          .\n", style="cyan")
    t.append("         / \\\n", style="cyan")
    t.append("        / ", style="cyan")
    t.append("1", style="bold white")
    t.append(" \\\n", style="cyan")
    t.append("       /     \\\n", style="cyan")
    t.append("      /       \\\n", style="cyan")
    t.append("     /_________\\\n", style="cyan")
    t.append("\n")
    t.append("   F O R G E G O D", style="bold cyan")
    t.append(f"  v{_VER}\n", style="dim")
    t.append("   Autonomous coding engine\n", style="dim")
    return t


def _print_banner(mini: bool = False):
    """Print the ForgeGod mascot banner."""
    if mini:
        console.print(f"[cyan]^[/cyan] [bold cyan]ForgeGod[/bold cyan] [dim]v{_VER}[/dim]")
    else:
        console.print(_build_banner())


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    if version:
        _print_banner()
        raise typer.Exit()


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project root directory"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Skip wizard, auto-detect only"),
    lang: str = typer.Option("auto", "--lang", "-l", help="Language: en, es, auto"),
):
    """Initialize a ForgeGod project — interactive wizard or quick auto-detect."""
    from forgegod.i18n import set_lang

    set_lang(lang)

    if not quick:
        # Interactive wizard (default for new users)
        from forgegod.onboarding import OnboardingWizard

        wizard = OnboardingWizard(project_path=path, lang=lang)
        wizard.run()
        return

    # Quick mode: silent auto-detect (original behavior)
    import os

    from forgegod.config import init_project

    _print_banner()
    console.print("[bold]Initializing project...[/bold]")
    console.print()

    providers: list[str] = []
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
        console.print("  [dim]-[/dim] Ollama not detected (optional — install for $0 local mode)")

    if not providers and not ollama_available:
        console.print()
        console.print("[yellow]No API keys or Ollama found.[/yellow]")
        console.print("Set at least one:")
        console.print("  export OPENAI_API_KEY=sk-...")
        console.print("  export ANTHROPIC_API_KEY=sk-ant-...")
        console.print("  or: ollama serve  (for free local mode)")
        console.print()

    project_dir = init_project(path)

    console.print()
    console.print(f"[green]Initialized at {project_dir}[/green]")
    console.print()
    console.print("[bold]Quick start:[/bold]")
    console.print('  forgegod run "Describe your task here"')
    console.print()
    console.print("[dim]Config: .forgegod/config.toml | Memory: .forgegod/memory.db[/dim]")
    if ollama_available and not providers:
        console.print("[dim]Running in local-only mode ($0). Add API keys for cloud models.[/dim]")


@app.command()
def run(
    task: str = typer.Argument(..., help="Task description"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override coder model"),
    review: bool = typer.Option(True, "--review/--no-review", help="Review output with frontier"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    terse: bool = typer.Option(
        False, "--terse", help="Caveman mode — terse prompts"
    ),
):
    """Execute a single coding task."""
    from forgegod.config import load_config

    _print_banner(mini=True)
    config = load_config()
    log_fmt = "%(asctime)s %(levelname)s %(name)s — %(message)s"
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format=log_fmt)
    if model:
        config.models.coder = model
    config.review.always_review_run = review
    if terse:
        config.terse.enabled = True
        console.print("[dim]Caveman mode enabled — ultra-terse prompts[/dim]")

    async def _run():
        from forgegod.agent import Agent
        from forgegod.router import ModelRouter

        router = ModelRouter(config)
        agent = Agent(router=router, config=config)
        result = await agent.run(task)

        if result.success:
            console.print(Panel(f"[green]Task completed[/green]\n{result.output[:500]}"))
            if result.files_modified:
                console.print(f"Files modified: {', '.join(result.files_modified)}")
            console.print(
                f"Cost: ${result.total_usage.cost_usd:.4f} | "
                f"Tokens: {result.total_usage.input_tokens + result.total_usage.output_tokens:,}"
            )
        else:
            console.print(f"[red]Task failed:[/red] {result.error}")

    asyncio.run(_run())


@app.command()
def loop(
    prd: Path = typer.Option(
        Path(".forgegod/prd.json"), "--prd", "-p", help="PRD file path"
    ),
    workers: int = typer.Option(1, "--workers", "-w", help="Parallel workers"),
    max_iterations: Optional[int] = typer.Option(None, "--max", help="Max iterations"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Print story order, don't run"
    ),
    terse: bool = typer.Option(
        False, "--terse", help="Caveman mode — terse prompts"
    ),
):
    """Run 24/7 Ralph loop — autonomous coding from PRD."""
    from forgegod.config import load_config

    config = load_config()
    if terse:
        config.terse.enabled = True
    if workers > 1:
        config.loop.parallel_workers = workers
    if max_iterations is not None:
        config.loop.max_iterations = max_iterations

    if not prd.exists():
        console.print(f"[red]PRD not found at {prd}[/red]")
        console.print("Create one with: forgegod plan <task>")
        raise typer.Exit(1)

    # Configure logging to both console and file
    log_file = config.project_dir / "logs" / "loop.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(str(log_file), mode="a"),
        ],
    )

    async def _loop():
        from forgegod.loop import RalphLoop
        from forgegod.router import ModelRouter

        router = ModelRouter(config)
        ralph = RalphLoop.from_prd_file(prd, config, router=router)

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

    asyncio.run(_loop())


@app.command()
def plan(
    task: str = typer.Argument(..., help="High-level project description"),
    output: Path = typer.Option(
        Path(".forgegod/prd.json"), "--output", "-o", help="Output PRD path"
    ),
    terse: bool = typer.Option(
        False, "--terse", help="Caveman mode — terse prompts"
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
        console.print(f"[green]PRD generated with {len(prd.stories)} stories → {output}[/green]")
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
    """Research-grounded planning — web research + adversarial debate.

    The only coding agent that researches before it codes.
    Phase 1: RECON — searches the web for best libraries, CVEs, patterns.
    Phase 2: ARCHITECT — generates PRD using research findings.
    Phase 3: ADVERSARY — hostile critic debates the plan until score >= min_score.
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
            "[cyan]RECON MODE[/cyan] — Research-grounded planning\n"
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
    table.add_row("Current Story", state.current_story_id or "—")
    table.add_row("Completed", str(state.stories_completed))
    table.add_row("Failed", str(state.stories_failed))
    table.add_row("Iterations", str(state.total_iterations))
    table.add_row("Cost", f"${state.total_cost_usd:.4f}")
    table.add_row("Context Rotations", str(state.context_rotations))
    table.add_row("Started", state.started_at or "—")

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
def benchmark(
    models: Optional[str] = typer.Option(
        None, "--models", "-m",
        help="Comma-separated models (e.g. 'ollama:qwen3.5:9b,openai:gpt-4o-mini')",
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
    """Benchmark models — compare speed, quality, cost, and self-repair."""
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
