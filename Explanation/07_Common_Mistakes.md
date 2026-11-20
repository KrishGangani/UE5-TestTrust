# 07 · Common Mistakes: TestTrust

**Rule:** for every module, the mistakes that are easy to make here, **how to spot them, how to prevent them and how to debug them**. Mistakes **actually caught in this project** are marked ⚠ caught; they make the best interview stories. (Current to Phase 4.)

---

## Mutation runner (Python, `Tools\`)

| Mistake | How to spot it | How to prevent it | How to debug it |
|---|---|---|---|
| ⚠ caught: **a pinned launch that hides the exit code.** `cmd /c start "" /wait /affinity <MASK> prog` returns 0 even when the program returns 3 or −1 | Every mutant "survives"; a deliberately failing test still gives exit 0 | `cmd /v:on /s /c "start "" /wait /affinity <MASK> prog & exit !errorlevel!"` (`tt_common.pinned`, `01b #14`) | Launch a program that exits 3 through the wrapper and print the return code (how it was found) |
| ⚠ caught: **a path with a space split by the queue.** The queue joins its arguments with spaces, so `D:/UNREAL PORTFOLIO/...` became two arguments | The job fails in 0.1 s: "can't open file 'D:\\UNREAL'" | Pass the whole command as one pre-quoted string (`tt_mutate.py queue` does) | Read the second line of the queue job log: it shows the exact command |
| ⚠ caught: **statement deletion inside a `for` header.** The first lexer treated `I < N;` in `for (…; I < N; ++I)` as a statement | The mutant list for UE5-UpdateBudget's scheduler contained `SDL 'Index < Clients.Num();'` | Statements must start at the bracket depth of their enclosing brace (`_statement_level`) | Run `tt_mutants.py <file>` on real code and read the SDL lines; the self-test now contains a `for` loop |
| ⚠ caught (self-review): **an exception between "apply" and "build" crashed the batch.** If `Mutant.apply()` refused (the file changed since planning), the code went on to classify a build result that was never assigned | A `NameError` traceback in the queue log; the batch stops; later mutants never run | Initialise the build result as "nothing ran" and catch `OSError`/`ValueError` around apply-build-test; the mutant becomes an *error* and is retried once | Edit a pristine file by hand and run a batch: the manifest's `detail` field names the problem |
| ⚠ caught (P4-R): **printing crashed a finished campaign.** The Windows console's cp1252 can't encode `→`, so `print()` raised after the batch had succeeded | `UnicodeEncodeError` in the driver; exit 1 although the queue job was ok | `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`; write files as UTF-8 explicitly | Re-run `report`: it needs no Unreal |
| ⚠ caught (P4-R): **a running batch that already claims why it stopped** | The manifest said "all mutants have a fate" while mutants were still running | Leave the stop reason empty until the loop ends | Watch the manifest during a run (how it was found) |
| Mutating from the working tree | A campaign's results change when the target's author edits a file | Snapshot from a commit object only | The manifest records the full hash; re-plan at the same commit and compare ids |
| Snapshot inside the target repository | `git status` in the target shows new files | `check_destination()` refuses unless the path is outside or ignored | The SC2 self-test |
| The snapshot is a git checkout | Every first mutant of a file rebuilds a whole unity blob, then again on restore | Keep `.git` out of the snapshot's project folder and its parent (`01b #3`) | Compare `compile_actions` per mutant: more than 1–2 means a blob is being rebuilt |
| Faking timestamps after restoring a file | A "restored" build still behaves like the last mutant | Never touch timestamps; accept one recompile (`01b #1`) | Build after restore and check the file is compiled |
| Counting compile failures as kills | The score looks better than the suite is | Stillborn mutants are excluded; M1-naive is reported next to M1 to show the difference | Compare the two numbers in the report |
| Running mutants against a red suite | Every mutant is "killed" and the score is meaningless | The batch refuses unless the unmutated snapshot builds, exits 0 and runs ≥ 1 test with 0 failures | Batch exit code 3, "baseline not green" in the manifest |
| Trusting the exit code alone | A mutant crashes a test half-way, the controller still exits non-zero, but which tests ran is unknown | Also read `index.json` and compare the completed-test count to the baseline | `failed_tests` per mutant in the manifest |
| A substring filter that matches two suites | The baseline test count is higher than the suite's size | Always `StartsWith:` (`01b #5`) | `tests[]` in `index.json` |
| Mutating headers | Every mutant re-runs UHT and recompiles every includer; costs balloon (`01b #2`) | `.cpp` only | `uht_ran` and `compile_actions` in the probe |
| Reusing one editor process for several mutants | A test registered by a mutated DLL, or state left by the previous mutant, changes the next result | A fresh process per mutant (`04` §9) | — |
| A mutant that loops forever | The batch never ends | Test timeout max(120 s, 3 × baseline) and a tree kill | The *timeout* fate; the queue's own timeout is the second guard |
| A half-written manifest after a killed batch | JSON decode error on the next batch | Atomic write (`.tmp` then `os.replace`) | — |
| ⚠ caught (S7): **`git apply` inside another repository's ignored folder.** In a snapshot under `Tools\_work\`, `git apply` resolved the paths against this repository and changed nothing, with exit 0 | An "after" campaign whose score equals the "before" score | `GIT_CEILING_DIRECTORIES` = the snapshot's parent, and a check that every target changed (`tt_mutate.apply_patch`) | `tt_mutate.py selftest` (`patch_selftest`); hash a target before and after |
| ⚠ caught (code review, S7): **a patch whose line endings differ from the files.** `git diff` ran inside this repository, whose `* text=auto` turned the CRLF test file into an LF patch | `git apply` reports "patch does not apply" | Apply with `--ignore-whitespace`; keep the patch's bytes with `*.patch -text`, so its recorded SHA-256 stays valid | Count CRLF and LF in the patch and in the target |
| ⚠ caught (code review, S7): **an inherited `GIT_DIR`.** A git hook or wrapper that sets it redirects every git call of the runner to that repository | A snapshot or patch from the wrong repository | `main()` clears `GIT_DIR` and `GIT_WORK_TREE` | The self-test with `GIT_DIR` set |

## Sample module (`TestTrustSample`)

| Mistake | How to spot it | How to prevent it | How to debug it |
|---|---|---|---|
| "Fixing" the deliberate gap before the smoke test | The boundary mutant is killed, and the smoke test no longer proves the runner can report a survivor | The gap is documented in the test file's header comment | `09` P4-R lists the expected survivor |
| `EditorContext` only on a test | The test is missing from `-game` runs | `EditorContext | ClientContext` | `Automation List` in each mode |
| Exact float comparison | A rounding difference fails the test | `TestEqual` with its float tolerance | The failure message prints both values |
| Putting rule constants in the `.cpp` and copying them into tests | A constant changes in one place only | One `static constexpr` in the header, used by both | — |

## Build and project files

| Mistake | How to spot it | How to prevent it |
|---|---|---|
| A module missing from `ExtraModuleNames` | Its tests are never found; the runner's baseline has 0 tests and refuses | List every project module in both targets |
| A public dependency that only a `.cpp` needs | Wider rebuilds for every mutant | Private unless a public header needs it |
| LF line endings in `.bat` files | `call :step` can fail to find its label | `.gitattributes` forces CRLF for `.bat`; files written on this machine are converted (Phase 4). ⚠ caught: an in-place `sed` edit silently turned a CRLF file back into LF; `file Tools\*.bat` is now part of the audit |
| No `DefaultInput.ini` with Enhanced Input enabled | `LogEnhancedInput: Warning: ... does not have a valid PlayerInput object` on every map load (grep the smoke log for `LogEnhancedInput`) | The two class lines from Epic's template (`05` A7) |
| Leaving the engine's `AndroidFileServer` plugin enabled | After the first editor run, `DefaultEngine.ini` has a new block with a random `SecurityToken` (`git diff` shows it) | `{ "Name": "AndroidFileServer", "Enabled": false }` in the `.uproject`; delete the block if it is already there |
| Copying a command-line switch that nothing reads (`-ExitAfterSeconds=0`) | The run "works", for another reason (`quit`) | Grep the engine source for a switch before relying on it |
| Expecting the Test configuration on the launcher engine | "Targets cannot be built in the Test configuration with this engine distribution" | Packaged Development for the gate; Development editor for mutants |
