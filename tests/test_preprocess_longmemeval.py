from pathlib import Path

import pytest

from memd.parser.loaders import ParserError
from memd.preprocessing.longmemeval import (
    is_conversational_filler,
    is_excluded_content,
    preprocess_longmemeval_jsonl,
    removal_reason,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "longmemeval_audit_sample.jsonl"
EVAL_SAMPLE = Path("datasets/evaluation/longmemeval_sample.jsonl")


def test_removal_reason_detects_assistant_turn() -> None:
    record = {"role": "assistant", "content": "Sure, here are some tips."}

    assert removal_reason(record) == "assistant"


def test_removal_reason_detects_puzzle_content() -> None:
    record = {
        "role": "user",
        "content": "The farmer needs to transport a fox, a chicken, and some grain across a river.",
    }

    assert removal_reason(record) == "excluded_content"


def test_removal_reason_detects_ephemeral_user_query_as_filler() -> None:
    record = {"role": "user", "content": "Can you give me numbered topics on radiation therapy?"}

    assert removal_reason(record) == "filler"


def test_removal_reason_keeps_personal_user_memory() -> None:
    record = {
        "role": "user",
        "content": "I bought my Fitbit Inspire HR on February 15th.",
    }

    assert removal_reason(record) is None


def test_preprocess_longmemeval_jsonl_writes_cleaned_dataset(tmp_path: Path) -> None:
    output_path = tmp_path / "cleaned.jsonl"

    report = preprocess_longmemeval_jsonl(SAMPLE, output_path)

    assert report.originalRecordCount == 6
    assert report.removedAssistantTurns == 1
    assert report.removedFillerRecords >= 1
    assert report.removedExcludedContent == 1
    assert report.removedDuplicateRecords == 1
    assert report.finalRecordCount == 2
    assert report.retentionPercentage == pytest.approx(33.33)
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert "Fitbit" in lines[0]
    assert "Serenity Yoga" in lines[1]


def test_preprocess_deduplicates_on_normalized_content(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jsonl"
    input_path.write_text(
        '\n'.join(
            [
                '{"memory_id": "a", "role": "user", "content": "Hello   world"}',
                '{"memory_id": "b", "role": "user", "content": "hello world"}',
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "cleaned.jsonl"

    report = preprocess_longmemeval_jsonl(input_path, output_path)

    assert report.originalRecordCount == 2
    assert report.removedDuplicateRecords == 1
    assert report.finalRecordCount == 1


def test_preprocess_rejects_malformed_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.jsonl"
    input_path.write_text('{"role": "user", "content": "ok"}\n{bad}\n', encoding="utf-8")
    output_path = tmp_path / "cleaned.jsonl"

    with pytest.raises(ParserError, match="Invalid JSONL on line 2"):
        preprocess_longmemeval_jsonl(input_path, output_path)


def test_is_conversational_filler_detects_generic_closings() -> None:
    assert is_conversational_filler("Hope this helps if you need more guidance.", "user")


def test_is_excluded_content_detects_roleplay_requests() -> None:
    assert is_excluded_content("Rewrite the script for the bank heist scene.")


@pytest.mark.skipif(not EVAL_SAMPLE.exists(), reason="LongMemEval sample dataset not present")
def test_preprocess_longmemeval_sample_retains_meaningful_share() -> None:
    output_dir = Path("examples/benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "longmemeval_sample.cleaned.jsonl"

    report = preprocess_longmemeval_jsonl(EVAL_SAMPLE, output_path)

    assert report.originalRecordCount == 2690
    assert report.removedAssistantTurns == 1355
    assert report.finalRecordCount > 800
    assert report.retentionPercentage > 30.0
