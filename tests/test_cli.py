from pathlib import Path

from typer.testing import CliRunner

from memd.cli.app import app

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Analyze agent memory exports locally" in result.output


def test_cli_analyze_json_output() -> None:
    result = CliRunner().invoke(
        app,
        ["analyze", str(FIXTURES / "memories.json"), "--format", "json"],
    )

    assert result.exit_code == 0
    assert '"totalMemories": 3' in result.output
    assert '"categoryBreakdown"' in result.output
    assert '"content": "User prefers dark mode"' in result.output
    assert '"validation"' in result.output
    assert '"reason"' in result.output
    assert '"insights"' in result.output
    assert '"recommendedAction"' in result.output
    assert '"largestClusterAudit"' in result.output
    assert '"trustedCompressionOpportunity"' in result.output
    assert '"unverifiedCompressionOpportunity"' in result.output
    assert '"clusterTrust"' in result.output
    assert '"highTrustClusters"' in result.output
    assert '"categoryAgreementRate"' in result.output
    assert '"reclassificationOpportunityCount"' in result.output
    assert '"categoryConsistency"' in result.output
    assert '"categoryAuditV2"' in result.output
    assert '"topUnknownCauses"' in result.output
    assert '"suggestedTaxonomyGaps"' in result.output
    assert '"categoryConfidenceDistribution"' in result.output
    assert '"taxonomyDiscovery"' in result.output
    assert '"candidateCategories"' in result.output
    assert '"semanticThemeAnalysis"' in result.output
    assert '"candidateSemanticCategories"' in result.output
    assert '"unknownResolutionAudit"' in result.output
    assert '"classifierFailureCount"' in result.output
    assert '"taxonomyGapCount"' in result.output
    assert '"memoryEvolutionAudit"' in result.output
    assert '"evolutionConfidence"' in result.output
    assert '"memoryLifecycle"' in result.output
    assert '"lifecycleCounts"' in result.output
    assert '"memoryLifecycleAssignments"' in result.output
    assert '"actionSummary"' in result.output
    assert '"actions"' in result.output
    assert '"totalActions"' in result.output
    assert '"policySummary"' in result.output
    assert '"policyDecision"' in result.output
    assert '"policyExplanation"' in result.output
    assert '"workflowPlan"' in result.output
    assert '"plannerVersion": "2"' in result.output


def test_cli_analyze_terminal_includes_workflow_summary_and_notice() -> None:
    result = CliRunner().invoke(
        app,
        ["analyze", str(FIXTURES / "memories.json"), "--format", "terminal"],
    )

    assert result.exit_code == 0
    assert "Workflow Plan:" in result.output
    assert "Planner state: initial" in result.output
    assert "Planning only — operator decisions have not been applied." in result.output


def test_cli_analyze_terminal_has_no_approval_prompt() -> None:
    result = CliRunner().invoke(
        app,
        ["analyze", str(FIXTURES / "memories.json"), "--format", "terminal"],
    )

    assert result.exit_code == 0
    workflow_section = result.output.split("Workflow Plan:", maxsplit=1)[-1].lower()
    assert "approve item" not in workflow_section
    assert "interactive" not in workflow_section


def test_cli_analyze_markdown_includes_workflow_plan_hierarchy() -> None:
    result = CliRunner().invoke(
        app,
        ["analyze", str(FIXTURES / "memories.json"), "--format", "markdown"],
    )

    assert result.exit_code == 0
    assert "# Mem-D Analysis Report" in result.output
    simulation = result.output.index("## Simulation Summary")
    workflow = result.output.index("## Workflow Plan")
    compression = result.output.index("## Compression Explanation")
    assert simulation < workflow < compression
    assert "Planning only" in result.output
    workflow_section = result.output[workflow:compression].lower()
    assert "approve item" not in workflow_section
    assert "interactive" not in workflow_section
    assert "executed" not in workflow_section


def test_cli_analyze_accepts_policy_profile() -> None:
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(FIXTURES / "memories.json"),
            "--format",
            "json",
            "--policy",
            "conservative",
        ],
    )

    assert result.exit_code == 0
    assert '"profile": "conservative"' in result.output


def test_cli_evaluate_clusters_json_output() -> None:
    result = CliRunner().invoke(
        app,
        [
            "evaluate-clusters",
            "datasets/validation/clustering_quality.json",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"precision"' in result.output
    assert '"falsePositives"' in result.output
    assert '"falseNegatives"' in result.output
    assert '"insights"' in result.output
