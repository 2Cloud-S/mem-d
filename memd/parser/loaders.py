from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from memd.contracts import MemoryRecord
from memd.ids import stable_id

CONTENT_KEYS = ("content", "text", "memory", "message", "value")
COLLECTION_KEYS = ("memories", "items", "records", "data")


class ParserError(ValueError):
    """Raised when an input file cannot be converted into memory records."""


def load_memory_file(path: Path) -> list[MemoryRecord]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json(path)
    if suffix == ".csv":
        return load_csv(path)
    if suffix == ".txt":
        return load_txt(path)
    raise ParserError(f"Unsupported input format: {suffix or '<none>'}")


def load_json(path: Path) -> list[MemoryRecord]:
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise ParserError(f"Invalid JSON: {exc}") from exc

    records = _coerce_json_collection(data)
    return _records_from_items(records, source=str(path))


def load_csv(path: Path) -> list[MemoryRecord]:
    with path.open("r", encoding=detect_encoding(path), newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ParserError("CSV file must include a header row")
        return _records_from_items(list(reader), source=str(path))


def load_txt(path: Path) -> list[MemoryRecord]:
    lines = read_text(path).splitlines()
    items = [{"content": line} for line in lines if line.strip()]
    return _records_from_items(items, source=str(path))


def read_text(path: Path) -> str:
    return path.read_text(encoding=detect_encoding(path))


def detect_encoding(path: Path) -> str:
    prefix = path.read_bytes()[:4]
    if prefix.startswith(b"\xff\xfe") or prefix.startswith(b"\xfe\xff"):
        return "utf-16"
    if prefix.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return "utf-8"


def _coerce_json_collection(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in COLLECTION_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                return value
        return [data]
    raise ParserError("JSON root must be an object or array")


def _records_from_items(items: Iterable[Any], source: str) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(items, start=1):
        record = _record_from_item(item, source=source, index=index)
        if record.id in seen_ids:
            record = record.model_copy(update={"id": stable_id(source, index, record.content)})
        seen_ids.add(record.id)
        records.append(record)

    if not records:
        raise ParserError("No memory records found")
    return records


def _record_from_item(item: Any, source: str, index: int) -> MemoryRecord:
    if isinstance(item, str):
        content = item
        raw: dict[str, Any] = {}
    elif isinstance(item, dict):
        content = _extract_content(item)
        raw = item
    else:
        content = str(item)
        raw = {"raw": item}

    if not content or not str(content).strip():
        raise ParserError(f"Record {index} has no content")

    record_id = str(raw.get("id") or raw.get("memoryId") or stable_id(source, index, str(content)))
    metadata = {
        key: value
        for key, value in raw.items()
        if key not in {"id", "memoryId", "source", "timestamp", *CONTENT_KEYS}
    }
    return MemoryRecord(
        id=record_id,
        content=str(content),
        source=str(raw.get("source") or source),
        timestamp=raw.get("timestamp"),
        metadata=metadata,
    )


def _extract_content(item: dict[str, Any]) -> str | None:
    for key in CONTENT_KEYS:
        value = item.get(key)
        if value is not None:
            return str(value)
    return None
