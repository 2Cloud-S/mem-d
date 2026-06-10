from __future__ import annotations

import re
from dataclasses import dataclass

from memd.contracts import CategorizedMemory, MemoryCategory, MemoryRecord


@dataclass(frozen=True)
class RuleSignal:
    label: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class CategoryRule:
    category: MemoryCategory
    signals: tuple[RuleSignal, ...]


def signal(label: str, pattern: str) -> RuleSignal:
    return RuleSignal(label=label, pattern=re.compile(pattern, re.IGNORECASE))


RULES: tuple[CategoryRule, ...] = (
    CategoryRule(
        MemoryCategory.PREFERENCE,
        tuple(
            [
                signal(
                    "explicit preference verb",
                    r"\b(prefers?|likes?|dislikes?|favorite|favourite|wants?)\b",
                ),
                signal("avoidance preference", r"\b(avoids?|avoid|never use|no\s+\w+)\b"),
                signal("acceptance preference", r"\b(fine with|okay with|ok with)\b"),
                signal("comparison preference", r"\bover\b|instead of|rather than"),
                signal("style rule", r"\b(style|rule|always wants|by default|soft target)\b"),
                signal(
                    "short-form preference",
                    r"^(REST|Fastify|const|interface|semver|Async-first)\b",
                ),
                signal("changed preference", r"\b(switched|moved)\s+(from|to|back to)\b"),
            ]
        ),
    ),
    CategoryRule(
        MemoryCategory.TASK,
        tuple(
            [
                signal("task marker", r"\b(todo|task|reminder|remind)\b"),
                signal(
                    "action item",
                    r"\b(follow up|fix|implement|ship|review|rotate|renew|merge|delete|enable)\b",
                ),
                signal("obligation phrase", r"\b(needs to|has to|should)\s+\w+"),
            ]
        ),
    ),
    CategoryRule(
        MemoryCategory.GOAL,
        tuple(
            [
                signal("goal marker", r"\b(goal|objective|aim|target|long-term goal)\b"),
                signal("future intent", r"\b(trying to|wants to|intends to|plans to)\b"),
                signal(
                    "outcome phrase",
                    r"\b(build|create|launch|learn|improve|adopt|migrate)\s+.+"
                    r"\b(by|so that|in order|team-wide)\b",
                ),
            ]
        ),
    ),
    CategoryRule(
        MemoryCategory.RELATIONSHIP,
        tuple(
            [
                signal(
                    "person or role relationship",
                    r"\b(manager|teammate|colleague|friend|partner|spouse|client)\b",
                ),
                signal(
                    "direct relationship phrase",
                    r"\b(works with|reports to|married to|related to)\b",
                ),
                signal(
                    "derived relationship",
                    r"\b(connects to|relates to|tied to|context for|directly connects to)\b",
                ),
                signal(
                    "cross-memory link",
                    r"\b(fact|goal|reminder|task)\b.+\b(context for|connects to|relates to)\b",
                ),
                signal("team collaboration context", r"\b(team|Sarah|Jess|DevOps|security team)\b"),
            ]
        ),
    ),
    CategoryRule(
        MemoryCategory.TEMPORARY,
        tuple(
            [
                signal(
                    "time-bounded phrase",
                    r"\b(today|tomorrow|tonight|this week|for now|currently|by end of sprint)\b",
                ),
                signal("calendar/event", r"\b(meeting|appointment|deadline|expires in \d+ days)\b"),
            ]
        ),
    ),
    CategoryRule(
        MemoryCategory.FACT,
        tuple(
            [
                signal("fact marker", r"^Fact:"),
                signal("state verb", r"\b(is|are|was|were|born|lives|located|has|owns|works as)\b"),
                signal(
                    "tool/process usage",
                    r"\b(uses|runs|codes in|logs with|provisions|monitors with|documents"
                    r" with|validates|maintains|writes|keeps|colocates|rebases|indents"
                    r"|follow|follows|guide|guides|live|lives|abstracts)\b",
                ),
                signal("tooling via phrase", r"\bvia\s+[A-Z][A-Za-z0-9+-]*\b"),
                signal("architecture/process pattern", r"\b(pattern|principles|checks|testing)\b"),
                signal(
                    "system/process fact",
                    r"\b(CI/CD|Kubernetes|Terraform|Grafana|Prometheus|Markdown|JSDoc|"
                    r"GitHub|Stripe|Redis|PostgreSQL|microservices|production)\b",
                ),
                signal(
                    "numeric operational fact",
                    r"\b\d+(\.\d+)?\s*(ms|days|weeks|engineers|requests|orgs|deploys|%)\b",
                ),
            ]
        ),
    ),
)


def categorize_records(records: list[MemoryRecord]) -> list[CategorizedMemory]:
    return [categorize_record(record) for record in records]


def categorize_record(record: MemoryRecord) -> CategorizedMemory:
    text = record.content
    best_category = MemoryCategory.UNKNOWN
    best_signals: list[str] = []

    for rule in RULES:
        matched = [signal.label for signal in rule.signals if signal.pattern.search(text)]
        if len(matched) > len(best_signals):
            best_signals = matched
            best_category = rule.category

    if not best_signals:
        confidence = 0.2
        reason = "No V1 heuristic matched; inspect manually."
    else:
        confidence = min(0.95, 0.55 + (len(best_signals) * 0.2))
        reason = f"Matched {best_category.value.lower()} signal(s): {', '.join(best_signals)}."

    return CategorizedMemory(
        memoryId=record.id,
        category=best_category,
        confidence=confidence,
        reason=reason,
        matchedSignals=tuple(best_signals),
    )
