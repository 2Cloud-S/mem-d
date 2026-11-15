"""Two compact publication figures drawn only from independently recomputed artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
DATA = json.loads((HERE / "derived/metrics.json").read_text())
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.titlesize": 9,
        "axes.labelsize": 8.5,
        "legend.fontsize": 7.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    }
)


def save(fig, name):
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"{name}.{suffix}", dpi=300, bbox_inches="tight", pad_inches=0.04)
        if suffix == "svg":
            path = OUT / f"{name}.{suffix}"
            path.write_text(
                "\n".join(line.rstrip(" \t") for line in path.read_text().splitlines()) + "\n"
            )
    plt.close(fig)


def compression():
    rows = DATA["compression"]
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.05), layout="constrained")
    x = np.arange(6)
    methods = [
        ("exact", "Exact", "#9ca3af"),
        ("similarity_first", "Matched similarity-first", "#4e9b9b"),
        ("gated", "Existing mem-d gate", "#1f2937"),
    ]
    for i, (method, label, color) in enumerate(methods):
        axes[0].bar(
            x + (i - 1) * 0.23,
            [r["methods"][method]["tokens"] for r in rows],
            width=0.23,
            color=color,
            label=label,
        )
    axes[0].set(
        title="(a) Memory tokens saved",
        ylabel="Memory tokens saved",
        xticks=x,
        xticklabels=[f"{r['threshold']:.2f}" for r in rows],
        ylim=(0, 255),
        xlabel="Similarity threshold",
    )
    axes[0].legend(
        loc="upper left",
        frameon=False,
        ncol=1,
        borderaxespad=0.2,
        handlelength=1.2,
        labelspacing=0.2,
    )
    axes[1].plot(
        x,
        [100 * r["review_groups"] / r["candidate_groups"] for r in rows],
        color="#1f2937",
        marker="o",
        lw=1.3,
        ms=3.5,
        label="Candidate groups reviewed",
    )
    axes[1].plot(
        x,
        [100 * r["review_memories"] / 52 for r in rows],
        color="#4e9b9b",
        marker="s",
        lw=1.1,
        ms=3,
        linestyle="--",
        label="Original records reviewed",
    )
    axes[1].set(
        title="(b) Gate review recommendations",
        ylabel="Frequency (%)",
        xticks=x,
        xticklabels=[f"{r['threshold']:.2f}" for r in rows],
        ylim=(0, 105),
        xlabel="Similarity threshold",
    )
    axes[1].text(4.96, 57, "3/6", fontsize=8, ha="center")
    axes[1].text(4.95, 33, "23/52", fontsize=8, ha="center", color="#357777")
    axes[1].legend(loc="lower left", frameon=False, fontsize=7, handlelength=1.4)
    for ax in axes:
        ax.tick_params(labelsize=7.5)
        ax.grid(axis="y", alpha=0.16)
        ax.set_axisbelow(True)
    save(fig, "compression_review")


def neutral():
    data = DATA["neutral"]
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 1.95), layout="constrained")
    values = [r["correct"] for r in data["by_permutation"]]
    bars = axes[0].bar(np.arange(6), values, color="#4e9b9b", width=0.6)
    axes[0].set(
        title="(a) Accuracy under every mapping",
        ylabel="Correct / 18 reused items",
        xticks=np.arange(6),
        xticklabels=[f"P{i}" for i in range(1, 7)],
        ylim=(0, 18),
        yticks=[0, 6, 12, 18],
        xlabel="Frozen code-to-label mapping",
    )
    for bar, value in zip(bars, values, strict=True):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2, value + 0.4, str(value), ha="center", fontsize=8
        )
    values = [data["code_counts"][code] for code in ("A", "B", "C")]
    bars = axes[1].bar(np.arange(3), values, color=["#9ca3af", "#1f2937", "#9ca3af"], width=0.55)
    axes[1].axhline(
        36, color="#4e9b9b", linestyle="--", lw=1, label="Correct codes: 36 each by design"
    )
    axes[1].set(
        title="(b) Selected output codes",
        ylabel="Count / 108 answers",
        xticks=np.arange(3),
        xticklabels=["A", "B", "C"],
        ylim=(0, 108),
        yticks=[0, 36, 72, 108],
        xlabel="Single-token output code",
    )
    for bar, value in zip(bars, values, strict=True):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2, value + 2, str(value), ha="center", fontsize=8
        )
    axes[1].legend(loc="upper left", frameon=False, fontsize=7)
    for ax in axes:
        ax.grid(axis="y", alpha=0.16)
        ax.set_axisbelow(True)
    save(fig, "neutral_mapping")


if __name__ == "__main__":
    compression()
    neutral()
    print("Two figures generated from derived/metrics.json; no model calls or image generation.")
