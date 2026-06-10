from pathlib import Path

import pytest

from memd.parser import load_memory_file

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("name", ["memories.json", "memories.csv", "memories.txt"])
def test_load_memory_file_supported_formats(name: str) -> None:
    records = load_memory_file(FIXTURES / name)

    assert len(records) == 3
    assert records[0].content == "User prefers dark mode"
    assert all(record.id for record in records)


def test_load_utf16_json(tmp_path: Path) -> None:
    path = tmp_path / "memories.json"
    path.write_text(
        '[{"id": "mem_1", "content": "User runs Kubernetes in production."}]',
        encoding="utf-16",
    )

    records = load_memory_file(path)

    assert len(records) == 1
    assert records[0].content == "User runs Kubernetes in production."
