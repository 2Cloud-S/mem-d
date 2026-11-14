"""Canonical serialization, artifact freezing, and reproducibility manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from typing import Any

THRESHOLDS = (0.45, 0.55, 0.65, 0.75, 0.85, 0.95)
ORDER_SEEDS = (2026, 2027, 2028)
SCHEDULE_SEED = 2026
ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parents[1]


def canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_hash(value: Any) -> str:
    return digest(canonical(value).encode())


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    from ..validate_development import unique_object

    return [
        json.loads(line, object_pairs_hook=unique_object)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def freeze(directory: Path, names: list[str], filename: str = "freeze.json") -> dict:
    target = directory / filename
    if target.exists():
        raise ValueError(f"Refusing to overwrite freeze: {target}")
    hashes = {name: digest((directory / name).read_bytes()) for name in names}
    write_json(target, hashes)
    return hashes


def verify(directory: Path, filename: str = "freeze.json") -> dict:
    hashes = json.loads((directory / filename).read_text())
    if not hashes or any(Path(name).name != name for name in hashes):
        raise ValueError("Invalid freeze manifest")
    for name, expected in hashes.items():
        if digest((directory / name).read_bytes()) != expected:
            raise ValueError(f"Frozen artifact changed: {name}")
    return hashes


def manifest(data: Path, lock: dict) -> dict:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    files = sorted(
        set(ROOT.glob("memd/**/*.py"))
        | set(RESEARCH.glob("**/*.py"))
        | {
            RESEARCH / "PROTOCOL.md",
            RESEARCH / "model-lock.json",
            RESEARCH / "requirements-phase2.txt",
            ROOT / "pyproject.toml",
        }
    )
    versions = {
        d.metadata["Name"]: d.version
        for d in importlib.metadata.distributions()
        if d.metadata["Name"]
    }
    for package in (
        "memd",
        "numpy",
        "scikit-learn",
        "pydantic",
        "torch",
        "transformers",
        "sentence-transformers",
        "huggingface-hub",
        "tokenizers",
        "pytest",
        "ruff",
    ):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "schema": "phase2-v1",
        "purpose": "development feasibility; no solver responses",
        "code_commit": git("rev-parse", "HEAD"),
        "worktree_status": git("status", "--short"),
        "source_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in files},
        "data_sha256": digest(data.read_bytes()),
        "model_lock": lock,
        "python": platform.python_version(),
        "dependencies": versions,
        "thresholds": THRESHOLDS,
        "min_samples": 2,
        "policy": "balanced",
        "order_seeds": ORDER_SEEDS,
        "schedule_seed": SCHEDULE_SEED,
        "bootstrap": {"resamples": 10000, "seed": 2026, "unit": "scenario_family"},
        "serialization": "compact sorted-key UTF-8 JSON array; no specials or truncation",
        "solver": {
            "model_id": "UNASSIGNED",
            "revision": "UNASSIGNED",
            "temperature": 0,
            "max_output_tokens": 256,
        },
    }
