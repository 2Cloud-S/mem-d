from __future__ import annotations

import re

from memd.contracts import MemoryRecord
from memd.ids import stable_id

WHITESPACE_RE = re.compile(r"\s+")


def normalize_records(records: list[MemoryRecord]) -> list[MemoryRecord]:
    normalized: list[MemoryRecord] = []
    seen_ids: set[str] = set()

    for index, record in enumerate(records, start=1):
        content = normalize_content(record.content)
        if not content:
            continue

        record_id = record.id.strip() if record.id else stable_id(index, content)
        if record_id in seen_ids:
            record_id = stable_id(record_id, index, content)
        seen_ids.add(record_id)

        metadata = {str(key): value for key, value in record.metadata.items()}
        normalized.append(
            MemoryRecord(
                id=record_id,
                content=content,
                source=record.source,
                timestamp=record.timestamp,
                metadata=metadata,
            )
        )

    return normalized


def normalize_content(content: str) -> str:
    return WHITESPACE_RE.sub(" ", content).strip()
