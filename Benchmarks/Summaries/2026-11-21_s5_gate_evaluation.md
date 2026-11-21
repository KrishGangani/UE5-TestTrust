# Gate evaluation 2026-11-21_s5

Counts are flagged / judged runs. X0 = unchanged (any flag is a false positive).

## (a) baseline = the X0 runs interleaved in the same batch

| Rule | X0 (false positives) | X025 | X05 | X10 |
|---|---|---|---|---|
| TT | 5/32 (16%) | 18/32 (56%) | 30/32 (94%) | 32/32 (100%) |
| N1 | 3/32 (9%) | 12/32 (38%) | 29/32 (91%) | 32/32 (100%) |
| N2 | 2/32 (6%) | 9/32 (28%) | 22/32 (69%) | 32/32 (100%) |
| N3 | 15/32 (47%) | 31/32 (97%) | 32/32 (100%) | 32/32 (100%) |

## (b) baseline = the stored batch captured earlier

| Rule | X0 (false positives) | X025 | X05 | X10 |
|---|---|---|---|---|
| TT | 1/32 (3%) | 13/32 (41%) | 28/32 (88%) | 32/32 (100%) |
| N1 | 4/32 (12%) | 22/32 (69%) | 30/32 (94%) | 32/32 (100%) |
| N2 | 7/32 (22%) | 23/32 (72%) | 30/32 (94%) | 32/32 (100%) |
| N3 | 29/32 (91%) | 30/32 (94%) | 32/32 (100%) | 32/32 (100%) |

## Success criteria

| # | Criterion | Pass |
|---|---|---|
| SC5a | TT false positives, interleaved baseline: 15.6% of 32 runs (target <= 5% of >= 30) | **no** |
| SC6a | TT detection X10, interleaved: 100.0% (target >= 100%) | yes |
| SC6a | TT detection X05, interleaved: 93.8% (target >= 95%) | **no** |
| SC6a | TT detection X025, interleaved: 56.2% (target >= 80%) | **no** |
| SC7a | TT no worse than N1/N2/N3 on every rate, interleaved | **no** |
| SC5b | TT false positives, stored baseline: 3.1% of 32 runs (target <= 5% of >= 30) | yes |
| SC6b | TT detection X10, stored: 100.0% (target >= 100%) | yes |
| SC6b | TT detection X05, stored: 87.5% (target >= 95%) | **no** |
| SC6b | TT detection X025, stored: 40.6% (target >= 80%) | **no** |
| SC7b | TT no worse than N1/N2/N3 on every rate, stored | **no** |

Stored baseline: `2026-11-21_050350_gate-stored_manifest.json` (10 valid runs). Evaluation batches: `2026-11-21_053701_gate-eval1_manifest.json`, `2026-11-21_054518_gate-eval2_manifest.json`, `2026-11-21_055612_gate-eval3_manifest.json`, `2026-11-21_060429_gate-eval4_manifest.json`.
Rule parameters fixed before the data: Z = 3.0, floor = 0.1 ms, N1 ratio 1.05, N2 2.0 sd, N3 alpha 0.05.
