# Mutation campaign `2026-11-21_031347_mut-sample`

Target: UE5-TestTrust at `03771bfe8796`, `TestTrust`; tests `StartsWith:TestTrust.Sample`. Raw data: `Benchmarks/Raw/2026-11-21_031347_mut-sample_manifest.json`.

| Fate | Count |
|---|---|
| killed | 11 |
| timeout | 0 |
| crash | 0 |
| survived | 3 |
| stillborn | 0 |
| error | 0 |
| not run | 0 |

- **M1 mutation score** (stillborn and reviewed-equivalent excluded): **91.7%** (11 killed of 12)
- M1 before the equivalence review: 78.6%
- M1-naive (compile failures counted as kills): 78.6%
- Reviewed equivalent: 2

| Operator | Killed | Survived | Stillborn |
|---|---|---|---|
| ROR | 3 | 1 | 0 |
| AOR | 4 | 0 | 0 |
| COND | 2 | 0 | 0 |
| SDL | 2 | 0 | 0 |

Cost per mutant (build + test): median 11.8 s, max 12.2 s, over 14 mutants. Batches: 1: 14 mutants in 238.8 s.

## Survivors

| Id | Where | Operator | Change | Review |
|---|---|---|---|---|
| `8125da701a` | `Source/TestTrustSample/Private/TTSampleRules.cpp:8` | ROR | `<` → `<=` | equivalent: Damage < MinDamage vs Damage <= MinDamage differ only when Damage == MinDamage, and then both branches leave Damage at MinDamage. No input can tell them apart. |
| `62c038c366` | `Source/TestTrustSample/Private/TTSampleRules.cpp:22` | ROR | `<=` → `<` | real gap: The deliberate gap: no test puts a target exactly at the range limit, so <= becoming < is not noticed. Phase 7 adds that test (03, S8). |
| `1c78e5d36c` | `Source/TestTrustSample/Private/TTSampleRules.cpp:28` | ROR | `>` → `>=` | equivalent: Next > 0.f vs Next >= 0.f differ only when Next is exactly zero (or negative zero), and then both return a value equal to 0.f. No input can tell them apart. |
