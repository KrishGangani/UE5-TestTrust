# 06 · Unreal APIs And Macros: TestTrust

**Rule:**
- Only APIs this project **actually uses** appear here, each in the same step it enters the code.
- Each entry follows the 8-point format: what it is · why it exists · how it works · when to use it · when not to · common mistakes · a small example · how we use it.
- Verified against UE **5.8.4** source; file references are relative to `Engine/Source/` unless they start with `Engine/`.

| # | API | First used in |
|---|---|---|
| 1 | `IMPLEMENT_PRIMARY_GAME_MODULE` / `IMPLEMENT_MODULE`, `FDefaultGameModuleImpl` / `FDefaultModuleImpl` | Phase 4 |
| 2 | `ModuleRules` and `TargetRules` (`.Build.cs`, `.Target.cs`) | Phase 4 |
| 3 | `IMPLEMENT_SIMPLE_AUTOMATION_TEST` and `EAutomationTestFlags` | Phase 4 |
| 4 | `TestEqual` / `TestTrue` / `TestFalse` | Phase 4 |
| 5 | `WITH_DEV_AUTOMATION_TESTS` | Phase 4 |
| 6 | The `Automation` console command: `RunTests`, `StartsWith:`, `Quit` | Phase 4 |
| 7 | `-ReportExportPath=` and `index.json` | Phase 4 |
| 8 | UnrealBuildTool from the command line: `Build.bat`, `-WaitMutex`, `-Log=` | Phase 2 / 4 |
| 9 | `FVector::DistSquared` | Phase 4 |

---

## 1. `IMPLEMENT_PRIMARY_GAME_MODULE` / `IMPLEMENT_MODULE`

1. **What it is.** Macros that generate a module's entry point (`Runtime/Core/Public/Modules/ModuleManager.h:946, 955, 1100–1136`).
2. **Why it exists.** The engine loads code as modules: DLLs in editor builds, static code in packaged builds. Each needs a standard entry point so the module manager can create it and call `StartupModule()`/`ShutdownModule()`.
3. **How it works.** In a modular build it exports an `InitializeModule` function that returns an instance of the named class; in a monolithic build it registers a static initializer. The *primary* game variant also defines the project-name globals packaged builds need.
4. **When to use it.** Exactly one per module; at least one primary game module per project.
5. **When not to.** Never twice in one module (duplicate symbols). Plugins use `IMPLEMENT_MODULE`.
6. **Common mistakes.** The module name argument doesn't match `Build.cs` and the descriptor ("module not found"); writing an empty custom module class when `FDefaultModuleImpl` would do.
7. **Example.** `IMPLEMENT_MODULE(FDefaultModuleImpl, MyModule);`
8. **In this project.** `TestTrustModule.cpp` (primary), `TestTrustSampleModule.cpp` and `TestTrustProbeModule.cpp` (`IMPLEMENT_MODULE`), all with the default classes (`ModuleManager.h:884, 892`): none needs start-up logic.

## 2. `ModuleRules` and `TargetRules`

1. **What it is.** C# classes in `<Module>.Build.cs` and `<Target>.Target.cs` that tell UnrealBuildTool what to compile and how.
2. **Why it exists.** A UE project is many modules and several executables (game, editor). Each module declares its dependencies; each target declares its type and settings.
3. **How it works.** UBT compiles these C# files, constructs the rules objects and derives include paths, link inputs and the action graph. A target of `TargetType.Editor` builds one DLL per module; `TargetType.Game` builds one monolithic executable.
4. **When to use which dependency list.** `PublicDependencyModuleNames` only if a *public header* of yours includes that module; otherwise `PrivateDependencyModuleNames`.
5. **When not to.** Don't add dependencies "just in case": each one widens what a change rebuilds, which for mutation testing is directly a cost.
6. **Common mistakes.** Making everything public; a module name that differs from its class name; forgetting a module in `ExtraModuleNames`, so it is never built.
7. **Example.** `PrivateDependencyModuleNames.Add("TestTrustProbe");`
8. **In this project.** Two targets (`TestTrust`, `TestTrustEditor`) with `BuildSettingsVersion.V7` and `EngineIncludeOrderVersion.Unreal5_8`, both listing `TestTrust` and `TestTrustSample`. The runner builds the **editor** target, so a mutant relinks only the mutated module's DLL (`01b #8`). `TestTrustSample` depends on `Core` only, which keeps each mutant's compile small.

## 3. `IMPLEMENT_SIMPLE_AUTOMATION_TEST` and `EAutomationTestFlags`

1. **What it is.** A macro that declares a test class deriving `FAutomationTestBase` and a static instance that registers it by name (`Runtime/Core/Public/Misc/AutomationTest.h:4297–4302`). The flags say where the test may run and which filter group it belongs to (`AutomationTest.h:93–139`).
2. **Why it exists.** Tests must be discoverable by name from the editor, the Session Frontend, the command line and Gauntlet, without a central list anyone has to maintain.
3. **How it works.**
   - The static instance's constructor registers the test when the module loads (`04` §9).
   - At run time the framework keeps only tests whose **context** flags match the running application (editor, client, server, commandlet; `Runtime/Core/Private/Misc/AutomationTest.cpp:805–830`) and whose **filter** flag matches the request.
   - The macro `static_assert`s at least one context flag and exactly one filter flag (`AutomationTest.h:4127–4133`).
4. **When to use it.** Small, synchronous tests: one function, no frames to wait for. For fixtures and per-test reset, CQTest; for "given/when/then" structure, Spec; for tests that need frames to pass, latent commands or functional tests.
5. **When not to.** Anything that must wait for the world to tick; tests sharing state through statics (registration order is not a contract).
6. **Common mistakes.**
   - Only `EditorContext`: the test silently doesn't exist in `-game` or a packaged Development build.
   - Two filter flags: compile error from the `static_assert`.
   - Returning `false` to signal failure but never calling `Test…` or `AddError`: the description of what failed is lost.
   - A name that is a prefix of another suite's name, so a plain substring filter runs both (`§6`).
7. **Example.**
   ```cpp
   IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMyTest, "Game.Rules.Damage", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
   bool FMyTest::RunTest(const FString& Parameters) { TestEqual(TEXT("damage"), Damage(10, 3), 7); return true; }
   ```
8. **In this project.** Six tests named `TestTrust.Sample.*` with `EditorContext | ClientContext | ProductFilter` (the same flags as UE5-UpdateBudget's scheduler suite, the runner's first external target).

## 4. `TestEqual` / `TestTrue` / `TestFalse`

1. **What it is.** `FAutomationTestBase` members that record a failure with a description when the check fails (`AutomationTest.h:1985` for `int32`, `:1988` for `float` with a tolerance, `:2367`, `:2603`).
2. **Why it exists.** A failing check should report *what* failed and keep running the rest of the test, so one run shows every broken expectation.
3. **How it works.** On mismatch, an error with the description, the actual and the expected value is added to the current test; the test is marked failed at the end. The return value tells you whether the check passed (the `UTEST_*` macros use it to `return false` early).
4. **When to use it.** Every expectation. Prefer `TestEqual` over `TestTrue(A == B)`: it prints both values.
5. **When not to.** When a failed check would make the next line crash (an out-of-range index): use `UTEST_*`, which returns early.
6. **Common mistakes.** Comparing floats with `TestTrue(A == B)` (no tolerance); forgetting that `TestEqual` for `float` uses `UE_KINDA_SMALL_NUMBER` by default, which is too strict for large values.
7. **Example.** `TestEqual(TEXT("cooldown"), TickCooldown(1.0f, 0.25f), 0.75f);`
8. **In this project.** Every sample test. For mutation testing the description matters: the runner stores the names of failed tests per mutant, so a report shows *which* test killed each mutant.

## 5. `WITH_DEV_AUTOMATION_TESTS`

1. **What it is.** A preprocessor macro UBT defines to 1 or 0 per build (`Programs/UnrealBuildTool/Configuration/UEBuildTarget.cs:6315–6331`).
2. **Why it exists.** Tests must not ship: they cost size and start-up time and can expose internals.
3. **How it works.** 1 for every configuration except Test and Shipping (unless a target forces it); `WITH_AUTOMATION_TESTS` combines it with the perf-test variant (`AutomationTest.h:63–64`).
4. **When to use it.** Wrap every test file in `#if WITH_DEV_AUTOMATION_TESTS`.
5. **When not to.** Don't wrap production code in it: behaviour would differ between configurations.
6. **Common mistakes.** Expecting tests in a Test-configuration build (they aren't compiled there; and the launcher engine can't build Test at all).
7. **Example.** `#if WITH_DEV_AUTOMATION_TESTS … #endif`
8. **In this project.** `TTSampleRulesTests.cpp`. The runner's mutants are built in Development, where the tests exist.

## 6. The `Automation` console command

1. **What it is.** A console command handled by `FAutomationExecCmd` in the AutomationController module (`Developer/AutomationController/Private/AutomationCommandline.cpp:566–810`).
2. **Why it exists.** To run tests without a UI: from `-ExecCmds`, a console, or a build machine.
3. **How it works.**
   - The argument is split on `;` into sub-commands (`:581–582`), so `Automation RunTests X;Quit` is two commands. `-ExecCmds` itself splits on commas (`Runtime/Engine/Private/ParseExecCommands.cpp:20–35`).
   - `RunTests <filter>` queues one run (`:610–627`). The filter is split on `+`; `StartsWith:Prefix` matches from the start (a `.` is appended); `Group:Name` uses an ini group; anything else is a **substring** match (`:134–160`).
   - `Quit` waits for the run, sets `GIsCriticalError` if any report has errors, logs `**** TEST COMPLETE. EXIT CODE: %d ****` and exits with **-1 on failure, 0 on success** (`:494–504`).
   - Before it looks for test workers, the controller counts down a fixed `DefaultDelayTimer = 5.0f` (`:243–254, 871`). `Now` sets that delay to 0 (`:606–609`), so `Automation Now;RunTests X;Quit` starts at once.
4. **When to use it.** Every scripted test run.
5. **When not to.** `-testexit=` alone: it exits without a failure code (`Runtime/Launch/Private/LaunchEngineLoop.cpp:1919–1931, 5590–5594`).
6. **Common mistakes.** A substring filter that also matches another suite; quoting `-ExecCmds` so that only its first word arrives; checking only the exit code and missing that fewer tests ran than expected.
7. **Example.** `UnrealEditor-Cmd.exe Game.uproject -nullrhi -unattended -ExecCmds="Automation RunTests StartsWith:Game.Rules;Quit"`
8. **In this project.** `run_tests.bat`, the probe, and every mutant run (`tt_mutate.py run_tests`), always with `StartsWith:`. The runner prefixes `Now`: the probe measured the 5 s wait in every launch (`09` P2), about a third of a test launch.

## 7. `-ReportExportPath=` and `index.json`

1. **What it is.** A command-line option that makes the automation controller write a JSON summary of the run (`Developer/AutomationController/Private/AutomationControllerManager.cpp:213–233, 746`).
2. **Why it exists.** Machines need results, not log text.
3. **How it works.** At the end of the run, `FAutomatedTestPassResults` is serialised with `FJsonObjectConverter` to `<path>/index.json` (`:725–730`): `succeeded`, `succeededWithWarnings`, `failed`, `notRun`, `inProcess`, `totalDuration`, and `tests[]` with `fullTestPath`, `state` (`NotRun`, `InProcess`, `Fail`, `Success`, `Skipped`), `duration` (`Private/AutomationControllerManager.h:32–48, 134–153`; `Runtime/AutomationTest/Public/AutomationState.h:14–21`). The old name `-ReportOutputPath=` still works but logs a warning (`:213–219`).
4. **When to use it.** Whenever a script must know which tests ran and which failed.
5. **When not to.** As the only signal: a crash before the end writes no report, which is itself information.
6. **Common mistakes.** Reading a stale `index.json` from an earlier run (the runner deletes the folder first); trusting it without comparing the test count to an expected value.
7. **Example.** `-ReportExportPath="D:\Reports\run1"` → `D:\Reports\run1\index.json`.
8. **In this project.** The runner reads it for every mutant: *killed* if anything failed or fewer tests completed than in the baseline; *crash* if it is missing.

## 8. UnrealBuildTool from the command line

1. **What it is.** `Engine/Build/BatchFiles/Build.bat <Target> <Platform> <Configuration> -Project=<uproject> [options]`, which runs `UnrealBuildTool.dll` with the bundled .NET.
2. **Why it exists.** Reproducible builds without an IDE, scriptable by a runner.
3. **How it works.** UBT loads the target and module rules, builds or loads a cached makefile, decides which actions are out of date by **timestamps** (`Programs/UnrealBuildTool/Actions/ActionGraph.cs:752–773`), runs UHT only if reflected headers changed (`System/UHTExecution.cs:1013–1030`), compiles and links. `Build.bat` holds a machine-wide lock file while it runs (`Engine/Build/BatchFiles/Build.bat:17–30`).
4. **When to use it.** Every build in this project, always through the machine queue.
5. **When not to.** With an editor of the same project running: Live Coding or a loaded DLL can block the link.
6. **Common mistakes.** Faking timestamps to "skip" a rebuild (links stale objects, `01b #1`); putting a mutation target under git so that adaptive unity keeps changing its working set (`01b #3`).
7. **Example.** `Build.bat MyGameEditor Win64 Development -Project="D:\MyGame\MyGame.uproject" -WaitMutex -NoHotReloadFromIDE "-Log=D:\logs\ubt.txt"`
8. **In this project.** `build.bat`, the probe and the runner. `-WaitMutex` waits for UBT's mutex; `-NoHotReloadFromIDE` avoids patching a running editor; `-Log=` gives each build its own debug log (`Programs/UnrealBuildTool/GlobalOptions.cs:30–34`), where UHT and the working set are reported.

## 9. `FVector::DistSquared`

1. **What it is.** A static function returning the squared distance between two vectors (`Runtime/Core/Public/Math/Vector.h:1041`).
2. **Why it exists.** A square root is not free, and comparisons don't need it: for non-negative values, a ≤ b exactly when a² ≤ b².
3. **How it works.** Sum of squared component differences.
4. **When to use it.** Range checks and nearest-of comparisons.
5. **When not to.** When you need the actual distance (UI, falloff curves).
6. **Common mistakes.** Comparing a squared distance with an unsquared range.
7. **Example.** `FVector::DistSquared(A, B) <= Range * Range`
8. **In this project.** `FTTSampleRules::IsInRange`, where its `<=` is the deliberately unprotected boundary.
