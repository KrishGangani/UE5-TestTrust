> **Raw Phase 2 research notes (A_test_frameworks), UE 5.8.4, 2026-11-21.** Working notes, kept as an evidence trail. Every claim cites a `File:line` (paths relative to `Engine/`) or a URL. **The claims the design depends on are restated in [../01b_Research_Findings.md](../01b_Research_Findings.md); treat anything here that isn't restated there as unverified.**

# A. Test frameworks and command-line automation

## A1. What a test is, in every framework

| Framework | How a test is declared | What it really is | Evidence |
|---|---|---|---|
| Simple / complex automation tests | `IMPLEMENT_SIMPLE_AUTOMATION_TEST(TClass, PrettyName, TFlags)`; `IMPLEMENT_COMPLEX_AUTOMATION_TEST` | A class deriving `FAutomationTestBase`, plus a static instance that registers it by name | `Source/Runtime/Core/Public/Misc/AutomationTest.h:4297–4302, 4303` |
| Latent commands | `DEFINE_LATENT_AUTOMATION_COMMAND(Name)`, `ADD_LATENT_AUTOMATION_COMMAND` | Work spread over frames | `AutomationTest.h:3796, 4087` |
| Automation Spec | `BEGIN_DEFINE_SPEC` … `END_DEFINE_SPEC`, `Describe`, `It`, `BeforeEach`, `AfterEach` | `FAutomationSpecBase : public FAutomationTestBase` | `AutomationTest.h:4346, 2899–2900, 2757, 2789, 2821, 2826` |
| CQTest | `TEST_CLASS`, `TEST_METHOD`, `BEFORE_EACH`, `AFTER_EACH`, `ASSERT_THAT`; default flags = every application context + `ProductFilter` | `TTestRunner : public FAutomationTestBase`; README: "Extension of the Unreal Engine FAutomationTestBase" | `Source/Developer/CQTest/Public/CQTest.h:69, 147, 291, 305, 329, 333–334`; `Source/Developer/CQTest/README.md:3` |
| Functional tests | `AFunctionalTest` actors placed in a map | Registered under `Project.Functional Tests.<map>.<actor label>` | `Source/Developer/FunctionalTesting/Classes/FunctionalTest.h:249`; `Private/FunctionalTest.cpp:733` |

**Consequence:** every framework ends up as a named `FAutomationTestBase` that `Automation RunTests` can select. One runner works for all of them.

## A2. Which builds contain the tests

- `WITH_AUTOMATION_TESTS = WITH_DEV_AUTOMATION_TESTS || WITH_PERF_AUTOMATION_TESTS` (`AutomationTest.h:63–64`).
- UBT sets `WITH_DEV_AUTOMATION_TESTS=1` for every configuration except Test and Shipping (`Source/Programs/UnrealBuildTool/Configuration/UEBuildTarget.cs:6315–6331`). The launcher editor is Development, so tests exist there.
- The macros only register tests when `WITH_AUTOMATION_WORKER` is set, which is `!UE_BUILD_SHIPPING` (`Source/Runtime/Core/Public/Misc/Build.h:126–127`; `AutomationTest.h:4296`).

## A3. Contexts: which tests run where

`FAutomationTestFramework` builds the set of allowed contexts from the running application (`Source/Runtime/Core/Private/Misc/AutomationTest.cpp:805–830`):
- editor (not a commandlet) → `EditorContext`;
- not editor, not dedicated server → `ClientContext` (so `UnrealEditor-Cmd -game` and packaged games);
- commandlet → `CommandletContext`.
`-nullrhi` removes `NonNullRHI` tests (`:841–844`); `-unattended` removes `RequiresUser` tests (`:847–849`).

**Consequence:** a test flagged `EditorContext` only does not run in `-game`. UE5-UpdateBudget's scheduler tests use `EditorContext | ClientContext | ProductFilter`, so both modes work.

## A4. Running tests from the command line

- `-ExecCmds="a, b"` is split on commas (`Source/Runtime/Engine/Private/ParseExecCommands.cpp:20–35`).
- The `Automation` command splits its own argument on `;` (`Source/Developer/AutomationController/Private/AutomationCommandline.cpp:581–582`). So `-ExecCmds="Automation RunTests <filter>;Quit"`.
- `RunTests` / `RunTest` queue a command-line run (`:610–627`). The filter is split on `+`; `StartsWith:X` matches from the start and appends a `.` if missing; `Group:X` expands an ini group; anything else is a **substring** match (`:134–160`).
- When `Quit` is processed: if any report has errors, `GIsCriticalError` is set; it logs `**** TEST COMPLETE. EXIT CODE: %d ****` and calls `RequestExitWithStatus(..., GIsCriticalError ? -1 : 0)` (`:494–504`). **The process exit code is the pass/fail signal.**
- `...Automation Test Queue Empty %d tests performed.` is logged when the queue drains (`:122`).
- `-testexit=` (an output device that requests exit when a phrase is logged) exists, but it calls `RequestExit(true, ...)` without a failure code (`Source/Runtime/Launch/Private/LaunchEngineLoop.cpp:1919–1931, 5590–5594`). Not used: `Quit` already exits with the right code.

## A5. The JSON report

- `-ReportExportPath=<dir>` (the old `-ReportOutputPath=` still works with a warning) (`Source/Developer/AutomationController/Private/AutomationControllerManager.cpp:213–233`).
- The report is `<dir>/index.json` (`:369, 746`), serialised from `FAutomatedTestPassResults` with `FJsonObjectConverter` (`:725–730`).
- Fields: `succeeded`, `succeededWithWarnings`, `failed`, `notRun`, `inProcess`, `totalDuration`, and `tests[]` with `testDisplayName`, `fullTestPath`, `state`, `duration` (`Private/AutomationControllerManager.h:32–48, 134–153`). JSON keys start lower-case because `FJsonObjectConverter::StandardizeCase` lowers the first letter (`Source/Runtime/JsonUtilities/Private/JsonObjectConverter.cpp:26–34`) **[inferred from the function name and use; the body was not traced]**.
- `state` values: `NotRun`, `InProcess`, `Fail`, `Success`, `Skipped` (the `EAutomationState` enum, `Source/Runtime/AutomationTest/Public/AutomationState.h:14–21`).

## A6. Gauntlet

- Plugin `Gauntlet`: `IsBetaVersion: true`, `EnabledByDefault: false` (`Plugins/Experimental/Gauntlet/Gauntlet.uplugin:13–15`). In-game controller `UGauntletTestController : public UObject` (`Plugins/Experimental/Gauntlet/Source/Gauntlet/Public/GauntletTestController.h:23`).
- UAT side: `UnrealTestNode<TConfigClass>` (`Source/Programs/AutomationTool/Gauntlet/Unreal/Base/Gauntlet.UnrealTestNode.cs:30`), `RunUnreal` (`Gauntlet/Unreal/RunUnreal.cs:18, 70`).
- Telemetry rows carry a `Baseline` value (`Gauntlet/Framework/Base/Gauntlet.TestReport.cs:129–137, 275–282`) and can be written to a SQL table with a `baseline` column (`Gauntlet/Unreal/Config/Gauntlet.EpicConfig.cs:68, 89, 177`). A grep of the Gauntlet folder for `regression` and `baseline` finds only these: it **stores** a baseline next to a measurement, and nothing compares them **[inferred from grep]**.

## A7. Coverage

- UBT has `-CodeCoverage` (`bCodeCoverage`) (`Source/Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:2351–2356`). On Windows it adds flags **only** `if (Target.WindowsPlatform.Compiler.IsClang())` (`Platform/Windows/VCToolChain.cs:885–893`, link side `:1999–2005`). With MSVC (this machine's toolchain) it adds nothing.
- VS 2022 on this machine also ships clang-cl 19.1.5 with `llvm-cov` and `llvm-profdata` (`C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\bin`); UE 5.8 accepts Clang ≥ 18.1.8 (`Engine/Config/Windows/Windows_SDK.json:14`). Whether a launcher-engine project can build its modules with `-Compiler=Clang` against MSVC-built engine binaries was **not tested** **[unverified]**. Recorded as a growth path, not used.

## A8. Low-Level Tests

`LowLevelTestsRunner` exists ([research/03](../Research/03_existing_solutions_gap_analysis.md) §7.1). They build as separate test executables. Whether that works with a launcher engine was not checked **[unverified]**; out of scope (gameplay code here is tested through the automation framework, like UE5-UpdateBudget's suite).
