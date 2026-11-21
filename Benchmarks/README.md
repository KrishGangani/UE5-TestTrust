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
| `2026-11-21_025734_mut-updatebudget` | mutation | S6: UE5-UpdateBudget scheduler at `b890bc6`, before any new test (`09` S6) | 39 mutants; M1 92.1% after review (89.7% before); 3 real boundary gaps, 1 equivalent; 14.1 s median per mutant; [summary](Summaries/2026-11-21_025734_mut-updatebudget_summary.md) |
| `2026-11-21_031329_mut-updatebudget` | mutation | S7: the S6 campaign plus 3 survivor tests, applied as a patch to the snapshot only (`09` S7) | 39 mutants; M1 **100.0%** after review (97.4% before); the 3 real gaps killed, 1 equivalent left; 14.0 s median per mutant; [summary](Summaries/2026-11-21_031329_mut-updatebudget_summary.md) |
| `2026-11-21_031347_mut-sample` | mutation | S8: the P4-R campaign on M-S repeated from a fresh snapshot (`09` S8) | **14 of 14** fates identical to `2026-11-21_014645_mut-sample` (SC1); 11.8 s median per mutant; all campaigns: 13.9 s median over 106 mutants (SC3); [summary](Summaries/2026-11-21_031347_mut-sample_summary.md) |
| `2026-11-21_032032_s1check` | step check | S1: builds, tests, package, two packaged probe runs (`09` S1) | 0 warnings; 13 of 13 tests; 600 frames, `BenchStart` on frame 180; 1.0 ms injected = +0.93 ms median `GameThreadTime` |
| `2026-11-21_040556_s2check` | step check | S1 re-check of the reviewed probe, then S2: calibration W = 64/128/256 and determinism at N = 1,000 (`09` S1, S2) | 0 warnings; 13 of 13 tests; W = 128 → 5.8 ms `GameThreadTime`, game-thread bound; start and end-state hashes equal in all 5 packaged runs |
| `2026-11-21_041111_s2editorcheck` | step check | S2: determinism in the editor's `-game` mode (`09` S2) | Hashes equal in both editor runs; the editor's end state differs from the packaged build's (cross-build, not run-to-run) |
| `2026-11-21_045922_s3smoke-stored` | gate (smoke) | S3: pipeline test, priming + 3 × `X0`, short runs (`09` S3) | 4 of 4 valid; [summary](Summaries/2026-11-21_045922_s3smoke-stored_summary.md) |
| `2026-11-21_052824_s3smoke-eval` | gate (smoke) | S3: pipeline test, priming + 4 rounds × 4 configs, short runs, then `tt_gate.py evaluate` (`09` S3) | 17 of 17 valid; injected 0.250 / 0.500 / 1.000 ms exactly; not a gate result (4 unchanged runs); [summary](Summaries/2026-11-21_052824_s3smoke-eval_summary.md), [evaluation](Summaries/2026-11-21_052824_s3smoke_gate_evaluation.md) |
| `2026-11-21_050350_gate-stored` | gate | S4: the stored baseline, priming + 10 × `X0`, 5 s + 20 s runs (`09` S4) | 11 of 11 valid; `GameThreadTime` median 5.236 ms [4.853–5.480]; [summary](Summaries/2026-11-21_050350_gate-stored_summary.md) |
| `2026-11-21_053701_gate-eval1` | gate | S4: evaluation batch 1 of 4, priming + 8 rounds × `X0`/`X025`/`X05`/`X10` (`09` S4) | 33 of 33 valid; [summary](Summaries/2026-11-21_053701_gate-eval1_summary.md) |
| `2026-11-21_054518_gate-eval2` | gate | S4: evaluation batch 2 of 4, priming + 8 rounds × `X0`/`X025`/`X05`/`X10` (`09` S4) | 33 of 33 valid; [summary](Summaries/2026-11-21_054518_gate-eval2_summary.md) |
| `2026-11-21_055612_gate-eval3` | gate | S4: evaluation batch 3 of 4, priming + 8 rounds × `X0`/`X025`/`X05`/`X10` (`09` S4) | 33 of 33 valid; [summary](Summaries/2026-11-21_055612_gate-eval3_summary.md) |
| `2026-11-21_060429_gate-eval4` | gate | S4: evaluation batch 4 of 4, priming + 8 rounds × `X0`/`X025`/`X05`/`X10` (`09` S4) | 33 of 33 valid; [summary](Summaries/2026-11-21_060429_gate-eval4_summary.md) |
| `2026-11-21_s5` | gate evaluation | S5: `tt_gate.py evaluate`, stored baseline + the 4 evaluation batches (`09` S5) | TT false positives 15.6% (interleaved) / 3.1% (stored); detection 100% at 1.0 ms, 94% / 88% at 0.5 ms, 56% / 41% at 0.25 ms; SC5a, SC6 at 0.5 and 0.25 ms, and SC7 not met; [evaluation](Summaries/2026-11-21_s5_gate_evaluation.md) |
