# 08 · Debugging And Profiling: TestTrust

**Rule:** how to see each part working and how to find out why it didn't, with the exact commands for UE 5.8.4 on this machine. Every command that starts Unreal (a build, the editor, the game) goes **through the machine queue** (`tools\ue_queue.py run --project P03 …`); a direct start would disturb other projects' benchmarks. Engine references are relative to `Engine/Source/`.

---

## 1. Where everything is written

| What | Where | Committed? |
|---|---|---|
| A queue job's console output and exit status | `D:\UNREAL PORTFOLIO\tools\ue_queue\jobs\<job id>.log`, and one line per job in `tools\ue_queue\history.jsonl` | no (outside the project) |
| A mutation campaign's manifest (config, environment, every mutant's fate, cost, failed tests; every batch's baseline and stop reason) | `Benchmarks\Raw\<campaign>_manifest.json` | **yes** |
| One mutant's logs | `Benchmarks\Raw\<campaign>\<id>_a<attempt>_build.log` (console), `_ubt.txt` / `_ubt.json` (UBT's own logs), `_test.log` (the pinned launcher), `_engine.log` (the editor's full log) | no (ignored: they contain local paths) |
| One mutant's test report | `Tools\_work\<campaign>\<project>\Saved\TestTrustReports\<id>_a<attempt>\index.json` | no (inside the snapshot) |
| The campaign report | `Benchmarks\Summaries\<campaign>_summary.md` (`tt_mutate.py report`) | **yes** |
| A gate run's capture and log | `Benchmarks\Raw\<batch>_<Config>_r<round>.csv` and `.log` | no |
| A gate batch's manifest and summary | `Benchmarks\Raw\<batch>_manifest.json`, `Benchmarks\Summaries\<batch>_summary.md` | **yes** |
| A gate evaluation | `Benchmarks\Summaries\<label>_gate_evaluation.md` (`tt_gate.py evaluate`) | **yes** |
| A step check (`run_checks.py`) | `Benchmarks\Raw\<batch>_<step>check_manifest.json` plus one log per step and the packaged runs' CSVs and game logs | the manifest |

Every log the tools write starts with the exact command line as its first line (`# …`), so any step can be repeated as it ran.

## 2. A mutant: why did it get this fate?

Read the fate in the manifest (`mutants[].fate`, `detail`, `failed_tests`, `build_s`, `test_s`, `compile_actions`), then the logs in this order:

| Fate | Where the evidence is | What it looks like |
|---|---|---|
| **stillborn** | `_build.log` | `error C2678`-style lines (`COMPILE_ERROR` in `tt_mutate.py`); the build exited non-zero |
| **error** | `_build.log` without a compile error, or `detail` | A hung build (killed at 1,200 s), a locked file, or a mutant that couldn't be applied (`detail` holds Python's message). Retried once |
| **timeout** | `_test.log` and `_engine.log` | The engine log stops in the middle of a test: an endless loop. The runner killed the tree after max(120 s, 3 × the baseline's test time) |
| **crash** | `_engine.log` | No `TEST COMPLETE` line, no `index.json`; usually `Assertion failed: (Index >= 0) & (Index < ArrayNum)` (`Runtime/Core/Public/Containers/Array.h:1339`, 9 of S6's 11 crashes) or `EXCEPTION_ACCESS_VIOLATION` with a call stack into the mutated function |
| **killed** | `index.json` and `_engine.log` | `failed > 0` and the names in `failed_tests`; the engine log has `TEST COMPLETE. EXIT CODE: -1` and the failing assertion (`Expected 'X' to be Y, but it was Z`) |
| **survived** | `_engine.log` | `TEST COMPLETE. EXIT CODE: 0`, every test `Result={Success}`. Read the mutated line next to the tests: which input would tell the two versions apart? That input is the missing test (S6 → S7) |

**How many files did a mutant recompile?** `compile_actions` in the manifest, or `[n/m] Compile …` lines in `_build.log`. It should be exactly 1 for a `.cpp` mutant; more means the file was in a unity blob or a header changed (`01b #2–3`).

**Where a mutant's seconds go** (S6–S8 medians, `09`): build about 4 s, of which about 1.3 s is UBT's fixed overhead (no-op build, `09` P2) and the rest one compile and one DLL link; test launch about 10 s, almost all of it editor start-up (the tests themselves take under 1 s). The rare 30–60 s launch is the editor starting the shared Zen storage server (`Launching executable … zenserver` and `Waiting for ZenServer to be ready` in `_engine.log`).

## 3. Reproducing one mutant by hand

The runner never needs this. It is for checking a surprising fate.

1. Find the mutant in the manifest: `file`, `start`, `end`, `original`, `replacement`.
2. List the snapshot's mutants with the same ids: `cd Tools\_work\<campaign>\<project>` then `python -I ..\..\..\tt_mutants.py <file>` (the relative path as in the manifest; `05` D3 explains why ids match only on the snapshot's bytes).
3. Apply it to the snapshot file, from Python: `tt_mutants.Mutant(file, op, start, end, original, replacement, line, col).apply(text)` on the text of `_pristine\<file>`, written back with `newline=""`.
4. Build and test **through the queue** with the two command lines at the top of `<id>_a1_build.log` and `<id>_a1_test.log`.
5. Restore: copy `Tools\_work\<campaign>\_pristine\<file>` back, or simply start the next `tt_mutate.py batch`, which restores every target file first.

## 4. The test suite on its own

| Want | Command (through the queue) |
|---|---|
| Run the project's tests | `Tools\run_tests.bat` (filter `StartsWith:TestTrust`); report in `TestTrust\Saved\Automation\Reports\index.json`, log in `TestTrust\Saved\Logs\Tests.log` |
| One suite | `Tools\run_tests.bat StartsWith:TestTrust.Probe` |
| See which tests exist, without running them | `UnrealEditor-Cmd.exe <uproject> -ExecCmds="Automation List;Quit" -unattended -nullrhi -log` (`Automation List` is handled at `Developer/AutomationController/Private/AutomationCommandline.cpp:602`) |
| Why is the suite empty? | The module isn't in the `.uproject` or isn't loaded in that context, or the test lacks `EditorContext` and the run is in the editor (`06` §3) |

A plain filter is a **substring** match; `StartsWith:` selects one suite (`01b #5`).

## 5. A gate run: is it valid, and what did it measure?

`run_bench.py` records every reason a run can't be judged in `runs[].problems`; an invalid run is kept and never judged.

| Problem | Meaning | Look at |
|---|---|---|
| `exit code N` / `timed out` | The game crashed, or never quit (it quits 3 frames after `BenchEnd` only with `-TTExit`) | the run's `.log`: the last lines; `BenchEnd on frame` present? |
| `capture unreadable` / `no capture` | No CSV, or a stub of one row | Was `-csvStartOnEvent=BenchStart` reached? The log must show `BenchStart on frame 300` (5 s × 60) |
| `capture not finalised` | The CSV lacks its trailing header and metadata rows: the profiler didn't finish its file | the exit came too early |
| `N frames instead of 1200` | The window opened or closed on the wrong frame | `BenchStart on frame …` and `BenchEnd on frame … after … captured frames` in the log |
| `BenchEnd missing from the capture` | The stop event wasn't recorded inside the capture | `EVENTS` column of the last row |
| `N log errors` | An `Error:` line, for example a failed agent spawn | `grep "Error:" <run>.log` |

**What a valid capture contains:** 1,200 rows; the columns `FrameTime`, `GameThreadTime`, `RenderThreadTime`, `GPUTime` and `TestTrustProbe/GameThread/Injected` (only on frames that injected); the events `TestTrustProbe/BenchEnd` on the last row and usually two `PSO/…` events; the metadata keys `ttruntag`, `ttwarmup`, `ttcapture`, `ttinjectms`, `ttinjectevery`, `ttagents`, `ttseed`, `ttwork` (lower-cased by the file). `BenchStart` is never in the capture it starts (`09` S1).

**Analyse one capture by hand:** `python -I Tools\csv_stats.py <run>.csv` (all default columns), `--columns GameThreadTime`, `--skip 60` (drop the first second), `--split-event BenchEnd` (statistics before, on and after an event's frame), `--json out.json`.

**Is the workload the same in two runs?** Compare the two hash lines in each run's log: `Spawned 1000 agents (seed 1, work 128) in … ms; start-position hash 0x7F189215` and `End-state hash 0x… (N state changes) at world time … s`. Equal hashes mean the same frames were simulated; a different end-state hash with an equal start hash means the simulation diverged during the run (`09` S2).

**Why was a run flagged?** `python -I Tools\tt_gate.py decide --baseline <stored manifest> --candidate <batch manifest> --run <run name>` prints the run's median and p95 `GameThreadTime` against the two limits; exit 3 means "regression".

## 6. Profiling the workload

These are for looking, not measuring: the gate's numbers come only from pinned `run_bench.py` batches.

| Want | How (packaged build, through the queue) |
|---|---|
| Live frame, game, render and GPU times on screen | Add `-ExecCmds="stat unit"` to a windowed run (`stat unit` is the engine's `Unit` stat, `Runtime/Engine/Private/UnrealEngine.cpp:19705`) |
| A timeline of every frame | Add `-trace=default -tracefile=D:\…\run.utrace` (`Runtime/Core/Private/ProfilingDebugging/TraceAuxiliary.cpp:1952, 1987`); open the file with `Engine\Binaries\Win64\UnrealInsights.exe`. The gate's own runs pass `-traceautostart=0` (`:2378`), so they never trace |
| Where the game thread's 5–6 ms go | In Insights' Timing view: the agents' `TickComponent` under `TG_PrePhysics`, then the probe's `Tick` under the tickables after `TG_PostPhysics`; with an injection, the `TestTrustProbe/Injected` scope inside the probe's tick |
| Is the frame game-thread bound? | `FrameTime` ≈ `GameThreadTime` in the capture (S2: within 0.03 ms) while `RenderThreadTime` (about 3.4 ms) and `GPUTime` (about 3 ms) stay lower |

## 7. The probe's own lines (what a healthy run prints)

```text
LogTTProbe: Display: Probe active: warm-up 5.000 s, capture 20.000 s, inject 0.250 ms every 1 frame(s), tag '<run>'
LogTTWorkload: Display: Spawned 1000 agents (seed 1, work 128) in 36.1 ms; start-position hash 0x7F189215
LogTTProbe: Display: BenchStart on frame 300 (world time 5.000 s)
LogTTWorkload: Display: End-state hash 0x2C812651 (612 state changes) at world time 25.016668 s
LogTTProbe: Display: BenchEnd on frame 1500 after 1200 captured frames
```

The end-state line and the `BenchEnd` line come from the first frame after the capture (frame 1,501); their order depends on which subsystem ticked first, and doesn't matter (`05` E2). A second world in the same process prints `Probe already ran its window …` and does nothing.

## 8. The runner itself

| Symptom | Likely cause | Check |
|---|---|---|
| `batch` exits 3 before any mutant | The unmutated snapshot doesn't build, or its suite isn't green (the runner refuses on purpose) | the batch's `b<NN>_baseline_build.log` / `_engine.log` |
| A queue job "ok" but nothing happened | The command never reached the script (an unquoted path with a space) | the second line of the job log |
| Every mutant survives | Test exit codes lost, or the wrong filter | `tt_mutate.py selftest`; the filter in the config (`StartsWith:`) |
| An "after" campaign scores the same as "before" | The patch didn't apply | `target.patches` in the manifest must list the patch's SHA-256 and its target files; `tt_mutate.py selftest` checks the patch path |
| The batch stops early | The time budget: `batches[].stopped` says why | `estimate_seconds()` stops before the budget would be exceeded |
| A file still mutated after a killed batch | Expected: the next `batch` restores every target file from `_pristine\` first | compare the file with `_pristine\` |

Self-tests that need no Unreal: `python -I Tools\tt_mutants.py --selftest`, `python -I Tools\tt_mutate.py selftest`, `python -I Tools\csv_stats.py --selftest`, `python -I Tools\tt_gate.py selftest`.
