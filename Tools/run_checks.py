"""P03 TestTrust - the checks of one implementation step, run as ONE machine-queue job.

Usage (through the queue only; it builds, packages and runs the game):
    python -I -u "D:/UNREAL PORTFOLIO/tools/ue_queue.py" run --project P03 --label "P03 S1 checks" --timeout 5400 \
        --idle 1500 --watch "<P03>/Benchmarks/Raw" -- "python -I -u \"<P03>/Tools/run_checks.py\" s1"

Every step does the same first four things, then its own checks:
  1. build the editor target and 2. the game target (Development), counting compiler warnings and errors;
  3. run the project's automation tests in the editor (StartsWith:TestTrust) and read index.json;
  4. package a Development build (BuildCookRun);
  5. step-specific packaged runs, pinned to the performance cores (tt_common.pinned), each with a CSV capture.
Everything is written to Benchmarks/Raw/<batch>_<step>check_manifest.json; captures and logs go next to it (ignored).
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)
import csv_stats  # noqa: E402  (same folder)
import tt_common  # noqa: E402

PROJECT_DIR = os.path.dirname(TOOLS_DIR)
RAW_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Raw")
UE_DIR = os.path.join(PROJECT_DIR, "TestTrust")
EDITOR_CMD = os.path.join(tt_common.ENGINE_ROOT, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
EXE, PACKAGED_SAVED, GATE_ARGS = tt_common.PACKAGED_EXE, tt_common.PACKAGED_SAVED, tt_common.GATE_ARGS
COLUMNS = csv_stats.DEFAULT_COLUMNS


def run(name: str, batch: str, command: str, timeout: float) -> dict:
    log_path = os.path.join(RAW_DIR, f"{batch}_{name}.log")
    print(f"[checks] {dt.datetime.now():%H:%M:%S} {name}", flush=True)
    started = time.perf_counter()
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        log.write(f"# {command}\n")
        log.flush()
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait(timeout=60)
            code = None
    with open(log_path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    result = {"step": name, "exit_code": code, "seconds": round(time.perf_counter() - started, 1),
              "log": os.path.basename(log_path)}
    print(f"[checks] {name}: exit {code} in {result['seconds']} s", flush=True)
    return result | {"_text": text}


def build(batch: str, target: str) -> dict:
    command = f'cmd.exe /d /c call "{os.path.join(TOOLS_DIR, "build.bat")}" {target} Development'
    result = run(f"build_{target}", batch, command, 3600)
    text = result.pop("_text")
    result["compiler_warnings"] = len(re.findall(r"\bwarning (C|LNK)\d{4}\b", text))
    result["compiler_errors"] = len(re.findall(r"\berror (C|LNK)\d{4}\b", text))
    result["succeeded"] = "Result: Succeeded" in text
    return result


def tests(batch: str, test_filter: str) -> dict:
    report_dir = os.path.join(UE_DIR, "Saved", "Automation", "Reports")
    if os.path.exists(report_dir):
        shutil.rmtree(report_dir)
    command = f'cmd.exe /d /c call "{os.path.join(TOOLS_DIR, "run_tests.bat")}" {test_filter}'
    result = run("tests", batch, command, 900)
    result.pop("_text")
    index = os.path.join(report_dir, "index.json")
    if os.path.exists(index):
        with open(index, encoding="utf-8-sig") as handle:
            data = json.load(handle)
        result["report"] = {key: data.get(key) for key in ("succeeded", "succeededWithWarnings", "failed", "notRun")}
        result["report"]["tests"] = sorted(t.get("fullTestPath") for t in data.get("tests", []))
    return result


def package(batch: str) -> dict:
    result = run("package", batch, f'cmd.exe /d /c call "{os.path.join(TOOLS_DIR, "package.bat")}" Development', 5400)
    text = result.pop("_text")
    result["succeeded"] = "BUILD SUCCESSFUL" in text
    result["cook_line"] = next((line.strip()[-60:] for line in text.splitlines() if "Success - " in line), None)
    return result


def packaged_run(batch: str, name: str, extra_args: str) -> dict:
    """One pinned packaged run; its CSV, log and statistics. Raw files are moved into Benchmarks/Raw."""
    csv_dir = os.path.join(PACKAGED_SAVED, "Profiling", "CSV")
    gus = os.path.join(PACKAGED_SAVED, "Config", "Windows", "GameUserSettings.ini")
    if os.path.exists(gus):
        os.remove(gus)   # it can override VSync and frame-rate caps (UE5-UpdateBudget's finding)
    started = time.time()
    command = tt_common.pinned(f'"{EXE}" {GATE_ARGS} -TTRunTag={batch}_{name} {extra_args}')
    result = run(name, batch, command, 600)
    result.pop("_text")
    result["args"] = extra_args
    captures = [p for p in glob.glob(os.path.join(csv_dir, "*.csv")) if os.path.getmtime(p) >= started]
    if captures:
        destination = os.path.join(RAW_DIR, f"{batch}_{name}.csv")
        shutil.move(max(captures, key=os.path.getmtime), destination)
        analysis = csv_stats.analyse(destination, COLUMNS)
        result.update(frames=analysis["frames"], finalised=analysis["finalised"], events=analysis["events"],
                      metadata={k: v for k, v in analysis["metadata"].items() if k.startswith("tt")},
                      stats=analysis["columns"], capture=os.path.basename(destination))
    game_log = os.path.join(PACKAGED_SAVED, "Logs", "TestTrust.log")
    if os.path.exists(game_log) and os.path.getmtime(game_log) >= started:
        with open(game_log, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        result["log_errors"] = text.count("Error:")
        result["log_warnings"] = text.count("Warning:")
        result["probe_lines"] = [line.split(": Display: ")[-1].strip() for line in text.splitlines()
                                 if "LogTTProbe:" in line or "LogTTWorkload:" in line]
        shutil.copy(game_log, os.path.join(RAW_DIR, f"{batch}_{name}_game.log"))
    return result


def editor_run(batch: str, name: str, extra_args: str) -> dict:
    """One uncooked run in the editor's -game mode (no rendering, not pinned: nothing is timed); its probe lines."""
    log_path = os.path.join(RAW_DIR, f"{batch}_{name}_game.log")
    project = os.path.join(UE_DIR, "TestTrust.uproject")
    command = (f'"{EDITOR_CMD}" "{project}" -game -nullrhi -nosound -unattended -nosplash -traceautostart=0 '
               f'-deterministic -FPS=60 -TTProbe -TTExit -TTRunTag={batch}_{name} {extra_args} -log -abslog="{log_path}"')
    result = run(name, batch, command, 600)
    result.pop("_text")
    result["args"] = extra_args
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        result["log_errors"] = text.count("Error:")
        result["probe_lines"] = [line.split(": Display: ")[-1].strip() for line in text.splitlines()
                                 if "LogTTProbe:" in line or "LogTTWorkload:" in line]
    return result


def common(batch: str, results: list, save) -> bool:
    for target in ("TestTrustEditor", "TestTrust"):
        results.append(build(batch, target))
        save()
        if not results[-1]["succeeded"]:
            return False
    results.append(tests(batch, "StartsWith:TestTrust"))
    save()
    results.append(package(batch))
    save()
    return results[-1]["succeeded"]


def step_s1(batch: str, results: list, save) -> None:
    # Same window, same frames; one run with 1.0 ms injected per frame and one without.
    for name, args in (("X10", "-TTWarmup=3 -TTCapture=10 -TTInjectMs=1.0"), ("X0", "-TTWarmup=3 -TTCapture=10")):
        results.append(packaged_run(batch, name, args))
        save()


def step_s2(batch: str, results: list, save) -> None:
    # The S1 runs again (the probe changed after its own check), then the calibration of the compute step at
    # N = 1,000 (one priming run first), then the determinism check: the W128 run repeated with the same seed must give
    # the same start- and end-state hashes. The repeat leaves out -TTWork, so it also checks the class default (128).
    step_s1(batch, results, save)
    runs = [("W128_r0_prime", "-TTWork=128"), ("W64", "-TTWork=64"), ("W128", "-TTWork=128"), ("W256", "-TTWork=256"),
            ("W128_repeat", "")]
    for name, work in runs:
        results.append(packaged_run(batch, name, f"-TTWarmup=3 -TTCapture=10 -TTAgents=1000 -TTSeed=1 {work}".strip()))
        save()


def step_s2editor(batch: str, results: list, save) -> None:
    # The determinism check in the editor's -game mode (uncooked, modular build), as 03 S2 asks: two runs, same seed.
    for name in ("E128", "E128_repeat"):
        results.append(editor_run(batch, name, "-TTWarmup=3 -TTCapture=10 -TTAgents=1000 -TTSeed=1"))
        save()


STEPS = {"s1": step_s1, "s2": step_s2, "s2editor": step_s2editor}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    step = argv[0] if argv else ""
    if step not in STEPS:
        print(f"usage: run_checks.py {{{','.join(STEPS)}}}")
        return 2
    batch = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S") + f"_{step}check"
    os.makedirs(RAW_DIR, exist_ok=True)
    results: list[dict] = []
    environment = tt_common.environment_record("Development (editor target, game target, packaged)",
                                               {"gate_args": GATE_ARGS})

    def save() -> None:
        with open(os.path.join(RAW_DIR, batch + "_manifest.json"), "w", encoding="utf-8") as handle:
            json.dump({"batch": batch, "step": step, "environment": environment, "results": results}, handle, indent=1)

    if common(batch, results, save):
        STEPS[step](batch, results, save)
    save()
    failed = [r["step"] for r in results if r.get("exit_code") != 0]
    print(f"[checks] {batch}: {len(results)} steps, failed: {failed or 'none'}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
