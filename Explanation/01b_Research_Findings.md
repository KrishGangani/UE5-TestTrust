# 01b · Research Findings (Phase 2): TestTrust

**Phase:** 2 (Research), completed 2026-11-21 · **Engine:** UE 5.8.4 (CL 58902052), read from `C:\Program Files\Epic Games\UE_5.8\Engine`

**Method:**
- Four investigations: the test frameworks and their command-line contract (notes A), the build pipeline that decides what a mutant costs (notes B), perf measurement and the existing perf tooling (notes C), and existing work outside the engine (notes D).
- One **measurement**: a build-cost probe through the machine queue, on a snapshot of UE5-UpdateBudget (`09` P2). Research is not only reading: the cost of a mutant decides the whole design, so it was measured before the design was fixed.
- Every engine claim cites a path relative to `Engine/Source/` (or `Engine/`) and a line in 5.8.4. Claims that drive design decisions were re-opened by hand and are marked ✔. Conclusions from code flow rather than one explicit line are **[inferred]**; things not checked are **[unverified]**.

**Why this phase matters.** Phase 1 assumed "every mutant costs a slow C++ rebuild and an editor start". Phase 2 measured it: a `.cpp` mutant rebuilds in about 4–8 s and its test launch costs about 13–17 s, of which 5 s is a fixed wait that one word removes. It also found that the brief's pinned-launch command hides exit codes, which would have made every mutant "survive".

---

## 1. What Phase 2 changed

| # | Finding | Consequence for TestTrust |
|---|---|---|
| 1 | **UBT decides out-of-date actions by timestamps** ("any prerequisite item has a newer timestamp than the last execution time", `Programs/UnrealBuildTool/Actions/ActionGraph.cs:752–773`) ✔ | Restoring a file after a mutant recompiles it once more. Faking the old timestamp would link the mutant's object into a "restored" build, so the runner never touches timestamps |
| 2 | **UHT re-runs only when a reflected header (or the module's `.Build.cs`, or UHT itself) changed** (`System/UHTExecution.cs:961–1030`) ✔. **Measured:** a `.cpp` mutant: UHT "Generated code is up to date", 1 compile; a UObject-header default change: UHT ran, **4 compiles** (every includer) | Mutants are `.cpp`-only in v1. In this small module a header mutant cost 6.7 s vs 4.2 s for a plugin `.cpp`; the cost grows with the number of includers, and headers also hold inline and template code the text-level mutator handles worst |
| 3 | **Unity and the adaptive-unity working set.** Game modules under `<Project>/Source` with < 32 files are never unity-built (`Configuration/UEBuildModuleCPP.cs:944–953`; `Rules/TargetRules.cs:1930–1936`) ✔; plugin modules are **[inferred]**. Adaptive unity takes "working set" files out of unity blobs (`System/Unity.cs:366, 413`) ✔. The working set is `git status` if `.git` is in the project folder or its parent, otherwise, **on an installed engine, every writable file** (`System/SourceFileWorkingSet.cs:378–411, 69–85`) ✔. **Measured:** in the snapshot (no `.git`), the plugin's three `.cpp` files were "Excluded from UpdateBudgetCore unity file" and each mutant compiled exactly one file | The snapshot is deliberately **not** a git checkout: every file compiles on its own from the first build, and the working set never changes between mutants, so no unity blob is ever rebuilt (a git checkout would rebuild a blob on the first change of each file and again on restore) |
| 4 | **`Automation RunTests <filter>;Quit` exits with −1 if any test failed, else 0**, after logging `TEST COMPLETE. EXIT CODE` (`Developer/AutomationController/Private/AutomationCommandline.cpp:494–504`) ✔. **Measured:** exit 0 and the line in all three probe launches | The exit code is one of the runner's two signals |
| 5 | **Filters and the report.** A plain filter is a substring match; `StartsWith:X` matches from the start (`AutomationCommandline.cpp:134–160`) ✔. `-ReportExportPath=` writes `index.json` with `succeeded`, `failed`, `tests[]` (`AutomationControllerManager.cpp:233, 746`; `AutomationControllerManager.h:134–153`) ✔. **Measured:** `index.json` parsed in all three launches (1 succeeded, 0 failed) | The runner always uses `StartsWith:` and compares the completed-test count with the baseline's: a mutant that makes a test stop early is *killed*, not *survived* |
| 6 | **Every framework is an `FAutomationTestBase`:** simple/complex tests (`Runtime/Core/Public/Misc/AutomationTest.h:4297–4303`), Spec (`:2899–2900`), CQTest (`Developer/CQTest/Public/CQTest.h:147`), functional tests (registered as `Project.Functional Tests.…`, `Developer/FunctionalTesting/Private/FunctionalTest.cpp:733`) ✔ | One runner serves all of them; it needs only a filter |
| 7 | **Where tests exist and run.** Dev tests are compiled for every configuration except Test and Shipping (`Programs/UnrealBuildTool/Configuration/UEBuildTarget.cs:6315–6331`) ✔. Contexts follow the application: editor → `EditorContext`, `-game` → `ClientContext` (`Runtime/Core/Private/Misc/AutomationTest.cpp:805–830`) ✔; `-nullrhi` drops `NonNullRHI` tests (`:841–844`) | Mutants are built in Development. The sample's tests use `EditorContext | ClientContext`, like UE5-UpdateBudget's suite, so either mode works |
| 8 | **What a mutant costs (measured, `09` P2).** Editor target, snapshot of UE5-UpdateBudget (UBT's own totals): cold build **70.2 s** (14 compiles, once per campaign); no-op **1.3 s**; `.cpp` mutant **3.6–7.6 s** (1 compile + 1 DLL link); header mutant **6.5–6.7 s** (4 compiles). Test launch with one trivial test: editor **17.3 s** cold, **14.8 s** warm; `-game` **13.4 s** | **The test launch, not the build, dominates.** The editor target (modular) was chosen; a monolithic game target would relink the whole executable. Editor mode is kept over `-game` (1.4 s faster) because `-game` silently drops `EditorContext`-only tests (#7). Per-mutant cost is about **15–25 s** for a fast suite; SC3's target was set at **60 s** to leave room for real suites |
| 9 | **A fixed 5 s wait before every run:** the command-line controller waits `DefaultDelayTimer = 5.0f` before requesting workers (`AutomationCommandline.cpp:243–254, 871`) ✔; `Automation Now` sets it to 0 (`:606–609`) ✔. **Measured:** 5.1 s between "Ready to start automation" and "Found 1 automation tests" in every launch | The runner sends `Automation Now;RunTests <filter>;Quit`: about a third of each test launch saved. If this ever broke test discovery, the green-baseline check (0 tests → refuse) would catch it. **Confirmed in P4-R** (`09`): 0.12–0.19 s instead of 5.0–5.1 s in all 15 launches, with the same 6 tests found |
| 10 | **APT captures and reports; it doesn't decide.** Its C++ has no baseline/threshold/regression logic (grep); its UAT script ships only as a DLL; its BuildGraph template includes `Build/Inc/*.xml` files that are **not in the launcher install** (`Engine/Plugins/Performance/AutomatedPerfTesting/Resources/TemplatesForHookup/AutoPerfTests.xml:25, 30`) ✔ | The gate is built locally in Python. The perf-gating gap is stated as **medium**: the statistics are standard; the value is a measured, local, gameplay gate |
| 11 | **No coverage with MSVC:** UBT's `-CodeCoverage` (`Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:2351–2356`) adds flags only if the compiler is Clang (`Platform/Windows/VCToolChain.cs:885–893`) ✔ | Mutation score is the suite-effectiveness measure. VS 2022's clang-cl 19.1.5 with `llvm-cov` is on this machine; using it with launcher-engine binaries is **[unverified]**, a growth path only |
| 12 | **`UTickableWorldSubsystem` ticks on the game thread after `TG_PostPhysics`, inside the frame** (`Runtime/Engine/Private/LevelTick.cpp:1750, 1778, 1821, 1877`; `Runtime/Engine/Public/Subsystems/WorldSubsystem.h:80`) ✔ | The probe's injector spins inside its subsystem's `Tick`, so the injected time lands in `GameThreadTime` **[inferred; checked in S1]**. No custom tick function is needed |
| 13 | **Deterministic MSVC output is Shipping-only by default and needs a unique build environment** (`Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:2155–2167`) ✔ | Trivial compiler equivalence (identical objects ⇒ equivalent mutant) can't be used with the launcher editor target **[inferred]**; equivalent mutants are reviewed by hand |
| 14 | **`cmd /c start "" /wait /affinity <MASK> prog` always returns 0** (tested on this machine 2026-11-21: programs exiting 3 and −1 both gave 0). `cmd /v:on /s /c "start "" /wait /affinity <MASK> prog & exit !errorlevel!"` returns the real code (3 → 3, −1 → 4294967295) | `tt_common.pinned()` uses the working form. Reported to the portfolio coordinator; the brief now recommends pinning the process directly and lists this form as the fallback |

**Benchmark-plan changes:**

| # | Finding | Consequence |
|---|---|---|
| B-1 | The fixed-step and CSV-event facts from UE5-UpdateBudget hold on 5.8.4 (`Runtime/Launch/Private/LaunchEngineLoop.cpp:2455–2462`; `Runtime/Engine/Private/UnrealEngine.cpp:3004–3023`; `Runtime/Core/Private/ProfilingDebugging/CsvProfiler.cpp:5078–5090, 4309–4312`) ✔ | Gate runs use `-deterministic -FPS=60`, `-csvStartOnEvent=BenchStart -csvStopOnEvent=BenchEnd`, and the probe plugin fires the events |
| B-2 | Unpinned runs on this hybrid CPU can land on an E-core and run ~1.6× slower (UE5-UpdateBudget's baseline batch) | Every timed process is pinned to the P-cores (`0xFFFF`), including mutant test launches; the mask is in every environment record |
| B-3 | A plain substring test filter can select more than one suite (#5) | The baseline test count is recorded per batch and mutants are compared against it |
| B-4 | The UBT user configuration on this machine is empty (`%APPDATA%\Unreal Engine\UnrealBuildTool\BuildConfiguration.xml`) | All build behaviour above is the engine default; nothing machine-specific to document |

---

## 2. The test frameworks (evidence, notes A)

| Fact | Evidence (5.8.4) |
|---|---|
| `WITH_AUTOMATION_TESTS = WITH_DEV_AUTOMATION_TESTS \|\| WITH_PERF_AUTOMATION_TESTS` | `Runtime/Core/Public/Misc/AutomationTest.h:63–64` ✔ |
| Registration needs `WITH_AUTOMATION_WORKER` = `!UE_BUILD_SHIPPING` | `Runtime/Core/Public/Misc/Build.h:126–127` ✔ |
| The test macros `static_assert` ≥ 1 context and exactly one filter flag | `AutomationTest.h:4127–4133` ✔ |
| CQTest default flags: all contexts + `ProductFilter` | `Developer/CQTest/Public/CQTest.h:69` ✔ |
| `-ExecCmds` splits on commas; `Automation` splits on `;` | `Runtime/Engine/Private/ParseExecCommands.cpp:20–35`; `AutomationCommandline.cpp:581–582` ✔ |
| `-testexit=` exits without a failure code | `Runtime/Launch/Private/LaunchEngineLoop.cpp:1919–1931, 5590–5594` ✔ |
| Report state values `NotRun`, `InProcess`, `Fail`, `Success`, `Skipped` | `Runtime/AutomationTest/Public/AutomationState.h:14–21` ✔ |
| Gauntlet is Beta, off by default; telemetry stores a `Baseline` value with no comparison found | `Engine/Plugins/Experimental/Gauntlet/Gauntlet.uplugin:13–15`; `Programs/AutomationTool/Gauntlet/Framework/Base/Gauntlet.TestReport.cs:129–137` ✔; no comparison **[inferred from grep]** |

## 3. The build pipeline (evidence, notes B)

| Fact | Evidence (5.8.4) |
|---|---|
| `bUseUnityBuild` follows the intermediate environment; `-DisableUnity` selects `NonUnity` | `Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:1838–1842`; `Configuration/Descriptors/TargetDescriptor.cs:138–139`; `Configuration/UEBuildTarget.cs:1231–1241` |
| `bUseAdaptiveUnityBuild = true`; `-DisableAdaptiveUnity` | `Rules/TargetRules.cs:1870–1877` ✔ |
| A changed working set invalidates the makefile | `System/TargetMakefile.cs:1123–1150` ✔ |
| A changed set of reflected headers invalidates the makefile ("UHT files changed") | `System/TargetMakefile.cs:1104–1121` ✔ |
| UHT's run/up-to-date messages are debug-level, visible with `-Log=` | `System/UHTExecution.cs:1427, 1518`; `GlobalOptions.cs:30–34` ✔ |
| `Build.bat` holds a machine-wide lock file | `Engine/Build/BatchFiles/Build.bat:17–30` ✔ |

## 4. Perf measurement (evidence, notes C)

| Fact | Evidence (5.8.4) |
|---|---|
| CSV global columns set from real timers every frame | `Runtime/Launch/Private/LaunchEngineLoop.cpp:1515–1527` ✔ |
| CSV macros used by the probe | `Runtime/Core/Public/ProfilingDebugging/CsvProfiler.h:50, 56, 85, 120, 155` ✔ |
| APT controllers derive `UGauntletTestController`; capture start/stop only | `Engine/Plugins/Performance/AutomatedPerfTesting/Source/AutomatedPerfTesting/Public/AutomatedPerfTestControllerBase.h:77, 100–116` ✔ |
| APT's UAT side is a compiled DLL; its strings mention local and "historic" PerfReportTool reports and Horde telemetry, nothing about baselines or thresholds | `Engine/Binaries/DotNET/AutomationTool/AutomationScripts/AutomatedPerfTesting/net10.0/AutomatedPerfTesting.Automation.dll` **[inferred from a string scan]** |
| Horde's dashboard source is not installed | `Programs/Horde/HordeDashboard/` holds only a `.tps` file ✔ |

## 5. Existing work, updated

| Solution | Measures suite effectiveness? | Statistical perf decision? | Works here (MSVC, launcher engine, one PC)? | Evidence |
|---|---|---|---|---|
| Automation / Spec / CQTest / Functional Tests | No (pass/fail) | No | Yes: the runner's foundation | §2 |
| Gauntlet (Beta) | No | No; stores a baseline next to a measurement | Yes (UAT) | §2 |
| Automated Perf Testing (Experimental) | No | No; captures and reports | Partly: its BuildGraph includes are missing from the launcher install | #10 |
| Horde Automation Hub / Performance Trends | No | Dashboards for people; logic not readable here | Needs a Horde server and a database | notes C3, D4 |
| UBT `-CodeCoverage` | Coverage (execution), not checking | — | No: Clang only | #11 |
| Mull | Yes (mutation, schemata) | — | No: Clang, macOS/Linux | notes D1 |
| Mutate++ | Yes (naive text patches; compile failures count as kills) | — | Generic; knows nothing of UBT/UHT/automation | notes D1 |
| **TestTrust** | **Yes:** `.cpp` mutants, UBT-aware snapshot, exit code + report, stillborn excluded | **Yes:** robust run-level gate with measured error rates | Yes (designed for it) | `02` |

**The gap, stated conservatively:**
- **Suite effectiveness: strong.** No Unreal tool measures it, and the general tools don't run here. But mutation testing is a 1970s idea; the contribution is the engineering that makes it cheap and trustworthy for UE C++ (#1–#9) and the measurements.
- **Perf gating: medium (weaker than the roadmap's framing).** The decision rule is textbook statistics, and Epic's stack may do more behind Horde than can be read locally. The project keeps the gate (owner rule: never swap the project), narrowed to what is still unsolved locally: a gameplay workload, a single-run decision, and **measured** false-positive and detection rates against naive gates.

## 6. Hypothesis status after Phase 2

| # | Hypothesis | Status |
|---|---|---|
| H1 | Weak oracles let faults in executed code survive | Unchanged **[to measure]** on M-S and M-P1 |
| H2 | Boundaries are under-tested | Unchanged **[to measure]**; M-S has one by design |
| H3 | Naive perf checks are noise-dominated | Unchanged **[to measure]**; pinning removes the E-core cause (B-2) |
| H4 | Stored baselines drift | Unchanged **[to measure]** (SC5 a vs b) |
| H5 | Frame-level tests overstate significance | Supported by reasoning (notes C4) **[to measure]** with N3 |
| H6 | Mutation is too expensive in UE | **Rejected for `.cpp` mutants on a small suite:** ≈ 4–8 s build + ≈ 10–15 s test launch (#8, #9). Still to measure on a real suite (M-P1) |

## 7. Carried into Phase 3

- Snapshot by `git archive` into a git-ignored, non-git folder; never the working tree; refuse a destination inside the target unless ignored.
- `.cpp`-only mutants; six operator families; binary operators only with whitespace on both sides; assertion/logging macros skipped.
- Editor target; incremental build per mutant; one fresh `UnrealEditor-Cmd -nullrhi` per mutant, pinned, with `Automation Now;RunTests StartsWith:<suite>;Quit` and `-ReportExportPath`.
- Fates from exit code **and** report; stillborn excluded; green baseline required per batch.
- One queue job per batch, 30-minute budget, resumable manifest.
- Gate: run-level median and p95 of `GameThreadTime`, robust threshold fixed in advance, naive gates evaluated on the same data.

**Raw research notes**, with every quote, are in [Phase2_Raw_Notes/](Phase2_Raw_Notes/README.md). This file is authoritative.
