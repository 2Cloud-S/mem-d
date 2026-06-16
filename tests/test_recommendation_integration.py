from __future__ import annotations

import json
from pathlib import Path

from memd.contracts import AnalysisReport
from memd.pipeline import analyze_file
from memd.reports import render_json, render_markdown, render_terminal, report_to_dict

FIXTURES = Path(__file__).parent / "fixtures"


def test_analyze_file_produces_recommendations() -> None:
    report = analyze_file(FIXTURES / "memories.json")
    assert isinstance(report.recommendationSummary.memoryResolutionCount, int)
    assert report.recommendationSummary.memoryResolutionCount == report.metrics.totalMemories
    assert len(report.memoryResolutions) == report.metrics.totalMemories
    for resolution in report.memoryResolutions:
        assert resolution.resolvedAction
        assert resolution.recommendationId


def test_recommendations_include_evidence() -> None:
    report = analyze_file(FIXTURES / "memories.json")
    for recommendation in report.recommendations:
        assert recommendation.evidence
        assert recommendation.reason
        assert recommendation.action


def test_json_report_includes_recommendation_fields() -> None:
    report = analyze_file(FIXTURES / "memories.json")
    payload = json.loads(render_json(report))
    assert "recommendations" in payload
    assert "memoryResolutions" in payload
    assert "recommendationSummary" in payload
    assert "mergeCount" in payload["recommendationSummary"]
    assert "actionSummary" in payload
    assert "policySummary" in payload


def test_markdown_report_includes_recommendation_summary() -> None:
    report = analyze_file(FIXTURES / "memories.json")
    markdown = render_markdown(report)
    assert "## Recommendation Summary" in markdown
    assert "### Merge recommendations" in markdown
    assert "### Archive recommendations" in markdown
    assert "### Review recommendations" in markdown
    assert "## Action Plan" in markdown


def test_backward_compatible_analysis_report_without_recommendations() -> None:
    from memd.contracts import (
        ActionPlanSummary,
        ActionPriority,
        AnalysisMetrics,
        MemoryCategory,
        PolicySummary,
    )

    report = AnalysisReport(
        metrics=AnalysisMetrics(
            totalMemories=0,
            duplicateCount=0,
            duplicatePercentage=0.0,
            compressionOpportunity=0.0,
            categoryBreakdown={category: 0 for category in MemoryCategory},
        ),
        clusters=(),
        actionSummary=ActionPlanSummary(
            totalActions=0,
            safeActions=0,
            reviewActions=0,
            estimatedTrustedSavings=0,
            estimatedUnverifiedSavings=0,
            actionsByPriority={priority: 0 for priority in ActionPriority},
        ),
        policySummary=PolicySummary(),
    )
    payload = report_to_dict(report)
    assert payload["recommendations"] == []
    assert payload["memoryResolutions"] == []
    assert payload["recommendationSummary"]["totalRecommendations"] == 0


def test_report_to_dict_matches_recommendation_contract() -> None:
    report = analyze_file(FIXTURES / "memories.json")
    recommendation = next(
        (item for item in report.recommendations if item.evidence),
        None,
    )
    if recommendation is None:
        return
    serialized = json.loads(render_json(report))
    first = serialized["recommendations"][0]
    assert "action" in first
    assert "confidence" in first
    assert "evidence" in first
    assert first["evidence"]


def test_terminal_render_includes_recommendations_when_present(capsys) -> None:
    from rich.console import Console

    report = analyze_file(FIXTURES / "memories.json")
    console = Console(record=True, width=120)
    render_terminal(report, console=console)
    output = console.export_text()
    if report.recommendations:
        assert "Governance Recommendations" in output or "Recommendation counts" in output


def test_pipeline_recommendation_behavior_matches_phase1_isolation() -> None:
    from memd.recommendations import plan_recommendations

    report = analyze_file(FIXTURES / "memories.json")
    isolated = plan_recommendations(
        report.memories,
        report.clusters,
        report.validation,
        report.insights,
        report.actions,
        metrics=report.metrics,
    )
    assert isolated[0] == report.recommendations
    assert isolated[1] == report.memoryResolutions
    assert isolated[2] == report.recommendationSummary


def test_memory_resolution_one_per_memory() -> None:
    report = analyze_file(FIXTURES / "memories.json")
    memory_ids = [resolution.memoryId for resolution in report.memoryResolutions]
    assert len(memory_ids) == len(set(memory_ids))
    assert set(memory_ids) == {memory.id for memory in report.memories}
