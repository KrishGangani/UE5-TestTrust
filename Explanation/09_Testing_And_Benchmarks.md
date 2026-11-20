# 09 · Testing And Benchmarks: TestTrust

**Rule:** every check is recorded with its date, its exact command and its result, **including failures**. The functional and benchmark sections of Phases 7–8 are filled in then; results from earlier phases are recorded as they happen.

---

## Phase 2 · P2: what one mutant costs (build-cost probe, 2026-11-21)

**Command** (one queue job): `python -I -u Tools\probe_build_cost.py` through `tools\ue_queue.py run --project P03 --timeout 3600 --idle 900`.
**Target:** a snapshot of UE5-UpdateBudget at commit `c25a996` (its `UpdateBudget\` folder, extracted with `git archive` into `Tools\_work\`), editor target `UpdateBudgetEditor`, Development.
**Not pinned:** the probe ran before the P-core rule; builds are never pinned, and its three test launches measure cost, not performance.
**Raw data:** `Benchmarks/Raw/2026-11-21_013437_buildcost_manifest.json`, plus one console log and one UBT debug log (`-Log=`) per step. Queue job `20261121_011236_300d64`: **ok, exit 0, 152.2 s** wall time for the whole probe.

**Submission note:** the first submission (job `20261121_010324_42bb9f`) failed in 0.1 s: the queue joins its arguments with spaces, so the unquoted script path `D:/UNREAL PORTFOLIO/...` became two arguments. Re-submitted with the command as one pre-quoted string; `tt_mutate.py queue` does the same.

**Builds** (editor target `UpdateBudgetEditor`, Development, MSVC 14.44.35229):

| Step | What changed | UBT total | Compile actions | UHT | Notes |
|---|---|---|---|---|---|
| b0 cold | nothing built yet | **70.2 s** | 14 (19 actions) | ran | Once per campaign; later batches reuse the snapshot's `Intermediate\` |
| b1 no-op | nothing | **1.3 s** | 0 | up to date | UBT's fixed overhead per build |
| b2 game `.cpp` | `UBDemoBrainComponent.cpp`: `<` → `<=` | **7.6 s** | 1 | up to date | `Compile UBDemoBrainComponent.cpp`, `Link UnrealEditor-UpdateBudget.lib/.dll` |
| b3 restore | the same file back | **3.6 s** | 1 | up to date | Recompiled because its timestamp is new (`01b #1`) |
| b4 plugin `.cpp` | `UpdateBudgetSubsystem.cpp`: `!=` → `==` | **4.2 s** | 1 | up to date | Only this file: the plugin's files were out of its unity blob |
| b5 restore | | **4.2 s** | 1 | up to date | |
| b6 UObject header | `UBDemoBrainComponent.h`: default `300.f` → `301.f` | **6.7 s** | **4** | **ran** | Every includer recompiled (`UBDemoBrainComponent`, `UBDemoAgent`, `UBBenchmarkSubsystem`, `UBBaselineDriverSubsystem`) |
| b7 restore | | **6.5 s** | 4 | ran | |

Every build: exit 0. Every build log contains `[Adaptive Build] Excluded from UpdateBudgetCore unity file: BudgetedUpdateComponent.cpp, UpdateBudgetCoreModule.cpp, UpdateBudgetSubsystem.cpp`, and no `git status` line: on the launcher engine, the snapshot (no `.git`) puts every writable file in the working set, as read in `SourceFileWorkingSet.cs:405–411` (`01b #3`). The user-level `BuildConfiguration.xml` is empty, so these are engine defaults.

**Test launches** (`UnrealEditor-Cmd <uproject> -nullrhi -nosound -unattended -nosplash -nopause -traceautostart=0 -ExecCmds="Automation RunTests StartsWith:System.Core.HAL.FileManager;Quit" -ReportExportPath=...`):

| Step | Mode | Wall time | Exit | Report | "Ready to start automation" → "Found 1 automation tests" |
|---|---|---|---|---|---|
| t1 | editor, first launch of the snapshot | **17.3 s** | 0 | 1 succeeded, 0 failed | 5.1 s |
| t2 | editor, warm | **14.8 s** | 0 | 1 succeeded, 0 failed | 5.1 s |
| t3 | `-game` | **13.4 s** | 0 | 1 succeeded, 0 failed | 5.0 s |

**What the numbers say:**
1. **The test launch, not the build, is the main cost** of a `.cpp` mutant on a fast suite: ≈ 4–8 s build + ≈ 15 s launch.
2. **5 s of every launch is a fixed wait** in the automation controller (`DefaultDelayTimer = 5.0f`, `AutomationCommandline.cpp:871`), skipped by `Automation Now` (`:606–609`). The runner uses it (`01b #9`); the saving is measured in P4-R.
3. **`-game` is 1.4 s faster** than the warm editor, but it silently drops `EditorContext`-only tests (`01b #7`), so the runner stays in editor mode.
4. **A header mutant here cost 6.7 s, not minutes,** because this module has four includers. The `.cpp`-only rule stands for scaling and for the inline/template code headers contain (`01b #2`), not because one header mutant is slow in a small module.

**After the run:** the three automation report folders (each with an engine-generated `index.html` whose asset links are absolute) were moved from `Benchmarks\Raw\` into the snapshot's `Saved\ProbeReports\`, because the portfolio link checker walks `Benchmarks\`. The probe and the runner now write reports there directly. The numbers are in the manifest.

## Phase 4 · Foundation checks (2026-11-21)

All seven checks ran as **one queue job**, `Tools\phase4_checks.bat`: job `20261121_011632_7422f2`, **ok, exit 0, 220.1 s**. Before it ran, `Config\DefaultInput.ini` was added and `-ExitAfterSeconds=0` was dropped from `smoke_game.bat` (both learned from a sibling project's log and checked in the 5.8.4 source, `05` A7 and Part C).

| # | Check | Command (from `P03_TestTrust\`) | Result |
|---|---|---|---|
| F-1 | Editor target builds | `Tools\build.bat TestTrustEditor Development` | ✅ Succeeded, UBT total 38.3 s, 20 actions, **0 errors, 0 warnings**. MSVC 14.44.35229, Windows SDK 10.0.22621.0. The sample module compiles against the small `SharedPCH.Core` (it depends on Core only) |
| F-2 | Game target builds | `Tools\build.bat TestTrust Development` | ✅ Succeeded, UBT total 39.9 s, 28 actions, `Link TestTrust.exe` (monolithic), **0 errors, 0 warnings** |
| F-3 | Uncooked game loads the map, all modules present, quits | `Tools\smoke_game.bat` | ✅ Exit 0. `Mounting Project plugin TestTrustProbe`; `TestTrustSample` and `TestTrustProbe` DLLs loaded; `Template_Default` loaded in 0.063 s. **0 errors.** 21 warnings, all `LogEditorDataStorageUI` ("Unable to register widget factory"): engine-side, from running the editor binary in `-game` (UE5-UpdateBudget saw the same). **No `LogEnhancedInput` warning**: `DefaultInput.ini` works |
| F-4 | The sample suite passes in the editor | `Tools\run_tests.bat StartsWith:TestTrust` | ✅ Exit 0. "Found 6 automation tests"; all six `Result={Success}`; `TEST COMPLETE. EXIT CODE: 0`; `index.json`: 6 succeeded, 0 failed, total test duration 0.099 s |
| F-5 | Package a **Development** build | `Tools\package.bat` | ✅ BUILD SUCCESSFUL; BuildCookRun 67.4 s; 526 packages cooked; cook "Success - 0 error(s), 0 warning(s)"; **0 errors, 0 warnings**. Output `Build\Windows\TestTrust.exe` (983 MB staged, git-ignored) |
| F-6 | Packaged build runs without a GPU | `Tools\smoke_packaged.bat nullrhi` | ✅ Exit 0; map loaded in 0.031 s; **0 errors, 0 warnings** |
| F-7 | Packaged build runs on the GPU | `Tools\smoke_packaged.bat gpu` | ✅ Exit 0; D3D12, SM6; **chosen adapter 0 = NVIDIA GeForce RTX 5070 Laptop GPU** (driver 610.47), not the Intel UHD (adapter 1); map loaded in 0.133 s; **0 errors, 0 warnings**. Observation: 32 s passed between the map load and "Preparing to exit" on this first GPU run of a fresh build (a sibling project saw 35 s); not a failure, re-checked in Phase 5 when the workload exists |

**Side effect, then fixed:** the first uncooked run (F-3) made the engine append an `AndroidFileServerEditor` block with a random `SecurityToken` to `Config\DefaultEngine.ini`. Per the portfolio rule of 2026-11-21 the block was deleted and the `AndroidFileServer` plugin disabled in `TestTrust.uproject` (`05` A1, A7). The seven checks were re-run on that configuration: see **Phase 4 · Re-run** below.

## Phase 4 · Re-run after disabling AndroidFileServer

The same seven checks (`Tools\phase4_checks.bat`, one queue job) on the committed configuration: `AndroidFileServer` disabled in the `.uproject`, its generated block removed from `DefaultEngine.ini`, no `-ExitAfterSeconds`. Job `20261121_015125_fbc4d1`: **ok, exit 0, 120.4 s**.

| # | Result |
|---|---|
| F-1 editor build | ✅ Succeeded, UBT total 11.1 s; only `Module.TestTrustProbe.cpp` recompiled and relinked (the plugin list in the `.uproject` changed); **0 errors, 0 warnings** |
| F-2 game build | ✅ Succeeded, 18.6 s; the same file plus `Link TestTrust.exe`; **0 errors, 0 warnings** |
| F-3 uncooked smoke | ✅ Exit 0; **0 errors**; the same 21 engine-side `LogEditorDataStorageUI` warnings and nothing else; no Android File Server line in the log; **`DefaultEngine.ini` was not rewritten** (`git status` clean) |
| F-4 sample tests | ✅ 6 found, `TEST COMPLETE. EXIT CODE: 0` |
| F-5 package | ✅ BUILD SUCCESSFUL, BuildCookRun 59.6 s, cook "Success - 0 error(s), 0 warning(s)" |
| F-6 packaged, no GPU | ✅ Exit 0; map loaded in 0.021 s; **0 errors, 0 warnings** |
| F-7 packaged, GPU | ✅ Exit 0; **chosen adapter 0 = RTX 5070 Laptop GPU**; map loaded in 0.058 s; **0 errors, 0 warnings**; "Preparing to exit" 0.8 s after the map load, so the 32 s of the first GPU run was a first-run cost, not a property of the build |

## Phase 4 · P4-R: runner smoke test on the sample module (M-S)

**Predicted before the run** (from reading the code and the tests, `05` B2–B3):

| Mutant (line in `TTSampleRules.cpp`) | Predicted fate | Why |
|---|---|---|
| 7 AOR `-` → `+` | killed | ArmorSubtracts: 13 ≠ 7 |
| 8 COND `!(Damage < MinDamage)` | killed | ArmorSubtracts: 1 ≠ 7 |
| 8 ROR `<` → `<=` | **survived, equivalent** | Differs only when `Damage == MinDamage`, and then both set it to `MinDamage` |
| 8 ROR `<` → `>=` | killed | ArmorSubtracts: 1 ≠ 7 |
| 10 SDL `Damage = MinDamage;` | killed | NeverBelowMinimum: −3 ≠ 1 |
| 12 COND `!(bCritical)` | killed | ArmorSubtracts: 14 ≠ 7 |
| 14 SDL `Damage *= 2;` | killed | CriticalDoubles: 7 ≠ 14 |
| 14 AOR `*=` → `/=` | killed | CriticalDoubles: 3 ≠ 14 |
| 22 ROR `<=` → `<` | **survived (the deliberate gap)** | No test puts a target exactly at the range |
| 22 ROR `<=` → `>` | killed | InsideAndOutside: both checks flip |
| 22 AOR `*` → `/` | killed | InsideAndOutside: 25 ≤ 1 is false |
| 27 AOR `-` → `+` | killed | CountsDown: 1.25 ≠ 0.75 |
| 28 ROR `>` → `>=` | **survived, equivalent** | Differs only when `Next == 0`, and then both return zero |
| 28 ROR `>` → `<=` | killed | CountsDown: 0 ≠ 0.75 |

**Predicted:** 14 mutants, 11 killed, 3 survived (1 real gap, 2 equivalent), 0 stillborn, 0 error. M1 before review = 11/14 = 78.6%; after the equivalence review = 11/12 = 91.7%.

The prediction was committed (`c18936d`) before the run.

**The run.** Campaign `2026-11-21_014645_mut-sample`: target UE5-TestTrust at `03771bf` (the Phase 4 commit), `TestTrust\`, filter `StartsWith:TestTrust.Sample`. Planned with `tt_mutate.py plan --config Tools\mutation\sample.json`; run with `tt_mutate.py queue --campaign … --batch-seconds 1800`: **one queue job**, `20261121_014653_c65626`, **ok, exit 0, 278.0 s** for the baseline plus all 14 mutants. Test launches pinned to the P-cores (`0xFFFF`); builds unpinned.

*Re-plan before the run:* the campaign was first planned on commit `4decfae`. Before its batch started, that local commit was rewritten as `03771bf` to keep a generated `SecurityToken` out of the repository's history (`05` A1, A7), and the campaign was re-planned in place with `plan --campaign <id>`, which is refused once any result exists. The mutated file and the tests are byte-identical in both commits; the 14 mutants and their ids didn't change.

| Mutant | Line | Change | Predicted | **Result** | Killed by |
|---|---|---|---|---|---|
| `26b8b01f6c` | 7 | AOR `-` → `+` | killed | ✅ **killed** | Damage.ArmorSubtracts, CriticalDoubles, NeverBelowMinimum |
| `ece7912d6a` | 8 | COND `!(Damage < MinDamage)` | killed | ✅ **killed** | the three Damage tests |
| `8125da701a` | 8 | ROR `<` → `<=` | survived, equivalent | ✅ **survived** | — (reviewed: equivalent) |
| `d8920aa447` | 8 | ROR `<` → `>=` | killed | ✅ **killed** | the three Damage tests |
| `c82e2cf751` | 10 | SDL `Damage = MinDamage;` | killed | ✅ **killed** | Damage.NeverBelowMinimum |
| `72300ed28a` | 12 | COND `!(bCritical)` | killed | ✅ **killed** | the three Damage tests |
| `f5019b4aac` | 14 | SDL `Damage *= 2;` | killed | ✅ **killed** | Damage.CriticalDoubles |
| `3b42b988c0` | 14 | AOR `*=` → `/=` | killed | ✅ **killed** | Damage.CriticalDoubles |
| `62c038c366` | 22 | ROR `<=` → `<` | survived (the gap) | ✅ **survived** | — (reviewed: real gap) |
| `249f330409` | 22 | ROR `<=` → `>` | killed | ✅ **killed** | Range.InsideAndOutside |
| `f08f35021c` | 22 | AOR `*` → `/` | killed | ✅ **killed** | Range.InsideAndOutside |
| `6dff9dc6e9` | 27 | AOR `-` → `+` | killed | ✅ **killed** | Cooldown.CountsDown, StopsAtZero |
| `1c78e5d36c` | 28 | ROR `>` → `>=` | survived, equivalent | ✅ **survived** | — (reviewed: equivalent) |
| `1cc079ff12` | 28 | ROR `>` → `<=` | killed | ✅ **killed** | Cooldown.CountsDown, StopsAtZero |

**Outcome: 14 of 14 fates as predicted.** 11 killed, 3 survived, 0 stillborn, 0 timeout, 0 crash, **0 error**. **M1 = 91.7%** (11 of 12) after the review in `Tools\mutation\sample_review.json`; 78.6% before it; M1-naive 78.6% (no stillborn mutants here, so the naive rule changes nothing on this sample). Per operator: ROR 3 killed / 3 survived (all three survivors are relational boundaries, consistent with H2 on a sample built to show it, not evidence for it), AOR 4/0, COND 2/0, SDL 2/0. Report: `Benchmarks\Summaries\2026-11-21_014645_mut-sample_summary.md`.

**Cost:**

| | Median | [min–max] | Notes |
|---|---|---|---|
| Baseline build (cold snapshot) | 49.9 s | — | Once per campaign |
| Baseline test launch | 34.0 s | — | First launch of a fresh snapshot |
| Mutant build | **2.11 s** | [1.95–2.61] | Exactly **1 compile action** per mutant, every time: the snapshot's working-set rule held (`01b #3`). The sample module compiles against the small `SharedPCH.Core` |
| Mutant test launch | **9.95 s** | [9.49–30.55] | The 30.55 s is the first mutant only: "AssetRegistryGather time 24.58 s … NumUncachedFiles 8896", a one-time scan of the fresh snapshot. The other 13: 9.88 s [9.49–11.42] |
| **Mutant total (build + test)** | **12.07 s** | [11.44–33.16] | |
| Batch | 277.9 s | | Baseline + 14 mutants |

**`Automation Now` confirmed:** "Ready to start automation" → "Found N automation tests" took **0.12–0.19 s** in all 15 launches, against **5.0–5.1 s** in the probe without it (`01b #9`).

**Against the targets** (judged in full in S8, across campaigns): SC1 so far: every mutant has a defined fate and 0 errors; the repeat-run half of SC1 is S8. SC3 so far: a 12.1 s median on M-S, within the 60 s target, on a suite of microsecond tests; M-P1 will show the cost on a real suite.

**Found by this run and fixed:**
1. The batch succeeded, but the queue driver then crashed while **printing** the report: the Windows console's cp1252 can't encode `→`. The summary file had been written (UTF-8). Fixed: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` in `main()`; the report was regenerated without UE.
2. While the batch ran, its manifest already said `stopped: all mutants have a fate`, because the reason was set before the loop. Fixed: the reason is `None` while running and set when the loop ends.
3. Expected but now measured: the first launch on a fresh snapshot pays a one-time asset-registry scan (≈ 25 s here).

## Phase 5 · S1: the probe plugin (2026-11-21)

**First check.** Batch `2026-11-21_032032_s1check` (`Tools\run_checks.py s1`), queue job `20261121_030407_979279`: **ok, exit 0, 120.2 s**.
- Builds: editor target 12.8 s, game target 17.5 s, **0 warnings, 0 errors**.
- Automation tests `StartsWith:TestTrust`: **13 of 13 pass** (the 7 new `TestTrust.Probe.*` tests and the 6 sample tests).
- Packaged Development build: ok.
- Two packaged runs, pinned to `0xFFFF`, 3 s warm-up and 10 s capture: `X10` (1.0 ms injected per frame) and `X0`.

| Check | Expected | `X10` | `X0` |
|---|---|---|---|
| Captured frames, capture finalised | 600, yes | 600, yes | 600, yes |
| `BenchStart` | frame 180 (3 s × 60) | frame 180 | frame 180 |
| `BenchEnd` | after 600 captured frames | after 600 | after 600 |
| `TestTrustProbe/GameThread/Injected` | 1.0 ms per frame in `X10` only | median 1.0003 [1.000–1.94], p95 1.002 | absent |
| `GameThreadTime` median / mean | about +1.0 ms in `X10` | 2.255 / 2.435 ms | 1.325 / 1.418 ms (+0.93 / +1.02) |
| Log errors and warnings | 0 | 0 | 0 |

**Found in this check:** the timing column is `TestTrustProbe/GameThread/Injected` (the thread name is a middle segment), and `BenchStart` is not in the capture it starts (it sits on the frame before the first row); the scripts expected otherwise and were corrected before any gate data (`07`, probe section). Each capture also contains 2 `PSO` events (pipeline-state compilation); they are part of every run alike.

**Audit (after the check).** Code review (medium): PIE support plus `-TTExit` would quit the editor (now Game worlds only); `nan`/`inf` options passed the clamp (now `ClampFinite`); the injection kept spinning after the window; a map change would open a second window; the run tag stopped at a comma. Simplify: no subsystem without `-TTProbe`; `CSV_EVENT_NOLOG` on the last captured frame; one shared test frame loop; the options hold the injection schedule directly. Every fix is listed where it lives in `05` Part E. S2's altitude review later moved the probe's "frames since the end" onto `GFrameCounter` (`05` E2, `06` §16).

**Re-check of the reviewed code.** The fixes were built and run again inside S2's check job (batch `2026-11-21_040556_s2check`, queue job `20261121_034607_ca7fdd`, **ok, exit 0, 179.8 s**; the plugin doesn't depend on the game module, so the combined build checks it as it is committed here): both builds **0 warnings**, **13 of 13 tests pass**, and the same two runs again give 600 frames, `BenchStart` on frame 180, `BenchEnd` on frame 780 after 600 captured frames, 0 log errors or warnings, `Injected` median 1.000 ms [1.000–1.348], and `GameThreadTime` median 2.363 vs 1.306 ms (+1.06), mean 2.483 vs 1.406 ms (+1.08).

## Phase 5 · S2: the workload, determinism and calibration (2026-11-21)

**The check.** Batch `2026-11-21_040556_s2check` (`Tools\run_checks.py s2`), queue job `20261121_034607_ca7fdd`: **ok, exit 0, 179.8 s**. Both builds **0 warnings, 0 errors**; **13 of 13** tests pass; packaged build ok; the two S1 runs again (S1 above); then five packaged runs with N = 1,000 agents, seed 1, 3 s warm-up and 10 s capture, pinned to `0xFFFF`. Every run: 600 frames, finalised, `BenchEnd` present, 0 log errors or warnings.

**Calibration** (`02` §7 fixed W = 128 iterations from UE5-UpdateBudget; S2 checks it on this workload before any gate data):

| Run | `-TTWork` | `GameThreadTime` median [p95] | `FrameTime` median | `RenderThreadTime` median | `GPUTime` median |
|---|---|---|---|---|---|
| `W128_r0_prime` (first run after packaging) | 128 | 5.306 [7.006] ms | 5.303 ms | 3.101 ms | 3.036 ms |
| `W64` | 64 | 4.361 [5.367] ms | 4.399 ms | 3.546 ms | 3.144 ms |
| `W128` | 128 | 5.776 [7.359] ms | 5.795 ms | 3.438 ms | 3.055 ms |
| `W256` | 256 | 8.006 [8.801] ms | 8.008 ms | 2.996 ms | 2.886 ms |
| `W128_repeat` (no `-TTWork`: the class default) | 128 | 5.917 [7.123] ms | 5.940 ms | 3.515 ms | 2.947 ms |

- **Chosen: W = 128, unchanged.** The frame is game-thread bound (`FrameTime` within 0.03 ms of `GameThreadTime`), with about 2.3 ms between the game thread and the render thread, so an injected game-thread cost lands one for one in the frame. W = 64 is also game-thread bound, but only about 0.8 ms above the render thread. At 5.8 ms the injected sizes are 4.3%, 8.6% and 17% of the game thread.
- **The compute step scales as expected:** +64 iterations cost about 1.4 ms; +128 cost about 2.2 ms.
- `W128_repeat` left out `-TTWork`; its metadata says `ttwork 128`, so the class-default path works.
- **A first look at run-to-run noise** (three runs, so only a hint): the W = 128 medians were 5.306, 5.776 and 5.917 ms. The first run after packaging was about 0.5 ms faster than the next two, which were 0.14 ms apart. Its cause is not known yet **[unverified]**. S4's stored baseline and interleaved batches measure the spread properly, and every batch starts with a discarded priming run.
- Each run took 6–10 s of wall time for 13 s of world time: the fixed step runs faster than real time when a frame takes less than 16.7 ms.

**Determinism** (packaged build, five runs, three different compute sizes):
- **Start-position hash `0x7F189215` in all five runs.** Spawning 1,000 agents took 36.7–47.2 ms, during the warm-up.
- **End-state hash `0x5CA911B4`, with 329 state changes, in all five runs.** The hash covers location, rotation and state changes, not the compute step's result, so W = 64, 128 and 256 agree too: the compute step changes the cost, not the behaviour.
- Every end-state line was logged at world time 13.016667 s, which is frame 781, the first frame after `BenchEnd` on frame 780. So the report is outside the capture. In this build the workload ticked before the probe in that frame (its line comes before the probe's `BenchEnd on frame 780` line); `GFrameCounter` makes the frame the same in either order (`05` F3).
- **In the editor:** batch `2026-11-21_041111_s2editorcheck` (`run_checks.py s2editor`), queue job `20261121_035052_81920c`: **ok, exit 0, 99.4 s** (no-op builds, 13 of 13 tests, package, then two uncooked runs in the editor's `-game -nullrhi` mode, same seed). Start-position hash `0x7F189215`, the same as packaged, and end-state hash `0xA11AE791` with 329 state changes in **both** runs.
- **Deterministic within each build, not bit-identical across builds.** The editor's end state differs from the packaged build's `0x5CA911B4`, although the start positions and the 329 state changes agree. The editor runs modular DLLs, built differently from the monolithic packaged game, and the per-frame trigonometry and transform maths can round differently in the last bits between such builds **[inferred; which component differs was not isolated]**. The gate only ever compares packaged runs with packaged runs, so this doesn't affect it; it is a limit of the determinism claim.

**Audit (before the commit).** Code review (medium): no subsystem without `-TTAgents` (`ShouldCreateSubsystem`); the compute-step value in the metadata is the one actually used, also from the class default; the hash covers rotation and state changes, not only positions; the end-of-run report stays out of the capture. Simplify (4 reviewers): one options struct with the resolved compute value instead of a sentinel plus a second member; one `bEndReported` flag; the camera radius computed once; an unused getter removed. Altitude: `IsCaptureDone()` moved onto `GFrameCounter` in the probe, instead of a three-state counter in the workload (`05` E2, F3). Skipped: caching the probe subsystem and the player controller (tens of nanoseconds per frame); spawning at the start position directly (warm-up only); `bAutoManageActiveCameraTarget` instead of re-applying the view target (a behaviour change with no measured benefit). Reuse: nothing to change.

## Phase 5 · S6: UE5-UpdateBudget "before" (M-P1, 2026-11-21)

**Order note:** S6–S8 need only the runner, so they were queued at the start of Phase 5, while S1 was being written, to use the machine's queue time; their order relative to S1–S5 doesn't affect any result. S6 was captured **before** any new test existed (`03` rule: baselines before the new thing).

**The run.** Campaign `2026-11-21_025734_mut-updatebudget`: UE5-UpdateBudget at **`b890bc6`** (its step S4: `FUpdateBudgetScheduler` and 8 automation tests), `UpdateBudget\`, mutating only `Plugins/UpdateBudgetCore/Source/UpdateBudgetCore/Private/UpdateBudgetScheduler.cpp`, filter `StartsWith:UpdateBudget.Scheduler`. Config `Tools\mutation\updatebudget.json`. **One queue job**, `20261121_025744_764736`: **ok, exit 0, 687.9 s** for the baseline and 39 mutants. UE5-UpdateBudget's repository was only read (`git rev-parse`, `git archive` on the commit).

**Baseline:** cold build 36.7 s; 8 tests, 0 failed, test launch 17.1 s.

**Fates:** 24 killed, **11 crash**, 4 survived, 0 stillborn, 0 timeout, **0 error**.
- **Every crash is a genuine detection, not infrastructure:** 9 engine-log `Assertion failed: (Index >= 0) & (Index < ArrayNum)` (`Core/Public/Containers/Array.h:1339`) and 2 `EXCEPTION_ACCESS_VIOLATION`, all from off-by-one loop bounds (`<` → `<=` on lines 31, 47, 52), a deleted initialisation (lines 17, 30, 33) or an inverted loop condition. A test run that crashes has failed, so crashes count as killed (`02` §9).

**Survivors and review** (`Tools\mutation\updatebudget_review.json`):

| Id | Line | Change | Verdict |
|---|---|---|---|
| `fbd237213c` | 42 | tie-break `A < B` → `A <= B` | **equivalent**: indices are unique, so the two differ only when the sort compares an element with itself, which `Algo::IntroSort` never does (selection sort compares distinct positions, `Core/Public/Algo/IntroSort.h:70`; the partition loops exclude the pivot, `:98–99`; heap sort compares distinct nodes **[inferred]**) |
| `0072839e65` | 47 | `Deadline < NextFrameTime` → `<=` | **real gap**: no test has a deadline exactly at the next frame time |
| `84989a4f35` | 56 | `SpentMs + Predicted > BudgetMs` → `>=` | **real gap**: no update ever exactly fills the remaining budget |
| `60ff682b30` | 70 | `bOverBudget = SpentMs > BudgetMs` → `>=` | **real gap**: no frame spends exactly the budget |

**Score:** **M1 = 92.1%** (35 of 38) after the review; 89.7% (35 of 39) before it; M1-naive 89.7% (no stillborn mutants).

**What it says about the hypotheses** (one suite, so evidence, not proof):
- **H2 (boundaries are under-tested): supported.** All 4 survivors are relational-operator boundary shifts: 4 of 19 ROR mutants survived, against 0 of 20 others (AOR 3/3, LCR 4/4, COND 2/2, SDL 11/11 killed).
- **H1 (weak oracles): supported in its boundary form.** Every survivor sits on a line that every test executes; the suite runs the code but never checks the exact boundary.
- **H6 (cost): rejected for this suite.** Median 14.1 s per mutant [13.2–60.8]: build 4.1 s [3.8–7.5] with exactly **1 compile action** every time (the plugin's file came out of its unity blob, `01b #3`), test launch 9.9 s [9.4–56.7].

**The 56.7 s outlier** (mutant `3569416fdb`, killed) was infrastructure, not the mutant: that editor launch had to start the shared Zen storage server ("Launching executable … zenserver", then about 31 s of "Waiting for ZenServer to be ready", and 10 s of shader-type setup), because no Zen server was running at that moment. Its tests themselves took 0.8 s. The cost is reported as measured.

**Report:** `Benchmarks\Summaries\2026-11-21_025734_mut-updatebudget_summary.md`.


## Phase 5 · S7: UE5-UpdateBudget "after" (M-P1 + survivor tests, 2026-11-21)

**What changed:** only the tests. `Tools\mutation\patches\updatebudget_boundary_tests.patch` adds three automation tests to UE5-UpdateBudget's `UpdateBudgetSchedulerTests.cpp` at `b890bc6`, one per real gap that S6 found (`05` H1). The patch is applied to this project's snapshot only (`tt_mutate.py apply_patches`, `05` H2); UE5-UpdateBudget's repository was only read. Config `Tools\mutation\updatebudget_after.json` = the S6 config plus `"patches"`, so the 39 mutants and their ids are identical and the S6 review applies unchanged.

**The run.** Campaign `2026-11-21_031329_mut-updatebudget`, queue job `20261121_031339_a69cc4`: **ok, exit 0, 657.1 s**. The manifest records the patch's SHA-256 (`38b3f333…`) and its target file.

**Baseline:** cold build 51.3 s; **11 tests** (8 + 3), 0 failed, test launch 16.5 s. The three new tests pass on the unmutated scheduler, so they encode its current behaviour, not a change to it.

**Fates:** 27 killed, 11 crash, **1 survived**, 0 stillborn, 0 timeout, 0 error. Compared mutant by mutant with S6, exactly three fates changed, all **survived → killed**, each by the test written for it:

| Id | Line | Change | Killed by |
|---|---|---|---|
| `0072839e65` | 47 | `Deadline < NextFrameTime` → `<=` | `DeadlineAtNextFrameIsOptional` |
| `84989a4f35` | 56 | `SpentMs + Predicted > BudgetMs` → `>=` | `ExactFitStillRuns` and `ExactlyOnBudgetIsNotOverBudget` |
| `60ff682b30` | 70 | `bOverBudget = SpentMs > BudgetMs` → `>=` | `ExactlyOnBudgetIsNotOverBudget` |

The remaining survivor is `fbd237213c`, the tie-break already reviewed as **equivalent** in S6.

**Score:** **M1 = 100.0%** (38 of 38) after the review; 97.4% (38 of 39) before it; M1-naive 97.4%. **SC4 met:** M1-after ≥ 90%, and the one remaining survivor is classified (equivalent, with its reason). Before → after: **92.1% → 100.0%**.

**Cost:** median 14.0 s per mutant [13.5–20.0]: build 4.0 s [3.8–7.8], 1 compile action every time; test launch 10.0 s [9.6–12.1]. Three more tests added no measurable time: the launch, not the tests, dominates (`01b #8`).

**What it says:** the survivor list was directly actionable. Each real gap needed one short test with exact binary-fraction inputs (0.25 ms, 0.5 ms) so the boundary is hit without rounding, and each test killed its mutant. This is one suite, so it is an example, not a general claim.

**The patch is offered to UE5-UpdateBudget's owner** as `Tools\mutation\patches\updatebudget_boundary_tests.patch` (apply with `git apply --ignore-whitespace` in that repository); it is not committed there by this project.

**Audit (after the run, before the commit).** The reviews changed only how the runner applies a patch, not the patch or the campaign:
- **Code review (medium):** 7 findings. Fixed: git's own error text is kept when a patch fails; an inherited `GIT_DIR`/`GIT_WORK_TREE` is cleared; targets come from `git apply --numstat -z` (the regex cut paths at spaces and missed deletions); a self-test for the patch path; the `.gitattributes` comment, which wrongly called the patch CRLF. Documented: `--ignore-whitespace` stays, because the patch is LF and the snapshot CRLF (`05` H1). Skipped: asserting the run order in `ExactFitStillRuns` would change the measured patch; the order is covered by `DeadlineOrder` and `BudgetCutOff`.
- **Simplify (4 reviewers):** one `content()` helper instead of a repeated expression, each `numstat` record split once, a dead assignment removed, the self-test's patch file next to its folder (no temp folder), `GIT_DIR` cleared once in `main()` (altitude: it affects every git call, not only the patch). Reuse and efficiency: nothing to change.
- **Re-verified with the final code:** `tt_mutate.py selftest` ok (also with `GIT_DIR` set to this repository); the patch re-applied to a copy of the S6 snapshot's test file gives the same SHA-256, the same target, and a byte-identical file to the one the campaign measured.

**Report:** `Benchmarks\Summaries\2026-11-21_031329_mut-updatebudget_summary.md`.


## Phase 5 · S8: repeatability (SC1) and cost (SC3), 2026-11-21

**The repeat.** Campaign `2026-11-21_031347_mut-sample`, queue job `20261121_031356_4cd6c6`: **ok, exit 0, 239.0 s**. Config `Tools\mutation\sample_repeat.json`: the Phase 4 smoke test's `sample.json` with its commit pinned to `03771bf` (`sample.json` says `HEAD`, which has moved on), so the same 14 mutants and ids; a new campaign folder from a fresh snapshot. Baseline: 6 tests, 0 failed.

**SC1 (the runner is trustworthy): met.**
- **Same fate for 14 of 14 mutants (100%)** as `2026-11-21_014645_mut-sample`: 11 killed, 3 survived in both, and every killed mutant was killed by the same failing tests.
- **0 error** in both campaigns (and in S6 and S7).
- The unmutated snapshot built and passed before every batch of all four campaigns (the runner refuses to start a batch otherwise).

**SC3 (cost per mutant): met.**

| Campaign | Mutants | Median build + test | Range | Median build | Compile actions |
|---|---|---|---|---|---|
| `014645_mut-sample` (P4-R) | 14 | 12.1 s | 11.4–33.2 | 2.1 s | 1 each |
| `031347_mut-sample` (S8) | 14 | 11.8 s | 11.5–12.2 | 2.0 s | 1 each |
| `025734_mut-updatebudget` (S6) | 39 | 14.1 s | 13.1–60.8 | 4.1 s | 1 each |
| `031329_mut-updatebudget` (S7) | 39 | 14.0 s | 13.5–20.0 | 4.0 s | 1 each |
| **All** | **106** | **13.9 s** | 11.4–60.8 | | |

- Median **13.9 s** per `.cpp` mutant, against the 60 s target. Both long outliers are test launches, not builds: 60.8 s in S6 was an editor launch that had to start the shared Zen storage server (S6 above); 33.2 s in P4-R was the first mutant of that batch (launch 30.6 s, build 2.6 s), whose cause wasn't recorded, because the runner keeps each mutant's test report but not its editor log **[unverified cause]**.
- **4 of 4 batches (100%)** finished inside their queue timeout, every one with "all mutants have a fate".

**H6 (each mutant costs a full C++ rebuild and an editor start): the rebuild half is rejected, the editor-start half holds.** For `.cpp` mutants in a game module (M-S) and a plugin module (M-P1), every mutant compiled exactly one file (2–4 s); the editor launch (about 10 s) is real and sets the floor. Across 106 mutants that is about 14 s each, practical for suites of this size.
