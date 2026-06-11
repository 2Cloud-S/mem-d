from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from memd import __version__
from memd.contracts import PolicyProfile
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD
from memd.evaluation import (
    ClusterEvaluation,
    evaluate_dataset,
    evaluation_metrics_dict,
    render_evaluation_json,
    render_evaluation_markdown,
)
from memd.insights import generate_evaluation_insights
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
    ] = DEFAULT_SIMILARITY_THRESHOLD,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Optional local sentence-transformers model name. Falls back if unavailable.",
        ),
    ] = None,
    policy: Annotated[
        PolicyProfile,
        typer.Option("--policy", help="Governance policy profile."),
    ] = PolicyProfile.BALANCED,
) -> None:
    """Analyze a JSON, CSV, or TXT memory export."""
    try:
        report = analyze_file(
            file,
            threshold=threshold,
            model_name=model,
            policy_profile=policy,
        )
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


@app.command("evaluate-clusters")
def evaluate_clusters(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.terminal,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write evaluation report to this path."),
    ] = None,
    threshold: Annotated[
        float,
        typer.Option("--threshold", min=0.0, max=1.0, help="Duplicate similarity threshold."),
    ] = DEFAULT_SIMILARITY_THRESHOLD,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Optional local sentence-transformers model name. Falls back if unavailable.",
        ),
    ] = None,
) -> None:
    """Evaluate duplicate clustering against a labelled validation dataset."""
    evaluation = evaluate_dataset(file, threshold=threshold, model_name=model)

    if output_format == OutputFormat.json:
        _emit_or_write(render_evaluation_json(evaluation), output)
    elif output_format == OutputFormat.markdown:
        _emit_or_write(render_evaluation_markdown(evaluation), output)
    else:
        render_evaluation_terminal(evaluation)


def render_evaluation_terminal(evaluation: ClusterEvaluation) -> None:
    metrics = {
        "Precision": evaluation.precision,
        "Recall": evaluation.recall,
        "F1": evaluation.f1,
        "Cluster purity": evaluation.clusterPurity,
        "Cluster coverage": evaluation.clusterCoverage,
    }
    console.print(f"[bold]Clustering Evaluation:[/bold] {evaluation.datasetName}")
    console.print(f"Threshold: [bold]{evaluation.threshold}[/bold]")
    for label, value in metrics.items():
        console.print(f"{label}: [bold]{value}[/bold]")
    console.print(f"False positives: [bold]{evaluation.falsePositives}[/bold]")
    console.print(f"False negatives: [bold]{evaluation.falseNegatives}[/bold]")
    insights = generate_evaluation_insights(evaluation_metrics_dict(evaluation))
    if insights:
        insight_table = Table(title="Evaluation Insights")
        insight_table.add_column("Severity")
        insight_table.add_column("Finding")
        insight_table.add_column("Recommended Action")
        for insight in insights:
            insight_table.add_row(
                insight.severity.value,
                insight.title,
                insight.recommendedAction,
            )
        console.print(insight_table)
