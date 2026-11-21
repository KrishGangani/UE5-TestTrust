# 01 · Problem Analysis: TestTrust

**Phase:** 1 (Problem Analysis), 2026-11-21; updated after Phase 2 the same day (evidence in [01b_Research_Findings.md](01b_Research_Findings.md)).
**Engine:** UE **5.8.4** (CL 58902052). Engine facts are read from `C:\Program Files\Epic Games\UE_5.8\Engine` and cited as `File:line`. Paths are relative to `Engine/Source/`, except those starting with `Plugins/`, `Binaries/`, `Config/`, `Build/` or `Source/`, which are relative to `Engine/`.
**Status of every claim:** **[verified]** (read in engine source or a cited source), **[hypothesis]** (to be confirmed by measurement), **[target]** (a pass/fail threshold, not a result), **[inferred]** (reasoned from code, not read directly), **[unverified]** (could not be checked).

---

## 1. The problem in one paragraph

A test suite that passes tells you that every test passed. It does not tell you which bugs the tests would have caught. A test can call a function and never check its result; a boundary such as `<` versus `<=` can be wrong and no test notices. So suites look green and still let regressions through, and nobody can say how much protection they give. The second half of the problem is performance: gameplay regressions of a fraction of a millisecond are invisible by eye, and a naive check ("is this run 5% slower than the last one?") is dominated by run-to-run noise on real hardware, so it either raises false alarms until people ignore it, or misses small regressions entirely. Unreal ships good frameworks for **writing** tests and an Experimental harness for **capturing** performance; it ships nothing that **measures the suite** or **makes a statistical pass/fail decision** about gameplay performance.

## 2. Where this happens in real games

| Evidence | What it shows | Source |
|---|---|---|
| Sea of Thieves (Rare) | "Just over 23 thousand tests"; coverage 60% decision / 70% function; every test runs at least every 20 minutes; build verification fell to 1.5 days from "a full two weeks"; flaky tests are retried, then quarantined and deleted | [research/02](Research/02_technical_challenges.md) [T6-A] (raw text checked) |
| Call of Duty (Activision) | CI across "hundreds of PCs and devkits", perf and memory tracking, handling intermittent errors | [research/02](Research/02_technical_challenges.md) [T6-C] |
| Epic, Automated Performance Testing | Epic staff: the built-in perf tests focus on environment/GPU performance; for gameplay, studios "build data-driven frameworks that play their game nightly". The glue code is Experimental | [research/02](Research/02_technical_challenges.md) [T6-F] |
| Epic, UEFN stability | Epic tracks Defect Escape Rate; many regressions "span multiple systems or only appear in late-cycle, large-scale testing" | [research/02](Research/02_technical_challenges.md) [T6-G] |
| GDC 2021 testing roundtable | Flaky tests "need immediate investment to fix or de-automate before poisoning testing morale" | [research/02](Research/02_technical_challenges.md) [T6-H] (snippet only) |
| Job postings, 2026 | Respawn: "quantify game performance, prevent regressions". Riot: automated testing for UE plugins used by many teams. Testing/validation in 13 of 57 postings | [research/01](Research/01_job_market.md) (EA2, R3; tally row 22) |

**What these share:** the studios that publish numbers treat the *trustworthiness* of tests (flakiness, what they catch) and *performance regressions* as the hard part, not writing individual tests.

## 3. What already exists, and why it doesn't fully solve the problem

| Existing tool | What it does | What it doesn't do | Evidence |
|---|---|---|---|
| Automation Test Framework (`IMPLEMENT_SIMPLE_AUTOMATION_TEST`, complex tests, latent commands) | Registers C++ tests by name and flags; runs them from the editor, the Session Frontend or the command line | Says pass/fail per test. Says nothing about which faults the tests would catch | [verified] `Runtime/Core/Public/Misc/AutomationTest.h:4297, 4303, 3796` |
| Automation Spec (`BEGIN_DEFINE_SPEC`, `Describe`/`It`) | BDD-style tests on the same framework | Same as above | [verified] `AutomationTest.h:4346, 2900–2901` (`FAutomationSpecBase : public FAutomationTestBase`) |
| CQTest (`TEST_CLASS`, `TEST_METHOD`, `BEFORE_EACH`, `FActorTestSpawner`) | Fixtures with automatic per-test reset; world/actor helpers; no plugin flag (a Developer module) | Same as above | [verified] `Developer/CQTest/Public/CQTest.h:305, 291, 333`; `TTestRunner : public FAutomationTestBase` at `:147` |
| Functional Tests (`AFunctionalTest`) | Tests placed in maps as actors, named `Project.Functional Tests.<map>.<actor>` | Same as above; needs authored maps | [verified] `Developer/FunctionalTesting/Classes/FunctionalTest.h:249`; `Private/FunctionalTest.cpp:733` |
| Command-line automation | `Automation RunTests <filter>;Quit` exits with `-1` if any test failed and writes `index.json` with `-ReportExportPath=` | Gives the raw signal TestTrust is built on; nothing more | [verified] `Developer/AutomationController/Private/AutomationCommandline.cpp:503–504, 610–627`; `AutomationControllerManager.cpp:233, 746` |
| Gauntlet (Beta) | UAT-side session framework (`UnrealTestNode`, `RunUnreal`) plus an in-game `UGauntletTestController`; telemetry records carry a `Baseline` value | Orchestrates and reports. No comparison of a measurement against its baseline was found | [verified] `Plugins/Experimental/Gauntlet/Gauntlet.uplugin:15`; `Source/Programs/AutomationTool/Gauntlet/Framework/Base/Gauntlet.TestReport.cs:129–137`; no comparison logic **[inferred from grep]** |
| Automated Perf Testing (Experimental) | Gauntlet test controllers for StaticCamera, Sequence, Replay, Material and ProfileGo tests; start/stop CSV profiler, Insights, FPS chart, video; PerfReportTool reports and Horde telemetry | Camera, sequence and replay oriented. No C++ threshold or baseline logic; its UAT script ships only as a compiled DLL, and the BuildGraph includes its template references are **not in the launcher install** | [verified] `Plugins/Performance/AutomatedPerfTesting/AutomatedPerfTesting.uplugin:15`; `Public/AutomatedPerfTestControllerBase.h:77, 100–116`; `01b` §5 |
| CSV tools + PerfReportTool | Summaries and HTML reports from CSV captures; `CsvInfo` gives avg/min/max | No percentiles, no statistical regression test | [verified] `Binaries/DotNET/CsvTools/` (UE5-UpdateBudget's finding, re-checked by listing the folder) |
| Horde Automation Hub / Performance Trends (5.8, Experimental) | Test results across streams and platforms; trend dashboards over Automated Perf Testing telemetry, with a user-supplied database | Needs a Horde server and a telemetry database. The dashboard source is not in the launcher install, so its regression logic (if any) can't be read | [verified absence] `Source/Programs/Horde/HordeDashboard/` holds only a `.tps` file; docs: https://dev.epicgames.com/documentation/en-us/unreal-engine/horde-automation-hub-for-unreal-engine |
| UnrealBuildTool `-CodeCoverage` | Adds coverage flags | **Only when the compiler is Clang.** With MSVC, the default here, it adds nothing | [verified] `Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:2354–2356`; `Platform/Windows/VCToolChain.cs:885–893` |
| General C/C++ mutation tools | Mull (LLVM, mutant schemata, macOS/Linux); Mutate++ (naive text patches, any build command) | Mull needs Clang and isn't supported on Windows; Mutate++ counts a compile failure as a "kill" and knows nothing about UBT, UHT or the automation framework. No Unreal-specific mutation tool was found | Mull docs https://mull.readthedocs.io/en/latest/Features.html; https://github.com/nlohmann/mutate_cpp; [research/03](Research/03_existing_solutions_gap_analysis.md) §7.3 |

**The gap, after Phase 2:**
- **Suite effectiveness (strong gap).** No Unreal tool measures a C++ suite's fault-detection ability, and coverage is unavailable with MSVC in the stock toolchain. Mutation testing is an old, well-studied idea (Jia and Harman's survey, IEEE TSE 2011, https://doi.org/10.1109/TSE.2010.62), so the contribution is **making it practical for UE C++ under MSVC, UBT and UHT, with its cost measured**, not the idea.
- **Gameplay perf gating (medium gap, weaker than it sounds).** The statistics are standard (robust control limits on run-level medians). Epic's tooling captures and reports; it doesn't decide. What TestTrust adds is a **local** gate on a **gameplay** workload with a **measured** false-positive and detection rate, compared against naive gates on the same data. We state this as an engineering gap, not a research one.

## 4. Root-cause hypotheses

Each hypothesis gets a measurement that can confirm or reject it.

| # | Hypothesis | Why we suspect it | How we test it |
|---|---|---|---|
| H1 | **Weak oracles:** tests run code but don't check enough of its effects, so faults in executed code survive | Rare tracked coverage (60–70%) as a proxy; executing a line is not checking it | Classify every surviving mutant by hand: *not reached*, *reached but not checked*, *equivalent*. If most survivors are "reached but not checked", H1 holds |
| H2 | **Boundaries are under-tested:** relational-operator mutants (`<` ↔ `<=`) survive more often than other kinds | Happy-path tests rarely sit exactly on a threshold | Survival rate per operator family; H2 holds if relational survival is clearly the highest |
| H3 | **Naive perf checks are noise-dominated:** a fixed-percentage rule on one run either fires on unchanged builds or misses 0.25 ms | Run-to-run spread on a laptop (thermal state, background load) is of the same order as small regressions. On this hybrid CPU an unpinned run can even land on an E-core and run about 1.6× slower (UE5-UpdateBudget's baseline batch); pinning removes that cause (§7), not the rest | False-positive and detection rates of naive gates on the same captures (`§6.2`) |
| H4 | **Stored baselines drift:** noise between sessions is larger than within a session, so a baseline captured earlier raises the false-positive rate | Laptop thermal state and background load change over hours | Same gate, two baselines: one interleaved with the candidates, one captured in an earlier batch. Compare the false-positive rates |
| H5 | **Frames are not independent samples:** a frame-level test (thousands of "samples") reports significance where there is none | Consecutive frames share thermal state, caches and simulation phase (autocorrelation) | Run a frame-level two-sample test on pairs of unchanged runs; H5 holds if its false-positive rate is far above its nominal α |
| H6 | **Mutation testing isn't used in UE because each mutant costs a full C++ rebuild and an editor start** | No UE mutation tool exists; C++ builds are known to be slow | Measure per-mutant build and test time by code path (game-module `.cpp`, plugin `.cpp`, UObject header). **Phase 2 measured it** (`01b` §1, `09` P2) |

## 5. The cost of leaving it unsolved

- A suite nobody can measure grows by habit: tests get added where it is easy, not where they protect most. Rare's numbers show what effective automated testing buys: build verification in 1.5 days instead of two weeks, and 17 instead of 50 full-time testers at release ([research/02](Research/02_technical_challenges.md) [T6-A]).
- A perf check that raises false alarms gets switched off, as the GDC roundtable notes for flaky tests ([T6-H]). One that misses small regressions lets them add up: *arithmetic illustration, not a measurement:* ten unnoticed 0.25 ms regressions are 2.5 ms, 15% of a 60 fps frame.

## 6. What "solved" means: success criteria, defined now

### 6.1 The workloads (identical in every run)

**Mutation workloads** (each pinned to a git commit; the runner never touches the repository itself):

| ID | Code under test | Suite | When |
|---|---|---|---|
| M-S | TestTrust's own sample module `TestTrustSample`: small gameplay rules (damage with armour and critical hits, range check, cooldown) | Its automation tests (`TestTrust.Sample.*`), written with one boundary deliberately left untested so a survivor must appear | Phase 4 smoke test, Phase 7 |
| M-P1 | UE5-UpdateBudget's scheduling policy (`UpdateBudgetScheduler.cpp` in the `UpdateBudgetCore` plugin) | Its automation tests (`UpdateBudget.Scheduler.*`, step S4 of that project) | Once that step is committed |
| M-P2 | UE5-SpawnPacer gameplay code | Its suite | When it exists |

**Perf-gate workload:** a deterministic gameplay workload **copied and adapted** from UE5-UpdateBudget's benchmark: N = 1,000 agents placed from a fixed seed, each running sense → decide → act plus a calibrated compute step every frame (native tick), a fixed camera path, fixed step `-deterministic -FPS=60`. Its game-thread time is expected near 5 ms, as in UE5-UpdateBudget's calibration (to be re-measured here). **Injected regression:** the probe plugin spins the game thread for exactly X ms per frame, X ∈ {0, 0.25, 0.5, 1.0}, inside its own CSV timing stat so the injected time is visible in every capture.

### 6.2 Compared configurations

**Mutation side** (all computed from the same mutant runs):

| ID | What is reported | Why it is included |
|---|---|---|
| M0 | The suite's pass/fail only | The status quo: "green" |
| M1 | **TestTrust mutation score** = killed / (killed + survived); compile failures (*stillborn*) and reviewed equivalent mutants excluded; timeouts and crashes count as killed and are listed separately | Our measure |
| M1-naive | Compile failures counted as kills (Mutate++'s rule) | Shows how much a careless definition inflates the score |
| M1-after | M1 after adding tests aimed at the survivors | The "before vs after test improvements" result |

**Gate side** (all evaluated offline on the same captures, so the comparison is fair):

| ID | Rule | Why it is included |
|---|---|---|
| N1 | Flag if the run's **average** `FrameTime` > 1.05 × the previous reference run's average | The common "+5% vs last run" check on averages |
| N2 | Flag if the run's mean `GameThreadTime` > mean + 2 σ of the m baseline runs' means | A classic, non-robust "2-sigma" alert |
| N3 | Flag if a frame-level Mann–Whitney test (all frames of candidate vs all frames of one reference run) gives p < 0.05 and the median is higher | Tests H5: treats frames as independent samples |
| **TT** | **TestTrust gate** (robust, run-level; parameters in `02` §7): flag if the run's median **or** p95 `GameThreadTime` exceeds the baseline's median + max(0.10 ms, 3 × 1.4826 × MAD) | Our gate |

### 6.3 Metrics

| Metric | Unit | Tool |
|---|---|---|
| Mutants by fate: killed, survived, stillborn, timeout, crash, error | count | `Tools/tt_mutate.py` results file |
| Mutation score (M1, M1-naive, M1-after), per file and per operator | % | `tt_mutate.py report` |
| Per-mutant cost: build, test, total | s | wall-clock timers in the runner |
| Batch wall time vs its queue timeout | s | runner + queue history |
| Gate false-positive rate over unchanged runs | % (with count) | `Tools/tt_gate.py` |
| Gate detection rate per injected size | % (with count) | `tt_gate.py` |
| Per-run median, p95, p99 of `GameThreadTime` and `FrameTime` | ms | CSV profiler + `Tools/csv_stats.py` (copied from UE5-UpdateBudget) |
| Gate decision time (one run + analysis) | s | wall clock |

### 6.4 Pass/fail criteria [target]

| # | Criterion | Threshold |
|---|---|---|
| SC1 | **The runner is trustworthy** | On M-S: every mutant ends in a defined fate (**0** *error*); a second run of the same batch gives the **same fate for 100%** of mutants; the unmutated snapshot builds and passes before every batch (otherwise the batch refuses to run) |
| SC2 | **It never touches the code it measures** | **0** files written inside any target repository. Checked by construction (snapshot from a commit object with read-only git commands; a path guard) and by a test against a throwaway repository whose tree hash must be identical before and after |
| SC3 | **Cost per mutant** | Median build + test time per `.cpp` mutant ≤ **60 s** on this machine; **100%** of batches finish inside their queue timeout. (Set at 90 s in the first Phase 1 draft; tightened after the Phase 2 probe, `01b` §1) |
| SC4 | **The score is useful** | On M-P1, the tests written from the survivor list raise the M1 score to **≥ 90%**, and every remaining survivor is classified (equivalent with a written reason, or an accepted gap). The score before is reported as it is, however low |
| SC5 | **False positives** | Gate TT flags **≤ 5%** of ≥ 30 unchanged runs: (a) against a baseline interleaved in the same batch, **and** (b) against a baseline stored from an earlier batch |
| SC6 | **Detection** | Single-run detection of injected regressions: **100%** at +1.0 ms, **≥ 95%** at +0.5 ms, **≥ 80%** at +0.25 ms |
| SC7 | **Better than the naive gates** | TT's false-positive rate ≤ that of N1, N2 and N3, with equal or higher detection at every size. If not met, we report it and analyse why. No reframing |
| SC8 | **Fast enough to use** | One gate decision (one run + analysis) ≤ **90 s**; the M-P1 mutation batch's total wall time is reported |

## 7. Measurement plan (summary; the full protocol is in `09_Testing_And_Benchmarks.md` and `Benchmarks/README.md`)

**Mutation runs**
- The target repository is snapshotted at a pinned commit with `git archive` into `Tools/_work/` (git-ignored, outside every repository's history). The runner writes only there and into `Benchmarks/`.
- The editor target of the snapshot is built once; each mutant changes **one `.cpp` file**, rebuilds incrementally, and runs the suite in a **fresh** `UnrealEditor-Cmd -nullrhi` process with a timeout. Fates are decided from the exit code **and** the JSON report (test count must equal the baseline's).
- Mutants are run in **batches**, one machine-queue job per batch, each with a timeout sized from the measured per-mutant cost (`02` §7). Results are appended per mutant, so a killed batch resumes where it stopped.

**Perf-gate runs** (the portfolio's measurement protocol)
- **Packaged Development build** (the launcher engine can't build Test; [research/04](Research/04_local_engine_verification.md) §0b).
- Fixed step `-deterministic -FPS=60`, real GPU, windowed 1280×720, `-novsync`, `-nosound`, `-traceautostart=0`. The capture window is opened and closed by the game itself with CSV events after warm-up.
- **Every timed process is pinned to the performance cores** (this i7-14650HX is hybrid: P-cores are logical CPUs 0–15, mask `0xFFFF`). UE5-UpdateBudget's baseline batch showed runs at two stable levels about 1.6× apart when Windows put the game thread on an E-core. `run_bench.py` pins itself with `tt_common.pin_self(mask)` (`SetProcessAffinityMask`) before it starts anything, and every game it launches inherits the mask; the step checks and the mutant test launches wrap their command in `cmd /v:on /s /c "start "" /wait /affinity <MASK> <command> & exit !errorlevel!"` (`tt_common.pinned`, which also keeps the exit code, `01b #14`). A batch refuses to run if the mask is unknown or pinning fails. The mask comes from `performance_core_mask()`, copied from UE5-UpdateBudget's `run_bench.py`, and is written into every environment record. The same pinning is used for the test launches of mutant runs, so their timeouts are stable. Builds are not pinned.
- One discarded priming run per batch, then **interleaved** runs with the configuration order rotated every round. With four configurations (X = 0, 0.25, 0.5, 1.0 ms), each round is one rotation, so every configuration sits in every position equally often; **32 rounds** give 32 unchanged runs (≥ 30) and 32 runs per injected size. Split into four batches of 8 rounds so no single queue job is long.
- A separate, earlier batch of m = 10 reference runs is the **stored baseline** for SC5(b).
- Statistics: median, p95 and p99 per run (linear-interpolation percentiles), then medians across runs with [min–max]. The **run** is the sampling unit; frames are never treated as independent samples (except in N3, which exists to test H5).
- The environment is recorded with every batch (CPU, GPU and driver, OS build, power plan, AC power, engine version, build configuration, resolution).
- **Honest precision:** a rate measured on 32 trials is coarse. One false alarm in 32 is 3.1%, two are 6.3%. We report counts, not just percentages.

## 8. Limits we accept up front

- **Equivalent mutants can't all be detected automatically.** Some mutants don't change behaviour (for example `<` to `<=` where equality can't happen). They are reviewed by hand and listed with a reason; they never silently inflate or deflate the score.
- **Source-level mutation in `.cpp` files only (v1).** Header mutations re-run UHT and rebuild every includer (`01b` §1), and inline or template code in headers is out of scope. This is a scope limit, stated in every report.
- **Text-level operators, not a C++ parser.** The mutator is a careful lexer, not a compiler front end. Some generated mutants won't compile; they are counted as *stillborn* and excluded, never counted as kills.
- **The injected perf regression is synthetic.** A spin-wait is a clean, known-size shift. Real regressions can be spiky; the gate also checks p95, and a spiky-injection experiment is reported as exploratory, not as a success criterion.
- **One machine, one laptop.** All rates are for this hardware and protocol. A desktop or a CI farm would have different noise.
- **The mutation score measures the suite against our mutation operators**, not against every real bug. It is a stronger signal than "green", not a proof of correctness.
