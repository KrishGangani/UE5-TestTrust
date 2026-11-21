"""P03 TestTrust - run a perf-gate batch on the packaged build and collect every artefact.

Copied and adapted from UE5-UpdateBudget's Tools/run_bench.py (commit b890bc6). Run it through the machine queue only:
    python -I -u "D:/UNREAL PORTFOLIO/tools/ue_queue.py" run --project P03 --label "P03 gate batch" --timeout 1800 \
        --idle 600 --watch "<P03>/Benchmarks/Raw" -- "python -I -u \"<P03>/Tools/run_bench.py\" --configs X0 --rounds 10 --label stored"

What one batch does:
  1. Pins this process to the performance cores (every game it starts inherits the mask) and records the environment,
     including the mask Windows actually applied.
  2. One discarded PRIMING run (the first config), so file, driver and PSO caches are warm.
  3. --rounds rounds; in round r the config order is rotated by r, so with k configs and a multiple of k rounds every
     config sits in every position equally often (thermal drift spreads over all configs).
  4. Each run: deletes GameUserSettings.ini, launches the REAL game exe directly (exit code and kill are reliable),
     waits with a timeout, kills the tree if needed, then moves the CSV and the game log into Benchmarks/Raw as
     <batch>_<Config>_r<round>.<ext> (never overwriting), and records per-run statistics in the manifest.
  5. A run is valid only if it exited 0, its capture is finalised with exactly the expected number of frames and
     contains BenchEnd, and the log has no errors. Invalid runs are kept in the manifest and never judged.
Configurations: X0 (nothing injected), X025, X05, X10 (0.25 / 0.5 / 1.0 ms of game-thread spin per frame).
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import glob
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)
import csv_stats  # noqa: E402  (same folder)
import tt_common  # noqa: E402

PROJECT_DIR = os.path.dirname(TOOLS_DIR)
EXE, SAVED, COMMON_ARGS = tt_common.PACKAGED_EXE, tt_common.PACKAGED_SAVED, tt_common.GATE_ARGS   # as the step checks
RAW_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Raw")
SUMMARY_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Summaries")
STARTUP_MARGIN_SECONDS = 180.0
CONFIGS = {"X0": 0.0, "X025": 0.25, "X05": 0.5, "X10": 1.0}   # injected game-thread milliseconds per frame
COLUMNS = csv_stats.DEFAULT_COLUMNS


def unique_path(path: str) -> str:
    """Raw data is never overwritten."""
    if os.path.exists(path):
        raise FileExistsError(f"refusing to overwrite raw data: {path}")
    return path


def launch(name: str, config: str, args) -> tuple[str, int | None, float, float]:
    """Starts one run and waits for it. Returns (command, exit code or None on timeout, start time, wall seconds)."""
    inject = f" -TTInjectMs={CONFIGS[config]}" if CONFIGS[config] > 0 else ""
    command = (f'"{EXE}" {COMMON_ARGS} -TTAgents={args.agents} -TTSeed={args.seed} -TTWork={args.work} '
               f'-TTWarmup={args.warmup} -TTCapture={args.capture} -TTRunTag={name}{inject}')
    gus = os.path.join(SAVED, "Config", "Windows", "GameUserSettings.ini")
    if os.path.exists(gus):
        os.remove(gus)   # it can override VSync and frame-rate caps
    started = time.time()
    process = subprocess.Popen(command)   # inherits this process's CPU affinity (main: pin_self)
    try:
        exit_code = process.wait(timeout=args.warmup + args.capture + STARTUP_MARGIN_SECONDS)
    except subprocess.TimeoutExpired:
        exit_code = None
    finally:
        if process.poll() is None:   # timeout, Ctrl+C or any error: never leave a game running into the next run
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
    return command, exit_code, started, time.time() - started


def collect(name: str, started: float) -> dict:
    """Moves this run's artefacts into Benchmarks/Raw and returns what was found."""
    record: dict = {}
    captures = [p for p in glob.glob(os.path.join(SAVED, "Profiling", "CSV", "*.csv")) if os.path.getmtime(p) >= started]
    if captures:
        destination = unique_path(os.path.join(RAW_DIR, name + ".csv"))
        shutil.move(max(captures, key=os.path.getmtime), destination)
        record["capture"] = os.path.basename(destination)
        try:
            analysis = csv_stats.analyse(destination, COLUMNS)
        except ValueError as error:   # a crashed run's stub CSV: keep the run as invalid, never stop the batch
            record["analysis_error"] = str(error)
        else:
            record.update(stats=analysis["columns"], frames=analysis["frames"], finalised=analysis["finalised"],
                          events=analysis["events"],
                          metadata={k: v for k, v in analysis["metadata"].items() if k.startswith("tt")})
    log = os.path.join(SAVED, "Logs", "TestTrust.log")
    if os.path.exists(log) and os.path.getmtime(log) >= started:   # only this run's log, never a stale one
        with open(log, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        record["log_errors"] = text.count("Error:")
        record["log_warnings"] = text.count("Warning:")
        record["hashes"] = [line.split(": Display: ")[-1].strip() for line in text.splitlines()
                            if "LogTTWorkload:" in line and " hash 0x" in line]
        shutil.copy(log, unique_path(os.path.join(RAW_DIR, name + ".log")))
    return record


def problems(record: dict, expected_frames: int) -> list[str]:
    """Every reason a run can't be judged; a run is valid only if there is none."""
    found = []
    if record.get("exit_code") != 0:
        found.append("timed out" if record.get("exit_code") is None else f"exit code {record['exit_code']}")
    if "analysis_error" in record:
        found.append(f"capture unreadable: {record['analysis_error']}")
    elif "GameThreadTime" not in record.get("stats", {}):
        found.append("no capture or no GameThreadTime column")
    if record.get("finalised") is False:
        found.append("capture not finalised")
    if record.get("frames") is not None and record["frames"] != expected_frames:
        found.append(f"{record['frames']} frames instead of {expected_frames}")
    # BenchStart starts the capture, so it lands on the frame BEFORE the first captured row; only BenchEnd is inside
    # the capture (S1 check, 09). The frame count above proves the window's start.
    if "stats" in record and not record.get("events", {}).get("TestTrustProbe/BenchEnd"):
        found.append("BenchEnd missing from the capture")
    if record.get("log_errors"):
        found.append(f"{record['log_errors']} log errors")
    if "log_errors" not in record:
        found.append("no log")
    return found


def write_manifest(batch: str, environment: dict, settings: dict, records: list[dict]) -> None:
    tt_common.write_json(os.path.join(RAW_DIR, batch + "_manifest.json"),
                         {"batch": batch, "environment": environment, "settings": settings, "runs": records})


def write_summary(batch: str, environment: dict, records: list[dict]) -> str:
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    def cell(group: list[dict], column: str, stat: str) -> str:
        values = [r["stats"][column][stat] for r in group if column in r["stats"]]
        return f"{statistics.median(values):.3f} [{min(values):.3f}-{max(values):.3f}]" if values else "n/a"

    lines = [f"# Gate batch {batch}", "", "Each cell: median across valid runs of each run's statistic, then [min-max].", "",
             "| Config | Valid runs | GameThreadTime median (ms) | GameThreadTime p95 (ms) | FrameTime median (ms) | Injected median (ms) |",
             "|---|---|---|---|---|---|"]
    for config in CONFIGS:
        group = [r for r in records if r["config"] == config and not r["priming"] and r.get("valid")]
        if not group:
            continue
        lines.append(f"| {config} | {len(group)} | {cell(group, 'GameThreadTime', 'median')} | "
                     f"{cell(group, 'GameThreadTime', 'p95')} | {cell(group, 'FrameTime', 'median')} | "
                     f"{cell(group, 'TestTrustProbe/GameThread/Injected', 'median')} |")
    invalid = [r["name"] for r in records if not r.get("valid")]
    lines += ["", f"Invalid runs (never judged): {invalid or 'none'}.", "",
              f"Raw files: `Benchmarks/Raw/{batch}_*`; environment and per-run statistics in `{batch}_manifest.json`.",
              "", "```json", tt_common.sanitize(json.dumps(environment, indent=1)), "```"]
    path = os.path.join(SUMMARY_DIR, batch + "_summary.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", default="X0")
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--agents", type=int, default=1000)
    parser.add_argument("--work", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--capture", type=float, default=20.0)
    parser.add_argument("--cooldown", type=float, default=3.0)
    parser.add_argument("--label", default="gate")
    parser.add_argument("--no-prime", action="store_true")
    args = parser.parse_args(argv)

    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    if any(c not in CONFIGS for c in configs):
        parser.error(f"unknown config; available: {sorted(CONFIGS)}")
    if args.rounds % len(configs):
        print(f"WARNING: {args.rounds} rounds is not a multiple of {len(configs)} configs; the rotation is unbalanced")
    if not os.path.exists(EXE):
        parser.error(f"packaged build not found: {EXE} (run Tools\\package.bat first)")
    # Keep the system and display awake for the whole batch (ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED).
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
    # Every timed run is pinned (01 section 7): without a mask (the processor query failed) the batch is refused too,
    # because an unpinned game thread can land on an E-core and split the runs into two levels.
    mask = tt_common.PERFORMANCE_CORE_MASK
    if not mask or not tt_common.pin_self(mask):
        parser.error(f"could not pin the batch to the performance cores (mask {mask}); refusing to measure without it")

    batch = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S") + f"_{args.label}"
    os.makedirs(RAW_DIR, exist_ok=True)
    environment = tt_common.environment_record("Development (packaged)", {
        "cpu_affinity": tt_common.applied_mask(), "common_args": COMMON_ARGS,
        "resolution": "1280x720 windowed, default scalability"})
    settings = dict(vars(args))
    expected_frames = round(args.capture * 60)
    records: list[dict] = []

    def run(config: str, round_index: int, position: int, priming: bool = False) -> None:
        name = f"{batch}_{config}_r{round_index}" + ("_prime" if priming else "")
        command, exit_code, started, wall = launch(name, config, args)
        record = {"name": name, "config": config, "inject_ms": CONFIGS[config], "round": round_index,
                  "position": position, "priming": priming, "exit_code": exit_code, "wall_seconds": round(wall, 1),
                  "command": command}
        record.update(collect(name, started))
        record["problems"] = problems(record, expected_frames)
        record["valid"] = not record["problems"]
        records.append(record)
        write_manifest(batch, environment, settings, records)
        gt = record.get("stats", {}).get("GameThreadTime", {})
        print(f"  {name}: exit {exit_code}, {wall:.0f} s, GT median {gt.get('median', float('nan')):.3f} ms "
              f"p95 {gt.get('p95', float('nan')):.3f} ms, valid {record['valid']} {record['problems'] or ''}"
              + ("  [PRIMING, discarded]" if priming else ""), flush=True)
        time.sleep(args.cooldown)

    if not args.no_prime:
        run(configs[0], 0, 0, priming=True)
    for round_index in range(1, args.rounds + 1):
        rotation = (round_index - 1) % len(configs)
        for position, config in enumerate(configs[rotation:] + configs[:rotation]):
            run(config, round_index, position)

    print("summary:", write_summary(batch, environment, records), flush=True)
    invalid = [r["name"] for r in records if not r["priming"] and not r["valid"]]
    if invalid:
        print("ATTENTION - invalid runs (kept, never judged):", invalid, flush=True)
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
