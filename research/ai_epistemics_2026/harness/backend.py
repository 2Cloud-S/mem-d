"""Pinned local models and observation of the genuine mem-d pipeline."""

from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from memd import pipeline
from memd.contracts import PolicyProfile
from memd.embeddings import EmbeddingEngine
from memd.similarity import cosine_similarity_matrix

from .artifacts import canonical, digest, object_hash
from .transform import memory_input


class BackendInvalid(RuntimeError):
    """The requested real backend was not verified; no valid experiment exists."""


def snapshot(spec: dict, cache: Path, download: bool, *, tokenizer_only: bool = False) -> tuple:
    from huggingface_hub import snapshot_download

    revision = spec["revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise BackendInvalid("An immutable 40-character model revision is required")
    patterns = ["*.json", "*.txt"]
    if not tokenizer_only:
        patterns.append("*.safetensors")
    path = Path(
        snapshot_download(
            repo_id=spec["repo_id"],
            revision=revision,
            cache_dir=str(cache),
            allow_patterns=patterns,
            local_files_only=not download,
        )
    )
    if path.name != revision:
        raise BackendInvalid("Snapshot directory does not match requested revision")
    files = {
        str(p.relative_to(path)): digest(p.read_bytes())
        for p in sorted(path.rglob("*"))
        if p.is_file()
    }
    if not files:
        raise BackendInvalid("Empty model snapshot")
    return path, {**spec, "files_sha256": files}


class VerifiedEngine(EmbeddingEngine):
    """Observe parent success, then reject its silent fallback rather than replace it."""

    def __init__(self, model_path: Path):
        super().__init__(model_name=str(model_path))
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(1)
        torch.manual_seed(2026)
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True, trust_remote_code=False
        )
        self._model.eval()
        self.real_vectors = None
        self.last_embeddings = None

    def _embed_with_sentence_transformers(self, texts):
        vectors = super()._embed_with_sentence_transformers(texts)
        self.real_vectors = vectors.copy()
        return vectors

    def _embed_texts(self, texts):
        self.real_vectors = None
        vectors = super()._embed_texts(texts)
        if self.real_vectors is None or not np.array_equal(vectors, self.real_vectors):
            raise BackendInvalid("mem-d silently used hashing or an unverified embedding path")
        if not np.isfinite(vectors).all() or vectors.shape != (len(texts), 384):
            raise BackendInvalid("Invalid real embedding dimensions or values")
        return vectors

    def embed(self, records):
        self.last_embeddings = super().embed(records)
        return self.last_embeddings


class MemdAdapter:
    def __init__(self, engine: VerifiedEngine):
        self.engine = engine

    def analyze(self, records: list[dict], threshold: float) -> dict:
        public = memory_input(records)
        before = object_hash(public)
        captured = {}
        failures = []
        genuine_simulate = pipeline.simulate_recommendations
        genuine_workflow = pipeline.plan_workflows

        def observe_simulate(report):
            captured["report"] = report
            captured["hash"] = object_hash(report.model_dump(mode="json"))
            try:
                return genuine_simulate(report)
            except Exception as error:
                failures.append(("simulation", error))
                raise

        def observe_workflow(report):
            try:
                return genuine_workflow(report)
            except Exception as error:
                failures.append(("workflow", error))
                raise

        completed = True
        with TemporaryDirectory(prefix="memd-research-") as directory:
            path = Path(directory) / "memories.json"
            path.write_text(canonical(public), encoding="utf-8")
            file_before = path.read_bytes()
            # Scoped observation only. All evidence and recommendation functions stay genuine.
            with (
                patch.object(pipeline, "EmbeddingEngine", return_value=self.engine),
                patch.object(pipeline, "simulate_recommendations", side_effect=observe_simulate),
                patch.object(pipeline, "plan_workflows", side_effect=observe_workflow),
            ):
                try:
                    pipeline.analyze_file(
                        path,
                        threshold=threshold,
                        model_name=self.engine.model_name,
                        policy_profile=PolicyProfile.BALANCED,
                    )
                except Exception as error:
                    if not captured or not failures or failures[-1][1] is not error:
                        raise
                    completed = False
            if path.read_bytes() != file_before or object_hash(public) != before:
                raise BackendInvalid("Source records changed during analysis")
        report = captured["report"]
        if object_hash(report.model_dump(mode="json")) != captured["hash"]:
            raise BackendInvalid("Recommendation report mutated during downstream processing")
        ids = [m.id for m in report.memories]
        if ids != [m["id"] for m in public]:
            raise BackendInvalid("Normalization dropped or changed original IDs")
        embeddings = self.engine.last_embeddings
        if embeddings is None or [e.memoryId for e in embeddings] != ids:
            raise BackendInvalid("Pipeline embeddings cannot be matched to original IDs")
        payload = report.model_dump(mode="json")
        return {
            "similarities": cosine_similarity_matrix(embeddings).tolist(),
            "embedding_sha256": object_hash([e.model_dump(mode="json") for e in embeddings]),
            "clusters": payload["clusters"],
            "recommendations": payload["recommendations"],
            "resolutions": payload["memoryResolutions"],
            "actions": payload["actions"],
            "categories": payload["categories"],
            "validation": payload["validation"],
            "policy_summary": payload["policySummary"],
            "pipeline_completed": completed,
            "post_recommendation_failure": {
                "stage": failures[-1][0],
                "type": type(failures[-1][1]).__name__,
                "message": str(failures[-1][1]),
            }
            if failures
            else None,
        }


class TokenCounter:
    def __init__(self, path: Path | None, provenance: dict | None = None):
        self.info = provenance or {"available": False, "reason": "No pinned tokenizer available"}
        self.tokenizer = None
        if path is not None:
            from transformers import AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(
                str(path), local_files_only=True, trust_remote_code=False
            )
            self.info = {
                **self.info,
                "available": True,
                "class": type(self.tokenizer).__name__,
                "add_special_tokens": False,
                "truncation": False,
            }

    def count(self, memories: list[dict]) -> int | None:
        if self.tokenizer is None:
            return None
        return len(
            self.tokenizer.encode(canonical(memories), add_special_tokens=False, truncation=False)
        )
