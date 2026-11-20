"""P03 TestTrust - Phase 2 probe: what does one source-level mutant cost to build and test?

Run it ONLY through the machine-wide UE job queue (it starts UnrealBuildTool and UnrealEditor-Cmd):
    python -I -u "D:/UNREAL PORTFOLIO/tools/ue_queue.py" run --project P03 --label "P03 Phase 2 build-cost probe" \
        --timeout 3600 --idle 900 --watch "<P03>/Benchmarks/Raw" -- python -I -u "<P03>/Tools/probe_build_cost.py"

What it does (one batch, one queue job, bounded by the queue timeout):
  1. Snapshots the target UE project at a pinned commit with `git archive` into Tools/_work/ (git-ignored).
     The target repository is only read: `git rev-parse` and `git archive` on a commit object, never its working tree.
  2. Builds the editor target of the snapshot from cold, then once more with nothing changed.
  3. Applies one mutation at a time and rebuilds: a .cpp in a project-Source game module, a .cpp in a plugin module,
     and a default value in a UObject header (the UHT path). Each is restored and rebuilt afterwards.
  4. Starts UnrealEditor-Cmd on the snapshot and runs one tiny engine automation test, twice in editor mode
     (cold, warm) and once in -game mode, to measure the fixed per-mutant test-launch cost.
  5. Writes Benchmarks/Raw/<batch>_manifest.json (numbers, action lines, exit codes; no personal paths) and keeps
     each step's full log next to it as <batch>_<step>.log (git-ignored).
This is research instrumentation, not the mutation runner: the runner (Phase 4) is designed from its numbers.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TOOLS_DIR)
RAW_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Raw")
WORK_DIR = os.path.join(TOOLS_DIR, "_work")

ENGINE = r"C:\Program Files\Epic Games\UE_5.8\Engine"
BUILD_BAT = os.path.join(ENGINE, "Build", "BatchFiles", "Build.bat")
EDITOR_CMD = os.path.join(ENGINE, "Binaries", "Win64", "UnrealEditor-Cmd.exe")

# The target: UE5-UpdateBudget at its only commit on 2026-11-21 (read-only for this project).
TARGET_REPO = r"D:\UNREAL PORTFOLIO\P01_UpdateBudget"
TARGET_COMMIT = "c25a996"
TARGET_SUBDIR = "UpdateBudget"           # the UE project folder inside the repository
UPROJECT = "UpdateBudget.uproject"
EDITOR_TARGET = "UpdateBudgetEditor"

# One mutation per code path. (file relative to the UE project, exact original text, replacement)
MUTATIONS = {
    "game_cpp": ("Source/UpdateBudget/Private/UBDemoBrainComponent.cpp",
                 "DistanceSquared < FMath::Square(AlertRadius)", "DistanceSquared <= FMath::Square(AlertRadius)"),
    "plugin_cpp": ("Plugins/UpdateBudgetCore/Source/UpdateBudgetCore/Private/UpdateBudgetSubsystem.cpp",
                   "if (Client->RegistryIndex != INDEX_NONE)", "if (Client->RegistryIndex == INDEX_NONE)"),
    "uobject_header": ("Source/UpdateBudget/Public/UBDemoBrainComponent.h",
                       "float PatrolRadius = 300.f;", "float PatrolRadius = 301.f;"),
}

# A fast engine test that exists in every Development editor (Core/Private/Tests/HAL/FileManagerTest.cpp:9).
PROBE_TEST_FILTER = "StartsWith:System.Core.HAL.FileManager"

BUILD_TIMEOUT_S = 1500
TEST_TIMEOUT_S = 420
ACTION_LINE = re.compile(r"^\[\d+/\d+\] .*")


def sanitize(text: str) -> str:
    """Personal paths never reach a committed file."""
    home = os.path.expanduser("~")
    return text.replace(home, "%USERPROFILE%").replace(home.replace("\\", "/"), "%USERPROFILE%")


def git(*args: str) -> str:
    return subprocess.run(["git", "--no-optional-locks", "-C", TARGET_REPO, *args],
                          capture_output=True, text=True, check=True).stdout


def snapshot(destination: str) -> dict:
    """Extracts TARGET_SUBDIR at TARGET_COMMIT into destination. Returns the provenance record."""
    # The target is developed in parallel, so its working tree may change while we run. That is why the snapshot
    # comes from a commit object (immutable) and never from the working tree, and why only read-only git commands
    # are used. Our own writes go to `destination`, which must lie outside the target repository.
    if os.path.commonpath([os.path.abspath(destination), os.path.abspath(TARGET_REPO)]) == os.path.abspath(TARGET_REPO):
        raise RuntimeError("the snapshot must not be written inside the target repository")
    full_hash = git("rev-parse", TARGET_COMMIT + "^{commit}").strip()
    archive = subprocess.run(["git", "--no-optional-locks", "-C", TARGET_REPO, "archive", "--format=tar",
                              full_hash, TARGET_SUBDIR], capture_output=True, check=True).stdout
    if os.path.exists(destination):
        shutil.rmtree(destination)
    os.makedirs(destination)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")
    return {"repo": "UE5-UpdateBudget", "commit": full_hash, "subdir": TARGET_SUBDIR}


def run_logged(name: str, batch: str, command: str, timeout: float) -> dict:
    """Runs one command string (quoted by hand, as P01's run_bench.py does) with its output in a step log."""
    log_path = os.path.join(RAW_DIR, f"{batch}_{name}.log")
    print(f"[probe] {dt.datetime.now():%H:%M:%S} start {name}", flush=True)
    started = time.perf_counter()
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        log.write(f"# {command}\n")
        log.flush()
        try:
            exit_code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            exit_code = None
    seconds = round(time.perf_counter() - started, 2)
    with open(log_path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    print(f"[probe] {name}: exit {exit_code} in {seconds} s", flush=True)
    return {"step": name, "exit_code": exit_code, "seconds": seconds, "log": os.path.basename(log_path), "text": text}


def build(name: str, batch: str, uproject: str) -> dict:
    # -Log= gives this step its own UBT debug log (GlobalOptions.cs:33), which is where UHT and the adaptive-unity
    # working set are reported (UHTExecution.cs logs "Parsing headers for ..." at debug level).
    ubt_log = os.path.join(RAW_DIR, f"{batch}_{name}_ubt.txt")
    command = (f'cmd.exe /d /c call "{BUILD_BAT}" {EDITOR_TARGET} Win64 Development "-Project={uproject}" '
               f'-WaitMutex -NoHotReloadFromIDE "-Log={ubt_log}"')
    record = run_logged(name, batch, command, BUILD_TIMEOUT_S)
    lines = record.pop("text").splitlines()
    debug_lines = []
    if os.path.exists(ubt_log):
        with open(ubt_log, encoding="utf-8", errors="replace") as handle:
            debug_lines = handle.read().splitlines()
    record["actions"] = [sanitize(line.strip()) for line in lines if ACTION_LINE.match(line.strip())]
    record["compile_actions"] = sum(1 for a in record["actions"] if "Compile" in a)
    record["link_actions"] = sum(1 for a in record["actions"] if "Link" in a)
    record["uht_ran"] = any("Parsing headers for" in line for line in debug_lines)
    record["uht_up_to_date"] = any("Generated code is up to date" in line for line in debug_lines)
    record["working_set_lines"] = [sanitize(l.strip()) for l in debug_lines + lines
                                   if "working set" in l or "[Adaptive" in l or "git status" in l][:12]
    record["errors"] = sum(1 for line in lines if re.search(r"\berror\b", line, re.I) and "0 error" not in line)
    record["warnings"] = sum(1 for line in lines if re.search(r"\bwarning\b", line, re.I) and "0 warning" not in line)
    record["ubt_total"] = next((sanitize(l.strip()) for l in lines if "Total execution time" in l), None)
    record["result_line"] = next((sanitize(l.strip()) for l in reversed(lines) if l.strip().startswith("Result:")), None)
    return record


def editor_tests(name: str, batch: str, uproject: str, game_mode: bool) -> dict:
    # The report folder also holds an HTML page with absolute asset links, so it goes into the snapshot's Saved
    # folder (git-ignored and skipped by the portfolio link checker); its numbers are copied into the manifest.
    report_dir = os.path.join(os.path.dirname(uproject), "Saved", "ProbeReports", f"{batch}_{name}_report")
    abslog = os.path.join(RAW_DIR, f"{batch}_{name}_engine.log")
    mode = "-game " if game_mode else ""
    command = (f'"{EDITOR_CMD}" "{uproject}" {mode}-nullrhi -nosound -unattended -nosplash -nopause '
               f'-traceautostart=0 -ExecCmds="Automation RunTests {PROBE_TEST_FILTER};Quit" '
               f'-ReportExportPath="{report_dir}" -log -abslog="{abslog}"')
    record = run_logged(name, batch, command, TEST_TIMEOUT_S)
    text = record.pop("text")
    record["test_complete_line"] = next((l.strip()[-60:] for l in text.splitlines() if "TEST COMPLETE" in l), None)
    index = os.path.join(report_dir, "index.json")
    if os.path.exists(index):
        with open(index, encoding="utf-8-sig") as handle:
            report = json.load(handle)
        record["report"] = {key: report.get(key) for key in ("succeeded", "succeededWithWarnings", "failed",
                                                            "notRun", "inProcess", "totalDuration")}
        record["report"]["tests"] = [t.get("fullTestPath") for t in report.get("tests", [])]
    else:
        record["report"] = None
    return record


def mutate(project: str, key: str, apply: bool) -> None:
    relative, original, replacement = MUTATIONS[key]
    path = os.path.join(project, relative)
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    old, new = (original, replacement) if apply else (replacement, original)
    if text.count(old) != 1:
        raise RuntimeError(f"{relative}: expected exactly one '{old}'")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace(old, new))


def main() -> int:
    batch = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_buildcost"
    os.makedirs(RAW_DIR, exist_ok=True)
    copy_root = os.path.join(WORK_DIR, f"probe_{TARGET_COMMIT}")
    provenance = snapshot(copy_root)
    project = os.path.join(copy_root, TARGET_SUBDIR)
    uproject = os.path.join(project, UPROJECT)
    steps: list[dict] = []
    manifest_path = os.path.join(RAW_DIR, batch + "_manifest.json")

    def save() -> None:
        manifest = {"batch": batch, "purpose": "Phase 2: build and test cost per source-level mutant",
                    "target": provenance, "copy": os.path.relpath(copy_root, PROJECT_DIR), "steps": steps}
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)

    plan = [
        ("b0_cold", None, None), ("b1_noop", None, None),
        ("b2_game_cpp", "game_cpp", True), ("b3_game_cpp_restore", "game_cpp", False),
        ("b4_plugin_cpp", "plugin_cpp", True), ("b5_plugin_cpp_restore", "plugin_cpp", False),
        ("b6_header", "uobject_header", True), ("b7_header_restore", "uobject_header", False),
    ]
    for name, key, apply in plan:
        if key:
            mutate(project, key, apply)
        steps.append(build(name, batch, uproject))
        save()
        if steps[-1]["exit_code"] != 0:
            print(f"[probe] stopping: {name} failed", flush=True)
            return 1
    for name, game_mode in (("t1_editor_cold", False), ("t2_editor_warm", False), ("t3_game_mode", True)):
        steps.append(editor_tests(name, batch, uproject, game_mode))
        save()

    save()
    print(f"[probe] manifest: {os.path.relpath(manifest_path, PROJECT_DIR)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
