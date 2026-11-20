# 03 · Implementation Roadmap: TestTrust

**Written:** end of Phase 3, 2026-11-21 · **Engine:** UE 5.8.4

**Rules for every step:**
- Each step is small enough to read in one sitting: a few hundred lines at most.
- A step is finished only when its code **compiles with 0 warnings** (through the machine queue), its check **passes**, and its `Explanation/` entries (`05`, `06`, and `07` where relevant) are **written in the same step**.
- After each step that adds code: `simplify`, then `code-review`.
- **Baselines before the new thing.** The mutation score of a suite is measured *before* any test is written to improve it (S6 before S7). The gate's stored baseline and the naive gates' inputs are captured *before* the TT rule is evaluated on any data (S4 before S5), and the TT parameters are fixed now (`02` §7), not fitted later.
- Every UE job goes through `tools\ue_queue.py`, one queue job per batch, with a timeout.

---

**Progress (2026-11-21):** Phases 1–3 ✅. Phase 4 ✅: F1–F3 (`09`, one queue job, re-run after the AndroidFileServer rule); F4 runner and self-tests; F4 runner smoke test P4-R: 14 of 14 fates as predicted, M1 = 91.7%, 12.1 s median per mutant. Next: **S1** (probe plugin).

## Phase 4: Foundation

| Step | What gets built | How it is checked |
|---|---|---|
| **F1** | `TestTrust\TestTrust.uproject` (EngineAssociation 5.8; modules `TestTrust`, `TestTrustSample`; plugin `TestTrustProbe`), `Source\TestTrust.Target.cs`, `TestTrustEditor.Target.cs` (V7 settings, `Unreal5_8` include order), the two game modules and the plugin skeleton, `Config\DefaultEngine.ini` and `DefaultGame.ini` | The editor and game targets build from the command line with **0 errors, 0 warnings** |
| **F2** | `FTTSampleRules` (three rules) and six automation tests in `TestTrustSample` | `run_tests.bat` in the editor: 6 tests, 0 failures, exit 0 |
| **F3** | `Tools\build.bat`, `package.bat`, `smoke_game.bat`, `smoke_packaged.bat`, `run_tests.bat`, `phase4_checks.bat` (adapted from UE5-UpdateBudget) | `phase4_checks.bat` through the queue: editor build, game build, uncooked smoke, tests, packaged Development, packaged smoke without and with the GPU |
| **F4** | The runner v0: `tt_mutants.py` (lexer + 6 operators), `tt_mutate.py` (plan / batch / queue / report), `tt_common.py` (P-core pinning, environment, sanitising), `Tools\mutation\sample.json` | Self-tests (no UE). **Runner smoke test P4-R** on M-S through the queue: the predicted outcome (14 mutants; 11 killed; 1 real survivor; 2 equivalent survivors) is written down in `09` before the run |

## Phase 5: Implementation

| Step | What gets built | How it is checked | Explanation files |
|---|---|---|---|
| **S1. Probe plugin** | `UTTProbeSubsystem`: command-line options, a time-based capture window (half-frame tolerance) with `CSV_EVENT(BenchStart/BenchEnd)`, `CSV_METADATA`, exit, the spin-wait injector inside `CSV_SCOPED_TIMING_STAT`; the window arithmetic in a pure helper with automation tests | Tests for the window arithmetic; one packaged run: `BenchStart` at exactly warm-up × 60 frames, capture length exact, the `Injected` stat equal to X ms per frame | 04, 05, 06, 07 |
| **S2. Workload** | `UTTWorkloadBrainComponent`, `ATTWorkloadAgent`, `UTTWorkloadSubsystem`, copied and adapted from UE5-UpdateBudget (native tick in `TG_PrePhysics`) | Determinism: the same seed gives the same position hash twice, in the editor and the packaged build. **Calibration** (packaged, pinned, fixed step): compute iterations such that `FrameTime` ≈ `GameThreadTime` (game-thread bound) at N = 1,000 | 05, 06, 09 |
| **S3. Gate tools** | `run_bench.py` and `csv_stats.py` (adapted copies), `tt_gate.py` (TT, N1, N2, N3; `decide`, `evaluate`) | `csv_stats.py --selftest` (hand-calculated percentiles); `tt_gate.py --selftest` on synthetic runs with a known answer; one short real batch end to end | 05, 08, 09 |
| **S4. Gate data, captured before evaluation** | No new code | **Stored baseline:** one batch of m = 10 reference runs. Then, in a later session, **four evaluation batches** of 8 rounds × {0, 0.25, 0.5, 1.0} ms (32 runs per configuration, order rotated), one priming run each | 09 |
| **S5. Gate evaluation** | `tt_gate.py evaluate` output | **SC5–SC8:** false-positive rate (interleaved and stored baseline), detection per size, TT against N1, N2, N3; H3–H5 answered | 09, 11 |
| **S6. M-P1 "before"** | `Tools\mutation\updatebudget.json` (UE5-UpdateBudget, the commit of its S4 tests) | Campaign through the queue; report; every survivor reviewed (equivalent with a reason, or a real gap). **This is the "before" score, captured before any new test is written** | 09 |
| **S7. M-P1 "after"** | New tests aimed at the survivors, written as a patch file in `Tools\mutation\patches\` and applied to the snapshot only (UE5-UpdateBudget is never edited by this project); `tt_mutate.py` gains a `patches` config key | Campaign on snapshot + patch; **SC4** (M1-after ≥ 90%). The patch is offered to UE5-UpdateBudget's owner, not committed there | 05, 09 |
| **S8. Repeatability and cost** | No new code | **SC1:** the M-S campaign re-run gives identical fates; **SC3:** median cost per `.cpp` mutant across all campaigns | 09 |

## Phases 6–10 (after the code exists)

| Phase | Work |
|---|---|
| 6 Explanation | Consolidate 04–07 into one consistent line-by-line pass; re-check every API against 5.8.4 |
| 7 Testing | Edge cases: a mutant that crashes the editor, a mutant that hangs (timeout path), a red baseline (refusal path), a batch killed mid-mutant (restore path), a file that changed since planning (refused), an empty filter (0 tests: refused) |
| 8 Profiling | Gate: spiky-injection exploratory batch; cost of `UnrealEditor-Cmd` startup vs test time; runner: where the per-mutant seconds go (UBT overhead, compile, link, editor start, tests) |
| 9 Code review | `code-review` and `simplify`, plus a written self-review: weaknesses, not praise |
| 10 Portfolio | Mutation report page and gate charts (`dataviz`), the architecture page (`artifact-diagramming`), demo capture, README results, interview Q&A |

**Rough queue cost:** S4 = 10 + 4 × 33 runs ≈ 142 runs × ~40 s ≈ 95 min, in 5 batches. M-P1 = 43 mutants (`09` P2 lists them) at the per-mutant cost measured in `09` P2, in 30-minute batches.
