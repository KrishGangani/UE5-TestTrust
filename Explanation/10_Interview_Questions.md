# 10 · Interview Questions: TestTrust

Answers come from this project's code and measurements (`09`).

**1. What does mutation testing tell you that code coverage doesn't?**
Coverage says a line ran. A mutant says whether any test would notice if that line were wrong. In UE5-UpdateBudget's scheduler, every survivor sat on a line that every test executes. The tests ran the boundary but never checked it exactly (`09` S6).

**2. Why don't Unreal teams use mutation testing, and was the cost really the problem?**
The usual assumption is "a full rebuild and an editor start per mutant". Measured here, a `.cpp` mutant recompiles exactly one file in about 4 s; the editor launch, about 10 s, is the real floor. The median was 13.9 s per mutant over 106 mutants, so a few hundred mutants fit in an hour (`09` S8, P2).

**3. How do you keep the runner from damaging the code it measures?**
- It never touches the target's working tree. It takes a `git archive` of a commit object into a git-ignored folder and uses read-only git commands.
- A self-test proves it: an uncommitted edit stays out of the snapshot, and the target's tree hash, status and file time are unchanged (SC2).

**4. A test run crashes. Is that a kill?**
Yes: a failing test run is a detected fault. 11 of S6's 39 mutants crashed, mostly with `Array.h:1339` bounds asserts from off-by-one loops. Compile failures (stillborn) are excluded from M1 instead, never counted as kills.

**5. What is an equivalent mutant, and how did you handle one?**
It changes the code but not the behaviour. The scheduler's tie-break `A < B` → `A <= B` can differ only when the sort compares an element with itself, which `Algo::IntroSort` never does. It is reviewed in writing and excluded, and the score is reported both before and after the review.

**6. What did the score lead to?**
Three survivors were real boundary gaps. Three tests with exact binary-fraction inputs (0.25 and 0.5 ms) killed them, and M1 went from 92.1% to 100%. The tests were applied as a patch to a snapshot only; the other project was never edited.

**7. Your perf gate missed its targets. What happened?**
- Unchanged runs vary 0.2–0.7 ms within one batch, as much as the smallest injected regression (0.25 ms).
- The gate catches 1.0 ms every time and 0.5 ms 88–94% of the time, but 0.25 ms only 41–56%.
- Its false-positive rate met 5% only against the stored baseline.
- These are reported as measured. The rule was not loosened after seeing the data (`09` S5).

**8. Why not use a t-test or a Mann–Whitney test over all frames?**
Frames are autocorrelated. The frame-level test flagged 47–91% of unchanged runs at a nominal 5%. The run, not the frame, has to be the sampling unit (H5).

**9. Name one surprise from the Windows tooling.**
- `cmd /c start "" /wait /affinity <mask> prog` returns 0 whatever the program returns.
- A batch chain written as `call step || exit /b` exits 0 after a failure when it is started with `cmd /c`.
- Both were reproduced, fixed and re-checked against every past log; no result was a false pass (`09`, Rule 12).

**10. How did you make performance runs comparable?**
- Every timed process is pinned to the P-cores. An E-core placement had shown a 1.6× split in a sibling project.
- A fixed 60 fps step, a deterministic seeded workload, and the capture window opened and closed by CSV events from the game itself.
- Start and end-state hashes prove that every run simulated the same frames.
