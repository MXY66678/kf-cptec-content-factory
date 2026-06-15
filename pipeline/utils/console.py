"""Rich Console — Beautiful terminal output for the pipeline CLI.

Uses Textualize/rich and tqdm for progress visualization.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any, Optional

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# Global rich console
console = Console()

# Pipeline stage colors
STAGE_COLORS: dict[str, str] = {
    "PENDING": "dim",
    "ingest": "cyan",
    "M1": "yellow",
    "M2": "blue",
    "M3": "magenta",
    "M4": "green",
    "assembly": "white",
    "ASSEMBLED": "bright_green",
    "QA_HOLD": "bright_yellow",
    "PUBLISH_READY": "bright_blue",
    "PUBLISHED": "bright_green",
    "FAILED": "bright_red",
}


def print_header() -> None:
    """Print the KF CPTEC banner."""
    title = """
╔═══════════════════════════════════════════════════════════════╗
║           KF CPTEC Multi-AI Content Factory v2.0              ║
║     DeepSeek → GPT → Claude → YouTube → Assembly Pipeline     ║
╚═══════════════════════════════════════════════════════════════╝
"""
    console.print(title, style="bold cyan")


def print_sku_header(sku_id: str) -> None:
    """Print a per-SKU processing header."""
    console.rule(f"[bold]SKU: {sku_id}[/bold]", style="blue")


def print_stage_status(stage: str, status: str, detail: str = "") -> None:
    """Print a stage status line with color coding.

    Args:
        stage: Pipeline stage name.
        status: 'started', 'completed', 'failed', 'retry'.
        detail: Optional detail message.
    """
    color = STAGE_COLORS.get(stage, "white")
    icon = {
        "started": "▶",
        "completed": "✓",
        "failed": "✗",
        "retry": "⟳",
        "skipped": "○",
    }.get(status, "•")

    msg = f"  {icon} [bold {color}]{stage:10s}[/] {status}"
    if detail:
        msg += f"  — {detail}"
    console.print(msg)


def make_progress_bar(desc: str = "Processing", total: int = 1):
    """Create a tqdm-style rich progress bar.

    Returns:
        A (Progress, task_id) tuple for updating.
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )
    task_id = progress.add_task(desc, total=total)
    return progress, task_id


def print_results_table(
    sku_id: str,
    sections: int,
    clusters: int,
    coverage_pct: float,
    videos_filled: int,
    videos_total: int,
    state: str,
) -> None:
    """Print a results summary table for a SKU."""
    table = Table(
        title=f"[bold]Results: {sku_id}[/bold]",
        box=box.ROUNDED,
        border_style="blue",
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Blog Sections", str(sections))
    table.add_row("Keyword Clusters", str(clusters))
    table.add_row(
        "Keyword Coverage",
        f"{coverage_pct:.1%} {'✓' if coverage_pct >= 0.9 else '✗'}",
    )
    table.add_row("Video Slots", f"{videos_filled}/{videos_total} filled")
    state_style = STAGE_COLORS.get(state, "white")
    table.add_row("Pipeline State", f"[{state_style}]{state}[/{state_style}]")

    console.print(table)


def print_batch_summary(
    total: int,
    succeeded: int,
    failed: int,
    elapsed_seconds: float,
) -> None:
    """Print a batch execution summary."""
    table = Table(
        title="[bold]Batch Summary[/bold]",
        box=box.ROUNDED,
        border_style="green",
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total SKUs", str(total))
    table.add_row("Succeeded", f"[green]{succeeded}[/green]")
    table.add_row("Failed", f"[red]{failed}[/red]")
    table.add_row("Elapsed", f"{elapsed_seconds:.1f}s")
    table.add_row("Throughput", f"{total / max(elapsed_seconds, 1):.2f} SKU/s")

    console.print(table)


def print_validation_errors(errors: list[str]) -> None:
    """Print validation errors."""
    if not errors:
        return
    console.print("\n[bold red]Validation Errors:[/bold red]")
    for e in errors:
        console.print(f"  • [red]{e}[/red]")


def print_api_config() -> None:
    """Print which APIs are configured."""
    from config import (
        DEEPSEEK_API_KEY,
        OPENAI_API_KEY,
        ANTHROPIC_API_KEY,
        YOUTUBE_API_KEY,
    )

    table = Table(box=box.SIMPLE, border_style="dim")
    table.add_column("Service", style="bold")
    table.add_column("Status", style="bold")

    for name, key, label in [
        ("DeepSeek", DEEPSEEK_API_KEY, "M1 Keyword Clustering"),
        ("OpenAI GPT", OPENAI_API_KEY, "M2 Feature/Listing"),
        ("Anthropic Claude", ANTHROPIC_API_KEY, "M3 Blog Structure"),
        ("YouTube Data", YOUTUBE_API_KEY, "M4 Video Retrieval"),
    ]:
        status = "✓ Configured" if key else "✗ Not set"
        style = "green" if key else "red"
        table.add_row(
            Text(name, style=style),
            f"[{style}]{status}[/{style}] ({label})",
        )

    console.print(table)
