# P03 · Benchmarks

Every number in this project's write-up must trace back to a file in this folder. The method is in [../Explanation/01_Problem_Analysis.md §7](../Explanation/01_Problem_Analysis.md); results batch by batch are in [../Explanation/09_Testing_And_Benchmarks.md](../Explanation/09_Testing_And_Benchmarks.md).

Two kinds of batch live here: **mutation campaigns** (how many injected faults a suite catches, and what each mutant cost) and **perf-gate batches** (packaged runs of the deterministic workload, Phase 5 onwards).

## Measurement rules

**Mutation campaigns**
1. **The target is never touched.** It is snapshotted from a pinned commit with `git archive` into `Tools/_work/` (git-ignored); the manifest records the repository name and the full commit hash.
2. **The suite must be green first.** Every batch builds and tests the unmutated snapshot and refuses to run mutants otherwise.
3. **One mutant per build, one fresh `UnrealEditor-Cmd -nullrhi` per test run**, pinned to the performance cores, with timeouts. Fates: killed, survived, stillborn, timeout, crash, error (`02` §9).
4. **One queue job per batch**, with a time budget (default 30 min) and a queue timeout. Batches resume where the previous one stopped.

**Perf-gate batches** (the portfolio protocol)
1. **Packaged Development build only** (never PIE). The launcher engine can't build Test.
2. **Fixed step** (`-deterministic -FPS=60`), real GPU, 1280×720 windowed, `-novsync`, `-nosound`, `-traceautostart=0`. The capture window is opened and closed by the game (`BenchStart` / `BenchEnd` CSV events from the `TestTrustProbe` plugin), never by a timer.
3. **Pinned to the performance cores** (mask `0xFFFF` on this i7-14650HX; logical CPUs 0–15) and recorded in every environment record.
4. **One discarded priming run per batch**, then interleaved runs with the configuration order rotated every round, so every configuration sits in every position equally often.
5. **Statistics:** median, p95 and p99 per run (linear-interpolation percentiles), then the median across runs with [min–max]. The run is the sampling unit.
6. **The environment is recorded with every batch** (below), automatically.

## Folders

| Folder | What goes in it | Rule |
|---|---|---|
| `Raw\` | One `<batch>_manifest.json` per batch or campaign (committed); CSV captures, logs, UBT logs, (git-ignored; per-campaign logs in `Raw\<campaign>\`) | **Never edited.** Anything re-processed goes to `Summaries\`. Cited raw batches are attached as `<batch>_raw.zip` to this repository's Releases page |
| `Summaries\` | Mutation reports (`<campaign>_summary.md`), gate tables and charts | Each summary names the batch it was computed from |

## File naming

- **Batch id:** `YYYY-MM-DD_HHMMSS_<label>`, time-stamped so two batches never collide.
- **Mutation campaign:** `<date>_<time>_mut-<config name>` → `Raw\<campaign>_manifest.json`, `Raw\<campaign>\<mutant id>_a<attempt>_{build.log, ubt.txt, test.log, engine.log}` (the automation report itself stays in the snapshot's `Saved\` folder; its numbers are in the manifest), `Summaries\<campaign>_summary.md`.
- **Build-cost probe:** `<date>_<time>_buildcost` → `Raw\<batch>_manifest.json` and `Raw\<batch>_<step>.log`.
- **Perf-gate runs (Phase 5):** `<batch>_<Config>_r<run>.csv` (+ `.log`), with `<Config>` = `X0`, `X025`, `X05`, `X10` (injected ms); `_r0_prime` is the discarded priming run.

## Environment record (written into every manifest)

```text
Engine:            UE 5.8.4 (CL 58902052), launcher build
Build:             mutation: Development editor target, tests in UnrealEditor-Cmd -nullrhi
                   gate:     Development, standalone packaged (never PIE)
Compiler:          MSVC 14.44.35229 (VS 2022 17.14), Windows SDK 10.0.22621.0
CPU / GPU / RAM:   i7-14650HX (8P + 8E) / RTX 5070 Laptop / 32 GB
CPU affinity:      0xFFFF (performance cores only) for every timed process; builds unpinned
Storage:           project on D: (Kingston NVMe), engine on C: (WD NVMe)
OS:                Windows 11 build 26200
Power:             AC, recorded power plan
Resolution (gate): 1280x720 windowed, default scalability, no VSync, no sound
```

## Run log

| Batch | Kind | Purpose | Result |
|---|---|---|---|
| `2026-11-21_013437_buildcost` | probe | Phase 2: build and test cost per mutant on a snapshot of UE5-UpdateBudget at `c25a996` (`09` P2) | `.cpp` mutant 3.6–7.6 s build; test launch 13.4–17.3 s, 5 s of it a fixed controller wait |
| `2026-11-21_014645_mut-sample` | mutation | Phase 4 runner smoke test on the sample module M-S at `03771bf` (`09` P4-R) | 14 of 14 fates as predicted; M1 91.7% after review; 12.1 s median per mutant; [summary](Summaries/2026-11-21_014645_mut-sample_summary.md) |
