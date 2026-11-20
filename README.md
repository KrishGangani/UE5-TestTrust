# P03 · TestTrust: measuring whether tests actually catch bugs

**Domain:** Debugging & automated testing · **Difficulty:** ★★★★☆ · **Engine:** UE 5.8.4

> **Status: planned, not started.** The projects in this portfolio are built one at a time, and this one starts after the projects before it are complete. Everything below is the plan. The success criteria are **targets fixed before any code exists, not results**. Real numbers will only come from controlled before/after runs, each traceable to a raw benchmark batch.

## The problem

Test suites look green and still miss regressions. Gameplay perf regressions slip through, and Epic's perf-test tooling targets cameras and replays, not gameplay. No mutation testing was found for Unreal

## Proposed solution

A mutation runner that injects controlled faults into gameplay C++ and reports a **mutation score** for the suite. A **statistical perf gate** (median/p95 vs baseline with noise bounds) on a deterministic gameplay workload, runnable locally without Horde

## Main Unreal Engine technologies

Automation Spec / CQTest, `AFunctionalTest`, command-line automation, CSV profiler, Python statistics, Gauntlet (Beta) where it fits

## Success criteria (targets, defined before implementation)

Mutation score of the P1/P2 suites before vs after test improvements; detection rate of injected 0.25 / 0.5 / 1.0 ms regressions; false-positive rate over 30 unchanged runs ≤ 5%; suite wall time

## Existing work it must be compared against

Automation/Spec, CQTest, Functional Tests, Gauntlet, Automated Perf Testing plugin (Experimental), Horde trends (5.8)

**The gap it targets:** Mutation score for UE gameplay C++; local statistical gameplay perf gate (gap strength: Strong / Medium).

**Main risk:** MSVC + UHT-generated code makes mutation harder. We start with source-level mutants

## Why studios care

Respawn "quantify game performance, prevent regressions"; Riot automated testing; Rare's Sea of Thieves numbers; Epic says gameplay perf gates are left to studios

## Method

Every project in the portfolio follows the same ten phases: problem analysis → research → architecture → foundation → implementation → explanation → testing → profiling → review → portfolio. Each phase is documented in `Explanation/` (files 00–12, including a line-by-line code walkthrough), and every claimed improvement must be measured against the existing solutions above on the same workload. Engine: Unreal Engine 5.8.4, C++.

## Folder layout

```text
P03_TestTrust\
├── README.md        ← this page (becomes the project's portfolio page)
├── Explanation\     ← 00–12, created when the project starts
├── Benchmarks\      ← Raw\ + Summaries\
├── Media\           ← diagrams, screenshots, demo video
├── Tools\           ← analysis and run scripts
└── TestTrust\     ← the Unreal Engine project (created in its Phase 4)
```
