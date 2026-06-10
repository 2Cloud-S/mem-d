from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence

from memd.contracts import CategorizedMemory, DuplicateCluster, MemoryCategory, MemoryRecord

TOKEN_RE = re.compile(r"[a-z][a-z0-9+-]{2,}", re.IGNORECASE)
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "user",
    "users",
    "that",
    "this",
    "from",
    "into",
    "all",
    "over",
    "under",
    "when",
    "where",
    "than",
    "then",
    "their",
    "they",
    "are",
    "has",
    "uses",
    "use",
    "using",
}


def enrich_clusters(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
    clusters: Sequence[DuplicateCluster],
) -> list[DuplicateCluster]:
    records_by_id = {record.id: record for record in records}
    categories_by_id = {category.memoryId: category for category in categories}
    enriched: list[DuplicateCluster] = []

    for cluster in clusters:
        cluster_records = [
            records_by_id[member]
            for member in cluster.members
            if member in records_by_id
        ]
        shared_terms = common_terms(record.content for record in cluster_records)
        category_counts = Counter(
            categories_by_id[record.id].category
            for record in cluster_records
            if record.id in categories_by_id
        )
        reasons = [
            f"{len(cluster.members)} records grouped by embedding similarity",
            f"average similarity {cluster.averageSimilarity:.2f}",
        ]
        if shared_terms:
            reasons.append(f"shared terms: {', '.join(shared_terms[:6])}")
        if category_counts:
            top_category, count = category_counts.most_common(1)[0]
            reasons.append(
                f"dominant category: {top_category.value} ({count}/{len(cluster.members)})"
            )

        enriched.append(
            cluster.model_copy(
                update={
                    "sharedTerms": tuple(shared_terms),
                    "reasons": tuple(reasons),
                }
            )
        )

    return enriched


def build_validation_summary(
    records: Sequence[MemoryRecord],
    categories: Sequence[CategorizedMemory],
    clusters: Sequence[DuplicateCluster],
) -> dict[str, object]:
    records_by_id = {record.id: record for record in records}
    categories_by_id = {category.memoryId: category for category in categories}
    unknown = [
        category
        for category in categories
        if category.category == MemoryCategory.UNKNOWN
    ]
    low_confidence = sorted(categories, key=lambda category: category.confidence)[:15]
    largest_clusters = sorted(clusters, key=lambda cluster: len(cluster.members), reverse=True)[:10]
    suspicious_clusters = [
        cluster_quality(cluster, records_by_id, categories_by_id)
        for cluster in clusters
        if is_suspicious_cluster(cluster, categories_by_id)
    ][:15]
    exact_duplicate_groups = exact_duplicate_summary(records)

    return {
        "categoryQuality": {
            "unknownCount": len(unknown),
            "unknownPercentage": percentage(len(unknown), len(records)),
            "unknownSamples": [
                sample_category(category, records_by_id)
                for category in unknown[:20]
            ],
            "lowConfidenceSamples": [
                sample_category(category, records_by_id)
                for category in low_confidence
            ],
            "interpretation": unknown_interpretation(unknown, records_by_id),
        },
        "clusterQuality": {
            "largestClusters": [
                cluster_quality(cluster, records_by_id, categories_by_id)
                for cluster in largest_clusters
            ],
            "possibleFalsePositiveClusters": suspicious_clusters,
            "exactDuplicateGroups": exact_duplicate_groups[:10],
        },
        "compressionDrivers": compression_drivers(records, clusters, records_by_id),
    }


def common_terms(contents: Iterable[str], limit: int = 8) -> list[str]:
    counter: Counter[str] = Counter()
    document_counts: defaultdict[str, int] = defaultdict(int)
    contents_list = list(contents)
    for content in contents_list:
        terms = set(tokens(str(content)))
        for term in terms:
            document_counts[term] += 1
        counter.update(tokens(str(content)))

    minimum_docs = 2 if len(contents_list) > 1 else 1
    ranked = [
        (term, count)
        for term, count in counter.items()
        if document_counts[term] >= minimum_docs
    ]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]


def tokens(content: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(content)
        if token.lower() not in STOPWORDS
    ]


def sample_category(
    category: CategorizedMemory,
    records_by_id: dict[str, MemoryRecord],
) -> dict[str, object]:
    record = records_by_id.get(category.memoryId)
    return {
        "memoryId": category.memoryId,
        "content": record.content if record else "",
        "category": category.category.value,
        "confidence": category.confidence,
        "reason": category.reason,
        "matchedSignals": list(category.matchedSignals),
    }


def cluster_quality(
    cluster: DuplicateCluster,
    records_by_id: dict[str, MemoryRecord],
    categories_by_id: dict[str, CategorizedMemory],
) -> dict[str, object]:
    records = [records_by_id[member] for member in cluster.members if member in records_by_id]
    category_counts = Counter(
        categories_by_id[record.id].category.value
        for record in records
        if record.id in categories_by_id
    )
    return {
        "clusterId": cluster.clusterId,
        "size": len(cluster.members),
        "averageSimilarity": cluster.averageSimilarity,
        "sharedTerms": list(cluster.sharedTerms),
        "categoryMix": dict(category_counts),
        "records": [
            {"id": record.id, "content": record.content}
            for record in records[:8]
        ],
        "reasons": list(cluster.reasons),
    }


def is_suspicious_cluster(
    cluster: DuplicateCluster,
    categories_by_id: dict[str, CategorizedMemory],
) -> bool:
    categories = {
        categories_by_id[member].category
        for member in cluster.members
        if member in categories_by_id
    }
    return cluster.averageSimilarity < 0.88 or len(categories) > 2 or not cluster.sharedTerms


def exact_duplicate_summary(records: Sequence[MemoryRecord]) -> list[dict[str, object]]:
    grouped: defaultdict[str, list[MemoryRecord]] = defaultdict(list)
    for record in records:
        grouped[normalize_for_duplicate_check(record.content)].append(record)

    duplicates = [
        {
            "content": group[0].content,
            "count": len(group),
            "ids": [record.id for record in group[:20]],
        }
        for group in grouped.values()
        if len(group) > 1
    ]
    duplicates.sort(key=lambda item: int(item["count"]), reverse=True)
    return duplicates


def compression_drivers(
    records: Sequence[MemoryRecord],
    clusters: Sequence[DuplicateCluster],
    records_by_id: dict[str, MemoryRecord],
) -> dict[str, object]:
    largest = sorted(clusters, key=lambda cluster: len(cluster.members), reverse=True)[:5]
    duplicate_members = {member for cluster in clusters for member in cluster.members}
    removable = max(0, len(duplicate_members) - len(clusters))
    return {
        "formula": (
            "compressionOpportunity = "
            "(duplicate members - duplicate clusters) / total memories"
        ),
        "duplicateMembers": len(duplicate_members),
        "clusters": len(clusters),
        "estimatedRemovableRecords": removable,
        "totalMemories": len(records),
        "largestClusterDrivers": [
            {
                "clusterId": cluster.clusterId,
                "size": len(cluster.members),
                "removableRecords": max(0, len(cluster.members) - 1),
                "sharedTerms": list(cluster.sharedTerms),
                "sampleContents": [
                    records_by_id[member].content
                    for member in cluster.members[:5]
                    if member in records_by_id
                ],
            }
            for cluster in largest
        ],
        "recurringThemes": top_cluster_terms(clusters),
    }


def top_cluster_terms(clusters: Sequence[DuplicateCluster]) -> list[dict[str, object]]:
    counter: Counter[str] = Counter()
    for cluster in clusters:
        counter.update(cluster.sharedTerms[:5])
    return [
        {"term": term, "clusters": count}
        for term, count in counter.most_common(15)
    ]


def unknown_interpretation(
    unknown: Sequence[CategorizedMemory],
    records_by_id: dict[str, MemoryRecord],
) -> dict[str, object]:
    contents = [
        records_by_id[category.memoryId].content
        for category in unknown
        if category.memoryId in records_by_id
    ]
    terms = common_terms(contents, limit=15)
    return {
        "summary": (
            "Unknown means no current V1 heuristic matched. It can indicate a true edge case, "
            "a missing rule, or content that belongs to a future category."
        ),
        "commonTerms": terms,
        "likelyAction": (
            "Inspect samples and either accept them as uncategorizable or add explainable "
            "heuristics when the same pattern repeats."
        ),
    }


def normalize_for_duplicate_check(content: str) -> str:
    return " ".join(tokens(content))


def percentage(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round((part / whole) * 100, 2)
