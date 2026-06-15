"""Typer-based CLI application — modern replacement for argparse.

Provides: `kf-pipeline run`, `kf-pipeline sample`, `kf-pipeline status`, `kf-pipeline check`
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import typer
from loguru import logger as log
from rich import print as rprint
from rich.prompt import Confirm, Prompt

from pipeline.core.orchestrator import Orchestrator
from pipeline.utils.console import (
    console,
    print_api_config,
    print_batch_summary,
    print_header,
    print_sku_header,
    print_stage_status,
    make_progress_bar,
    print_results_table,
)

app = typer.Typer(
    name="kf-content-factory",
    help="KF CPTEC Multi-AI Content Factory Pipeline",
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        rprint("[bold cyan]KF CPTEC Content Factory v2.0.0[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """KF CPTEC Multi-AI Content Factory — automated content pipeline."""
    pass


@app.command()
def run(
    manifest: str = typer.Option(
        "data/sample/sku_manifest.csv",
        "--manifest", "-m",
        help="Path to SKU manifest CSV",
    ),
    keywords: str = typer.Option(
        "data/sample/keywords.csv",
        "--keywords", "-k",
        help="Path to keyword table CSV",
    ),
    specs: str = typer.Option(
        "data/sample/specs.json",
        "--specs", "-s",
        help="Path to specs JSON file",
    ),
    sku_id: Optional[str] = typer.Option(
        None, "--sku", "-u",
        help="Process a single SKU only",
    ),
    workers: int = typer.Option(
        3, "--workers", "-w",
        help="Number of parallel workers",
        min=1, max=10,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Dry-run mode (mock outputs, no API calls)",
    ),
    live: bool = typer.Option(
        False, "--live", "-l",
        help="Use real API calls (requires .env API keys)",
    ),
) -> None:
    """Execute the full content factory pipeline for one or more SKUs."""
    print_header()

    if dry_run:
        log.info("Dry-run mode — generating mock outputs")
        from main import run_sample_pipeline
        run_sample_pipeline(dry_run=True)
        return

    # Load inputs
    log.info("Loading SKU manifest: {}", manifest)
    sku_rows = _load_csv(manifest)
    log.info("Loading keyword table: {}", keywords)
    keyword_csv = _load_csv_text(keywords)
    log.info("Loading specs: {}", specs)
    specs_data = _load_json(specs)

    # Filter single SKU
    if sku_id:
        sku_rows = [r for r in sku_rows if r.get("sku_id") == sku_id]
        if not sku_rows:
            rprint(f"[red]SKU '{sku_id}' not found in manifest[/red]")
            raise typer.Exit(code=1)

    # Check API config
    print_api_config()
    if not all([
        cfg.DEEPSEEK_API_KEY,
        cfg.OPENAI_API_KEY,
        cfg.ANTHROPIC_API_KEY,
        cfg.YOUTUBE_API_KEY,
    ]) and live:
        rprint("[yellow]Warning: Some API keys are missing. Set them in .env[/yellow]")
        proceed = Confirm.ask("Continue anyway?", default=False)
        if not proceed:
            raise typer.Exit()

    # Build specs dict
    import config as cfg
    specs_keyed: dict[str, dict[str, Any]] = {}
    for row in sku_rows:
        key = row.get("sku_key", row["sku_id"])
        specs_keyed[key] = specs_data.get(key, {})

    # Run pipeline
    t0 = time.time()
    orchestrator = Orchestrator(max_workers=workers)

    if sku_id:
        row = sku_rows[0]
        print_sku_header(sku_id)
        try:
            result = orchestrator.process_single_sku(
                sku_id=sku_id,
                sku_csv_row=row,
                keyword_csv=keyword_csv,
                specs_json_data=specs_keyed.get(row.get("sku_key", sku_id), {}),
            )
            rprint(f"[green]✓ SKU {sku_id} processed successfully[/green]")
        except Exception as e:
            rprint(f"[red]✗ SKU {sku_id} failed: {e}[/red]")
            raise typer.Exit(code=1)
    else:
        rprint(f"[bold]Batch: {len(sku_rows)} SKUs, {workers} workers[/bold]")
        results = orchestrator.run_batch(sku_rows, keyword_csv, specs_keyed)
        elapsed = time.time() - t0
        print_batch_summary(
            total=len(sku_rows),
            succeeded=len(results),
            failed=len(sku_rows) - len(results),
            elapsed_seconds=elapsed,
        )


@app.command()
def sample(
    output: str = typer.Option(
        "output/samples",
        "--output", "-o",
        help="Output directory for sample data",
    ),
) -> None:
    """Generate sample data and run pipeline in mock mode."""
    print_header()
    rprint("[bold]Generating sample data and mock pipeline output...[/bold]")
    from main import run_sample_pipeline
    run_sample_pipeline(dry_run=False)


@app.command()
def status(
    sku_id: str = typer.Argument(
        ..., help="SKU ID to check status for",
    ),
) -> None:
    """Show pipeline status for a specific SKU."""
    import config as cfg
    state_path = cfg.OUTPUT_DIR / sku_id / "_state.json"

    if not state_path.exists():
        rprint(f"[red]No pipeline state found for SKU: {sku_id}[/red]")
        raise typer.Exit(code=1)

    with open(state_path) as f:
        state = json.load(f)

    rprint(f"[bold cyan]SKU: {sku_id}[/bold cyan]")
    rprint(f"  State: [bold]{state.get('state', 'UNKNOWN')}[/bold]")
    rprint(f"  Output: [blue]{state.get('output_dir', 'N/A')}[/blue]")


@app.command()
def check() -> None:
    """Check API configuration and environment setup."""
    print_header()
    print_api_config()

    import config as cfg
    rprint(f"\n[bold]Paths:[/bold]")
    rprint(f"  Project root: [blue]{cfg.PROJECT_ROOT}[/blue]")
    rprint(f"  Output dir: [blue]{cfg.OUTPUT_DIR}[/blue]")
    rprint(f"  Logs dir: [blue]{cfg.LOGS_DIR}[/blue]")
    rprint(f"  Config dir: [blue]{cfg.CONFIG_DIR}[/blue]")

    # Check category templates
    categories = cfg.list_categories()
    if categories:
        rprint(f"\n[bold]Category Templates:[/bold]")
        for cat in categories:
            rprint(f"  • [green]{cat}[/green]")
    else:
        rprint(f"\n[dim]No category templates found[/dim]")


@app.command()
def list_skus(
    manifest: str = typer.Option(
        "data/sample/sku_manifest.csv",
        "--manifest", "-m", help="Path to SKU manifest CSV",
    ),
) -> None:
    """List all SKUs in a manifest."""
    rows = _load_csv(manifest)
    from rich.table import Table
    table = Table(title=f"SKU Manifest: {manifest}")
    if rows:
        for col in rows[0].keys():
            table.add_column(col, style="cyan")
        for row in rows:
            table.add_row(*[str(v) for v in row.values()])
    console.print(table)


def _load_csv(path: str) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        rprint(f"[red]File not found: {p}[/red]")
        raise typer.Exit(code=1)
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_csv_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        rprint(f"[red]File not found: {p}[/red]")
        raise typer.Exit(code=1)
    with open(p, encoding="utf-8-sig") as f:
        return f.read()


def _load_json(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        rprint(f"[red]File not found: {p}[/red]")
        raise typer.Exit(code=1)
    with open(p) as f:
        return json.load(f)


if __name__ == "__main__":
    app()
