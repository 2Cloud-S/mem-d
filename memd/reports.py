from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.table import Table

from memd.contracts import (
    ActionPriority,
    AnalysisReport,
    CategorizedMemory,
    GovernanceAction,
    Insight,
    MemoryCategory,
    MemoryRecord,
    MemoryResolution,
    PolicyDecision,
    Recommendation,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationSummary,
)


def report_to_dict(report: AnalysisReport) -> dict[str, object]:
    records_by_id = {record.id: record for record in report.memories}
    categories_by_id = {category.memoryId: category for category in report.categories}
    return {
        "metrics": {
            "totalMemories": report.metrics.totalMemories,
            "duplicateCount": report.metrics.duplicateCount,
            "duplicatePercentage": report.metrics.duplicatePercentage,
            "compressionOpportunity": report.metrics.compressionOpportunity,
            "trustedDuplicateCount": report.metrics.trustedDuplicateCount,
            "unverifiedDuplicateCount": report.metrics.unverifiedDuplicateCount,
            "trustedCompressionOpportunity": report.metrics.trustedCompressionOpportunity,
            "unverifiedCompressionOpportunity": report.metrics.unverifiedCompressionOpportunity,
            "categoryAgreementRate": report.metrics.categoryAgreementRate,
            "reclassificationOpportunityCount": (
                report.metrics.reclassificationOpportunityCount
            ),
            "compressionReasons": list(report.metrics.compressionReasons),
            "categoryBreakdown": {
                category.value: report.metrics.categoryBreakdown.get(category, 0)
                for category in MemoryCategory
            },
        },
        "actionSummary": action_summary_to_dict(report),
        "policySummary": policy_summary_to_dict(report),
        "actions": [action_to_dict(action) for action in report.actions],
        "clusters": [
            {
                "clusterId": cluster.clusterId,
                "members": list(cluster.members),
                "averageSimilarity": cluster.averageSimilarity,
                "sharedTerms": list(cluster.sharedTerms),
                "reasons": list(cluster.reasons),
                "trustScore": cluster.trustScore,
                "trustLevel": cluster.trustLevel.value,
                "trustReasons": list(cluster.trustReasons),
                "recommendedAction": cluster.recommendedAction,
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
        "recommendations": [
            recommendation_to_dict(recommendation) for recommendation in report.recommendations
        ],
        "memoryResolutions": [
            memory_resolution_to_dict(resolution) for resolution in report.memoryResolutions
        ],
        "recommendationSummary": recommendation_summary_to_dict(report.recommendationSummary),
    }


def render_terminal(report: AnalysisReport, console: Console | None = None) -> None:
    console = console or Console()
    metrics = report.metrics

    console.print("[bold]Mem-D Analysis[/bold]")
    console.print(f"Analyzed: [bold]{metrics.totalMemories}[/bold] memories")
    console.print(f"Duplicate Clusters: [bold]{len(report.clusters)}[/bold]")
    console.print(f"Duplicate Memories: [bold]{metrics.duplicateCount}[/bold]")
    console.print(f"Compression Opportunity: [bold]{metrics.compressionOpportunity}%[/bold]")
    console.print(
        "Trusted Compression Opportunity: "
        f"[bold]{metrics.trustedCompressionOpportunity}%[/bold]"
    )
    console.print(
        "Unverified Compression Opportunity: "
        f"[bold]{metrics.unverifiedCompressionOpportunity}%[/bold]"
    )
    console.print(f"Category Agreement Rate: [bold]{metrics.categoryAgreementRate}%[/bold]")
    console.print(
        "Reclassification Opportunities: "
        f"[bold]{metrics.reclassificationOpportunityCount}[/bold]"
    )
    console.print(f"Governance Actions: [bold]{report.actionSummary.totalActions}[/bold]")
    console.print(
        "Safe / Review Actions: "
        f"[bold]{report.actionSummary.safeActions}[/bold] / "
        f"[bold]{report.actionSummary.reviewActions}[/bold]"
    )
    console.print(f"Policy Profile: [bold]{report.policySummary.profile.value}[/bold]")
    console.print(
        "Policy Outcomes: "
        f"[bold]{report.policySummary.approvedActions}[/bold] approved / "
        f"[bold]{report.policySummary.reviewRequiredActions}[/bold] review / "
        f"[bold]{report.policySummary.blockedActions}[/bold] blocked"
    )
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

    if report.actions:
        action_table = Table(title="Recommended Governance Actions")
        action_table.add_column("Priority")
        action_table.add_column("Type")
        action_table.add_column("Title")
        action_table.add_column("Approval")
        action_table.add_column("Policy")
        for action in report.actions[:10]:
            action_table.add_row(
                action.priority.value,
                action.actionType.value,
                action.title,
                "human" if action.requiresHumanApproval else "not required",
                action.policyDecision.value if action.policyDecision else "",
            )
        console.print(action_table)

    displayable = displayable_recommendations(report.recommendations)
    if displayable:
        recommendation_table = Table(title="Governance Recommendations")
        recommendation_table.add_column("Action")
        recommendation_table.add_column("Confidence", justify="right")
        recommendation_table.add_column("Reason")
        recommendation_table.add_column("Evidence")
        for recommendation in displayable[:5]:
            recommendation_table.add_row(
                recommendation.action.value,
                f"{recommendation.confidence:.2f}",
                recommendation.reason[:80],
                format_evidence_summary(recommendation.evidence),
            )
        console.print(recommendation_table)
        summary = report.recommendationSummary
        console.print(
            "Recommendation counts: "
            f"[bold]{summary.mergeCount}[/bold] merge / "
            f"[bold]{summary.archiveCount}[/bold] archive / "
            f"[bold]{summary.reviewCount}[/bold] review"
        )

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
        cluster_table.add_column("Trust")
        cluster_table.add_column("Why grouped")
        cluster_table.add_column("Avg Similarity", justify="right")
        for cluster in report.clusters[:10]:
            cluster_table.add_row(
                cluster.clusterId,
                ", ".join(cluster.members),
                f"{cluster.trustLevel.value} ({cluster.trustScore})",
                "; ".join(cluster.reasons[:2]),
                f"{cluster.averageSimilarity:.2f}",
            )
        console.print(cluster_table)

    cluster_quality = report.validation.get("clusterQuality", {})
    over_clustering = cluster_quality.get("overClusteringCandidates", [])
    contamination = cluster_quality.get("clusterContamination", [])
    if over_clustering:
        console.print(
            f"Possible over-clustering: [bold]{len(over_clustering)}[/bold] "
            "largest clusters need semantic review."
        )
    if contamination:
        console.print(
            f"Cluster contamination candidates: [bold]{len(contamination)}[/bold] "
            "clusters contain low-similarity outliers."
        )

    category_quality = report.validation.get("categoryQuality", {})
    unknown_count = category_quality.get("unknownCount")
    unknown_percentage = category_quality.get("unknownPercentage")
    if unknown_count is not None:
        console.print(
            f"Unknown categories: [bold]{unknown_count}[/bold] "
            f"({unknown_percentage}%); inspect JSON/Markdown validation samples."
        )
    category_audit = category_quality.get("categoryAuditV2", {})
    if isinstance(category_audit, dict):
        top_causes = category_audit.get("topUnknownCauses", [])
        if isinstance(top_causes, list) and top_causes:
            first_cause = top_causes[0] if isinstance(top_causes[0], dict) else {}
            console.print(
                "Top Unknown cause: "
                f"[bold]{first_cause.get('cause', '')}[/bold] "
                f"({first_cause.get('count', 0)} memories)."
            )
        discovery = category_audit.get("taxonomyDiscovery", {})
        if isinstance(discovery, dict):
            candidates = discovery.get("candidateCategories", [])
            if isinstance(candidates, list) and candidates:
                top_candidate = candidates[0] if isinstance(candidates[0], dict) else {}
                console.print(
                    "Top taxonomy candidate: "
                    f"[bold]{top_candidate.get('label', '')}[/bold] "
                    f"({top_candidate.get('memoryCount', 0)} memories, "
                    f"{top_candidate.get('issueType', '')})."
                )
    consistency = category_quality.get("categoryConsistency", {})
    if isinstance(consistency, dict) and consistency.get("conflictClusterCount"):
        console.print(
            "Category conflict clusters: "
            f"[bold]{consistency.get('conflictClusterCount')}[/bold]; "
            "inspect category consistency validation details."
        )

    evolution = report.validation.get("memoryEvolutionAudit", {})
    if isinstance(evolution, dict) and integer_value(evolution.get("totalEvolutionSignals")) > 0:
        console.print(
            "Memory evolution signals: "
            f"[bold]{evolution.get('totalEvolutionSignals')}[/bold] "
            f"(confidence {evolution.get('evolutionConfidence', 0)}); "
            f"contradictions={evolution.get('contradictionCount', 0)}, "
            f"preference changes={evolution.get('preferenceChangeCount', 0)}, "
            f"superseded={evolution.get('supersededMemoryCount', 0)}, "
            f"stale={evolution.get('staleMemoryCount', 0)}, "
            f"status transitions={evolution.get('statusTransitionCount', 0)}."
        )

    lifecycle = report.validation.get("memoryLifecycle", {})
    if isinstance(lifecycle, dict):
        assignments = lifecycle.get("memoryLifecycleAssignments", [])
        if isinstance(assignments, list) and assignments:
            counts = lifecycle.get("lifecycleCounts", {})
            if not isinstance(counts, dict):
                counts = {}
            console.print(
                "Memory lifecycle states: "
                f"[bold]{len(assignments)}[/bold] assignments "
                f"(confidence {lifecycle.get('lifecycleConfidence', 0)}); "
                f"active={counts.get('Active', 0)}, "
                f"historical={counts.get('Historical', 0)}, "
                f"superseded={counts.get('Superseded', 0)}, "
                f"deprecated={counts.get('Deprecated', 0)}, "
                f"temporary={counts.get('Temporary', 0)}, "
                f"completed={counts.get('Completed', 0)}."
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
        f"- Trusted compression opportunity: {metrics.trustedCompressionOpportunity}%",
        f"- Unverified compression opportunity: {metrics.unverifiedCompressionOpportunity}%",
        f"- Category agreement rate: {metrics.categoryAgreementRate}%",
        f"- Reclassification opportunities: {metrics.reclassificationOpportunityCount}",
        f"- Governance actions: {report.actionSummary.totalActions}",
        f"- Safe actions: {report.actionSummary.safeActions}",
        f"- Review actions: {report.actionSummary.reviewActions}",
        f"- Estimated trusted savings: {report.actionSummary.estimatedTrustedSavings}",
        f"- Estimated unverified savings: {report.actionSummary.estimatedUnverifiedSavings}",
        f"- Policy profile: {report.policySummary.profile.value}",
        f"- Policy approved actions: {report.policySummary.approvedActions}",
        f"- Policy review-required actions: {report.policySummary.reviewRequiredActions}",
        f"- Policy blocked actions: {report.policySummary.blockedActions}",
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
    lines.extend(render_policy_summary_markdown(report))
    lines.extend(render_action_plan_markdown(report.actions))
    lines.extend(render_recommendation_summary_markdown(report))
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
                    f"- Trust: {cluster.trustLevel.value} ({cluster.trustScore})",
                    f"- Recommended action: {cluster.recommendedAction}",
                    f"- Trust reasons: {', '.join(cluster.trustReasons) or 'none'}",
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


def action_summary_to_dict(report: AnalysisReport) -> dict[str, object]:
    summary = report.actionSummary
    return {
        "totalActions": summary.totalActions,
        "safeActions": summary.safeActions,
        "reviewActions": summary.reviewActions,
        "estimatedTrustedSavings": summary.estimatedTrustedSavings,
        "estimatedUnverifiedSavings": summary.estimatedUnverifiedSavings,
        "actionsByPriority": {
            priority.value: summary.actionsByPriority.get(priority, 0)
            for priority in ActionPriority
        },
    }


def policy_summary_to_dict(report: AnalysisReport) -> dict[str, object]:
    summary = report.policySummary
    return {
        "profile": summary.profile.value,
        "totalDecisions": summary.totalDecisions,
        "approvedActions": summary.approvedActions,
        "reviewRequiredActions": summary.reviewRequiredActions,
        "blockedActions": summary.blockedActions,
        "decisionsByType": {
            decision.value: summary.decisionsByType.get(decision, 0)
            for decision in PolicyDecision
        },
        "matchedRules": summary.matchedRules,
    }


def action_to_dict(action: GovernanceAction) -> dict[str, object]:
    return {
        "actionId": action.actionId,
        "actionType": action.actionType.value,
        "target": action.target,
        "title": action.title,
        "rationale": action.rationale,
        "supportingEvidence": list(action.supportingEvidence),
        "trustLevel": action.trustLevel.value if action.trustLevel else None,
        "confidence": action.confidence,
        "estimatedImpact": action.estimatedImpact,
        "requiresHumanApproval": action.requiresHumanApproval,
        "priority": action.priority.value,
        "sourceSignals": list(action.sourceSignals),
        "policyDecision": action.policyDecision.value if action.policyDecision else None,
        "policyProfile": action.policyProfile.value if action.policyProfile else None,
        "policyRuleId": action.policyRuleId,
        "policyExplanation": action.policyExplanation,
    }


def recommendation_summary_to_dict(summary: RecommendationSummary) -> dict[str, object]:
    return {
        "totalRecommendations": summary.totalRecommendations,
        "mergeCount": summary.mergeCount,
        "archiveCount": summary.archiveCount,
        "reviewCount": summary.reviewCount,
        "keepCount": summary.keepCount,
        "deferredCount": summary.deferredCount,
        "memoryResolutionCount": summary.memoryResolutionCount,
        "estimatedTrustedRemovals": summary.estimatedTrustedRemovals,
        "estimatedArchivableRecords": summary.estimatedArchivableRecords,
        "recommendationsByPriority": {
            priority.value: summary.recommendationsByPriority.get(priority, 0)
            for priority in ActionPriority
        },
    }


def recommendation_to_dict(recommendation: Recommendation) -> dict[str, object]:
    return {
        "recommendationId": recommendation.recommendationId,
        "action": recommendation.action.value,
        "subtype": recommendation.subtype,
        "confidence": recommendation.confidence,
        "reason": recommendation.reason,
        "affected_memories": [
            {
                "memoryId": memory.memoryId,
                "role": memory.role,
                "lifecycleState": memory.lifecycleState,
            }
            for memory in recommendation.affected_memories
        ],
        "evidence": [evidence_to_dict(item) for item in recommendation.evidence],
        "estimatedImpact": recommendation.estimatedImpact,
        "priority": recommendation.priority.value,
        "requiresHumanApproval": recommendation.requiresHumanApproval,
        "sourceActionIds": list(recommendation.sourceActionIds),
        "sourceInsightIds": list(recommendation.sourceInsightIds),
        "suppressedCandidates": list(recommendation.suppressedCandidates),
        "conflictDetected": recommendation.conflictDetected,
    }


def memory_resolution_to_dict(resolution: MemoryResolution) -> dict[str, object]:
    return {
        "memoryId": resolution.memoryId,
        "resolvedAction": resolution.resolvedAction.value,
        "role": resolution.role,
        "confidence": resolution.confidence,
        "recommendationId": resolution.recommendationId,
        "suppressedActions": [action.value for action in resolution.suppressedActions],
        "conflictDetected": resolution.conflictDetected,
    }


def evidence_to_dict(evidence: RecommendationEvidence) -> dict[str, object]:
    return {
        "source": evidence.source,
        "signal": evidence.signal,
        "value": evidence.value,
        "caseId": evidence.caseId,
        "ruleId": evidence.ruleId,
        "actionId": evidence.actionId,
        "insightId": evidence.insightId,
    }


def displayable_recommendations(
    recommendations: tuple[Recommendation, ...],
) -> list[Recommendation]:
    return [
        recommendation
        for recommendation in recommendations
        if recommendation.evidence
        and recommendation.action != RecommendationAction.KEEP
    ]


def format_evidence_summary(evidence: tuple[RecommendationEvidence, ...]) -> str:
    return "; ".join(f"{item.source}:{item.signal}" for item in evidence[:3])


def render_recommendation_summary_markdown(report: AnalysisReport) -> list[str]:
    recommendations = displayable_recommendations(report.recommendations)
    keep_recommendations = [
        recommendation
        for recommendation in report.recommendations
        if recommendation.action == RecommendationAction.KEEP and recommendation.evidence
    ]
    summary = report.recommendationSummary
    lines = [
        "",
        "## Recommendation Summary",
        "",
        f"- Total recommendations: {summary.totalRecommendations}",
        f"- Merge: {summary.mergeCount}",
        f"- Archive: {summary.archiveCount}",
        f"- Review: {summary.reviewCount}",
        f"- Memory resolutions: {summary.memoryResolutionCount}",
        "",
    ]
    grouped = {
        RecommendationAction.MERGE: [],
        RecommendationAction.ARCHIVE: [],
        RecommendationAction.REVIEW: [],
    }
    for recommendation in recommendations:
        if recommendation.action in grouped:
            grouped[recommendation.action].append(recommendation)

    lines.extend(render_recommendation_group_markdown("Merge recommendations", grouped[RecommendationAction.MERGE]))
    lines.extend(render_recommendation_group_markdown("Archive recommendations", grouped[RecommendationAction.ARCHIVE]))
    lines.extend(render_recommendation_group_markdown("Review recommendations", grouped[RecommendationAction.REVIEW]))
    if keep_recommendations:
        lines.extend(render_recommendation_group_markdown("Keep recommendations", keep_recommendations))
    return lines


def render_recommendation_group_markdown(
    title: str,
    recommendations: Sequence[Recommendation],
) -> list[str]:
    lines = [f"### {title}", ""]
    if not recommendations:
        lines.extend(["No recommendations in this category.", ""])
        return lines
    for recommendation in recommendations[:20]:
        lines.extend(
            [
                f"#### `{recommendation.recommendationId}`",
                "",
                f"- Action: {recommendation.action.value}",
                f"- Confidence: {recommendation.confidence}",
                f"- Reason: {recommendation.reason}",
                "- Evidence:",
                *[
                    f"  - {item.source}: {item.signal}"
                    + (f" ({item.value})" if item.value is not None else "")
                    for item in recommendation.evidence
                ],
                "",
            ]
        )
    return lines


def render_policy_summary_markdown(report: AnalysisReport) -> list[str]:
    summary = report.policySummary
    lines = [
        "",
        "## Policy Outcomes",
        "",
        f"- Profile: {summary.profile.value}",
        f"- Total decisions: {summary.totalDecisions}",
        f"- Approved actions: {summary.approvedActions}",
        f"- Review-required actions: {summary.reviewRequiredActions}",
        f"- Blocked actions: {summary.blockedActions}",
        "",
        "| Decision | Count |",
        "| --- | ---: |",
    ]
    for decision in PolicyDecision:
        lines.append(f"| {decision.value} | {summary.decisionsByType.get(decision, 0)} |")
    if summary.matchedRules:
        lines.extend(["", "Matched policy rules:", ""])
        for rule_id, count in sorted(summary.matchedRules.items()):
            lines.append(f"- `{rule_id}`: {count}")
    return lines


def render_action_plan_markdown(actions: tuple[GovernanceAction, ...]) -> list[str]:
    safe, review, deferred = grouped_actions(actions)
    lines = ["", "## Action Plan", ""]
    lines.extend(render_action_group("Recommended Safe Actions", safe))
    lines.extend(render_action_group("Recommended Review Actions", review))
    lines.extend(render_action_group("Deferred / Low-Priority Actions", deferred))
    return lines


def grouped_actions(
    actions: tuple[GovernanceAction, ...],
) -> tuple[list[GovernanceAction], list[GovernanceAction], list[GovernanceAction]]:
    deferred_priorities = {ActionPriority.LOW, ActionPriority.DEFERRED}
    safe = [
        action
        for action in actions
        if not action.requiresHumanApproval and action.priority not in deferred_priorities
    ]
    review = [
        action
        for action in actions
        if action.requiresHumanApproval and action.priority not in deferred_priorities
    ]
    deferred = [
        action
        for action in actions
        if action.priority in deferred_priorities
    ]
    return safe, review, deferred


def render_action_group(title: str, actions: Sequence[GovernanceAction]) -> list[str]:
    lines = [f"### {title}", ""]
    if not actions:
        lines.append("No actions in this category.")
        lines.append("")
        return lines
    for action in actions[:20]:
        approval = "yes" if action.requiresHumanApproval else "no"
        evidence = "; ".join(action.supportingEvidence[:3])
        lines.extend(
            [
                f"#### {action.title}",
                "",
                f"- Action ID: `{action.actionId}`",
                f"- Type: {action.actionType.value}",
                f"- Priority: {action.priority.value}",
                f"- Requires human approval: {approval}",
                (
                    "- Policy decision: "
                    f"{action.policyDecision.value if action.policyDecision else 'none'}"
                ),
                f"- Policy rule: {action.policyRuleId or 'none'}",
                f"- Policy explanation: {action.policyExplanation or 'none'}",
                f"- Confidence: {action.confidence}",
                f"- Estimated impact: {action.estimatedImpact}",
                f"- Rationale: {action.rationale}",
                f"- Source signals: {', '.join(action.sourceSignals)}",
                f"- Evidence: {evidence}",
                "",
            ]
        )
    return lines


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
        consistency = category_quality.get("categoryConsistency", {})
        if isinstance(consistency, dict) and consistency:
            lines.extend(render_category_consistency_markdown(consistency))
        category_audit = category_quality.get("categoryAuditV2", {})
        if isinstance(category_audit, dict) and category_audit:
            lines.extend(render_category_audit_v2_markdown(category_audit))

    if cluster_quality:
        false_positive_candidates = cluster_quality.get("possibleFalsePositiveClusters", [])
        over_clustering = cluster_quality.get("overClusteringCandidates", [])
        contamination = cluster_quality.get("clusterContamination", [])
        trust = cluster_quality.get("clusterTrust", {})
        if not isinstance(trust, dict):
            trust = {}
        lines.extend(
            [
                "",
                "### Cluster Quality",
                "",
                f"- Possible false-positive candidates: {len(false_positive_candidates)}",
                f"- Possible over-clustering candidates: {len(over_clustering)}",
                f"- Cluster contamination candidates: {len(contamination)}",
                f"- High-trust clusters: {trust.get('highTrustClusters', 0)}",
                f"- Medium-trust clusters: {trust.get('mediumTrustClusters', 0)}",
                f"- Low-trust clusters: {trust.get('lowTrustClusters', 0)}",
            ]
        )
        lines.extend(render_cluster_audit_markdown(cluster_quality))

    if compression:
        lines.extend(["", "### Compression Drivers", ""])
        lines.extend(
            [
                f"- Trusted removable records: {compression.get('trustedRemovableRecords', 0)}",
                (
                    "- Unverified removable records: "
                    f"{compression.get('unverifiedRemovableRecords', 0)}"
                ),
            ]
        )
        for driver in compression.get("largestClusterDrivers", [])[:5]:
            if isinstance(driver, dict):
                lines.append(
                    f"- `{driver.get('clusterId')}` size {driver.get('size')}: "
                    f"{driver.get('removableRecords')} removable records "
                    f"({driver.get('trustLevel', 'Unknown')} trust)"
                )

    evolution = report.validation.get("memoryEvolutionAudit", {})
    if isinstance(evolution, dict) and evolution:
        lines.extend(render_memory_evolution_audit_markdown(evolution))
    lifecycle = report.validation.get("memoryLifecycle", {})
    if isinstance(lifecycle, dict) and lifecycle:
        lines.extend(render_memory_lifecycle_markdown(lifecycle))
    return lines


def escape_markdown_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_category_consistency_markdown(consistency: dict[str, object]) -> list[str]:
    lines = [
        "",
        "### Category Consistency Audit",
        "",
        f"- Category agreement rate: {consistency.get('categoryAgreementRate', 0)}%",
        f"- Conflict clusters: {consistency.get('conflictClusterCount', 0)}",
        (
            "- Reclassification opportunities: "
            f"{consistency.get('reclassificationOpportunityCount', 0)}"
        ),
        f"- Conflict rate: {consistency.get('conflictRate', 0)}%",
    ]
    recurring = consistency.get("recurringConflicts", [])
    if isinstance(recurring, list) and recurring:
        lines.extend(["", "Recurring conflicts:", ""])
        for conflict in recurring[:10]:
            if isinstance(conflict, dict):
                categories = conflict.get("categories", [])
                labels = " vs ".join(str(category) for category in categories)
                priority = " priority" if conflict.get("isPriorityConflict") else ""
                lines.append(
                    f"- {labels}: {conflict.get('clusterCount', 0)} clusters{priority}"
                )

    conflict_clusters = consistency.get("conflictClusters", [])
    if isinstance(conflict_clusters, list) and conflict_clusters:
        lines.extend(["", "Conflict clusters:", ""])
        for cluster in conflict_clusters[:10]:
            if isinstance(cluster, dict):
                lines.append(
                    f"- `{cluster.get('clusterId')}` dominant "
                    f"{cluster.get('dominantCategory')} "
                    f"({cluster.get('dominantCategoryCount')}/{cluster.get('size')}), "
                    f"minority categories: "
                    f"{format_minority_categories(cluster.get('minorityCategories', []))}"
                )

    candidates = consistency.get("reclassificationCandidates", [])
    if isinstance(candidates, list) and candidates:
        lines.extend(
            [
                "",
                "Potential reclassification candidates:",
                "",
                "| ID | Current | Suggested | Cluster | Content |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for candidate in candidates[:20]:
            if isinstance(candidate, dict):
                lines.append(
                    f"| `{candidate.get('memoryId')}` | "
                    f"{candidate.get('currentCategory')} | "
                    f"{candidate.get('suggestedCategory')} | "
                    f"`{candidate.get('clusterId')}` | "
                    f"{escape_markdown_table(str(candidate.get('content', '')))} |"
                )
    return lines


def render_category_audit_v2_markdown(audit: dict[str, object]) -> list[str]:
    lines = [
        "",
        "### Category Audit V2",
        "",
        f"- Unknown rate: {audit.get('unknownRate', 0)}%",
        f"- High-confidence Unknown rate: {audit.get('highConfidenceUnknownRate', 0)}%",
    ]
    distribution = audit.get("categoryConfidenceDistribution", {})
    if isinstance(distribution, dict):
        lines.append(f"- Average category confidence: {distribution.get('averageConfidence', 0)}")
        buckets = distribution.get("buckets", {})
        if isinstance(buckets, dict):
            lines.append(
                "- Confidence distribution: "
                f"high={buckets.get('high', 0)}, "
                f"medium={buckets.get('medium', 0)}, "
                f"low={buckets.get('low', 0)}"
            )

    top_causes = audit.get("topUnknownCauses", [])
    if isinstance(top_causes, list) and top_causes:
        lines.extend(["", "Top Unknown causes:", ""])
        for cause in top_causes[:10]:
            if isinstance(cause, dict):
                lines.append(
                    f"- {cause.get('cause')}: {cause.get('count')} memories "
                    f"({cause.get('percentageOfUnknown')}% of Unknown). "
                    f"Example: {cause.get('example')}"
                )

    gaps = audit.get("suggestedTaxonomyGaps", [])
    if isinstance(gaps, list) and gaps:
        lines.extend(["", "Suggested taxonomy gaps:", ""])
        for gap in gaps[:10]:
            if isinstance(gap, dict):
                lines.append(
                    f"- {gap.get('gap')} -> {gap.get('suggestedCategory')} "
                    f"({gap.get('evidenceCount')} examples, confidence {gap.get('confidence')})"
                )

    unknown_clusters = audit.get("unknownClusters", [])
    if isinstance(unknown_clusters, list) and unknown_clusters:
        lines.extend(["", "Unknown pattern clusters:", ""])
        for cluster in unknown_clusters[:10]:
            if isinstance(cluster, dict):
                lines.append(
                    f"- `{cluster.get('clusterId')}` {cluster.get('cause')}: "
                    f"{cluster.get('count')} memories, suggested "
                    f"{cluster.get('suggestedCategory')}, themes "
                    f"{', '.join(str(term) for term in cluster.get('themeTerms', []))}"
                )

    candidates = audit.get("reclassificationCandidates", [])
    if isinstance(candidates, list) and candidates:
        lines.extend(
            [
                "",
                "Ranked Unknown reclassification candidates:",
                "",
                "| ID | Suggested | Confidence | Frequency | Cause | Content |",
                "| --- | --- | ---: | ---: | --- | --- |",
            ]
        )
        for candidate in candidates[:20]:
            if isinstance(candidate, dict):
                lines.append(
                    f"| `{candidate.get('memoryId')}` | "
                    f"{candidate.get('suggestedCategory')} | "
                    f"{candidate.get('confidence')} | "
                    f"{candidate.get('frequency')} | "
                    f"{candidate.get('cause')} | "
                    f"{escape_markdown_table(str(candidate.get('content', '')))} |"
                )
    discovery = audit.get("taxonomyDiscovery", {})
    if isinstance(discovery, dict) and discovery:
        lines.extend(render_taxonomy_expansion_markdown(discovery))
    semantic = audit.get("semanticThemeAnalysis", {})
    if isinstance(semantic, dict) and semantic:
        lines.extend(render_semantic_theme_analysis_markdown(semantic))
    resolution = audit.get("unknownResolutionAudit", {})
    if isinstance(resolution, dict) and resolution:
        lines.extend(render_unknown_resolution_audit_markdown(resolution))
    return lines


def render_taxonomy_expansion_markdown(discovery: dict[str, object]) -> list[str]:
    lines = [
        "",
        "### Taxonomy Expansion",
        "",
        str(discovery.get("summary", "")),
        "",
    ]
    candidates = discovery.get("candidateCategories", [])
    if isinstance(candidates, list) and candidates:
        lines.extend(
            [
                "| Candidate category | Type | Count | Unknown reduction | Confidence | Mapping |",
                "| --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for candidate in candidates[:15]:
            if isinstance(candidate, dict):
                lines.append(
                    f"| {candidate.get('label')} | "
                    f"{candidate.get('issueType')} | "
                    f"{candidate.get('memoryCount')} | "
                    f"{candidate.get('estimatedUnknownRateReduction')}% | "
                    f"{candidate.get('confidence')} | "
                    f"{escape_markdown_table(str(candidate.get('suggestedMapping', '')))} |"
                )

    taxonomy_gaps = discovery.get("taxonomyGaps", [])
    if isinstance(taxonomy_gaps, list) and taxonomy_gaps:
        lines.extend(["", "Taxonomy gaps:", ""])
        for candidate in taxonomy_gaps[:10]:
            if isinstance(candidate, dict):
                lines.append(
                    f"- {candidate.get('label')}: {candidate.get('memoryCount')} memories; "
                    f"remaining Unknown rate would be "
                    f"{candidate.get('estimatedRemainingUnknownRate')}% if addressed."
                )

    classifier_failures = discovery.get("classifierFailures", [])
    if isinstance(classifier_failures, list) and classifier_failures:
        lines.extend(["", "Classifier failures:", ""])
        for candidate in classifier_failures[:10]:
            if isinstance(candidate, dict):
                lines.append(
                    f"- {candidate.get('label')}: {candidate.get('memoryCount')} memories; "
                    f"{candidate.get('suggestedMapping')}"
                )
    return lines


def render_semantic_theme_analysis_markdown(analysis: dict[str, object]) -> list[str]:
    lines = [
        "",
        "### Semantic Theme Analysis",
        "",
        str(analysis.get("summary", "")),
        "",
        f"- Meaningful Unknown memories: {analysis.get('meaningfulUnknownCount', 0)}",
        f"- Formatting issues: {analysis.get('formattingIssueCount', 0)}",
    ]
    formatting = analysis.get("formattingIssues", {})
    if isinstance(formatting, dict) and integer_value(formatting.get("count")) > 0:
        lines.extend(
            [
                "",
                "Formatting issues (not semantic gaps):",
                "",
                f"- Count: {formatting.get('count')}",
                f"- Purity: {formatting.get('categoryPurity')}",
            ]
        )
        examples = formatting.get("representativeExamples", [])
        if isinstance(examples, list) and examples:
            lines.append("- Examples:")
            for example in examples[:5]:
                if isinstance(example, dict):
                    lines.append(f"  - `{example.get('memoryId')}`: {example.get('content')}")

    concepts = analysis.get("recurringConcepts", [])
    if isinstance(concepts, list) and concepts:
        lines.extend(["", "Recurring semantic concepts:", ""])
        for concept in concepts[:10]:
            if isinstance(concept, dict):
                lines.append(
                    f"- {concept.get('concept')}: {concept.get('evidenceCount')} memories "
                    f"(purity {concept.get('categoryPurity')})"
                )

    candidates = analysis.get("candidateSemanticCategories", [])
    if isinstance(candidates, list) and candidates:
        lines.extend(
            [
                "",
                "Candidate semantic categories:",
                "",
                "| Theme | Count | Purity | Confidence | Mapping |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for candidate in candidates[:15]:
            if isinstance(candidate, dict):
                lines.append(
                    f"| {candidate.get('label')} | "
                    f"{candidate.get('memoryCount')} | "
                    f"{candidate.get('categoryPurity')} | "
                    f"{candidate.get('confidence')} | "
                    f"{escape_markdown_table(str(candidate.get('suggestedMapping', '')))} |"
                )
        lines.extend(["", "Representative examples by theme:", ""])
        for candidate in candidates[:10]:
            if isinstance(candidate, dict):
                label = candidate.get("label")
                count = candidate.get("memoryCount")
                lines.append(f"- **{label}** ({count} memories)")
                examples = candidate.get("representativeExamples", [])
                if isinstance(examples, list):
                    for example in examples[:3]:
                        if isinstance(example, dict):
                            lines.append(
                                f"  - `{example.get('memoryId')}`: {example.get('content')}"
                            )
    return lines


def render_memory_lifecycle_markdown(lifecycle: dict[str, object]) -> list[str]:
    lines = [
        "",
        "### Memory Lifecycle",
        "",
        str(lifecycle.get("summary", "")),
        "",
        f"- Lifecycle confidence: {lifecycle.get('lifecycleConfidence', 0)}",
    ]
    counts = lifecycle.get("lifecycleCounts", {})
    if isinstance(counts, dict):
        lines.extend(
            [
                f"- Active: {counts.get('Active', 0)}",
                f"- Historical: {counts.get('Historical', 0)}",
                f"- Superseded: {counts.get('Superseded', 0)}",
                f"- Deprecated: {counts.get('Deprecated', 0)}",
                f"- Temporary: {counts.get('Temporary', 0)}",
                f"- Completed: {counts.get('Completed', 0)}",
            ]
        )

    transitions = lifecycle.get("lifecycleTransitions", [])
    if isinstance(transitions, list) and transitions:
        lines.extend(
            [
                "",
                "Lifecycle transitions:",
                "",
                "| From | State | To | State | Confidence | Type |",
                "| --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for transition in transitions[:10]:
            if isinstance(transition, dict):
                lines.append(
                    f"| `{transition.get('fromMemoryId')}` | "
                    f"{transition.get('fromState')} | "
                    f"`{transition.get('toMemoryId') or ''}` | "
                    f"{transition.get('toState') or ''} | "
                    f"{transition.get('confidence')} | "
                    f"{transition.get('evolutionType')} |"
                )

    assignments = lifecycle.get("memoryLifecycleAssignments", [])
    if isinstance(assignments, list) and assignments:
        lines.extend(["", "Lifecycle assignments:", ""])
        for assignment in assignments[:15]:
            if isinstance(assignment, dict):
                lines.append(
                    f"- `{assignment.get('memoryId')}` -> "
                    f"{assignment.get('lifecycleState')} "
                    f"(confidence {assignment.get('confidence')}): "
                    f"{assignment.get('content')}"
                )
    return lines


def render_memory_evolution_audit_markdown(audit: dict[str, object]) -> list[str]:
    lines = [
        "",
        "### Memory Evolution Audit",
        "",
        str(audit.get("summary", "")),
        "",
        f"- Contradictions: {audit.get('contradictionCount', 0)}",
        f"- Preference changes: {audit.get('preferenceChangeCount', 0)}",
        f"- Superseded memories: {audit.get('supersededMemoryCount', 0)}",
        f"- Stale memory candidates: {audit.get('staleMemoryCount', 0)}",
        f"- Status transition candidates: {audit.get('statusTransitionCount', 0)}",
        f"- Evolution confidence: {audit.get('evolutionConfidence', 0)}",
    ]

    for title, key in (
        ("Contradictions", "contradictions"),
        ("Preference changes", "preferenceChanges"),
        ("Superseded memories", "supersededMemories"),
        ("Status transitions", "statusTransitionCandidates"),
    ):
        cases = audit.get(key, [])
        if isinstance(cases, list) and cases:
            lines.extend(["", f"{title}:", ""])
            for case in cases[:5]:
                if isinstance(case, dict):
                    lines.append(f"- {case.get('caseId')} (confidence {case.get('confidence')})")
                    lines.append(f"  - {case.get('explanation')}")
                    memories = case.get("involvedMemories", [])
                    if isinstance(memories, list):
                        for memory in memories[:2]:
                            if isinstance(memory, dict):
                                lines.append(
                                    f"  - `{memory.get('memoryId')}`: {memory.get('content')}"
                                )

    stale = audit.get("staleMemoryCandidates", [])
    if isinstance(stale, list) and stale:
        lines.extend(["", "Stale memory candidates:", ""])
        for case in stale[:5]:
            if isinstance(case, dict):
                lines.append(f"- {case.get('caseId')} (confidence {case.get('confidence')})")
                lines.append(f"  - {case.get('explanation')}")
                memories = case.get("involvedMemories", [])
                if isinstance(memories, list) and memories:
                    memory = memories[0]
                    if isinstance(memory, dict):
                        lines.append(f"  - `{memory.get('memoryId')}`: {memory.get('content')}")
    return lines


def render_unknown_resolution_audit_markdown(audit: dict[str, object]) -> list[str]:
    lines = [
        "",
        "### Unknown Resolution Audit",
        "",
        str(audit.get("summary", "")),
        "",
        f"- Classifier failures: {audit.get('classifierFailureCount', 0)} "
        f"({audit.get('classifierFailureRate', 0)}% of Unknown)",
        f"- Taxonomy gaps: {audit.get('taxonomyGapCount', 0)} "
        f"({audit.get('taxonomyGapRate', 0)}% of Unknown)",
        f"- Unresolved: {audit.get('unresolvedCount', 0)} "
        f"({audit.get('unresolvedRate', 0)}% of Unknown)",
        f"- Estimated Unknown reduction: {audit.get('estimatedUnknownReduction', 0)}% "
        "of total memories if classifier and taxonomy issues are addressed",
        f"- Estimated classifier-only reduction: "
        f"{audit.get('estimatedClassifierReduction', 0)}%",
        f"- Estimated taxonomy-gap reduction: "
        f"{audit.get('estimatedTaxonomyGapReduction', 0)}%",
    ]

    groups = audit.get("resolutionGroups", [])
    if isinstance(groups, list) and groups:
        lines.extend(["", "Resolution groups:", ""])
        for group in groups:
            if isinstance(group, dict):
                lines.append(
                    f"- {group.get('label')}: {group.get('count')} memories "
                    f"({group.get('percentageOfUnknown')}% of Unknown)"
                )
                examples = group.get("representativeExamples", [])
                if isinstance(examples, list):
                    for example in examples[:3]:
                        if isinstance(example, dict):
                            lines.append(
                                f"  - `{example.get('memoryId')}` "
                                f"({example.get('confidence')}): {example.get('content')}"
                            )

    causes = audit.get("topRecurringCauses", [])
    if isinstance(causes, list) and causes:
        lines.extend(
            [
                "",
                "Top recurring causes:",
                "",
                "| Cause | Count | Dominant resolution | Classifier | Gap | Unresolved |",
                "| --- | ---: | --- | ---: | ---: | ---: |",
            ]
        )
        for cause in causes[:10]:
            if isinstance(cause, dict):
                breakdown = cause.get("resolutionBreakdown", {})
                classifier = 0
                gap = 0
                unresolved = 0
                if isinstance(breakdown, dict):
                    classifier = integer_value(breakdown.get("classifier_failure"))
                    gap = integer_value(breakdown.get("taxonomy_gap"))
                    unresolved = integer_value(breakdown.get("unresolved"))
                lines.append(
                    f"| {cause.get('label')} | {cause.get('count')} | "
                    f"{cause.get('dominantResolutionType')} | {classifier} | {gap} | "
                    f"{unresolved} |"
                )
    return lines


def integer_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def format_minority_categories(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    labels = []
    for item in value:
        if isinstance(item, dict):
            labels.append(f"{item.get('category')} ({item.get('count')})")
    return ", ".join(labels) if labels else "none"


def render_cluster_audit_markdown(cluster_quality: dict[str, object]) -> list[str]:
    audits = cluster_quality.get("largestClusterAudit", [])
    if not isinstance(audits, list) or not audits:
        return []

    lines = ["", "### Largest Cluster Audit", ""]
    for audit in audits[:10]:
        if not isinstance(audit, dict):
            continue
        distribution = audit.get("similarityDistribution", {})
        if not isinstance(distribution, dict):
            distribution = {}
        heterogeneity_reasons = ", ".join(audit.get("heterogeneityReasons", [])) or "none"
        lines.extend(
            [
                f"#### {audit.get('clusterId')}",
                "",
                f"- Size: {audit.get('size')}",
                f"- Average similarity: {audit.get('averageSimilarity')}",
                f"- Concept assessment: {audit.get('conceptAssessment')}",
                f"- Dominant themes: {', '.join(audit.get('dominantThemes', []))}",
                (
                    "- Similarity distribution: "
                    f"min={distribution.get('min')}, "
                    f"p25={distribution.get('p25')}, "
                    f"median={distribution.get('median')}, "
                    f"p75={distribution.get('p75')}, "
                    f"max={distribution.get('max')}, "
                    f"spread={distribution.get('spread')}"
                ),
                f"- Heterogeneity reasons: {heterogeneity_reasons}",
                "",
                "| Representative ID | Content |",
                "| --- | --- |",
            ]
        )
        for memory in audit.get("representativeMemories", []):
            if isinstance(memory, dict):
                lines.append(
                    f"| `{memory.get('id')}` | "
                    f"{escape_markdown_table(str(memory.get('content', '')))} |"
                )
        outliers = audit.get("outlierMemories", [])
        if isinstance(outliers, list) and outliers:
            lines.extend(["", "Outliers:", ""])
            for outlier in outliers:
                if isinstance(outlier, dict):
                    lines.append(
                        f"- `{outlier.get('id')}` "
                        f"(avg similarity {outlier.get('averageSimilarityToCluster')}): "
                        f"{outlier.get('content')}"
                    )
        lines.append("")
    return lines
