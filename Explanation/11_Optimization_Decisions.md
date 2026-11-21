# 11 · Optimization Decisions: TestTrust

**Status:** not written yet. Filled in **Phase 8**.

**Will contain:** Every optimisation of the runner and the gate that was considered, with the measurement that motivated it, the change, the before/after numbers, and what was rejected (for example mutant ordering by file, test selection per mutant, mutant schemata, k = 3 candidate runs). The decisions already made from Phase 2 data are in [01b_Research_Findings.md](01b_Research_Findings.md) §1.

## Recorded in Phase 5, for Phase 8

S5 (`09`) measured the pre-registered gate and it missed SC5a, SC6 at 0.5 and 0.25 ms, and SC7. These are the options the data points to. None is applied: each would change the rule after seeing the data, so each needs its own batch, fixed before it runs.

| Option | What the S5 data says | Cost |
|---|---|---|
| k = 3 candidate runs (median of three), already offered in `02` §7 | One 20 s run's median moves 0.2–0.7 ms within a batch; a median of three should narrow that **[inferred]** | 3× the time per decision (about 36 s, still inside SC8's 90 s) |
| Median only, or a wider floor for the p95 | All 5 interleaved false positives involve the p95. An exploratory median-only re-count gives 2/32 (6.3%) false positives but only 12/32 detection at 0.25 ms | Less sensitivity to slow-frame regressions |
| Remove the post-pause dip (a second priming run, or a fixed cool-down before every batch) | The first runs after an idle gap were 0.2–0.7 ms faster in batches 1 and 3 | About 15 s per batch |
| Longer captures | Untested; the frame-level autocorrelation (H5) limits how much a longer run helps **[unverified]** | Proportional to the length |
