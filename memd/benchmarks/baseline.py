from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _format_category_distribution(categories: Mapping[str, int] | None) -> str:
    if not categories:
        return "_No category data._"
    lines = [
        "| Category | Count |",
        "| --- | ---: |",
    ]
    for label, count in sorted(categories.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {label} | {count} |")
    return "\n".join(lines)


def _format_lifecycle_distribution(lifecycle: Mapping[str, Any] | None) -> str:
    if not lifecycle:
        return "_No lifecycle data._"
    counts = lifecycle.get("lifecycleCounts")
    if not isinstance(counts, dict) or not counts:
        return "_No lifecycle assignments detected._"
    lines = [
        "| Lifecycle state | Count |",
        "| --- | ---: |",
    ]
    for state, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {state} | {count} |")
    confidence = lifecycle.get("lifecycleConfidence")
    if isinstance(confidence, (int, float)):
        lines.extend(["", f"Overall lifecycle confidence: {confidence}"])
    return "\n".join(lines)


def _format_evolution_signals(evolution: Mapping[str, Any] | None) -> str:
    if not evolution:
        return "_No evolution audit data._"
    lines = [
        f"- Total evolution signals: {evolution.get('totalEvolutionSignals', 0)}",
        f"- Contradictions: {evolution.get('contradictionCount', 0)}",
        f"- Preference changes: {evolution.get('preferenceChangeCount', 0)}",
        f"- Superseded memories: {evolution.get('supersededMemoryCount', 0)}",
        f"- Stale memory candidates: {evolution.get('staleMemoryCount', 0)}",
        f"- Status transitions: {evolution.get('statusTransitionCount', 0)}",
    ]
    confidence = evolution.get("evolutionConfidence")
    if isinstance(confidence, (int, float)):
        lines.append(f"- Evolution confidence: {confidence}")
    return "\n".join(lines)


def _format_insights_summary(insights: Sequence[Mapping[str, Any]] | None) -> str:
    if not insights:
        return "_No insights generated._"
    lines: list[str] = []
    for insight in insights[:10]:
        title = insight.get("title", "Insight")
        severity = insight.get("severity", "unknown")
        action = insight.get("recommendedAction", "")
        lines.append(f"- **{title}** ({severity}): {action}")
    if len(insights) > 10:
        lines.append(f"- _…and {len(insights) - 10} more insights in the analysis report._")
    return "\n".join(lines)


def render_baseline_markdown(
    *,
    dataset: str,
    input_path: str,
    cleaned_path: str,
    raw_audit: Mapping[str, Any] | None,
    cleaned_audit: Mapping[str, Any] | None,
    preprocess_report: Mapping[str, Any] | None,
    analysis: Mapping[str, Any] | None,
) -> str:
    """Render a benchmark baseline summary from existing Mem-D report payloads."""
    raw_dataset = _single_dataset(raw_audit)
    cleaned_dataset = _single_dataset(cleaned_audit)
    metrics = _analysis_metrics(analysis)
    validation = _analysis_validation(analysis)
    insights = analysis.get("insights") if isinstance(analysis, dict) else None

    meaningful_rate = _audit_rate(cleaned_dataset, "meaningfulMemoryRate")
    duplicate_rate = _audit_rate(cleaned_dataset, "duplicateRate")
    analyze_unknown_rate = _analysis_unknown_rate(metrics, cleaned_dataset)
    input_size = _input_size(raw_dataset, preprocess_report)
    category_breakdown = metrics.get("categoryBreakdown")
    if not isinstance(category_breakdown, dict) or not category_breakdown:
        category_breakdown = cleaned_dataset.get("categoryDistribution")

    lines = [
        f"# Benchmark Baseline: {dataset}",
        "",
        "Reproducible Mem-D benchmark summary. Generated from existing audit, preprocessing, "
        "and analysis reports — no additional metrics or intelligence layers.",
        "",
        "## Dataset",
        "",
        f"- Source: `{input_path}`",
        f"- Cleaned input: `{cleaned_path}`",
        f"- Benchmark stem: `{dataset}`",
        "",
        "## Input Size",
        "",
        _format_input_size(input_size, preprocess_report, metrics),
        "",
        "## Meaningful Memory Rate",
        "",
        _format_meaningful_rate(raw_dataset, cleaned_dataset, meaningful_rate),
        "",
        "## Unknown Rate",
        "",
        f"- Raw audit: {_audit_rate(raw_dataset, 'unknownRate')}%",
        f"- Cleaned audit: {_audit_rate(cleaned_dataset, 'unknownRate')}%",
        f"- Analyze pipeline (Unknown category): {analyze_unknown_rate}%",
        "",
        "## Duplicate Rate",
        "",
        _format_duplicate_rate(raw_dataset, cleaned_dataset, metrics, duplicate_rate),
        "",
        "## Compression Opportunity",
        "",
        _format_compression(metrics, duplicate_rate),
        "",
        "## Category Distribution",
        "",
        _format_category_distribution(
            category_breakdown if isinstance(category_breakdown, dict) else None
        ),
        "",
        "## Evolution Signals",
        "",
        _format_evolution_signals(
            validation.get("memoryEvolutionAudit")
            if isinstance(validation.get("memoryEvolutionAudit"), dict)
            else None
        ),
        "",
        "## Lifecycle Distribution",
        "",
        _format_lifecycle_distribution(
            validation.get("memoryLifecycle")
            if isinstance(validation.get("memoryLifecycle"), dict)
            else None
        ),
        "",
        "## Insights Summary",
        "",
        _format_insights_summary(insights if isinstance(insights, list) else None),
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def _single_dataset(audit_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if not audit_report:
        return {}
    datasets = audit_report.get("datasets")
    if isinstance(datasets, list) and datasets and isinstance(datasets[0], dict):
        return datasets[0]
    return {}


def _analysis_metrics(analysis: Mapping[str, Any] | None) -> dict[str, Any]:
    if not analysis:
        return {}
    metrics = analysis.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _analysis_validation(analysis: Mapping[str, Any] | None) -> dict[str, Any]:
    if not analysis:
        return {}
    validation = analysis.get("validation")
    return validation if isinstance(validation, dict) else {}


def _audit_rate(dataset: Mapping[str, Any], key: str) -> str:
    value = dataset.get(key)
    if value is None:
        return "n/a"
    return str(value)


def _analysis_unknown_rate(metrics: Mapping[str, Any], cleaned_dataset: Mapping[str, Any]) -> str:
    breakdown = metrics.get("categoryBreakdown")
    total = metrics.get("totalMemories")
    if isinstance(breakdown, dict) and isinstance(total, int) and total > 0:
        unknown = breakdown.get("Unknown", 0)
        if isinstance(unknown, int):
            return str(round((unknown / total) * 100, 2))
    return _audit_rate(cleaned_dataset, "unknownRate")


def _input_size(
    raw_dataset: Mapping[str, Any],
    preprocess_report: Mapping[str, Any] | None,
) -> dict[str, int | None]:
    original = None
    final = None
    if preprocess_report:
        original = preprocess_report.get("originalRecordCount")
        final = preprocess_report.get("finalRecordCount")
    if original is None:
        original = raw_dataset.get("totalRecords")
    return {"original": original, "final": final}


def _format_input_size(
    input_size: Mapping[str, int | None],
    preprocess_report: Mapping[str, Any] | None,
    metrics: Mapping[str, Any],
) -> str:
    original = input_size.get("original")
    final = input_size.get("final")
    analyzed = metrics.get("totalMemories")
    lines = []
    if original is not None:
        lines.append(f"- Raw records: {original}")
    if final is not None:
        lines.append(f"- Cleaned records: {final}")
    retention = (
        preprocess_report.get("retentionPercentage")
        if isinstance(preprocess_report, dict)
        else None
    )
    if retention is not None:
        lines.append(f"- Retention after preprocessing: {retention}%")
    if analyzed is not None:
        lines.append(f"- Records analyzed: {analyzed}")
    return "\n".join(lines) if lines else "_No input size data._"


def _format_meaningful_rate(
    raw_dataset: Mapping[str, Any],
    cleaned_dataset: Mapping[str, Any],
    meaningful_rate: str,
) -> str:
    lines = [
        f"- Raw audit meaningful rate: {_audit_rate(raw_dataset, 'meaningfulMemoryRate')}%",
        f"- Cleaned audit meaningful rate: {_audit_rate(cleaned_dataset, 'meaningfulMemoryRate')}%",
    ]
    if meaningful_rate != "n/a":
        lines.append(f"- Primary baseline (cleaned audit): {meaningful_rate}%")
    return "\n".join(lines)


def _format_duplicate_rate(
    raw_dataset: Mapping[str, Any],
    cleaned_dataset: Mapping[str, Any],
    metrics: Mapping[str, Any],
    duplicate_rate: str,
) -> str:
    lines = [
        f"- Raw audit duplicate rate: {_audit_rate(raw_dataset, 'duplicateRate')}%",
        f"- Cleaned audit duplicate rate: {duplicate_rate}%",
    ]
    duplicate_pct = metrics.get("duplicatePercentage")
    duplicate_count = metrics.get("duplicateCount")
    if duplicate_pct is not None:
        lines.append(f"- Analyze pipeline duplicate percentage: {duplicate_pct}%")
    if duplicate_count is not None:
        lines.append(f"- Analyze pipeline removable duplicates: {duplicate_count}")
    return "\n".join(lines)


def _format_compression(metrics: Mapping[str, Any], duplicate_rate: str) -> str:
    compression = metrics.get("compressionOpportunity")
    if compression is None:
        return (
            f"_No analyze compression metrics yet. "
            f"Cleaned audit duplicate rate: {duplicate_rate}%._"
        )
    lines = [f"- Compression opportunity: {compression}%"]
    trusted = metrics.get("trustedCompressionOpportunity")
    unverified = metrics.get("unverifiedCompressionOpportunity")
    if trusted is not None:
        lines.append(f"- Trusted compression opportunity: {trusted}%")
    if unverified is not None:
        lines.append(f"- Unverified compression opportunity: {unverified}%")
    reasons = metrics.get("compressionReasons")
    if isinstance(reasons, list) and reasons:
        lines.append("")
        lines.append("Compression drivers:")
        for reason in reasons[:5]:
            lines.append(f"- {reason}")
    return "\n".join(lines)
