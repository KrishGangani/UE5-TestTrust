# Phase 2 raw notes

These are the working notes behind [01b_Research_Findings.md](../01b_Research_Findings.md). They are kept so every statement in the findings can be traced back to the exact engine line or web page it came from.

| File | Scope |
|---|---|
| `A_test_frameworks.md` | Automation tests, Spec, CQTest, Functional Tests, Gauntlet; contexts; `Automation RunTests`, its exit code and JSON report; coverage |
| `B_build_pipeline.md` | How UnrealBuildTool decides what to rebuild: timestamps, UHT, unity and adaptive unity, the working set; editor vs game target |
| `C_perf_measurement.md` | Fixed step and CSV capture (re-opened from UE5-UpdateBudget's research), the Automated Perf Testing plugin, PerfReportTool, Horde, the statistics of a gate |
| `D_existing_work.md` | Mutation-testing literature and tools, coverage, studio practice, perf gating outside the engine |

The build-cost probe's raw output is in `Benchmarks/Raw/<batch>_buildcost_manifest.json`; its numbers are in `09_Testing_And_Benchmarks.md` (P2).

**The findings file is authoritative.** These notes are the audit trail.
