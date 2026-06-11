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
