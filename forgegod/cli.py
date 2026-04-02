"""ForgeGod CLI — Typer entry point."""

from __future__ import annotations

import asyncio
import json
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


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    if version:
        console.print(f"ForgeGod v{__version__}")
        raise typer.Exit()


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project root directory"),
):
    """Initialize a ForgeGod project (creates .forgegod/)."""
    from forgegod.config import init_project

    project_dir = init_project(path)
    console.print(f"[green]Initialized ForgeGod at {project_dir}[/green]")
    console.print("Edit .forgegod/config.toml to configure models and budget.")


@app.command()
def run(
    task: str = typer.Argument(..., help="Task description"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override coder model"),
    review: bool = typer.Option(True, "--review/--no-review", help="Review output with frontier"),
):
    """Execute a single coding task."""
    from forgegod.config import load_config

    config = load_config()
    if model:
        config.models.coder = model
    config.review.always_review_run = review

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
):
    """Run 24/7 Ralph loop — autonomous coding from PRD."""
    from forgegod.config import load_config

    config = load_config()
    if workers > 1:
        config.loop.parallel_workers = workers
    if max_iterations is not None:
        config.loop.max_iterations = max_iterations

    if not prd.exists():
        console.print(f"[red]PRD not found at {prd}[/red]")
        console.print("Create one with: forgegod plan <task>")
        raise typer.Exit(1)

    async def _loop():
        from forgegod.loop import RalphLoop
        from forgegod.router import ModelRouter

        router = ModelRouter(config)
        ralph = RalphLoop.from_prd_file(prd, config, router=router)

        console.print(Panel("[bold green]ForgeGod Loop Started[/bold green]\nPress Ctrl+C to stop."))
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
):
    """Generate a PRD (task decomposition) from a description."""
    from forgegod.config import load_config

    config = load_config()

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


if __name__ == "__main__":
    app()
