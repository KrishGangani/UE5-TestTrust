"""P03 TestTrust - the mutation runner: how many injected faults does a UE C++ automation suite catch?

Commands
  plan     --config FILE [--campaign ID]
                                    Snapshot the target at its pinned commit and list every mutant (a "campaign").
                                    --campaign re-plans an existing campaign that has no results yet.
  batch    --campaign ID [--max-seconds S]
                                    Run inside ONE machine-queue job: restore the snapshot, check that the unmutated
                                    code builds and its suite passes, then build and test one mutant at a time until the
                                    time budget is spent. Every result is saved immediately, so the next batch resumes.
  queue    --campaign ID [--batch-seconds S]
                                    Submit batches to the machine queue until every mutant has a fate.
  report   --campaign ID            Write the score and the survivor list to Benchmarks/Summaries.
  selftest                          Check classification, scoring and planning logic without Unreal.

Safety rules (02 section 8):
  - The target repository is only read, with `git rev-parse`, `git archive` and `git check-ignore` on a commit object.
    Its working tree is never read or written, so work in progress there can't leak in.
  - The snapshot goes to Tools/_work/<campaign>/, which is outside the target repository or ignored by it.
  - Only .cpp files are mutated (a header change re-runs UHT and rebuilds every includer, 01b section 1).
  - Every mutant is tested in a fresh UnrealEditor-Cmd process, pinned to the performance cores, with a timeout.

Fates: killed (a test failed), survived (every test passed), stillborn (it didn't compile; excluded from the score),
timeout and crash (counted as killed, listed separately), error (infrastructure; retried by the next batch).
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tarfile
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)
import tt_common  # noqa: E402  (same folder)
import tt_mutants  # noqa: E402

PROJECT_DIR = os.path.dirname(TOOLS_DIR)
RAW_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Raw")
SUMMARY_DIR = os.path.join(PROJECT_DIR, "Benchmarks", "Summaries")
WORK_DIR = os.path.join(TOOLS_DIR, "_work")
QUEUE = r"D:\UNREAL PORTFOLIO\tools\ue_queue.py"

ENGINE = os.path.join(tt_common.ENGINE_ROOT, "Engine")
BUILD_BAT = os.path.join(ENGINE, "Build", "BatchFiles", "Build.bat")
EDITOR_CMD = os.path.join(ENGINE, "Binaries", "Win64", "UnrealEditor-Cmd.exe")

BUILD_TIMEOUT_S = 1200
MIN_TEST_TIMEOUT_S = 120
COMPILE_ERROR = re.compile(r"\berror (C|LNK)\d{4}\b|\bfatal error (C|LNK)\d{4}\b")
KILLED_LIKE = ("killed", "timeout", "crash")


# --------------------------------------------------------------------------------------------------- campaign storage

def manifest_path(campaign: str) -> str:
    return os.path.join(RAW_DIR, campaign + "_manifest.json")


def load(campaign: str) -> dict:
    with open(manifest_path(campaign), encoding="utf-8") as handle:
        return json.load(handle)


def save(manifest: dict) -> None:
    """Atomic rewrite, so a batch killed by the queue never leaves a half-written manifest."""
    path = manifest_path(manifest["campaign"])
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
    os.replace(path + ".tmp", path)


def project_root(manifest: dict) -> str:
    return os.path.join(WORK_DIR, manifest["campaign"], manifest["config"]["project_subdir"])


def pristine_root(manifest: dict) -> str:
    return os.path.join(WORK_DIR, manifest["campaign"], "_pristine")


def log_dir(campaign: str) -> str:
    return os.path.join(RAW_DIR, campaign)


# ----------------------------------------------------------------------------------------------------- plan (snapshot)

def git(repo: str, *args: str, binary: bool = False):
    result = subprocess.run(["git", "--no-optional-locks", "-C", repo, *args], capture_output=True, check=True)
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def check_destination(repo: str, destination: str) -> None:
    """The snapshot must be outside the target repository, or inside a folder that repository ignores."""
    repo, destination = os.path.abspath(repo), os.path.abspath(destination)
    if os.path.commonpath([repo, destination]) != repo:
        return
    ignored = subprocess.run(["git", "--no-optional-locks", "-C", repo, "check-ignore", "-q", destination]).returncode == 0
    if not ignored:
        raise RuntimeError(f"refusing to write a snapshot inside the target repository: {destination}")


def snapshot(config: dict, destination: str) -> str:
    """Extracts the target's UE project at the pinned commit. Returns the full commit hash."""
    check_destination(config["repo"], destination)
    commit = git(config["repo"], "rev-parse", config["commit"] + "^{commit}")
    archive = git(config["repo"], "archive", "--format=tar", commit, config["project_subdir"], binary=True)
    if os.path.exists(destination):
        shutil.rmtree(destination)
    os.makedirs(destination)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")
    return commit


def files_to_mutate(project: str, config: dict) -> list[str]:
    """Project-relative .cpp paths (forward slashes) matching `mutate` and not `exclude`, sorted."""
    found = []
    for folder, _, names in os.walk(project):
        for name in names:
            relative = os.path.relpath(os.path.join(folder, name), project).replace("\\", "/")
            if not relative.endswith(".cpp"):
                continue   # headers are never mutated (UHT, 01b section 1)
            if any(fnmatch.fnmatch(relative, p) for p in config["mutate"]) and \
                    not any(fnmatch.fnmatch(relative, p) for p in config.get("exclude", [])):
                found.append(relative)
    return sorted(found)


def apply_patch(path: str, root: str) -> list[str]:
    """Applies one patch file to the snapshot at root, never to the target; returns the files it changed.

    The snapshot lies inside this repository's ignored tree, where a plain `git apply` resolves paths against this
    repository and silently changes nothing (tested 2026-11-21: exit 0, file unchanged). GIT_CEILING_DIRECTORIES
    stops git's repository search at the snapshot, so it patches like a plain `patch` tool (main() removes any
    inherited GIT_DIR, which would override the search). --ignore-whitespace: the snapshot has CRLF line endings, the
    patch LF (git diff normalised it, 05 H1). Every target must really change.
    """
    environment = dict(os.environ, GIT_CEILING_DIRECTORIES=os.path.dirname(os.path.abspath(root)))

    def git_apply(*options: str) -> str:
        result = subprocess.run(["git", "apply", "-p1", "--ignore-whitespace", "--whitespace=nowarn", *options, path],
                                cwd=root, env=environment, capture_output=True)
        if result.returncode != 0:   # keep git's reason (which hunk failed), not just the exit status
            raise RuntimeError(f"git apply {' '.join(options)} {path}: {result.stderr.decode(errors='replace').strip()}")
        return result.stdout.decode("utf-8", errors="replace")

    # --numstat -z lists the files the patch touches ("added<TAB>deleted<TAB>path<NUL>"), spaces included.
    fields = [r.split("\t") for r in git_apply("--numstat", "-z").split("\0") if r]
    if not fields or any(len(f) != 3 or not f[2] for f in fields):
        raise RuntimeError(f"patch {path}: no files, or a rename (not supported): {fields}")
    targets = [f[2] for f in fields]

    def content(target: str) -> str | None:   # None = no such file, so creating or deleting an empty file counts
        file = os.path.join(root, target)
        return read_text(file) if os.path.exists(file) else None

    before = {t: content(t) for t in targets}
    git_apply()
    unchanged = [t for t in targets if content(t) == before[t]]
    if unchanged:
        raise RuntimeError(f"patch {path} changed nothing in {unchanged}")
    return targets


def apply_patches(config: dict, root: str) -> list[dict]:
    """Applies the config's patch files (Tools/mutation/<name>) to the snapshot; returns one record per patch."""
    applied = []
    for name in config.get("patches", []):
        path = os.path.join(TOOLS_DIR, "mutation", name)
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        applied.append({"file": name, "sha256": digest, "targets": apply_patch(path, root)})
    return applied


def cmd_plan(args) -> int:
    with open(args.config, encoding="utf-8") as handle:
        config = json.load(handle)
    campaign = args.campaign or dt.datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_mut-" + config["name"]
    if args.campaign and os.path.exists(manifest_path(campaign)):
        # Re-planning keeps a queued campaign's id (and its place in the machine queue), but only before any result
        # exists: results must never be mixed across two commits.
        if any(m["fate"] for m in load(campaign)["mutants"]) or load(campaign)["baselines"]:
            raise RuntimeError(f"{campaign} already has results; plan a new campaign instead")
    root = os.path.join(WORK_DIR, campaign)
    commit = snapshot(config, root)
    patches = apply_patches(config, root)   # before the pristine copies, so mutants are planned on the patched tree
    project = os.path.join(root, config["project_subdir"])
    mutants = []
    for relative in files_to_mutate(project, config):
        with open(os.path.join(project, relative), encoding="utf-8", newline="") as handle:
            source = handle.read()
        pristine = os.path.join(root, "_pristine", relative)
        os.makedirs(os.path.dirname(pristine), exist_ok=True)
        with open(pristine, "w", encoding="utf-8", newline="") as handle:
            handle.write(source)
        for m in tt_mutants.generate(relative, source, tuple(config.get("operators", tt_mutants.ALL_OPERATORS))):
            mutants.append({"id": m.id, "file": m.file, "operator": m.operator, "line": m.line, "col": m.col,
                            "start": m.start, "end": m.end, "original": m.original, "replacement": m.replacement,
                            "fate": None, "attempts": 0})
    manifest = {
        "campaign": campaign,
        "purpose": "mutation campaign (02 section 4.1)",
        "config": {k: v for k, v in config.items() if k != "repo"},
        "target": {"repo": config["repo_name"], "commit": commit, "subdir": config["project_subdir"], "patches": patches},
        "environment": tt_common.environment_record(
            "Development editor target, tests in UnrealEditor-Cmd -nullrhi (not packaged)",
            {"runner": "Tools/tt_mutate.py", "snapshot": os.path.relpath(root, PROJECT_DIR).replace("\\", "/"),
             "pinning": "test launches pinned to cpu_affinity via tt_common.pinned(); builds unpinned"}),
        "mutants": mutants,
        "baselines": [],
        "batches": [],
    }
    os.makedirs(RAW_DIR, exist_ok=True)
    save(manifest)
    print(f"campaign {campaign}: {len(mutants)} mutants in {len({m['file'] for m in mutants})} file(s), commit {commit[:12]}")
    return 0


# ------------------------------------------------------------------------------------------------------ batch (UE jobs)

def run_step(command: str, log_path: str, timeout: float) -> tuple[int | None, float]:
    """Runs one command string; on timeout kills the whole process tree. Returns (exit code or None, seconds)."""
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
    return code, round(time.perf_counter() - started, 2)


def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def build(manifest: dict, name: str) -> dict:
    folder = log_dir(manifest["campaign"])
    uproject = os.path.join(project_root(manifest), manifest["config"]["uproject"])
    ubt_log = os.path.join(folder, name + "_ubt.txt")
    command = (f'cmd.exe /d /c call "{BUILD_BAT}" {manifest["config"]["editor_target"]} Win64 Development '
               f'"-Project={uproject}" -WaitMutex -NoHotReloadFromIDE "-Log={ubt_log}"')
    log_path = os.path.join(folder, name + "_build.log")
    code, seconds = run_step(command, log_path, BUILD_TIMEOUT_S)
    text = read_text(log_path)
    return {"exit_code": code, "seconds": seconds,
            "compile_actions": len(re.findall(r"^\[\d+/\d+\] Compile", text, re.M)),
            "compile_error": bool(COMPILE_ERROR.search(text))}


def run_tests(manifest: dict, name: str, timeout: float) -> dict:
    folder = log_dir(manifest["campaign"])
    uproject = os.path.join(project_root(manifest), manifest["config"]["uproject"])
    # The report (index.json + an HTML page with absolute asset links) goes into the snapshot's Saved folder, which
    # git ignores and the portfolio's link checker skips; its numbers are copied into the manifest below.
    report_dir = os.path.join(project_root(manifest), "Saved", "TestTrustReports", name)
    engine_log = os.path.join(folder, name + "_engine.log")
    if os.path.exists(report_dir):
        shutil.rmtree(report_dir)
    # "Now" first: the controller otherwise waits a fixed 5 s before looking for workers (DefaultDelayTimer,
    # AutomationCommandline.cpp:871; "Now" sets it to 0 at :606-609). Measured by the Phase 2 probe (09, P2).
    editor = (f'"{EDITOR_CMD}" "{uproject}" -nullrhi -nosound -unattended -nosplash -nopause -traceautostart=0 '
              f'-ExecCmds="Automation Now;RunTests {manifest["config"]["test_filter"]};Quit" '
              f'-ReportExportPath="{report_dir}" -log -abslog="{engine_log}"')
    code, seconds = run_step(tt_common.pinned(editor, console=True), os.path.join(folder, name + "_test.log"), timeout)
    report = None
    index = os.path.join(report_dir, "index.json")
    if os.path.exists(index):
        with open(index, encoding="utf-8-sig") as handle:
            data = json.load(handle)
        report = {key: data.get(key, 0) for key in ("succeeded", "succeededWithWarnings", "failed", "notRun")}
        report["failed_tests"] = [t.get("fullTestPath") for t in data.get("tests", []) if t.get("state") == "Fail"]
    return {"exit_code": code, "seconds": seconds, "report": report,
            "test_complete": "TEST COMPLETE" in read_text(engine_log)}


def classify(build_result: dict, test_result: dict | None, baseline_tests: int) -> str:
    """The fate of one mutant (02 section 4.1). Pure function, covered by the self-test."""
    if build_result["exit_code"] is None:
        return "error"                         # the build itself hung: an infrastructure problem
    if build_result["exit_code"] != 0:
        return "stillborn" if build_result["compile_error"] else "error"
    if test_result is None:
        return "error"
    if test_result["exit_code"] is None:
        return "timeout"
    report = test_result["report"]
    if report is None:
        return "crash"                         # the process ended before the controller wrote its report
    completed = report["succeeded"] + report["succeededWithWarnings"] + report["failed"]
    if report["failed"] > 0 or completed < baseline_tests or test_result["exit_code"] != 0:
        return "killed"
    return "survived"


def restore(manifest: dict) -> None:
    """Every file the campaign mutates goes back to its pristine text (also undoes a batch killed mid-mutant)."""
    for relative in sorted({m["file"] for m in manifest["mutants"]}):
        with open(os.path.join(pristine_root(manifest), relative), encoding="utf-8", newline="") as handle:
            pristine = handle.read()
        target = os.path.join(project_root(manifest), relative)
        if read_text(target) != pristine:
            with open(target, "w", encoding="utf-8", newline="") as handle:
                handle.write(pristine)


def pending(manifest: dict) -> list[dict]:
    """Mutants without a fate, then infrastructure errors once more (each mutant gets at most two attempts)."""
    return [m for m in manifest["mutants"] if m["fate"] is None or (m["fate"] == "error" and m["attempts"] < 2)]


def estimate_seconds(manifest: dict, baseline: dict) -> float:
    done = [m["build_s"] + m.get("test_s", 0.0) for m in manifest["mutants"] if m.get("build_s") is not None]
    return statistics.median(done) if done else baseline["build_s"] + baseline["test_s"] + 60.0


def cmd_batch(args) -> int:
    manifest = load(args.campaign)
    started, clock = dt.datetime.now().isoformat(timespec="seconds"), time.perf_counter()
    os.makedirs(log_dir(args.campaign), exist_ok=True)
    batch_index = len(manifest["batches"]) + 1
    record = {"batch": batch_index, "started": started, "max_seconds": args.max_seconds, "mutants_run": 0}
    manifest["batches"].append(record)

    restore(manifest)
    base_build = build(manifest, f"b{batch_index:02d}_baseline")
    base_tests = run_tests(manifest, f"b{batch_index:02d}_baseline", MIN_TEST_TIMEOUT_S * 3) \
        if base_build["exit_code"] == 0 else None
    report = (base_tests or {}).get("report") or {}
    baseline = {"batch": batch_index, "build_s": base_build["seconds"], "build_exit": base_build["exit_code"],
                "test_s": (base_tests or {}).get("seconds"), "test_exit": (base_tests or {}).get("exit_code"),
                "tests": report.get("succeeded", 0) + report.get("succeededWithWarnings", 0) + report.get("failed", 0),
                "failed": report.get("failed")}
    manifest["baselines"].append(baseline)
    if base_build["exit_code"] != 0 or not base_tests or base_tests["exit_code"] != 0 or not report \
            or report["failed"] or baseline["tests"] == 0:
        record.update(ended=dt.datetime.now().isoformat(timespec="seconds"),
                      stopped="baseline not green: the unmutated snapshot must build and pass before mutants run")
        save(manifest)
        print("[mutate] baseline is not green; no mutant was run", flush=True)
        return 3
    save(manifest)
    test_timeout = max(MIN_TEST_TIMEOUT_S, 3.0 * baseline["test_s"])
    print(f"[mutate] baseline green: {baseline['tests']} tests, build {baseline['build_s']} s, tests {baseline['test_s']} s",
          flush=True)

    record["stopped"] = None                  # set when the loop ends, so a running batch never claims a reason
    for mutant in pending(manifest):
        elapsed = time.perf_counter() - clock
        if elapsed + estimate_seconds(manifest, baseline) > args.max_seconds:
            record["stopped"] = "time budget reached"
            break
        mutant["attempts"] += 1
        path = os.path.join(project_root(manifest), mutant["file"])
        # Defaults describe "nothing ran", so a failure before the build (a file that changed since planning, a
        # locked file) is classified as an infrastructure error instead of crashing the batch.
        build_result = {"exit_code": None, "seconds": 0.0, "compile_actions": 0, "compile_error": False}
        test_result, mutant["detail"] = None, None
        try:
            with open(os.path.join(pristine_root(manifest), mutant["file"]), encoding="utf-8", newline="") as handle:
                pristine = handle.read()
            mutated = tt_mutants.Mutant(mutant["file"], mutant["operator"], mutant["start"], mutant["end"],
                                        mutant["original"], mutant["replacement"], mutant["line"], mutant["col"]).apply(pristine)
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(mutated)
            name = f"{mutant['id']}_a{mutant['attempts']}"
            build_result = build(manifest, name)
            test_result = run_tests(manifest, name, test_timeout) if build_result["exit_code"] == 0 else None
        except (OSError, ValueError) as problem:
            mutant["detail"] = str(problem)
        finally:
            restore(manifest)
        mutant["fate"] = classify(build_result, test_result, baseline["tests"])
        mutant["build_s"] = build_result["seconds"]
        mutant["compile_actions"] = build_result["compile_actions"]
        mutant["test_s"] = test_result["seconds"] if test_result else 0.0
        mutant["failed_tests"] = ((test_result or {}).get("report") or {}).get("failed_tests", [])
        mutant["batch"] = batch_index
        record["mutants_run"] += 1
        save(manifest)
        print(f"[mutate] {mutant['id']} {mutant['file']}:{mutant['line']} {mutant['operator']} "
              f"{mutant['original'][:30]!r}->{mutant['replacement'][:30]!r}: {mutant['fate']} "
              f"(build {mutant['build_s']} s, test {mutant['test_s']} s)", flush=True)
    record["stopped"] = record["stopped"] or ("all mutants have a fate" if not pending(manifest)
                                              else "remaining mutants are errors with no attempts left")
    record["ended"] = dt.datetime.now().isoformat(timespec="seconds")
    record["seconds"] = round(time.perf_counter() - clock, 1)
    save(manifest)
    print(f"[mutate] batch {batch_index}: {record['mutants_run']} mutants, {record['stopped']}, "
          f"{len(pending(manifest))} left", flush=True)
    return 0


def cmd_queue(args) -> int:
    """Submits one queue job per batch. Waiting in the queue costs no CPU; each batch is bounded by its timeout."""
    while True:
        before = len(pending(load(args.campaign)))
        if before == 0:
            break
        command = f'python -I -u "{os.path.abspath(__file__)}" batch --campaign {args.campaign} --max-seconds {args.batch_seconds}'
        subprocess.run([sys.executable, "-I", "-u", QUEUE, "run", "--project", "P03",
                        "--label", f"P03 mutation {args.campaign} ({before} mutants left)",
                        "--timeout", str(args.batch_seconds + 1200), "--idle", "900",
                        "--watch", log_dir(args.campaign), "--", command])
        after = len(pending(load(args.campaign)))
        if after >= before:
            print("[mutate] a batch made no progress; stopping (read its log)", flush=True)
            return 1
    return cmd_report(args)


# -------------------------------------------------------------------------------------------------------------- report

def scores(mutants: list[dict], review: dict) -> dict:
    """M1 (02 section 4.1) and the naive variant that counts compile failures as kills (Mutate++'s rule)."""
    def count(fates, exclude_equivalent):
        return sum(1 for m in mutants if m["fate"] in fates and not (exclude_equivalent and
                   review.get(m["id"], {}).get("verdict") == "equivalent"))
    killed = count(KILLED_LIKE, True)
    survived = count(("survived",), True)
    stillborn = count(("stillborn",), False)
    raw_survived = count(("survived",), False)
    return {
        "killed": killed, "survived": survived, "stillborn": stillborn,
        "equivalent": sum(1 for m in mutants if review.get(m["id"], {}).get("verdict") == "equivalent"),
        "M1": round(100.0 * killed / (killed + survived), 1) if killed + survived else None,
        "M1_unreviewed": round(100.0 * killed / (killed + raw_survived), 1) if killed + raw_survived else None,
        "M1_naive": round(100.0 * (killed + stillborn) / (killed + stillborn + raw_survived), 1)
        if killed + stillborn + raw_survived else None,
    }


def cmd_report(args) -> int:
    manifest = load(args.campaign)
    review_path = os.path.join(TOOLS_DIR, "mutation", manifest["config"]["name"] + "_review.json")
    review = {}
    if os.path.exists(review_path):
        with open(review_path, encoding="utf-8") as handle:
            review = json.load(handle)
    mutants = manifest["mutants"]
    overall = scores(mutants, review)
    lines = [f"# Mutation campaign `{manifest['campaign']}`", "",
             f"Target: {manifest['target']['repo']} at `{manifest['target']['commit'][:12]}`, "
             f"`{manifest['config']['project_subdir']}`; tests `{manifest['config']['test_filter']}`. "
             f"Raw data: `Benchmarks/Raw/{manifest['campaign']}_manifest.json`.", "",
             "| Fate | Count |", "|---|---|"]
    for fate in ("killed", "timeout", "crash", "survived", "stillborn", "error", None):
        lines.append(f"| {fate or 'not run'} | {sum(1 for m in mutants if m['fate'] == fate)} |")
    lines += ["", f"- **M1 mutation score** (stillborn and reviewed-equivalent excluded): **{overall['M1']}%** "
              f"({overall['killed']} killed of {overall['killed'] + overall['survived']})",
              f"- M1 before the equivalence review: {overall['M1_unreviewed']}%",
              f"- M1-naive (compile failures counted as kills): {overall['M1_naive']}%",
              f"- Reviewed equivalent: {overall['equivalent']}", ""]
    lines += ["| Operator | Killed | Survived | Stillborn |", "|---|---|---|---|"]
    for op in tt_mutants.ALL_OPERATORS:
        group = [m for m in mutants if m["operator"] == op]
        if group:
            s = scores(group, review)
            lines.append(f"| {op} | {s['killed']} | {s['survived']} | {s['stillborn']} |")
    costs = [m["build_s"] + m["test_s"] for m in mutants if m.get("build_s") is not None and m["fate"] != "error"]
    if costs:
        lines += ["", f"Cost per mutant (build + test): median {statistics.median(costs):.1f} s, "
                  f"max {max(costs):.1f} s, over {len(costs)} mutants. Batches: "
                  + ", ".join(f"{b['batch']}: {b.get('mutants_run', 0)} mutants in {b.get('seconds', '?')} s"
                              for b in manifest["batches"]) + "."]
    lines += ["", "## Survivors", "", "| Id | Where | Operator | Change | Review |", "|---|---|---|---|---|"]
    for m in mutants:
        if m["fate"] == "survived":
            verdict = review.get(m["id"], {})
            lines.append(f"| `{m['id']}` | `{m['file']}:{m['line']}` | {m['operator']} | "
                         f"`{m['original']}` → `{m['replacement']}` | "
                         f"{verdict.get('verdict', 'not reviewed')}{': ' + verdict['reason'] if 'reason' in verdict else ''} |")
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    out = os.path.join(SUMMARY_DIR, manifest["campaign"] + "_summary.md")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


# ------------------------------------------------------------------------------------------------------------ selftest

def cmd_selftest(_args) -> int:
    ok = True
    good_build = {"exit_code": 0, "compile_error": False}
    passing = {"exit_code": 0, "report": {"succeeded": 6, "succeededWithWarnings": 0, "failed": 0, "notRun": 0}}
    cases = [
        (good_build, passing, "survived"),
        (good_build, {"exit_code": 4294967295, "report": {"succeeded": 5, "succeededWithWarnings": 0, "failed": 1, "notRun": 0}}, "killed"),
        (good_build, {"exit_code": 0, "report": {"succeeded": 4, "succeededWithWarnings": 0, "failed": 0, "notRun": 0}}, "killed"),
        (good_build, {"exit_code": None, "report": None}, "timeout"),
        (good_build, {"exit_code": 3, "report": None}, "crash"),
        ({"exit_code": 6, "compile_error": True}, None, "stillborn"),
        ({"exit_code": 6, "compile_error": False}, None, "error"),
        ({"exit_code": None, "compile_error": False}, None, "error"),
    ]
    for build_result, test_result, expected in cases:
        got = classify(build_result, test_result, 6)
        if got != expected:
            ok = False
            print(f"classify: expected {expected}, got {got}")
    mutants = [{"id": "a", "fate": "killed"}, {"id": "b", "fate": "survived"}, {"id": "c", "fate": "survived"},
               {"id": "d", "fate": "stillborn"}, {"id": "e", "fate": "timeout"}]
    s = scores(mutants, {"c": {"verdict": "equivalent"}})
    if (s["M1"], s["M1_unreviewed"], s["M1_naive"]) != (66.7, 50.0, 60.0):
        ok = False
        print("scores:", s)
    ok = safety_selftest() and ok
    ok = patch_selftest() and ok
    print("selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def safety_selftest() -> bool:
    """SC2: a snapshot leaves the target repository exactly as it was (tree, status and file times).

    A throwaway repository is created in the system temp folder, with an uncommitted edit in its working tree that
    must NOT appear in the snapshot (the snapshot comes from the commit, never the working tree).
    """
    import tempfile
    root = tempfile.mkdtemp(prefix="tt_selftest_")
    repo, destination = os.path.join(root, "repo"), os.path.join(root, "snapshot")
    source = os.path.join(repo, "Proj", "Source", "M", "Private", "A.cpp")
    os.makedirs(os.path.dirname(source))
    with open(source, "w", encoding="utf-8") as handle:
        handle.write("int F(int A) { return A + 1; }\n")
    quiet = {"capture_output": True, "check": True}
    subprocess.run(["git", "-C", repo, "init", "-q"], **quiet)
    subprocess.run(["git", "-C", repo, "add", "-A"], **quiet)
    subprocess.run(["git", "-C", repo, "-c", "user.name=selftest", "-c", "user.email=selftest", "commit", "-q", "-m", "x"], **quiet)
    with open(source, "a", encoding="utf-8") as handle:
        handle.write("// uncommitted work in progress\n")
    before = (git(repo, "rev-parse", "HEAD^{tree}"), git(repo, "status", "--porcelain"), os.path.getmtime(source))
    snapshot({"repo": repo, "commit": "HEAD", "project_subdir": "Proj"}, destination)
    after = (git(repo, "rev-parse", "HEAD^{tree}"), git(repo, "status", "--porcelain"), os.path.getmtime(source))
    copied = read_text(os.path.join(destination, "Proj", "Source", "M", "Private", "A.cpp"))
    ok = before == after and "uncommitted" not in copied and "return A + 1" in copied
    shutil.rmtree(root, ignore_errors=True)
    if not ok:
        print("safety: the snapshot changed the target or took its working tree", before, after)
    return ok


def patch_selftest() -> bool:
    """apply_patch inside this repository's ignored tree, as in a real campaign: an LF patch with a space in its path
    changes the CRLF snapshot file, this repository's status is unchanged, and a patch that doesn't apply raises."""
    root = os.path.join(WORK_DIR, "_selftest_patch")
    shutil.rmtree(root, ignore_errors=True)
    target = os.path.join(root, "My Proj", "A.cpp")
    os.makedirs(os.path.dirname(target))
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write("int F()\r\n{\r\n\treturn 1;\r\n}\r\n")
    patch = root + ".patch"   # Tools/_work/ is ignored, so the status check below still holds
    with open(patch, "w", encoding="utf-8", newline="") as handle:
        handle.write('--- "a/My Proj/A.cpp"\n+++ "b/My Proj/A.cpp"\n@@ -1,4 +1,4 @@\n int F()\n {\n-\treturn 1;\n'
                     '+\treturn 2;\n }\n')
    status_before = git(PROJECT_DIR, "status", "--porcelain")
    try:
        ok = apply_patch(patch, root) == ["My Proj/A.cpp"] and "return 2;" in read_text(target)
        try:
            apply_patch(patch, root)   # already applied: the context no longer matches
            ok = False
        except RuntimeError as error:
            ok = ok and "patch failed" in str(error)
    except RuntimeError as error:
        print("patch selftest:", error)
        ok = False
    ok = ok and git(PROJECT_DIR, "status", "--porcelain") == status_before
    shutil.rmtree(root, ignore_errors=True)
    os.remove(patch)
    if not ok:
        print("patch selftest: apply_patch did not patch only the snapshot")
    return ok


def main(argv: list[str]) -> int:
    # The Windows console defaults to cp1252, which can't print the report's arrows; never let printing fail a run.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # An inherited GIT_DIR or GIT_WORK_TREE (a git hook, a wrapper) would point every git call at that repository
    # instead of the target or the snapshot (code review and altitude review, S7).
    for name in ("GIT_DIR", "GIT_WORK_TREE"):
        os.environ.pop(name, None)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--config", required=True)
    plan.add_argument("--campaign", help="re-plan this existing campaign id (only while it has no results)")
    batch = sub.add_parser("batch")
    batch.add_argument("--campaign", required=True)
    batch.add_argument("--max-seconds", type=float, default=1800)
    queue = sub.add_parser("queue")
    queue.add_argument("--campaign", required=True)
    queue.add_argument("--batch-seconds", type=float, default=1800)
    sub.add_parser("report").add_argument("--campaign", required=True)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    return {"plan": cmd_plan, "batch": cmd_batch, "queue": cmd_queue, "report": cmd_report,
            "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
