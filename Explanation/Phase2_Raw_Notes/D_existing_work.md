> **Raw Phase 2 research notes (D_existing_work), 2026-11-21.** Web sources, each with its URL and what was actually read. Restated in [../01b_Research_Findings.md](../01b_Research_Findings.md) §5.

# D. Existing work outside the engine

## D1. Mutation testing (the idea and its tools)

| Source | What it says | Status |
|---|---|---|
| Y. Jia and M. Harman, "An Analysis and Survey of the Development of Mutation Testing", IEEE TSE 37(5), 2011, pp. 649–678: https://doi.org/10.1109/TSE.2010.62 | Mutation testing is a fault-based technique studied for over three decades; mutation score, equivalent mutants and cost reduction are its classic problems | Citation and abstract checked (search result pages), paper not read in full |
| R. H. Untch, A. J. Offutt, M. J. Harrold, "Mutation Analysis Using Mutant Schemata", ISSTA 1993, pp. 139–148: https://dl.acm.org/doi/abs/10.1145/154183.154265 | Compile all mutants into one program and pick one at run time, to avoid one compile per mutant | Citation and abstract checked |
| Mull (LLVM-based): https://mull.readthedocs.io/en/latest/Features.html | Mutates LLVM IR / uses the Clang AST; supports mutant schemata; supports macOS and Linux; "works on Windows Subsystem for Linux, but no official support yet"; needs Clang ≥ 16 | Docs page read via search results |
| Mutate++ (nlohmann/mutate_cpp): https://github.com/nlohmann/mutate_cpp | Applies text patches "very naively on a purely syntactical level"; runs any build and test command per patch; a patch is "killed" if it **fails to compile** or a test catches it; supports a test timeout and a quick-check command; equivalent mutants are marked "ignore" by hand | README read |
| Mutation Testing Repository (tool list): https://mutationtesting.uni.lu/tools.php | Lists C/C++ tools (none Unreal-specific in the search) | Search result only |
| Search "mutation testing Unreal Engine C++ automation tests" (2026-11-21) | No Unreal-specific mutation tool, plugin or write-up found | Search; absence can't be proven |

**What this means for TestTrust**
- The idea is old and well understood. We claim no novelty for it.
- The practical blockers in Unreal are specific: MSVC (no Mull), UBT's build graph and UHT (no generic text tool knows when a change is cheap), and the automation framework's command-line contract (exit code, report, test count).
- Mutate++'s rule of counting compile failures as kills inflates the score. TestTrust reports that variant (M1-naive) only to show the difference.

## D2. Coverage in Unreal

- [research/03](../Research/03_existing_solutions_gap_analysis.md) §7.3: no built-in coverage; community setups use OpenCppCoverage or patch UBT for gcov (snippet only).
- Engine source: UBT's `-CodeCoverage` acts only with Clang (notes A7).
- Coverage and mutation answer different questions: coverage says a line was **executed**; mutation says a change to it was **noticed**. A line can be fully covered by a test with no assertion.

## D3. Testing practice at studios (from the portfolio research)

- Rare, Sea of Thieves ([research/02](../Research/02_technical_challenges.md) [T6-A], raw text checked): 23,000+ tests; coverage 60% decision / 70% function as their effectiveness proxy; failing tests retried once before the build turns red; a weekly top-intermittent list; quarantine and deletion of tests that stay broken.
- Epic, APT ([T6-F]): Epic staff say studios build their own frameworks to play the game nightly for gameplay performance.
- GDC 2021 roundtable ([T6-H], snippet only): flaky tests poison morale unless fixed or de-automated quickly.

## D4. Perf regression gating

- Horde Automation Hub docs (opened): results as tiles with relative health, historical data per test, cross-stream comparison: https://dev.epicgames.com/documentation/en-us/unreal-engine/horde-automation-hub-for-unreal-engine.
- Horde test automation tutorial (search result): https://dev.epicgames.com/documentation/en-us/unreal-engine/horde-test-automation-tutorial-for-unreal-engine.
- Epic knowledge base, "Practical Setup Tips for Horde Analytics & Performance Trends" (search result, not opened): https://dev.epicgames.com/community/learning/knowledge-base/dOrL/unreal-engine-practical-setup-tips-for-horde-analytics-performance-trends.
- Forum thread, APT → Horde Performance Trends with ClickHouse (search result summary): https://forums.unrealengine.com/t/how-to-set-up-the-automated-performance-testing-to-send-and-view-results-in-horde-performance-trends-dashboard-and-not-having-to-look-through-it-via-the-summarytable-html-locally/2738594.
- No source found that describes a statistical pass/fail rule (with a measured false-positive rate) in Horde or APT. Their dashboards show trends to a person **[unverified: the dashboard source is not installed, notes C3]**.

**Honest gap statement:** robust control limits on run-level statistics are textbook statistics. The engineering gap is a local, scripted gate for a *gameplay* workload whose false-positive and detection rates are *measured on this hardware* and compared against naive rules. Medium, not strong.
