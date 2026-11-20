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

*(results below)*
