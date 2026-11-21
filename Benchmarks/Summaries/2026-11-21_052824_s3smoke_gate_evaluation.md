# Gate evaluation 2026-11-21_052824_s3smoke

Counts are flagged / judged runs. X0 = unchanged (any flag is a false positive).

## (a) baseline = the X0 runs interleaved in the same batch

| Rule | X0 (false positives) | X025 | X05 | X10 |
|---|---|---|---|---|
| TT | 0/4 (0%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |
| N1 | 0/4 (0%) | 3/4 (75%) | 2/4 (50%) | 4/4 (100%) |
| N2 | 0/4 (0%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |
| N3 | 0/4 (0%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |

## (b) baseline = the stored batch captured earlier

| Rule | X0 (false positives) | X025 | X05 | X10 |
|---|---|---|---|---|
| TT | 0/4 (0%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |
| N1 | 0/4 (0%) | 2/4 (50%) | 1/4 (25%) | 4/4 (100%) |
| N2 | 0/4 (0%) | 1/4 (25%) | 1/4 (25%) | 4/4 (100%) |
| N3 | 0/4 (0%) | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |

## Success criteria

| # | Criterion | Pass |
|---|---|---|
| SC5a | TT false positives, interleaved baseline: 0.0% of 4 runs (target <= 5% of >= 30) | **no** |
| SC6a | TT detection X10, interleaved: 100.0% (target >= 100%) | yes |
| SC6a | TT detection X05, interleaved: 100.0% (target >= 95%) | yes |
| SC6a | TT detection X025, interleaved: 100.0% (target >= 80%) | yes |
| SC7a | TT no worse than N1/N2/N3 on every rate, interleaved | yes |
| SC5b | TT false positives, stored baseline: 0.0% of 4 runs (target <= 5% of >= 30) | **no** |
| SC6b | TT detection X10, stored: 100.0% (target >= 100%) | yes |
| SC6b | TT detection X05, stored: 100.0% (target >= 95%) | yes |
| SC6b | TT detection X025, stored: 100.0% (target >= 80%) | yes |
| SC7b | TT no worse than N1/N2/N3 on every rate, stored | yes |

Stored baseline: `2026-11-21_045922_s3smoke-stored_manifest.json` (3 valid runs). Evaluation batches: `2026-11-21_052824_s3smoke-eval_manifest.json`.
Rule parameters fixed before the data: Z = 3.0, floor = 0.1 ms, N1 ratio 1.05, N2 2.0 sd, N3 alpha 0.05.
