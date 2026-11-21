"""P03 TestTrust - the README charts, drawn only from committed manifests (no new measurement).

Usage: python -I Tools/make_charts.py   ->  Media/gate_rates.png, Media/gate_runs.png
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)
import tt_gate  # noqa: E402

PROJECT = os.path.dirname(TOOLS_DIR)
RAW = os.path.join(PROJECT, "Benchmarks", "Raw")
MEDIA = os.path.join(PROJECT, "Media")
STORED = "2026-11-21_050350_gate-stored"
BATCHES = ["2026-11-21_053701_gate-eval1", "2026-11-21_054518_gate-eval2", "2026-11-21_055612_gate-eval3",
           "2026-11-21_060429_gate-eval4"]
CONFIGS = ("X0", "X025", "X05", "X10")
LABELS = {"X0": "unchanged\n(false positives)", "X025": "+0.25 ms", "X05": "+0.5 ms", "X10": "+1.0 ms"}
COLORS = {"TT": "#2b6cb0", "N1": "#9c9c9c", "N2": "#c9a227", "N3": "#b34a4a"}


def manifest(name: str) -> str:
    return os.path.join(RAW, name + "_manifest.json")


def gate_rates() -> None:
    stored = tt_gate.baseline_runs(manifest(STORED))
    batches = [tt_gate.load_runs(manifest(b)) for b in BATCHES]
    table = tt_gate.evaluate(stored, batches)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    titles = {"a": "(a) baseline interleaved in the same batch", "b": "(b) baseline stored from an earlier batch"}
    for axis, condition in zip(axes, ("a", "b")):
        width = 0.2
        for offset, rule in enumerate(("TT", "N1", "N2", "N3")):
            rates = []
            for config in CONFIGS:
                flagged, total = tt_gate.counts(table, condition, rule, config)
                rates.append(100.0 * flagged / total if total else 0.0)
            xs = [i + (offset - 1.5) * width for i in range(len(CONFIGS))]
            axis.bar(xs, rates, width, label=rule if rule != "TT" else "TT (ours)", color=COLORS[rule])
        axis.axhline(5, color="black", linewidth=0.8, linestyle="--")
        axis.text(-0.45, 6.5, "5% target", fontsize=8)
        axis.set_xticks(range(len(CONFIGS)), [LABELS[c] for c in CONFIGS], fontsize=9)
        axis.set_title(titles[condition], fontsize=10)
        axis.set_ylim(0, 105)
        axis.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("runs flagged (%), 32 per bar")
    axes[1].legend(fontsize=8, loc="center right")
    figure.suptitle("Perf gate v1: single-run flag rates on 128 runs + 10 stored (S5, measured)", fontsize=11)
    figure.tight_layout()
    figure.savefig(os.path.join(MEDIA, "gate_rates.png"), dpi=110)


def gate_runs() -> None:
    figure, axis = plt.subplots(figsize=(9, 4))
    stored = tt_gate.baseline_runs(manifest(STORED))
    axis.scatter([0] * len(stored), [r["stats"]["GameThreadTime"]["median"] for r in stored], s=14, color="black",
                 label="stored X0")
    for b, name in enumerate(BATCHES, 1):
        runs = tt_gate.load_runs(manifest(name))
        for c, config in enumerate(CONFIGS):
            values = [r["stats"]["GameThreadTime"]["median"] for r in runs if r["config"] == config]
            axis.scatter([b + (c - 1.5) * 0.15] * len(values), values, s=12, color=list(COLORS.values())[c],
                         label=config if b == 1 else None)
    axis.set_xticks(range(5), ["stored", "eval 1", "eval 2", "eval 3", "eval 4"])
    axis.set_ylabel("per-run median GameThreadTime (ms)")
    axis.set_title("Every gate run (S4): within-batch spread is as large as the smallest injected cost", fontsize=10)
    axis.legend(fontsize=8, ncol=5, loc="upper left")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(os.path.join(MEDIA, "gate_runs.png"), dpi=110)


if __name__ == "__main__":
    os.makedirs(MEDIA, exist_ok=True)
    gate_rates()
    gate_runs()
    print("charts written to", MEDIA)
