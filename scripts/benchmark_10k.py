from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from memd.pipeline import analyze_file


def main() -> None:
    memories = [
        {"id": f"mem_{index}", "content": f"User prefers dark mode variant {index % 50}"}
        for index in range(10_000)
    ]

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "memories.json"
        path.write_text(json.dumps(memories), encoding="utf-8")

        started = time.perf_counter()
        report = analyze_file(path, threshold=0.85)
        elapsed = time.perf_counter() - started

    print(f"Analyzed {report.metrics.totalMemories} memories in {elapsed:.2f}s")
    print(f"Duplicate clusters: {len(report.clusters)}")
    print(f"Compression opportunity: {report.metrics.compressionOpportunity}%")


if __name__ == "__main__":
    main()
