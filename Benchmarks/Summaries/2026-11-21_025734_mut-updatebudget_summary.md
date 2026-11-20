# Mutation campaign `2026-11-21_025734_mut-updatebudget`

Target: UE5-UpdateBudget at `b890bc6b428c`, `UpdateBudget`; tests `StartsWith:UpdateBudget.Scheduler`. Raw data: `Benchmarks/Raw/2026-11-21_025734_mut-updatebudget_manifest.json`.

| Fate | Count |
|---|---|
| killed | 24 |
| timeout | 0 |
| crash | 11 |
| survived | 4 |
| stillborn | 0 |
| error | 0 |
| not run | 0 |

- **M1 mutation score** (stillborn and reviewed-equivalent excluded): **92.1%** (35 killed of 38)
- M1 before the equivalence review: 89.7%
- M1-naive (compile failures counted as kills): 89.7%
- Reviewed equivalent: 1

| Operator | Killed | Survived | Stillborn |
|---|---|---|---|
| ROR | 15 | 3 | 0 |
| AOR | 3 | 0 | 0 |
| LCR | 4 | 0 | 0 |
| COND | 2 | 0 | 0 |
| SDL | 11 | 0 | 0 |

Cost per mutant (build + test): median 14.1 s, max 60.8 s, over 39 mutants. Batches: 1: 39 mutants in 687.7 s.

## Survivors

| Id | Where | Operator | Change | Review |
|---|---|---|---|---|
| `fbd237213c` | `Plugins/UpdateBudgetCore/Source/UpdateBudgetCore/Private/UpdateBudgetScheduler.cpp:42` | ROR | `<` → `<=` | equivalent: Tie-break A < B becomes A <= B. Client indices are unique, so the two differ only when the sort compares an element with itself, which Algo::IntroSort never does: its selection sort compares distinct positions (Core/Public/Algo/IntroSort.h:70) and its partition loops exclude the pivot (:98-99); heap-sort comparisons are between distinct nodes [inferred]. |
| `0072839e65` | `Plugins/UpdateBudgetCore/Source/UpdateBudgetCore/Private/UpdateBudgetScheduler.cpp:47` | ROR | `<` → `<=` | real gap: Deadline < NextFrameTime becomes <=: no test has a deadline exactly equal to the next frame time, so whether such a client is mandatory is untested. |
| `84989a4f35` | `Plugins/UpdateBudgetCore/Source/UpdateBudgetCore/Private/UpdateBudgetScheduler.cpp:56` | ROR | `>` → `>=` | real gap: SpentMs + Predicted > BudgetMs becomes >=: no test has an update that exactly fills the remaining budget, so the cut-off boundary is untested. |
| `60ff682b30` | `Plugins/UpdateBudgetCore/Source/UpdateBudgetCore/Private/UpdateBudgetScheduler.cpp:70` | ROR | `>` → `>=` | real gap: bOverBudget = SpentMs > BudgetMs becomes >=: no test spends exactly the budget, so 'exactly on budget is not over budget' is untested. |
