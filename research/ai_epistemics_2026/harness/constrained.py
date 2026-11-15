"""One common, label-blind JSON constraint over the unchanged real local transport."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.metadata import version

from .artifacts import RESEARCH, object_hash
from .local_solver import LocalTransport


def schema() -> dict:
    return json.loads((RESEARCH / "answer-schema.json").read_text())


def parser():
    from lmformatenforcer import CharacterLevelParserConfig, JsonSchemaParser

    # Explicit values prevent LMFE environment defaults changing the experiment.
    config = CharacterLevelParserConfig(
        alphabet="".join(chr(c) for c in range(32, 127)),
        max_consecutive_whitespaces=12,
        force_json_field_order=False,
        max_json_array_length=20,
    )
    return JsonSchemaParser(schema(), config)


class ConstrainedModel:
    """Inject the supported generate callback; never patch global or historical code."""

    def __init__(self, model, tokenizer):
        from lmformatenforcer.integrations.transformers import build_token_enforcer_tokenizer_data

        self.model = model
        self.generation_config = model.generation_config
        self.tokenizer_data = build_token_enforcer_tokenizer_data(tokenizer)

    def generate(self, **kwargs):
        from lmformatenforcer.integrations.transformers import (
            build_transformers_prefix_allowed_tokens_fn,
        )

        if "prefix_allowed_tokens_fn" in kwargs:
            raise ValueError("Only the single frozen common constraint is permitted")
        # Fresh parser/enforcer state for every submission, including retries.
        callback = build_transformers_prefix_allowed_tokens_fn(self.tokenizer_data, parser())
        return self.model.generate(**kwargs, prefix_allowed_tokens_fn=callback)


class ConstrainedTransport(LocalTransport):
    def __init__(self, model_path, identity: dict, generation: dict, limits: dict):
        lock = json.loads((RESEARCH / "interface-lock.json").read_text())
        for package, key in (
            ("lm-format-enforcer", "lm_format_enforcer"),
            ("interegular", "interegular"),
        ):
            if version(package) != lock[key]:
                raise ValueError(f"Constraint dependency differs from lock: {package}")
        super().__init__(model_path, identity, generation, limits)
        self.model = ConstrainedModel(self.model, self.tokenizer)

    def submit(self, request: dict) -> dict:
        result = super().submit(request)
        return {
            **result,
            "constraint": {
                "implementation": "lm-format-enforcer==0.11.3",
                "schema_sha256": object_hash(schema()),
                "state": "fresh per submission",
                "answer_options": deepcopy(schema()["properties"]["answer_label"]["enum"]),
            },
        }
