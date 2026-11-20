# Mutation campaign `2026-11-21_031329_mut-updatebudget`

Target: UE5-UpdateBudget at `b890bc6b428c`, `UpdateBudget`; tests `StartsWith:UpdateBudget.Scheduler`. Raw data: `Benchmarks/Raw/2026-11-21_031329_mut-updatebudget_manifest.json`.

| Fate | Count |
|---|---|
| killed | 27 |
| timeout | 0 |
| crash | 11 |
| survived | 1 |
| stillborn | 0 |
| error | 0 |
| not run | 0 |

- **M1 mutation score** (stillborn and reviewed-equivalent excluded): **100.0%** (38 killed of 38)
- M1 before the equivalence review: 97.4%
- M1-naive (compile failures counted as kills): 97.4%
- Reviewed equivalent: 1

| Operator | Killed | Survived | Stillborn |
|---|---|---|---|
| ROR | 18 | 0 | 0 |
| AOR | 3 | 0 | 0 |
| LCR | 4 | 0 | 0 |
| COND | 2 | 0 | 0 |
| SDL | 11 | 0 | 0 |

Cost per mutant (build + test): median 14.0 s, max 20.0 s, over 39 mutants. Batches: 1: 39 mutants in 656.9 s.

## Survivors

| Id | Where | Operator | Change | Review |
|---|---|---|---|---|
| `fbd237213c` | `Plugins/UpdateBudgetCore/Source/UpdateBudgetCore/Private/UpdateBudgetScheduler.cpp:42` | ROR | `<` → `<=` | equivalent: Tie-break A < B becomes A <= B. Client indices are unique, so the two differ only when the sort compares an element with itself, which Algo::IntroSort never does: its selection sort compares distinct positions (Core/Public/Algo/IntroSort.h:70) and its partition loops exclude the pivot (:98-99); heap-sort comparisons are between distinct nodes [inferred]. |
