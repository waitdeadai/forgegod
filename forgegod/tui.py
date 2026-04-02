"""ForgeGod TUI — Rich-based terminal dashboard."""

from __future__ import annotations

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from forgegod.models import BudgetMode, BudgetStatus, LoopState, LoopStatus


console = Console()


def render_status(
    loop_state: LoopState | None = None,
    budget: BudgetStatus | None = None,
    model_breakdown: dict[str, dict] | None = None,
):
    """Render a status dashboard to the terminal."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    # Header
    layout["header"].update(
        Panel(
            Text("ForgeGod", style="bold green", justify="center"),
            subtitle="Multi-model autonomous coding engine",
            style="green",
        )
    )

    # Left: Loop status
    if loop_state:
        layout["left"].update(_loop_panel(loop_state))
    else:
        layout["left"].update(Panel("No loop running", title="Loop"))

    # Right: Budget + models
    right_layout = Layout()
    right_layout.split_column(
        Layout(name="budget", ratio=1),
        Layout(name="models", ratio=1),
    )
    right_layout["budget"].update(
        _budget_panel(budget) if budget else Panel("No budget data", title="Budget")
    )
    right_layout["models"].update(
        _model_panel(model_breakdown) if model_breakdown else Panel("No model data", title="Models")
    )
    layout["right"].update(right_layout)

    console.print(layout)


def render_cost_table(budget: BudgetStatus, breakdown: dict[str, dict]):
    """Render cost breakdown table."""
    # Budget summary
    mode_color = {
        BudgetMode.NORMAL: "green",
        BudgetMode.THROTTLE: "yellow",
        BudgetMode.LOCAL_ONLY: "cyan",
        BudgetMode.HALT: "red",
    }.get(budget.mode, "white")

    console.print(f"\n  Mode: [{mode_color}]{budget.mode.value}[/]")
    console.print(f"  Today: ${budget.spent_today_usd:.4f} / ${budget.daily_limit_usd:.2f}")
    console.print(f"  Remaining: ${budget.remaining_today_usd:.4f}")
    console.print(f"  Total all-time: ${budget.spent_total_usd:.4f}")
    console.print(f"  Calls today: {budget.calls_today}")

    # Model breakdown
    if breakdown:
        table = Table(title="\nModel Breakdown (Today)")
        table.add_column("Model", style="cyan")
        table.add_column("Calls", justify="right")
        table.add_column("Cost", justify="right", style="green")

        for model, data in sorted(breakdown.items(), key=lambda x: x[1].get("cost", 0), reverse=True):
            table.add_row(model, str(data.get("calls", 0)), f"${data.get('cost', 0):.4f}")

        console.print(table)
    else:
        console.print("\n  No model usage today.")


def _loop_panel(state: LoopState) -> Panel:
    """Build loop status panel."""
    status_color = {
        LoopStatus.RUNNING: "green",
        LoopStatus.PAUSED: "yellow",
        LoopStatus.KILLED: "red",
        LoopStatus.IDLE: "dim",
    }.get(state.status, "white")

    lines = [
        f"Status: [{status_color}]{state.status.value}[/]",
        f"Current story: {state.current_story_id or 'none'}",
        f"Completed: {state.stories_completed}",
        f"Failed: {state.stories_failed}",
        f"Iterations: {state.total_iterations}",
        f"Context rotations: {state.context_rotations}",
        f"Cost: ${state.total_cost_usd:.4f}",
    ]
    if state.started_at:
        lines.append(f"Started: {state.started_at[:19]}")
    if state.last_tick_at:
        lines.append(f"Last tick: {state.last_tick_at[:19]}")

    return Panel("\n".join(lines), title="Ralph Loop", border_style=status_color)


def _budget_panel(budget: BudgetStatus) -> Panel:
    """Build budget panel."""
    mode_color = {
        BudgetMode.NORMAL: "green",
        BudgetMode.THROTTLE: "yellow",
        BudgetMode.LOCAL_ONLY: "cyan",
        BudgetMode.HALT: "red",
    }.get(budget.mode, "white")

    pct = (budget.spent_today_usd / budget.daily_limit_usd * 100) if budget.daily_limit_usd > 0 else 0
    bar_width = 20
    filled = int(pct / 100 * bar_width)
    bar = f"[green]{'=' * filled}[/][dim]{'-' * (bar_width - filled)}[/]"

    lines = [
        f"Mode: [{mode_color}]{budget.mode.value}[/]",
        f"Today: ${budget.spent_today_usd:.4f} / ${budget.daily_limit_usd:.2f}",
        f"[{bar}] {pct:.0f}%",
        f"Calls: {budget.calls_today}",
    ]
    return Panel("\n".join(lines), title="Budget", border_style=mode_color)


def _model_panel(breakdown: dict[str, dict]) -> Panel:
    """Build model usage panel."""
    if not breakdown:
        return Panel("No usage today", title="Models")

    lines = []
    for model, data in sorted(breakdown.items(), key=lambda x: x[1].get("cost", 0), reverse=True):
        calls = data.get("calls", 0)
        cost = data.get("cost", 0)
        lines.append(f"  {model}: {calls} calls, ${cost:.4f}")

    return Panel("\n".join(lines), title="Models")
