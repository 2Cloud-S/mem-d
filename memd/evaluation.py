from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from memd.categorization import categorize_records
from memd.clustering import cluster_duplicates
from memd.contracts import DuplicateCluster, EmbeddedMemory, MemoryRecord
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD
from memd.embeddings import EmbeddingEngine
from memd.inspection import enrich_clusters
from memd.normalization import normalize_records
from memd.parser.loaders import detect_encoding
from memd.similarity import cosine_similarity_matrix


class EvaluationMemory(BaseModel):
    id: str
    content: str
    duplicateGroup: str | None = None
    duplicateType: str | None = None
    notes: str | None = None


class EvaluationDataset(BaseModel):
    name: str
    description: str = ""
    memories: list[EvaluationMemory]
    nonDuplicatePairs: list[tuple[str, str]] = Field(default_factory=list)


@dataclass(frozen=True)
class PairExample:
    memoryA: str
    memoryB: str
    contentA: str
    contentB: str
    similarity: float
    reason: str


@dataclass(frozen=True)
class ClusterEvaluation:
    datasetName: str
    threshold: float
    totalMemories: int
    trueDuplicatePairs: int
    predictedDuplicatePairs: int
    truePositives: int
    falsePositives: int
    falseNegatives: int
    precision: float
    recall: float
    f1: float
    clusterPurity: float
    clusterCoverage: float
    clusters: list[DuplicateCluster]
    falsePositiveExamples: list[PairExample]
    falseNegativeExamples: list[PairExample]
    clusterSummaries: list[dict[str, object]]


def load_evaluation_dataset(path: Path) -> EvaluationDataset:
    data = json.loads(path.read_text(encoding=detect_encoding(path)))
    return EvaluationDataset.model_validate(data)


def evaluate_dataset(
    path: Path,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    model_name: str | None = None,
) -> ClusterEvaluation:
    dataset = load_evaluation_dataset(path)
    records = normalize_records(
        [
            MemoryRecord(
                id=memory.id,
                content=memory.content,
                source=str(path),
                metadata={
                    "duplicateGroup": memory.duplicateGroup,
                    "duplicateType": memory.duplicateType,
                    "notes": memory.notes,
                },
            )
            for memory in dataset.memories
        ]
    )
    embeddings = EmbeddingEngine(model_name=model_name).embed(records)
    raw_clusters = cluster_duplicates(embeddings, threshold=threshold)
    categories = categorize_records(records)
    clusters = enrich_clusters(records, categories, raw_clusters)

    similarities = cosine_similarity_matrix(embeddings)
    similarity_by_pair = build_similarity_lookup(embeddings, similarities)
    true_pairs = expected_duplicate_pairs(dataset.memories)
    predicted_pairs = cluster_pairs(clusters)
    explicit_non_duplicates = {normalize_pair(*pair) for pair in dataset.nonDuplicatePairs}

    true_positives = predicted_pairs & true_pairs
    false_positives = predicted_pairs - true_pairs
    false_negatives = true_pairs - predicted_pairs

    precision = ratio(len(true_positives), len(predicted_pairs))
    recall = ratio(len(true_positives), len(true_pairs))
    f1 = ratio(2 * precision * recall, precision + recall)
    purity = cluster_purity(clusters, dataset.memories)
    coverage = cluster_coverage(clusters, dataset.memories)
    records_by_id = {record.id: record for record in records}

    return ClusterEvaluation(
        datasetName=dataset.name,
        threshold=threshold,
        totalMemories=len(records),
        trueDuplicatePairs=len(true_pairs),
        predictedDuplicatePairs=len(predicted_pairs),
        truePositives=len(true_positives),
        falsePositives=len(false_positives),
        falseNegatives=len(false_negatives),
        precision=precision,
        recall=recall,
        f1=f1,
        clusterPurity=purity,
        clusterCoverage=coverage,
        clusters=clusters,
        falsePositiveExamples=pair_examples(
            false_positives,
            records_by_id,
            similarity_by_pair,
            explicit_non_duplicates,
            "Predicted duplicate pair is not in a labelled duplicate group.",
        ),
        falseNegativeExamples=pair_examples(
            false_negatives,
            records_by_id,
            similarity_by_pair,
            explicit_non_duplicates,
            "Labelled duplicate pair was not clustered together.",
        ),
        clusterSummaries=cluster_summaries(clusters, dataset.memories, records_by_id),
    )


def expected_duplicate_pairs(memories: Sequence[EvaluationMemory]) -> set[tuple[str, str]]:
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for memory in memories:
        if memory.duplicateGroup:
            groups[memory.duplicateGroup].append(memory.id)
    return {
        normalize_pair(left, right)
        for members in groups.values()
        for left, right in combinations(members, 2)
    }


def cluster_pairs(clusters: Sequence[DuplicateCluster]) -> set[tuple[str, str]]:
    return {
        normalize_pair(left, right)
        for cluster in clusters
        for left, right in combinations(cluster.members, 2)
    }


def normalize_pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def build_similarity_lookup(
    embeddings: Sequence[EmbeddedMemory],
    similarities: Any,
) -> dict[tuple[str, str], float]:
    lookup: dict[tuple[str, str], float] = {}
    for row in range(len(embeddings)):
        for column in range(row + 1, len(embeddings)):
            lookup[normalize_pair(embeddings[row].memoryId, embeddings[column].memoryId)] = round(
                float(similarities[row, column]),
                4,
            )
    return lookup


def cluster_purity(
    clusters: Sequence[DuplicateCluster],
    memories: Sequence[EvaluationMemory],
) -> float:
    group_by_id = {memory.id: memory.duplicateGroup for memory in memories}
    weighted_correct = 0
    total_clustered = 0
    for cluster in clusters:
        labels = [
            group_by_id.get(member) or f"__singleton__:{member}"
            for member in cluster.members
        ]
        if not labels:
            continue
        counts = Counter(labels)
        weighted_correct += counts.most_common(1)[0][1]
        total_clustered += len(labels)
    return ratio(weighted_correct, total_clustered)


def cluster_coverage(
    clusters: Sequence[DuplicateCluster],
    memories: Sequence[EvaluationMemory],
) -> float:
    duplicate_memory_ids = {
        memory.id
        for memory in memories
        if memory.duplicateGroup
    }
    clustered_ids = {
        member
        for cluster in clusters
        for member in cluster.members
    }
    return ratio(len(duplicate_memory_ids & clustered_ids), len(duplicate_memory_ids))


def pair_examples(
    pairs: Iterable[tuple[str, str]],
    records_by_id: dict[str, MemoryRecord],
    similarity_by_pair: dict[tuple[str, str], float],
    explicit_non_duplicates: set[tuple[str, str]],
    default_reason: str,
    limit: int = 20,
) -> list[PairExample]:
    examples: list[PairExample] = []
    for left, right in sorted(pairs):
        pair = normalize_pair(left, right)
        reason = default_reason
        if pair in explicit_non_duplicates:
            reason = "Pair was explicitly labelled as non-duplicate."
        examples.append(
            PairExample(
                memoryA=left,
                memoryB=right,
                contentA=records_by_id[left].content,
                contentB=records_by_id[right].content,
                similarity=similarity_by_pair.get(pair, 0.0),
                reason=reason,
            )
        )
        if len(examples) >= limit:
            break
    return examples


def cluster_summaries(
    clusters: Sequence[DuplicateCluster],
    memories: Sequence[EvaluationMemory],
    records_by_id: dict[str, MemoryRecord],
) -> list[dict[str, object]]:
    memory_by_id = {memory.id: memory for memory in memories}
    summaries: list[dict[str, object]] = []
    for cluster in clusters:
        group_counts = Counter(
            memory_by_id[member].duplicateGroup or "unlabelled/non-duplicate"
            for member in cluster.members
            if member in memory_by_id
        )
        summaries.append(
            {
                "clusterId": cluster.clusterId,
                "size": len(cluster.members),
                "averageSimilarity": cluster.averageSimilarity,
                "sharedTerms": list(cluster.sharedTerms),
                "labelMix": dict(group_counts),
                "records": [
                    {
                        "id": member,
                        "duplicateGroup": memory_by_id[member].duplicateGroup,
                        "content": records_by_id[member].content,
                    }
                    for member in cluster.members
                    if member in memory_by_id and member in records_by_id
                ],
                "reasons": list(cluster.reasons),
            }
        )
    return summaries


def evaluation_to_dict(evaluation: ClusterEvaluation) -> dict[str, object]:
    return {
        "datasetName": evaluation.datasetName,
        "threshold": evaluation.threshold,
        "metrics": {
            "totalMemories": evaluation.totalMemories,
            "trueDuplicatePairs": evaluation.trueDuplicatePairs,
            "predictedDuplicatePairs": evaluation.predictedDuplicatePairs,
            "truePositives": evaluation.truePositives,
            "falsePositives": evaluation.falsePositives,
            "falseNegatives": evaluation.falseNegatives,
            "precision": evaluation.precision,
            "recall": evaluation.recall,
            "f1": evaluation.f1,
            "clusterPurity": evaluation.clusterPurity,
            "clusterCoverage": evaluation.clusterCoverage,
        },
        "clusters": evaluation.clusterSummaries,
        "mistakes": {
            "falsePositives": [
                pair_example_to_dict(example)
                for example in evaluation.falsePositiveExamples
            ],
            "falseNegatives": [
                pair_example_to_dict(example)
                for example in evaluation.falseNegativeExamples
            ],
        },
    }


def render_evaluation_json(evaluation: ClusterEvaluation) -> str:
    return json.dumps(evaluation_to_dict(evaluation), indent=2)


def render_evaluation_markdown(evaluation: ClusterEvaluation) -> str:
    metrics = evaluation_to_dict(evaluation)["metrics"]
    lines = [
        f"# Clustering Evaluation: {evaluation.datasetName}",
        "",
        f"- Threshold: {evaluation.threshold}",
        f"- Total memories: {metrics['totalMemories']}",
        f"- Precision: {metrics['precision']}",
        f"- Recall: {metrics['recall']}",
        f"- F1: {metrics['f1']}",
        f"- Cluster purity: {metrics['clusterPurity']}",
        f"- Cluster coverage: {metrics['clusterCoverage']}",
        "",
        "## Pair Metrics",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| True duplicate pairs | {metrics['trueDuplicatePairs']} |",
        f"| Predicted duplicate pairs | {metrics['predictedDuplicatePairs']} |",
        f"| True positives | {metrics['truePositives']} |",
        f"| False positives | {metrics['falsePositives']} |",
        f"| False negatives | {metrics['falseNegatives']} |",
        "",
        "## Clusters",
        "",
    ]
    if not evaluation.clusterSummaries:
        lines.append("No clusters predicted.")
    for cluster in evaluation.clusterSummaries:
        lines.extend(
            [
                f"### {cluster['clusterId']}",
                "",
                f"- Size: {cluster['size']}",
                f"- Average similarity: {cluster['averageSimilarity']}",
                f"- Shared terms: {', '.join(cluster['sharedTerms']) or 'none'}",
                f"- Label mix: {cluster['labelMix']}",
                f"- Why grouped: {'; '.join(cluster['reasons'])}",
                "",
                "| ID | Label | Content |",
                "| --- | --- | --- |",
            ]
        )
        for record in cluster["records"]:
            lines.append(
                f"| `{record['id']}` | {record['duplicateGroup'] or 'non-duplicate'} | "
                f"{escape_table(str(record['content']))} |"
            )
        lines.append("")

    lines.extend(render_pair_mistakes("False Positives", evaluation.falsePositiveExamples))
    lines.extend(render_pair_mistakes("False Negatives", evaluation.falseNegativeExamples))
    return "\n".join(lines).rstrip() + "\n"


def render_pair_mistakes(title: str, examples: Sequence[PairExample]) -> list[str]:
    lines = ["", f"## {title}", ""]
    if not examples:
        lines.append("None.")
        return lines
    lines.extend(["| Pair | Similarity | Reason |", "| --- | ---: | --- |"])
    for example in examples:
        lines.append(
            f"| `{example.memoryA}` / `{example.memoryB}` | {example.similarity} | "
            f"{escape_table(example.reason)} |"
        )
        lines.append(
            f"|  |  | {escape_table(example.contentA)} / {escape_table(example.contentB)} |"
        )
    return lines


def pair_example_to_dict(example: PairExample) -> dict[str, object]:
    return {
        "memoryA": example.memoryA,
        "memoryB": example.memoryB,
        "contentA": example.contentA,
        "contentB": example.contentB,
        "similarity": example.similarity,
        "reason": example.reason,
    }


def ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
