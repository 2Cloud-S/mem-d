from pathlib import Path

import pytest

from memd.parser import load_memory_file
from memd.parser.loaders import ParserError, load_jsonl

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "name",
    ["memories.json", "memories.csv", "memories.txt", "memories.jsonl"],
)
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


def test_load_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "memories.jsonl"
    path.write_text(
        '\n{"id": "mem_1", "content": "First memory"}\n\n'
        '{"id": "mem_2", "content": "Second memory"}\n',
        encoding="utf-8",
    )

    records = load_jsonl(path)

    assert len(records) == 2
    assert records[0].content == "First memory"
    assert records[1].content == "Second memory"


def test_load_jsonl_skips_empty_content(tmp_path: Path) -> None:
    path = tmp_path / "memories.jsonl"
    path.write_text(
        '\n'.join(
            [
                '{"id": "mem_1", "content": "Valid memory"}',
                '{"id": "mem_2", "content": ""}',
                '{"id": "mem_3", "content": "   "}',
                '{"id": "mem_4", "content": "Another valid memory"}',
            ]
        ),
        encoding="utf-8",
    )

    records = load_jsonl(path)

    assert len(records) == 2
    assert [record.id for record in records] == ["mem_1", "mem_4"]


def test_load_jsonl_reports_malformed_line_number(tmp_path: Path) -> None:
    path = tmp_path / "memories.jsonl"
    path.write_text(
        '{"id": "mem_1", "content": "Valid memory"}\n{bad json}\n',
        encoding="utf-8",
    )

    with pytest.raises(ParserError, match="Invalid JSONL on line 2"):
        load_jsonl(path)


def test_load_jsonl_reports_non_object_line(tmp_path: Path) -> None:
    path = tmp_path / "memories.jsonl"
    path.write_text(
        '{"id": "mem_1", "content": "Valid memory"}\n"not an object"\n',
        encoding="utf-8",
    )

    with pytest.raises(ParserError, match="JSONL line 2 must be a JSON object"):
        load_jsonl(path)


def test_load_jsonl_requires_at_least_one_valid_record(tmp_path: Path) -> None:
    path = tmp_path / "memories.jsonl"
    path.write_text('\n{"id": "mem_1", "content": ""}\n\n', encoding="utf-8")

    with pytest.raises(ParserError, match="No memory records found"):
        load_jsonl(path)


def test_load_jsonl_supports_memory_id_field(tmp_path: Path) -> None:
    path = tmp_path / "memories.jsonl"
    path.write_text(
        '{"memory_id": "lme_1", "content": "User bought a Fitbit on February 15th."}\n',
        encoding="utf-8",
    )

    records = load_jsonl(path)

    assert len(records) == 1
    assert records[0].id == "lme_1"
    assert "Fitbit" in records[0].content
