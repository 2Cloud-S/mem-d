"""Read frozen artifacts and independently derive report values. Never runs a model."""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ARTIFACTS = RESEARCH / "artifacts"
LABELS = ("proceed", "do_not_proceed", "insufficient_evidence")
SEEDS = (2026, 2027, 2028)


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(path):
    result = {}
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            if member.isfile():
                result[member.name.split("/", 1)[1]] = tar.extractfile(member).read()
    for name, content in result.items():
        if name.endswith("freeze.json"):
            for file, expected in json.loads(content).items():
                # Audit subdirectories carry their own relative freezes.
                prefix = str(Path(name).parent)
                key = file if prefix == "." else prefix + "/" + file
                assert hashlib.sha256(result[key]).hexdigest() == expected, (path, key)
    return result


def rows(data):
    return [json.loads(line) for line in data.splitlines()]


def strict_json(response):
    if response["status"] != "ok":
        return None

    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("Duplicate key")
            result[k] = v
        return result

    try:
        value = json.loads(response["text"], object_pairs_hook=unique)
        if set(value) != {"answer_label", "justification"}:
            return None
        if not all(isinstance(v, str) and v.strip() for v in value.values()):
            return None
        return value["answer_label"] if value["answer_label"] in LABELS else None
    except (ValueError, TypeError):
        return None


def main():
    ledger = []

    def claim(identifier, statement, value, sources, derivation, unit):
        ledger.append(
            {
                "id": identifier,
                "statement": statement,
                "value": value,
                "sources": sources,
                "derivation": derivation,
                "unit": unit,
            }
        )

    historical = sorted(p for p in ARTIFACTS.iterdir() if (p / "SHA256SUMS").exists())
    for directory in historical:
        for line in (directory / "SHA256SUMS").read_text().splitlines():
            expected, file = line.split("  ", 1)
            assert sha(directory / file) == expected, (directory, file)
    cases = rows((RESEARCH / "development.jsonl").read_bytes())
    case_map = {c["case_id"]: c for c in cases}
    assert len(cases) == 20 and len({c["family_id"] for c in cases}) == 10
    assert sum(len(c["input"]["memories"]) for c in cases) == 52
    assert sorted(Counter(c["category"] for c in cases).values()) == [5] * 4
    claim(
        "D1",
        "Development corpus",
        {
            "cases": 20,
            "families": 10,
            "records": 52,
            "categories": dict(Counter(c["category"] for c in cases)),
        },
        ["../development.jsonl"],
        "Count records, category membership and distinct family IDs",
        "development cases; families are the independent resampling unit",
    )

    phase2 = archive(ARTIFACTS / "phase2-development-2026-11-14/run.tar.gz")
    variants = rows(phase2["transformations.jsonl"])
    full = {}
    for r in variants:
        key = (r["threshold"], r["case_id"])
        if key not in full or r["prefix"] > full[key]["prefix"]:
            full[key] = r
    assert max(len(r["candidates"]) for r in full.values()) == 1
    phase2b = archive(ARTIFACTS / "phase2b-development-2026-11-14/run.tar.gz")
    points = {p["point_id"]: p for p in rows(phase2b["points.jsonl"])}
    compression = []
    identical = []
    for threshold in (0.45, 0.55, 0.65, 0.75, 0.85, 0.95):
        group_rows = [r for (t, _), r in sorted(full.items()) if t == threshold]
        count = sum(len(r["candidates"]) for r in group_rows)
        review_groups = review_memories = approvals = conflicts = vetoes = 0
        for r in group_rows:
            resolutions = {x["memoryId"]: x for x in r["memd"]["resolutions"]}
            review_memories += sum(x["resolvedAction"] == "review" for x in resolutions.values())
            for group, gate in zip(r["candidates"], r["gate_decisions"], strict=True):
                review_groups += any(
                    resolutions[m]["resolvedAction"] == "review" for m in group["members"]
                )
                conflicts += any(resolutions[m]["conflictDetected"] for m in group["members"])
                approvals += "approval_required" in gate["veto_reasons"]
                vetoes += not gate["allowed"]
        prefix = 3 if threshold == 0.95 else 2
        selected = {
            method: points[f"{threshold}:{method}"] for method in ("original", "exact", "gated")
        }
        selected["similarity_first"] = points[f"{threshold}:similarity_first:{prefix}"]
        payloads = {
            name: {cid: o["memories"] for cid, o in p["outputs"].items()}
            for name, p in selected.items()
        }
        identity = (
            canon(payloads["gated"])
            == canon(payloads["exact"])
            == canon(payloads["similarity_first"])
        )
        if identity:
            identical.append(threshold)
        savings = {}
        for name, p in selected.items():
            counts = p["metrics"]["token_counts"]
            assert len(counts) == 60
            before = sum(x["before"] for x in counts) / 3
            saved = sum(x["before"] - x["after"] for x in counts) / 3
            assert before == 3290 and saved == p["metrics"]["tokens_saved_mean_orders"]
            saved_records = sum(len(o["removed_ids"]) for o in p["outputs"].values())
            assert saved_records == p["metrics"]["records_removed"]
            savings[name] = {
                "tokens": saved,
                "fraction": saved / before,
                "records": saved_records,
                "groups": sum(len(o["executed_groups"]) for o in p["outputs"].values()),
                "cases": sum(
                    o["memories"] != selected["original"]["outputs"][cid]["memories"]
                    for cid, o in p["outputs"].items()
                ),
            }
        compression.append(
            {
                "threshold": threshold,
                "candidate_groups": count,
                "review_groups": review_groups,
                "review_memories": review_memories,
                "approval_groups": approvals,
                "conflict_groups": conflicts,
                "veto_groups": vetoes,
                "matched_prefix": prefix,
                "byte_identical_three_controls": identity,
                "methods": savings,
            }
        )
    assert identical == [0.45, 0.55, 0.65, 0.75, 0.85]
    assert [r["review_groups"] for r in compression] == [18, 17, 17, 15, 7, 3]
    assert [r["review_memories"] for r in compression] == [48, 46, 43, 36, 27, 23]
    last = compression[-1]
    assert [last["methods"][x]["tokens"] for x in ("exact", "gated", "similarity_first")] == [
        136,
        194,
        192,
    ]
    claim(
        "C1",
        "Five identical operating points",
        identical,
        ["../artifacts/phase2b-development-2026-11-14/run.tar.gz::points.jsonl"],
        (
            "Compare complete canonical survivor-record payloads, not token totals; "
            "questions/criteria/order policy held fixed"
        ),
        "thresholds on the same twenty-case corpus",
    )
    claim(
        "C2",
        "Memory-token budgets and review burden",
        compression,
        [
            "../artifacts/phase2-development-2026-11-14/run.tar.gz::transformations.jsonl",
            "../artifacts/phase2b-development-2026-11-14/run.tar.gz::points.jsonl",
        ],
        (
            "Sum actual tokenizer counts over cases and three seeded orders, divide by three; "
            "count explicit review resolutions and whole-group vetoes"
        ),
        "Qwen0.5B-tokenizer corpus memory tokens; recommendations, not review time",
    )

    gate = points["0.95:gated"]["outputs"]
    exact = points["0.95:exact"]["outputs"]
    control = points["0.95:similarity_first:3"]["outputs"]
    assert [cid for cid in sorted(gate) if gate[cid]["memories"] != exact[cid]["memories"]] == [
        "dev_005"
    ]
    assert [cid for cid in sorted(gate) if gate[cid]["memories"] != control[cid]["memories"]] == [
        "dev_005",
        "dev_016",
    ]
    assert gate["dev_005"]["removed_ids"] == ["m005_3"]
    assert [m["id"] for m in gate["dev_005"]["memories"]] == ["m005_1", "m005_2"]
    claim(
        "C3",
        "0.95 incremental transformation and matching residual",
        {
            "incremental_tokens_over_exact": 194 - 136,
            "gate_control_gap_tokens": 194 - 192,
            "gap_percentage_points_original": (194 - 192) / 3290 * 100,
            "gap_percent_gate_savings": (194 - 192) / 194 * 100,
            "tolerance_memory_tokens": 0.02 * 3290,
            "gate_extra_over_exact": gate["dev_005"],
            "control_extra_over_exact": control["dev_016"],
        },
        ["../artifacts/phase2b-development-2026-11-14/run.tar.gz::points.jsonl"],
        "Subtract frozen integer token sums; compare actual survivor payloads case by case",
        "memory tokens under Qwen0.5B tokenizer; fixed-medoid semantic safety unreviewed",
    )

    # Optional independent actual-tokenizer recount uses a cached vocabulary only,
    # never model weights, model generation, a download, or a provider.
    token_path = Path(
        "/tmp/memd-phase2-hf/hub/models--Qwen--Qwen2.5-0.5B-"
        "Instruct/snapshots/7ae557604adf67be50417f59c2c2f167def9a775/tokenizer.json"
    )
    token_recount = "cached tokenizer unavailable; frozen integer counts independently summed"
    if token_path.exists():
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(str(token_path))
        recounted = 0
        for threshold in (0.45, 0.55, 0.65, 0.75, 0.85, 0.95):
            for p in points.values():
                if p["threshold"] != threshold:
                    continue
                for count in p["metrics"]["token_counts"]:
                    original = points[f"{threshold}:original"]["outputs"][count["case_id"]][
                        "memories"
                    ]
                    order = [m["id"] for m in sorted(original, key=lambda m: m["id"])]
                    random.Random(count["order_seed"]).shuffle(order)
                    rank = {mid: i for i, mid in enumerate(order)}
                    after = sorted(
                        p["outputs"][count["case_id"]]["memories"], key=lambda m: rank[m["id"]]
                    )
                    before = sorted(original, key=lambda m: rank[m["id"]])
                    assert (
                        len(tok.encode(canon(before), add_special_tokens=False).ids)
                        == count["before"]
                    )
                    assert (
                        len(tok.encode(canon(after), add_special_tokens=False).ids)
                        == count["after"]
                    )
                    recounted += 2
        token_recount = {
            "actual_serializations_recounted": recounted,
            "cached_tokenizer_sha256": sha(token_path),
        }

    historical_solver = []
    for model in ("qwen", "smol"):
        run = archive(ARTIFACTS / f"phase3-development-2026-11-14/{model}/run.tar.gz")
        req = {r["request_id"]: r for r in rows(run["requests.jsonl"])}
        responses = rows(run["responses.jsonl"])
        assert len(req) == len(responses) == 240
        outcomes = defaultdict(list)
        for response in responses:
            r = req[response["request_id"]]
            label = strict_json(response)
            gold = case_map[r["case_id"]]["evaluator_only"]["acceptable_answer_labels"]
            outcomes[r["condition"]].append(
                {
                    "case": r["case_id"],
                    "seed": r["order_seed"],
                    "valid": label is not None,
                    "correct": label in gold,
                    "status": response["status"],
                }
            )
        stats = {
            c: {
                "planned": len(v),
                "valid": sum(x["valid"] for x in v),
                "correct": sum(x["correct"] for x in v),
                "valid_but_wrong": sum(x["valid"] and not x["correct"] for x in v),
            }
            for c, v in outcomes.items()
        }
        base = {(r["case"], r["seed"]): r for r in outcomes["original"]}
        changes = {}
        for condition, values in outcomes.items():
            rescued = [
                x for x in values if x["correct"] and not base[(x["case"], x["seed"])]["correct"]
            ]
            introduced = [
                x for x in values if not x["correct"] and base[(x["case"], x["seed"])]["correct"]
            ]
            changes[condition] = {
                "rescued": len(rescued),
                "introduced": len(introduced),
                "rescued_cases": sorted({x["case"] for x in rescued}),
            }
        execution = json.loads(run["execution-summary.json"])
        assert execution["actual_inference_attempts"] == 72
        assert all(r["status"] == "ok" for r in responses)
        format_categories = Counter()
        for response in responses:
            if strict_json(response) is not None:
                format_categories["strict_valid"] += 1
                continue
            try:
                value = json.loads(response["text"])
                key = "wrong_answer_key" if "answer" in value else "other_invalid_json"
            except ValueError:
                key = "non_json"
            format_categories[key] += 1
        if model == "qwen":
            assert format_categories == {"wrong_answer_key": 233, "non_json": 4, "strict_valid": 3}
        historical_solver.append(
            {
                "model": model,
                "conditions": stats,
                "changes": changes,
                "execution": execution,
                "format_categories": dict(format_categories),
            }
        )
    assert historical_solver[0]["conditions"]["original"]["correct"] == 0
    assert historical_solver[1]["conditions"]["original"]["correct"] == 14
    assert all(
        historical_solver[1]["conditions"][x]["correct"] == 17
        for x in ("exact", "gated", "similarity_first")
    )
    claim(
        "S1",
        "Historical solver counts",
        historical_solver,
        [
            "../artifacts/phase3-development-2026-11-14/qwen/run.tar.gz",
            "../artifacts/phase3-development-2026-11-14/smol/run.tar.gz",
        ],
        (
            "Strictly parse raw responses and compare labels to unchanged evidence-derived "
            "keys; preserve all case/order denominators"
        ),
        "60 case/order observations per condition/model; ten dependent scenario families",
    )

    calibration = []
    for folder, interface in (
        ("json-qwen-calibration", "json"),
        ("qwen-choice-calibration", "semantic"),
        ("smol-choice-calibration", "semantic"),
        ("larger-choice-calibration", "semantic"),
    ):
        run = archive(ARTIFACTS / f"phase3b-development-2026-11-15/{folder}/run.tar.gz")
        req = {r["request_id"]: r for r in rows(run["requests.jsonl"])}
        keys = json.loads(run["calibration-keys.json"])
        valid = correct = infra = 0
        for response in rows(run["responses.jsonl"]):
            label = (
                strict_json(response)
                if interface == "json"
                else response["text"]
                if response["status"] == "ok" and response["text"] in LABELS
                else None
            )
            valid += label is not None
            correct += label == keys[req[response["request_id"]]["case_id"]]["answer_label"]
            infra += response["status"] == "infrastructure"
        info = json.loads(run["manifest.json"])
        calibration.append(
            {
                "model": info["model"]["repo_id"],
                "revision": info["model"]["revision"],
                "interface": interface,
                "planned": 18,
                "valid": valid,
                "correct": correct,
                "infrastructure": infra,
            }
        )
    assert [(r["valid"], r["correct"]) for r in calibration] == [(13, 4), (18, 5), (18, 6), (18, 8)]
    claim(
        "S2",
        "Pre-code calibration outcomes",
        calibration,
        ["../artifacts/phase3b-development-2026-11-15/*/run.tar.gz"],
        (
            "Reparse all raw outputs under each frozen interface, keep failures in the "
            "eighteen-item eligibility denominator"
        ),
        "same eighteen reused calibration items, not independent replications",
    )

    run = archive(ARTIFACTS / "phase3c-neutral-codes-2026-11-15/run.tar.gz")
    req = {r["request_id"]: r for r in rows(run["requests.jsonl"])}
    keys = json.loads(run["calibration-keys.json"])
    neutral = []
    for response in rows(run["responses.jsonl"]):
        r = req[response["request_id"]]
        body = json.loads(r["request"]["messages"][1]["content"])
        code = (
            response["text"]
            if response["status"] == "ok" and response["text"] in ("A", "B", "C")
            else None
        )
        label = body["answer_code_mapping"][code] if code else None
        gold = keys[r["case_id"]]["answer_label"]
        neutral.append(
            {
                "item": r["case_id"],
                "permutation": r["mapping_index"],
                "code": code,
                "label": label,
                "gold": gold,
                "correct": label == gold,
                "valid": code is not None,
            }
        )
    assert len(neutral) == len(req) == 108
    by_perm = [
        {
            "permutation": i + 1,
            "planned": 18,
            "correct": sum(r["correct"] for r in neutral if r["permutation"] == i),
            "mapping": json.loads(
                next(r for r in req.values() if r["mapping_index"] == i)["request"]["messages"][1][
                    "content"
                ]
            )["answer_code_mapping"],
        }
        for i in range(6)
    ]
    by_class = {
        label: {"planned": 36, "correct": sum(r["correct"] and r["gold"] == label for r in neutral)}
        for label in LABELS
    }
    by_item = defaultdict(list)
    for row in neutral:
        by_item[row["item"]].append(row)
    diagnostic = {
        "planned": 108,
        "items": 18,
        "valid": sum(r["valid"] for r in neutral),
        "correct": sum(r["correct"] for r in neutral),
        "code_counts": dict(Counter(r["code"] for r in neutral)),
        "semantic_counts": dict(Counter(r["label"] for r in neutral)),
        "by_permutation": by_perm,
        "by_class": by_class,
        "semantic_changes": sum(
            len({r["label"] for r in values}) > 1 for values in by_item.values()
        ),
        "code_changes": sum(len({r["code"] for r in values}) > 1 for values in by_item.values()),
        "constant_code_items": sum(
            len({r["code"] for r in values}) == 1 for values in by_item.values()
        ),
        "false_abstentions": sum(
            r["label"] == "insufficient_evidence" and r["gold"] != "insufficient_evidence"
            for r in neutral
        ),
    }
    diagnostic["per_item"] = dict(by_item)
    diagnostic["confusion"] = {
        gold: dict(Counter(r["label"] for r in neutral if r["gold"] == gold)) for gold in LABELS
    }
    diagnostic["invariant_correct_items"] = sorted(
        item for item, values in by_item.items() if all(r["correct"] for r in values)
    )
    assert diagnostic["invariant_correct_items"] == ["interface_07", "interface_13"]
    assert all(
        values[0]["code"] == "B"
        for values in by_item.values()
        if len({r["code"] for r in values}) == 1
    )
    assert diagnostic["valid"] == 108 and diagnostic["correct"] == 50
    assert [x["correct"] for x in by_perm] == [11, 10, 6, 8, 6, 9]
    assert diagnostic["code_counts"] == {"A": 19, "B": 84, "C": 5}
    assert diagnostic["semantic_changes"] == 16 and diagnostic["code_changes"] == 11
    assert [by_class[x]["correct"] for x in LABELS] == [29, 11, 10]
    diagnostic.update(
        {
            "accuracy_percent": 50 / 108 * 100,
            "B_percent": 84 / 108 * 100,
            "changed_items_percent": 16 / 18 * 100,
        }
    )
    claim(
        "N1",
        "Counterbalanced neutral-code diagnostic",
        diagnostic,
        ["../artifacts/phase3c-neutral-codes-2026-11-15/run.tar.gz"],
        (
            "Decode each raw code using its own frozen public mapping, compare unchanged keys, "
            "group by item/permutation/class"
        ),
        (
            "108 repeated item/mapping pairs from eighteen reused items; no independent-sample "
            "significance claim"
        ),
    )
    audit = json.loads(
        (ARTIFACTS / "phase2b-development-2026-11-14/reviewer/packets.json").read_text()
    )
    packet_count = len(audit) if isinstance(audit, list) else len(audit["packets"])
    assert packet_count == 29
    claim(
        "A1",
        "Independent semantic reviews remain pending",
        {"unique_proposals": 29, "human_reviews": 0},
        [
            "../artifacts/phase2b-development-2026-11-14/reviewer/packets.json",
            "../artifacts/phase3c-neutral-codes-2026-11-15/study-status.json",
        ],
        (
            "Count unique reviewer packets and read frozen review status; no agreement or "
            "safety outcomes imputed"
        ),
        "proposals are dependent variants of ten development families",
    )
    inspection_path = ARTIFACTS / "phase3c-neutral-codes-2026-11-15/token-inspection.json"
    inspection = json.loads(inspection_path.read_text())
    assert len(inspection["models"]) == 3
    assert all(m["first_token_determines_complete_label"] for m in inspection["models"])
    claim(
        "T1",
        "Semantic-label tries and frozen model/tokenizer identities",
        inspection,
        [
            "../artifacts/phase3c-neutral-codes-2026-11-15/token-inspection.json",
            "../artifacts/phase3c-neutral-codes-2026-11-15/run.tar.gz::manifest.json",
        ],
        "Read pinned asset hashes, actual-boundary token sequences and divergence flags",
        "token IDs are tokenizer-specific; reachability does not establish unbiased choice",
    )
    claim(
        "P1",
        "Inherited production baseline and untouched historical evidence",
        {
            "baseline": "14af8eccc0141450d01981e189a48b72140ce754",
            "frozen_head": "255b73fd3986844ea17292e1e8c27776a77cc9a3",
        },
        ["../README.md", "../REPORT_HANDOFF.md", "../../../memd/"],
        "Verify artifact checksums/freeze digests and git diff production files against baseline",
        "repository provenance; no fixture/test accuracy used as decision evidence",
    )
    metric = {
        "dataset": ledger[0]["value"],
        "compression": compression,
        "historical_solver": historical_solver,
        "calibration": calibration,
        "neutral": diagnostic,
        "tokenizer_recount": token_recount,
        "verified_historical_directories": [p.name for p in historical],
        "baseline_commit": "14af8eccc0141450d01981e189a48b72140ce754",
        "frozen_evidence_head": "255b73fd3986844ea17292e1e8c27776a77cc9a3",
    }
    out = HERE / "derived"
    out.mkdir(exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(metric, indent=2, sort_keys=True) + "\n")
    (out / "claim-ledger.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    baseline = subprocess.run(
        ["git", "diff", "--quiet", "14af8eccc0141450d01981e189a48b72140ce754", "--", "memd"],
        cwd=RESEARCH.parents[1],
    ).returncode
    assert baseline == 0, "Production code differs from inherited baseline"
    print(
        json.dumps(
            {
                "development_cases": 20,
                "families": 10,
                "identical_thresholds": identical,
                "neutral_valid": 108,
                "neutral_correct": 50,
                "tokenizer_recount": token_recount,
                "claim_groups": len(ledger),
                "model_calls": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
