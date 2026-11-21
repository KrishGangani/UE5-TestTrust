# 12 · Future Scalability: TestTrust

How the two tools would grow into a studio pipeline. Nothing here has been built or measured.

| Direction | What changes | Why it is plausible from this project's data |
|---|---|---|
| Nightly campaigns on changed files only | Plan mutants only for `.cpp` files touched since the last campaign; reuse reviews by mutant id | Ids are stable per commit snapshot (`05` D3); a mutant costs about 14 s, so 200 changed-file mutants fit in about 45 min |
| Parallel batches on a build farm | One snapshot per agent, each running a disjoint slice of the pending list | Batches are already independent and resumable, with atomic manifests (`09` Phase 7, crash self-test) |
| Per-mutant test selection | Run only the tests that execute the mutated function | The editor launch, not the tests, dominates today, so the gain comes only once suites are long |
| Header and template mutants | Mutate headers with UHT-aware rebuild accounting, or move to mutant schemata with a Clang front end | Header mutants cost about 4 compiles each (`09` P2); out of scope in v1 |
| A gate that meets 0.25 ms | Several candidate runs per decision, longer captures, or a quieter machine | Within-batch spread of 0.2–0.7 ms is the limit (`09` S5). A pre-registered v2 (k = 3, median only) was designed but not measured |
| CI integration | `tt_gate.py decide` as a pre-merge step; results exported to Gauntlet/Horde telemetry instead of local files | One decision takes about 12 s plus build time (SC8) |
