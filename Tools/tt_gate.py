"""P03 TestTrust - the perf gate: is a run slower than its baseline, and how often is that verdict wrong?

Rules (01 section 6.2; parameters fixed before any gate data, 02 section 7):
  TT  (ours) flag if the run's median OR p95 GameThreadTime exceeds the baseline runs' median + max(FLOOR, Z * 1.4826 * MAD)
  N1  flag if the run's mean FrameTime > 1.05 x the mean FrameTime of ONE reference run ("+5% vs last run")
  N2  flag if the run's mean GameThreadTime > mean + 2 sd of the baseline runs' means (a classic 2-sigma alert)
  N3  flag if a frame-level one-sided Mann-Whitney test (the run's frames vs ONE reference run's frames) gives
      p < 0.05 and the run's median is higher (treats frames as independent samples: hypothesis H5)
The run is the sampling unit everywhere except N3, which exists to measure what goes wrong when it isn't.

Commands
  decide   --baseline MANIFEST --candidate MANIFEST --run NAME     TT verdict for one run (with the numbers)
  evaluate --stored MANIFEST --batches M [M ...] [--label L]        false-positive and detection rates of every rule,
                                                                     (a) against the X0 runs interleaved in the same
                                                                     batch and (b) against the stored baseline
  selftest                                                           checks the statistics on synthetic runs
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)
import csv_stats  # noqa: E402  (same folder)

PROJECT_DIR = os.path.dirname(TOOLS_DIR)
RAW_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Raw")
SUMMARY_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Summaries")

Z = 3.0             # robust "three-sigma" control limit
FLOOR_MS = 0.10     # smallest change worth flagging: 0.6% of a 60 fps frame, below the smallest injected size
MAD_TO_SIGMA = 1.4826
N1_RATIO = 1.05
N2_SIGMAS = 2.0
N3_ALPHA = 0.05
MIN_BASELINE = 3                     # fewer runs give no usable median and MAD
INJECTED = ("X025", "X05", "X10")
CONDITIONS = (("a", "interleaved"), ("b", "stored"))
GT = "GameThreadTime"
FT = "FrameTime"


# ------------------------------------------------------------------------------------------------------------- rules

def robust_limit(values: list[float]) -> float:
    centre = statistics.median(values)
    mad = statistics.median([abs(v - centre) for v in values])
    return centre + max(FLOOR_MS, Z * MAD_TO_SIGMA * mad)


def rule_tt(baseline: list[dict], run: dict) -> tuple[bool, dict]:
    detail = {}
    for stat in ("median", "p95"):
        limit = robust_limit([b["stats"][GT][stat] for b in baseline])
        detail[stat] = {"value": run["stats"][GT][stat], "limit": limit}
    return any(d["value"] > d["limit"] for d in detail.values()), detail


def rule_n1(reference: dict, run: dict) -> bool:
    return run["stats"][FT]["mean"] > N1_RATIO * reference["stats"][FT]["mean"]


def rule_n2(baseline: list[dict], run: dict) -> bool:
    means = [b["stats"][GT]["mean"] for b in baseline]
    return run["stats"][GT]["mean"] > statistics.mean(means) + N2_SIGMAS * statistics.stdev(means)


def mann_whitney_greater(sample: list[float], reference: list[float]) -> float:
    """One-sided p-value that `sample` tends to be larger than `reference` (normal approximation, tie-corrected)."""
    n1, n2 = len(sample), len(reference)
    combined = sorted([(v, 0) for v in sample] + [(v, 1) for v in reference])
    ranks, ties, i = [0.0] * len(combined), 0.0, 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        average = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = average
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    r1 = sum(rank for rank, (_, group) in zip(ranks, combined) if group == 0)
    u = r1 - n1 * (n1 + 1) / 2.0
    n = n1 + n2
    variance = n1 * n2 / 12.0 * ((n + 1) - ties / (n * (n - 1)))
    if variance <= 0:
        return 1.0
    z = (u - n1 * n2 / 2.0 - 0.5) / math.sqrt(variance)
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def frames(run: dict) -> list[float]:
    header, data, _, _ = csv_stats.load_capture(os.path.join(RAW_DIR, run["capture"]))
    return csv_stats.column_values(header, data, GT)


def rule_n3(reference: dict, run: dict, frame_cache: dict) -> bool:
    for r in (reference, run):
        if r["name"] not in frame_cache:
            frame_cache[r["name"]] = frames(r)
    sample, ref = frame_cache[run["name"]], frame_cache[reference["name"]]
    return mann_whitney_greater(sample, ref) < N3_ALPHA and statistics.median(sample) > statistics.median(ref)


# ------------------------------------------------------------------------------------------------------ evaluation

def load_runs(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    return [r for r in manifest["runs"] if not r["priming"] and r.get("valid")]


def reference_x0(runs: list[dict], run: dict) -> dict | None:
    """N1's and N3's reference run under (a): the X0 run that came last before `run` in the same batch (run order =
    manifest order). Runs before the batch's first X0 take the next X0 instead, so every rule judges the same runs
    and the rates compare like with like (code review, S3)."""
    index = runs.index(run)
    return next((r for r in reversed(runs[:index]) if r["config"] == "X0"),
                next((r for r in runs[index + 1:] if r["config"] == "X0"), None))


def baseline_runs(path: str, minimum: int = MIN_BASELINE) -> list[dict]:
    """A baseline manifest's valid X0 runs; refuses a baseline that contains injected runs or too few runs."""
    runs = load_runs(path)
    others = sorted({r["config"] for r in runs} - {"X0"})
    if others:
        raise SystemExit(f"{path}: a baseline must contain only X0 runs, found {others}")
    if len(runs) < minimum:
        raise SystemExit(f"{path}: {len(runs)} valid X0 runs; a baseline needs at least {minimum}")
    return runs


def evaluate(stored: list[dict], batches: list[list[dict]], use_frames: bool = True) -> dict:
    """Verdicts of every rule on every candidate, under conditions (a) interleaved and (b) stored baseline."""
    cache: dict = {}
    table: dict = {}

    def tally(condition: str, rule: str, run: dict, flagged: bool) -> None:
        cell = table.setdefault(condition, {}).setdefault(rule, {}).setdefault(run["config"], [0, 0])
        cell[0] += int(flagged)
        cell[1] += 1

    def judge(condition: str, baseline: list[dict], reference: dict, run: dict) -> None:
        """Every rule on one run, so all rules judge the same runs and their rates compare like with like."""
        tally(condition, "TT", run, rule_tt(baseline, run)[0])
        tally(condition, "N2", run, rule_n2(baseline, run))
        tally(condition, "N1", run, rule_n1(reference, run))
        if use_frames:
            tally(condition, "N3", run, rule_n3(reference, run, cache))

    reference_b = stored[-1]   # (b): the stored batch's last run is N1's and N3's reference
    for runs in batches:
        x0 = [r for r in runs if r["config"] == "X0"]
        for run in runs:
            # (a) interleaved: the batch's own X0 runs (7 for an X0 candidate, which is left out of its own
            # baseline, 8 for an injected one in an 8-round batch; 02 section 7). Every rule judges the same runs.
            baseline_a = [r for r in x0 if r is not run]
            if len(baseline_a) >= MIN_BASELINE:   # then reference_x0 always finds another X0 run
                judge("a", baseline_a, reference_x0(runs, run), run)
            judge("b", stored, reference_b, run)
    return table


def counts(table: dict, condition: str, rule: str, config: str) -> tuple[int, int]:
    """(flagged, judged) runs of one rule and configuration; (0, 0) if none was judged."""
    flagged, total = table.get(condition, {}).get(rule, {}).get(config, [0, 0])
    return flagged, total


def criteria(table: dict) -> list[tuple[str, str, bool]]:
    """SC5-SC7 (01 section 6.4) from an evaluation table. Counts are [flagged, total]."""
    def rate(condition, rule, config):
        flagged, total = counts(table, condition, rule, config)
        return flagged / total if total else float("nan")
    rows = []
    for condition, label in CONDITIONS:
        fpr = rate(condition, "TT", "X0")
        judged = counts(table, condition, "TT", "X0")[1]
        # SC5 needs at least 30 unchanged runs (01 section 6.4): a low rate on fewer runs is not a pass.
        rows.append((f"SC5{condition}", f"TT false positives, {label} baseline: {fpr:.1%} of {judged} runs "
                     f"(target <= 5% of >= 30)", fpr <= 0.05 and judged >= 30))
        for config, target in (("X10", 1.0), ("X05", 0.95), ("X025", 0.80)):   # 01 section 6.4, SC6
            d = rate(condition, "TT", config)
            rows.append((f"SC6{condition}", f"TT detection {config}, {label}: {d:.1%} (target >= {target:.0%})", d >= target))
        # evaluate() judges every rule on the same runs, so the rates share their denominators.
        better = all(fpr <= rate(condition, n, "X0") and all(rate(condition, "TT", c) >= rate(condition, n, c)
                                                              for c in INJECTED)
                     for n in ("N1", "N2", "N3") if n in table[condition])
        rows.append((f"SC7{condition}", f"TT no worse than N1/N2/N3 on every rate, {label}", better))
    return rows


def write_report(label: str, table: dict, notes: list[str]) -> str:
    lines = [f"# Gate evaluation {label}", "", "Counts are flagged / judged runs. X0 = unchanged (any flag is a false positive).", ""]
    for condition, title in (("a", "(a) baseline = the X0 runs interleaved in the same batch"),
                             ("b", "(b) baseline = the stored batch captured earlier")):
        lines += [f"## {title}", "", "| Rule | X0 (false positives) | X025 | X05 | X10 |", "|---|---|---|---|---|"]
        for rule in ("TT", "N1", "N2", "N3"):
            if rule in table.get(condition, {}):
                cells = []
                for config in ("X0",) + INJECTED:
                    flagged, total = counts(table, condition, rule, config)
                    cells.append(f"{flagged}/{total} ({flagged / total:.0%})" if total else "n/a")
                lines.append(f"| {rule} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## Success criteria", "", "| # | Criterion | Pass |", "|---|---|---|"]
    lines += [f"| {k} | {text} | {'yes' if ok else '**no**'} |" for k, text, ok in criteria(table)]
    lines += [""] + notes
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    path = os.path.join(SUMMARY_DIR, f"{label}_gate_evaluation.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


# ------------------------------------------------------------------------------------------------------------ CLI

def cmd_decide(args) -> int:
    candidate = next((r for r in load_runs(args.candidate) if r["name"] == args.run), None)
    if candidate is None:
        raise SystemExit(f"{args.run}: no valid, non-priming run of that name in {args.candidate}")
    # Leave-one-out by name: a candidate taken from the baseline's own batch never judges against itself.
    baseline = [r for r in baseline_runs(args.baseline) if r["name"] != args.run]
    flagged, detail = rule_tt(baseline, candidate)
    for stat, d in detail.items():
        print(f"{stat:6} GameThreadTime {d['value']:.3f} ms vs limit {d['limit']:.3f} ms")
    print("REGRESSION" if flagged else "pass")
    return 3 if flagged else 0


def cmd_evaluate(args) -> int:
    stored = baseline_runs(args.stored)
    batches = [load_runs(path) for path in args.batches]
    table = evaluate(stored, batches)
    notes = [f"Stored baseline: `{os.path.basename(args.stored)}` ({len(stored)} valid runs). Evaluation batches: "
             + ", ".join(f"`{os.path.basename(p)}`" for p in args.batches) + ".",
             f"Rule parameters fixed before the data: Z = {Z}, floor = {FLOOR_MS} ms, N1 ratio {N1_RATIO}, "
             f"N2 {N2_SIGMAS} sd, N3 alpha {N3_ALPHA}."]
    print(write_report(args.label, table, notes))
    for key, text, ok in criteria(table):
        print(f"{key}: {'PASS' if ok else 'FAIL'}  {text}")
    return 0


def cmd_selftest(_args) -> int:
    ok = True
    # Robust limit: median 5.0, MAD 0.02 -> 3 * 1.4826 * 0.02 = 0.0890 < floor, so limit = 5.10.
    values = [4.98, 5.00, 5.02, 5.00, 4.99, 5.01, 5.00]
    ok &= abs(robust_limit(values) - 5.10) < 1e-9
    # A wide spread: MAD 0.1 -> 0.44478 > floor.
    ok &= abs(robust_limit([4.8, 4.9, 5.0, 5.1, 5.2]) - (5.0 + 3 * 1.4826 * 0.1)) < 1e-9
    # Mann-Whitney: identical samples give p about 0.5; a clear shift gives p near 0; reversed gives p near 1.
    base = [float(i % 10) for i in range(200)]
    ok &= 0.4 < mann_whitney_greater(base, base) < 0.6
    ok &= mann_whitney_greater([v + 5 for v in base], base) < 1e-6
    ok &= mann_whitney_greater(base, [v + 5 for v in base]) > 0.999

    def run(name, config, med, p95, mean):
        return {"name": name, "config": config, "stats": {GT: {"median": med, "p95": p95, "mean": mean},
                                                          FT: {"mean": mean + 0.05}}}
    baseline = [run(f"b{i}", "X0", 5.0 + 0.01 * (i % 3), 5.5, 5.05) for i in range(10)]
    ok &= rule_tt(baseline, run("c", "X0", 5.03, 5.52, 5.06))[0] is False
    ok &= rule_tt(baseline, run("c", "X10", 6.0, 6.5, 6.05))[0] is True
    ok &= rule_tt(baseline, run("c", "X025", 5.26, 5.76, 5.30))[0] is True
    ok &= rule_n1(baseline[0], run("c", "X10", 6.0, 6.5, 6.05)) is True
    ok &= rule_n1(baseline[0], run("c", "X025", 5.26, 5.76, 5.30)) is False   # +5% of ~5.1 ms is ~0.26 ms
    table = evaluate(baseline, [[run("x", "X0", 5.0, 5.5, 5.05), run("y", "X10", 6.0, 6.5, 6.05)]], use_frames=False)
    ok &= table["b"]["TT"]["X0"] == [0, 1] and table["b"]["TT"]["X10"] == [1, 1]
    # (a): a run before the batch's first X0 takes the next X0 as its reference, so every rule judges every run.
    batch = [run("i", "X10", 6.0, 6.5, 6.05)] + [run(f"x{i}", "X0", 5.0 + 0.01 * i, 5.5, 5.05) for i in range(5)]
    ok &= reference_x0(batch, batch[0]) is batch[1] and reference_x0(batch, batch[2]) is batch[1]
    table = evaluate(baseline, [batch], use_frames=False)
    ok &= all(table["a"][n]["X10"][1] == 1 and table["a"][n]["X0"][1] == 5 for n in ("TT", "N1", "N2"))
    # SC5 is not met on fewer than 30 unchanged runs, even with no false positive.
    ok &= criteria(table)[0][2] is False
    print("selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    decide = sub.add_parser("decide")
    decide.add_argument("--baseline", required=True)
    decide.add_argument("--candidate", required=True)
    decide.add_argument("--run", required=True)
    evaluate_cmd = sub.add_parser("evaluate")
    evaluate_cmd.add_argument("--stored", required=True)
    evaluate_cmd.add_argument("--batches", nargs="+", required=True)
    evaluate_cmd.add_argument("--label", default="gate")
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    return {"decide": cmd_decide, "evaluate": cmd_evaluate, "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
