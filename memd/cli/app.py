from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from memd import __version__
from memd.parser.loaders import ParserError
from memd.pipeline import analyze_file
from memd.reports import render_json, render_markdown, render_terminal, write_report

app = typer.Typer(help="Analyze agent memory exports locally.")
console = Console()


class OutputFormat(StrEnum):
    terminal = "terminal"
    json = "json"
    markdown = "markdown"


def version_callback(value: bool) -> None:
    if value:
        console.print(f"memd {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    _ = version


@app.command()
def analyze(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.terminal,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write report to this path."),
    ] = None,
    threshold: Annotated[
        float,
        typer.Option("--threshold", min=0.0, max=1.0, help="Duplicate similarity threshold."),
    ] = 0.85,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Optional local sentence-transformers model name. Falls back if unavailable.",
        ),
    ] = None,
) -> None:
    """Analyze a JSON, CSV, or TXT memory export."""
    try:
        report = analyze_file(file, threshold=threshold, model_name=model)
    except ParserError as exc:
        console.print(f"[red]Input error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]Analysis error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if output_format == OutputFormat.json:
        content = render_json(report)
        _emit_or_write(content, output)
    elif output_format == OutputFormat.markdown:
        content = render_markdown(report)
        _emit_or_write(content, output)
    else:
        if output:
            write_report(output, render_markdown(report))
        render_terminal(report, console=console)


def _emit_or_write(content: str, output: Path | None) -> None:
    if output:
        write_report(output, content)
        console.print(f"Wrote report to {output}")
    else:
        console.print(content)
