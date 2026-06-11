from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from memd.contracts import AnalysisReport, CategorizedMemory, Insight, MemoryCategory, MemoryRecord


def report_to_dict(report: AnalysisReport) -> dict[str, object]:
    records_by_id = {record.id: record for record in report.memories}
    categories_by_id = {category.memoryId: category for category in report.categories}
    return {
        "metrics": {
            "totalMemories": report.metrics.totalMemories,
            "duplicateCount": report.metrics.duplicateCount,
            "duplicatePercentage": report.metrics.duplicatePercentage,
            "compressionOpportunity": report.metrics.compressionOpportunity,
            "compressionReasons": list(report.metrics.compressionReasons),
            "categoryBreakdown": {
                category.value: report.metrics.categoryBreakdown.get(category, 0)
                for category in MemoryCategory
            },
        },
        "clusters": [
            {
                "clusterId": cluster.clusterId,
                "members": list(cluster.members),
                "averageSimilarity": cluster.averageSimilarity,
                "sharedTerms": list(cluster.sharedTerms),
                "reasons": list(cluster.reasons),
                "records": [
                    cluster_record(member, records_by_id, categories_by_id)
                    for member in cluster.members
                ],
            }
            for cluster in report.clusters
        ],
        "categories": [
            {
                "memoryId": category.memoryId,
                "content": records_by_id[category.memoryId].content
                if category.memoryId in records_by_id
                else "",
                "category": category.category.value,
                "confidence": category.confidence,
                "reason": category.reason,
                "matchedSignals": list(category.matchedSignals),
            }
            for category in report.categories
        ],
        "validation": report.validation,
        "insights": [insight_to_dict(insight) for insight in report.insights],
    }


def render_terminal(report: AnalysisReport, console: Console | None = None) -> None:
    console = console or Console()
    metrics = report.metrics

    console.print("[bold]Mem-D Analysis[/bold]")
    console.print(f"Analyzed: [bold]{metrics.totalMemories}[/bold] memories")
    console.print(f"Duplicate Clusters: [bold]{len(report.clusters)}[/bold]")
    console.print(f"Duplicate Memories: [bold]{metrics.duplicateCount}[/bold]")
    console.print(f"Compression Opportunity: [bold]{metrics.compressionOpportunity}%[/bold]")
    for reason in metrics.compressionReasons:
        console.print(f"- {reason}")

    if report.insights:
        insight_table = Table(title="Ranked Insights")
        insight_table.add_column("Severity")
        insight_table.add_column("Finding")
        insight_table.add_column("Recommended Action")
        for insight in report.insights[:5]:
            insight_table.add_row(
                insight.severity.value,
                insight.title,
                insight.recommendedAction,
            )
        console.print(insight_table)

    category_table = Table(title="Category Distribution")
    category_table.add_column("Category")
    category_table.add_column("Count", justify="right")
    for category in MemoryCategory:
        category_table.add_row(category.value, str(metrics.categoryBreakdown.get(category, 0)))
    console.print(category_table)

    if report.clusters:
        cluster_table = Table(title="Duplicate Clusters")
        cluster_table.add_column("Cluster")
        cluster_table.add_column("Members")
        cluster_table.add_column("Why grouped")
        cluster_table.add_column("Avg Similarity", justify="right")
        for cluster in report.clusters[:10]:
            cluster_table.add_row(
                cluster.clusterId,
                ", ".join(cluster.members),
                "; ".join(cluster.reasons[:2]),
                f"{cluster.averageSimilarity:.2f}",
            )
        console.print(cluster_table)

    category_quality = report.validation.get("categoryQuality", {})
    unknown_count = category_quality.get("unknownCount")
    unknown_percentage = category_quality.get("unknownPercentage")
    if unknown_count is not None:
        console.print(
            f"Unknown categories: [bold]{unknown_count}[/bold] "
            f"({unknown_percentage}%); inspect JSON/Markdown validation samples."
        )


def render_json(report: AnalysisReport) -> str:
    return json.dumps(report_to_dict(report), indent=2)


def render_markdown(report: AnalysisReport) -> str:
    metrics = report.metrics
    lines = [
        "# Mem-D Analysis Report",
        "",
        f"- Total memories: {metrics.totalMemories}",
        f"- Duplicate clusters: {len(report.clusters)}",
        f"- Duplicate memories: {metrics.duplicateCount}",
        f"- Compression opportunity: {metrics.compressionOpportunity}%",
        "",
        "## Ranked Insights",
        "",
    ]
    if not report.insights:
        lines.append("No recommendations generated.")
    else:
        for insight in report.insights:
            lines.extend(
                [
                    f"### {insight.title}",
                    "",
                    f"- Severity: {insight.severity.value}",
                    f"- Confidence: {insight.confidence}",
                    f"- Estimated impact: {insight.estimatedImpact}",
                    f"- Recommended action: {insight.recommendedAction}",
                    f"- Explanation: {insight.explanation}",
                    "- Supporting evidence:",
                    *[f"  - {evidence}" for evidence in insight.supportingEvidence],
                    "",
                ]
            )
    lines.extend(
        [
        "## Compression Explanation",
        "",
        *[f"- {reason}" for reason in metrics.compressionReasons],
        "",
        "## Category Distribution",
        "",
        "| Category | Count |",
        "| --- | ---: |",
        ]
    )
    for category in MemoryCategory:
        lines.append(f"| {category.value} | {metrics.categoryBreakdown.get(category, 0)} |")

    lines.extend(["", "## Duplicate Clusters", ""])
    if not report.clusters:
        lines.append("No duplicate clusters detected.")
    else:
        records_by_id = {record.id: record for record in report.memories}
        categories_by_id = {category.memoryId: category for category in report.categories}
        for cluster in report.clusters:
            lines.extend(
                [
                    f"### {cluster.clusterId}",
                    "",
                    f"- Average similarity: {cluster.averageSimilarity:.2f}",
                    f"- Members: {', '.join(cluster.members)}",
                    f"- Shared terms: {', '.join(cluster.sharedTerms) or 'none detected'}",
                    f"- Why grouped: {'; '.join(cluster.reasons) or 'embedding similarity'}",
                    "",
                    "| ID | Category | Content |",
                    "| --- | --- | --- |",
                    *[
                        markdown_cluster_row(member, records_by_id, categories_by_id)
                        for member in cluster.members
                    ],
                    "",
                ]
            )
    lines.extend(render_validation_markdown(report))
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def cluster_record(
    memory_id: str,
    records_by_id: dict[str, MemoryRecord],
    categories_by_id: dict[str, CategorizedMemory],
) -> dict[str, object]:
    record = records_by_id.get(memory_id)
    category = categories_by_id.get(memory_id)
    return {
        "id": memory_id,
        "content": record.content if record else "",
        "category": category.category.value if category else "",
        "categoryReason": category.reason if category else "",
    }


def insight_to_dict(insight: Insight) -> dict[str, object]:
    return {
        "id": insight.id,
        "title": insight.title,
        "severity": insight.severity.value,
        "explanation": insight.explanation,
        "supportingEvidence": list(insight.supportingEvidence),
        "confidence": insight.confidence,
        "estimatedImpact": insight.estimatedImpact,
        "recommendedAction": insight.recommendedAction,
    }


def markdown_cluster_row(
    memory_id: str,
    records_by_id: dict[str, MemoryRecord],
    categories_by_id: dict[str, CategorizedMemory],
) -> str:
    record = records_by_id.get(memory_id)
    category = categories_by_id.get(memory_id)
    category_name = category.category.value if category else ""
    content = escape_markdown_table(record.content if record else "")
    return f"| `{memory_id}` | {category_name} | {content} |"


def render_validation_markdown(report: AnalysisReport) -> list[str]:
    category_quality = report.validation.get("categoryQuality", {})
    cluster_quality = report.validation.get("clusterQuality", {})
    compression = report.validation.get("compressionDrivers", {})
    lines = ["", "## Validation Notes", ""]

    if category_quality:
        lines.extend(
            [
                f"- Unknown count: {category_quality.get('unknownCount', 0)}",
                f"- Unknown percentage: {category_quality.get('unknownPercentage', 0)}%",
            ]
        )
        interpretation = category_quality.get("interpretation", {})
        if isinstance(interpretation, dict):
            lines.append(f"- Interpretation: {interpretation.get('summary', '')}")
        lines.extend(["", "### Unknown Samples", ""])
        for sample in category_quality.get("unknownSamples", [])[:10]:
            if isinstance(sample, dict):
                lines.append(
                    f"- `{sample.get('memoryId')}`: {sample.get('content')} "
                    f"({sample.get('reason')})"
                )

    if cluster_quality:
        false_positive_candidates = cluster_quality.get("possibleFalsePositiveClusters", [])
        lines.extend(
            [
                "",
                "### Cluster Quality",
                "",
                f"- Possible false-positive candidates: {len(false_positive_candidates)}",
            ]
        )

    if compression:
        lines.extend(["", "### Compression Drivers", ""])
        for driver in compression.get("largestClusterDrivers", [])[:5]:
            if isinstance(driver, dict):
                lines.append(
                    f"- `{driver.get('clusterId')}` size {driver.get('size')}: "
                    f"{driver.get('removableRecords')} removable records"
                )
    return lines


def escape_markdown_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
