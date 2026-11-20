# 00 · Project Overview: TestTrust

> *"This was the problem. This was my investigation. This was my solution. These were my technical decisions. This was how I measured the results."*

**Status (2026-11-21):** Phases 1–4 are done: problem analysis (`01`), verified research (`01b`), the final architecture v1.0 (`02`), the build steps (`03`) and the foundation (the UE project, build scripts and a first runner smoke test, recorded in `09`). **No results exist yet.** Every number below is a target set before the code that it judges.

---

## A. Identity

| | |
|---|---|
| **Name** | TestTrust: measuring whether tests actually catch bugs |
| **Technical category** | Debugging and automated testing: test-suite effectiveness (mutation analysis) and gameplay performance-regression gating |
| **Main objective** | Two measurements that a green test run doesn't give you. **(1) Mutation score:** inject small, controlled faults into gameplay C++ one at a time, rebuild, rerun the suite, and report how many faults the suite catches, plus the exact source lines it doesn't protect. **(2) Perf gate:** decide automatically whether a build made the game thread slower on a deterministic gameplay workload, with a **measured** false-positive rate, locally and without Horde |
| **Difficulty** | ★★★★☆ Advanced |
| **Core UE technologies** | Automation Test Framework (`IMPLEMENT_SIMPLE_AUTOMATION_TEST`, Automation Spec), CQTest, `Automation RunTests` + `-ReportExportPath` JSON reports, UnrealBuildTool incremental builds (adaptive unity, UHT), the CSV profiler (`CSV_EVENT`, `CSV_SCOPED_TIMING_STAT`), fixed-step `-deterministic` runs, world subsystems, a runtime plugin, Python for orchestration and statistics |
| **Relation to existing work** | Unreal already ships test frameworks (Automation, Spec, CQTest, Functional Tests, Gauntlet) and an Experimental perf-test harness (Automated Perf Testing, built on Gauntlet + CSV profiler + PerfReportTool). None of them measures **how good** a suite is, and none makes a statistical pass/fail decision on gameplay performance. Mutation testing itself is decades old (general C/C++ tools exist: Mull, Mutate++); what is new here is making it work with UnrealBuildTool, UHT and the automation framework on MSVC, at a measured cost. See `01` §3 and `01b` §5 |

## B–D. Problem, solution, architecture

- Problem, root-cause hypotheses, success criteria and the measurement plan: **[01_Problem_Analysis.md](01_Problem_Analysis.md)**
- What the engine actually does (verified in the 5.8.4 source) and how it changed the design: **[01b_Research_Findings.md](01b_Research_Findings.md)**
- Solution and architecture (final v1.0): **[02_System_Architecture.md](02_System_Architecture.md)**
- Build steps: **[03_Implementation_Roadmap.md](03_Implementation_Roadmap.md)**

## E. Technical demonstration

**What the viewer sees**
- **A mutation report** for a real suite (UE5-UpdateBudget's scheduler tests): one row per injected fault (file, line, the original and mutated code), its fate (*killed*, *survived*, *stillborn*, *timeout*), the cost of each mutant in seconds, and the mutation score per file and per operator.
- **The survivors**, each one a concrete line that no test protects ("`<` changed to `<=` on line 41 and every test still passed"), and the new tests that kill them.
- **A perf-gate chart:** per-run median game-thread time for ≥ 30 unchanged runs, the gate's threshold line, and runs with +0.25 / +0.5 / +1.0 ms of injected game-thread cost sitting above it. Next to it, the same runs judged by naive gates.

**Before** (the status quo)
- The suite is green. That says every test passed. It says nothing about which bugs the tests would catch.
- Performance is checked by eye, or with a fixed "+5% on average frame time vs last run" rule that either fires on laptop noise or misses a 0.25 ms regression.

**After**
- The suite has a **mutation score** with a list of unprotected lines. Writing tests for those lines raises the score, measurably.
- The perf gate flags +0.5 ms and +1.0 ms regressions in single runs, with a false-positive rate measured over ≥ 30 unchanged runs, and its result traces back to raw CSV captures.

**Recorded material:**
- the mutation report (HTML page) before and after the test improvements;
- the gate chart and the false-positive / detection table, against the naive gates;
- a short screen capture of one batch running through the machine's job queue.

## G. Portfolio presentation (produced in Phase 10)

1. Problem statement, one paragraph (from `01` §1).
2. The investigation: hypotheses H1–H6 and what the measurements showed for each.
3. The architecture diagram (from `02` §5) and the per-mutant flow.
4. The key decisions and the rejected alternatives: source-level mutants on `.cpp` files only, a snapshot outside every repository, the editor target instead of the game target, a fresh process per mutant, run-level (not frame-level) statistics.
5. Mutation scores before/after, and the gate's false-positive and detection rates against the naive gates, with the full environment and method.
6. What didn't work or didn't improve, stated plainly.
7. Video, source repository and the complete `Explanation/` folder.

## H. Industry relevance

**Skills demonstrated:**
- engine build-pipeline knowledge: how UnrealBuildTool decides what to rebuild, why a header change re-runs UHT, and how unity and adaptive-unity builds change incremental cost;
- the automation framework from the command line: test registration, application contexts, exit codes, JSON reports;
- test-design judgement: the difference between code that tests *run* and code that tests *check*;
- statistics on noisy hardware: choosing the sampling unit, robust thresholds, measuring false-positive rates instead of assuming them;
- tool engineering: a safe, resumable, time-bounded batch runner that never writes to the code it measures.

**Studios and roles that ask for this:**
- Respawn (Apex, senior generalist): "quantify game performance, prevent regressions, and improve launch stability";
- Riot (Staff SWE, Unreal Ecosystem): automated testing and CI/CD for UE plugins used by many teams;
- Ubisoft (senior gameplay): "CI/CD and automated testing"; Cloud Chamber: "sound testing procedures";
- testing or validation appears in 13 of 57 postings read (23%), more often in live-service roles.

Sources: [research/01](Research/01_job_market.md) (EA2, R3, U1, K1; tally row 22).

**Interview questions it prepares you for:**
- "All your tests pass. How do you know they're any good? Why isn't line coverage enough?"
- "What is an equivalent mutant, and why can't a tool detect every one?"
- "Why does touching one header in Unreal rebuild so much? What does UHT do?"
- "What is a unity build? What does adaptive unity do, and when does it help?"
- "How do you detect a 0.25 ms gameplay regression on a noisy laptop without crying wolf?"
- "Why not compare frame-time distributions frame by frame with a t-test?"
- "A test fails one run in twenty. What do you do?" (Rare's retry-then-quarantine policy, [research/02](Research/02_technical_challenges.md) [T6-A])
- "How would you make this a nightly CI job for a 100-person team?"
