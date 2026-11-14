"""Minimal stateless CPU Transformers transport; real weights, no provider/API adapter."""

from __future__ import annotations

import time
from copy import deepcopy

from .artifacts import object_hash
from .requests import SYSTEM


def validate_request(request: dict, identity: dict) -> None:
    if set(request) != {"model", "messages"}:
        raise ValueError("Only allowlisted model/messages may reach the transport")
    config = request["model"]
    if set(config) != {
        "model_id",
        "revision",
        "temperature",
        "max_output_tokens",
        "generation_seed",
    }:
        raise ValueError("Unexpected solver configuration")
    if any(config[k] != identity[k] for k in ("model_id", "revision")):
        raise ValueError("Request model differs from pinned transport")
    if config["temperature"] != 0 or config["max_output_tokens"] != 256:
        raise ValueError("Generation settings differ from frozen pilot")
    if config["generation_seed"] not in (2026, 2027, 2028):
        raise ValueError("Unknown paired generation seed")
    messages = request["messages"]
    if (
        len(messages) != 2
        or messages[0] != {"role": "system", "content": SYSTEM}
        or set(messages[1]) != {"role", "content"}
        or messages[1]["role"] != "user"
    ):
        raise ValueError("Unexpected solver messages")
    import json

    from ..validate_development import unique_object

    payload = json.loads(messages[1]["content"], object_pairs_hook=unique_object)
    if set(payload) != {
        "memories",
        "question",
        "decision_criteria",
        "answer_options",
        "query_time",
    }:
        raise ValueError("Evaluator/routing fields leaked into solver payload")
    if any(
        not isinstance(payload[k], str) or not payload[k].strip()
        for k in ("question", "decision_criteria", "query_time")
    ):
        raise ValueError("Expected plain text question, criteria and query time")
    if payload["answer_options"] != ["proceed", "do_not_proceed", "insufficient_evidence"]:
        raise ValueError("Unexpected answer options")
    if not isinstance(payload["memories"], list) or not payload["memories"]:
        raise ValueError("Expected nonempty memory list")
    for memory in payload["memories"]:
        if set(memory) != {"id", "content", "source", "timestamp"}:
            raise ValueError("Unexpected memory annotation")
        if any(not isinstance(v, str) or not v.strip() for v in memory.values()):
            raise ValueError("Expected plain text memory fields")


def render_request(tokenizer, request: dict, identity: dict) -> dict:
    validate_request(request, identity)
    rendered = tokenizer.apply_chat_template(
        request["messages"], tokenize=False, add_generation_prompt=True
    )
    ids = tokenizer.encode(rendered, add_special_tokens=False, truncation=False)
    return {
        "rendered_prompt": rendered,
        "input_token_ids_sha256": object_hash(ids),
        "prompt_tokens": len(ids),
        "rendered_prompt_sha256": object_hash(rendered),
    }


class LocalTransport:
    provenance = "real"

    def __init__(self, model_path, identity: dict, generation: dict, limits: dict):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.set_num_threads(generation["torch_threads"])
        torch.use_deterministic_algorithms(generation["deterministic_algorithms"])
        self.identity, self.generation, self.limits = identity, generation, limits
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True, trust_remote_code=False
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.float32,
            attn_implementation="sdpa",
        )
        self.model.eval()
        self.started = time.perf_counter()

    def submit(self, request: dict) -> dict:
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        rendered = render_request(self.tokenizer, request, self.identity)
        now = time.perf_counter()
        if now - self.started >= self.limits["model_inference_seconds"]:
            return {
                "status": "infrastructure",
                "text": "",
                "message": "model inference budget exhausted",
                "inference_submitted": False,
                "latency_seconds": 0,
                "usage": None,
            }
        if rendered["prompt_tokens"] + 256 > self.generation["max_total_tokens"]:
            return {
                "status": "context_overflow",
                "text": "",
                "inference_submitted": False,
                "latency_seconds": 0,
                "usage": {"prompt_tokens": rendered["prompt_tokens"], "completion_tokens": 0},
            }
        deadline = min(
            self.started + self.limits["model_inference_seconds"],
            now + self.limits["submission_seconds"],
        )

        class Deadline(StoppingCriteria):
            expired = False

            def __call__(self, input_ids, scores, **kwargs):
                self.expired = time.perf_counter() >= deadline
                return self.expired

        stop = Deadline()
        inputs = self.tokenizer(
            rendered["rendered_prompt"],
            return_tensors="pt",
            add_special_tokens=False,
            truncation=False,
        )
        torch.manual_seed(request["model"]["generation_seed"])
        start = time.perf_counter()
        try:
            with torch.inference_mode():
                output = self.model.generate(
                    **inputs,
                    do_sample=False,
                    temperature=None,
                    top_p=None,
                    top_k=None,
                    max_new_tokens=256,
                    use_cache=True,
                    stopping_criteria=StoppingCriteriaList([stop]),
                    pad_token_id=(
                        self.tokenizer.pad_token_id
                        if self.tokenizer.pad_token_id is not None
                        else self.tokenizer.eos_token_id
                    ),
                )
        except RuntimeError as error:
            return {
                "status": "infrastructure",
                "text": "",
                "message": f"Local generation failure: {type(error).__name__}: {error}",
                "inference_submitted": True,
                "submitted_request": deepcopy(request),
                **rendered,
                "latency_seconds": time.perf_counter() - start,
                "usage": None,
            }
        generated = output[0, inputs["input_ids"].shape[1] :].tolist()
        eos = self.model.generation_config.eos_token_id
        eos = [eos] if isinstance(eos, int) else (eos or [])
        status = (
            "infrastructure"
            if stop.expired
            else ("ok" if generated and generated[-1] in eos else "truncated")
        )
        return {
            "status": status,
            "text": self.tokenizer.decode(generated, skip_special_tokens=True),
            "raw_decoded_with_special_tokens": self.tokenizer.decode(
                generated, skip_special_tokens=False
            ),
            "generated_token_ids": generated,
            "submitted_request": deepcopy(request),
            **rendered,
            "inference_submitted": True,
            "latency_seconds": time.perf_counter() - start,
            "usage": {
                "prompt_tokens": rendered["prompt_tokens"],
                "completion_tokens": len(generated),
            },
            "message": "deadline reached; partial output unscored" if stop.expired else None,
        }
