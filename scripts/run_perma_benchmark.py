from __future__ import annotations

import argparse
import json
from pathlib import Path

from memd.benchmarks.workflow import run_dataset_benchmark
from memd.defaults import DEFAULT_SIMILARITY_THRESHOLD


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a PERMA memory export and run Mem-D benchmark artifacts "
            "(audit + analyze + baseline)."
        ),
    )
    parser.add_argument(
        "--perma-root",
        type=Path,
        default=Path("datasets/perma"),
        help="PERMA dataset root (default: datasets/perma).",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="user108",
        help="PERMA user id under profile/ (default: user108).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("examples/benchmarks"),
        help="Directory for benchmark artifacts (default: examples/benchmarks).",
    )
    parser.add_argument(
        "--stem",
        type=str,
        default=None,
        help="Artifact stem (default: perma_<user-id>).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Duplicate similarity threshold (default: {DEFAULT_SIMILARITY_THRESHOLD}).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Optional local embedding model name.",
    )
    return parser


def build_perma_memory_export(perma_root: Path, user_id: str, destination: Path) -> tuple[Path, int]:
    profile_path = perma_root / "profile" / user_id / "profile.json"
    tasks_path = perma_root / "profile" / user_id / "tasks.json"

    if not profile_path.exists():
        raise FileNotFoundError(f"Missing profile file: {profile_path}")
    if not tasks_path.exists():
        raise FileNotFoundError(f"Missing tasks file: {tasks_path}")

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

    records: list[dict[str, object]] = []
    affinity_records = _affinity_memories(user_id, profile)
    task_records = _task_memories(user_id, tasks)
    records.extend(affinity_records)
    records.extend(task_records)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return destination, len(records)


def _affinity_memories(user_id: str, profile: dict[str, object]) -> list[dict[str, object]]:
    memories: list[dict[str, object]] = []
    affinities = profile.get("affinities")
    if not isinstance(affinities, dict):
        return memories
    counter = 0
    for domain, domain_payload in sorted(affinities.items()):
        if not isinstance(domain_payload, dict):
            continue
        for field, value in sorted(domain_payload.items()):
            rendered = _render_value(value)
            if not rendered:
                continue
            counter += 1
            content = f"User {user_id} preference in {domain}: {field} = {rendered}."
            memories.append(
                {
                    "id": f"perma_{user_id}_affinity_{counter}",
                    "content": content,
                    "source": f"perma/profile/{user_id}/profile.json",
                }
            )
    return memories


def _task_memories(user_id: str, tasks: dict[str, object]) -> list[dict[str, object]]:
    memories: list[dict[str, object]] = []
    if not isinstance(tasks, dict):
        return memories
    counter = 0
    for task_name, payload in sorted(tasks.items()):
        if not isinstance(payload, dict):
            continue
        task_id = payload.get("task_id")
        intent = payload.get("User Intent")
        goal = payload.get("Task Goal")

        if isinstance(task_id, str) and isinstance(intent, str) and intent.strip():
            counter += 1
            memories.append(
                {
                    "id": f"perma_{user_id}_task_intent_{counter}",
                    "content": f"PERMA {task_id} intent: {intent.strip()}",
                    "source": f"perma/profile/{user_id}/tasks.json",
                    "metadata": {"taskName": task_name},
                }
            )
        if isinstance(task_id, str) and isinstance(goal, str) and goal.strip():
            counter += 1
            memories.append(
                {
                    "id": f"perma_{user_id}_task_goal_{counter}",
                    "content": f"PERMA {task_id} goal: {goal.strip()}",
                    "source": f"perma/profile/{user_id}/tasks.json",
                    "metadata": {"taskName": task_name},
                }
            )
    return memories


def _render_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    if value is None:
        return ""
    return str(value).strip()


def main() -> None:
    args = build_parser().parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.stem or f"perma_{args.user_id}"
    generated_input = output_dir / f"{stem}.input.jsonl"

    input_path, record_count = build_perma_memory_export(
        args.perma_root.resolve(),
        args.user_id,
        generated_input,
    )
    result = run_dataset_benchmark(
        input_path,
        output_dir,
        stem=stem,
        threshold=args.threshold,
        model_name=args.model,
    )

    print("PERMA benchmark complete")
    print(f"PERMA user: {args.user_id}")
    print(f"Generated records: {record_count}")
    print(f"Input: {input_path}")
    print(f"Output directory: {result.output_dir}")
    print(f"Stem: {result.stem}")
    for label, path in result.paths.items():
        if path.exists():
            print(f"{label}: {path}")


if __name__ == "__main__":
    main()

