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
| 10 | `UCLASS`, `GENERATED_BODY`, `MinimalAPI`, `UE_INLINE_GENERATED_CPP_BY_NAME` | S1 |
| 11 | `UWorldSubsystem` / `UTickableWorldSubsystem` | S1 |
| 12 | CSV profiler macros: `CSV_DEFINE_CATEGORY`, `CSV_EVENT`, `CSV_METADATA`, `CSV_SCOPED_TIMING_STAT` | S1 |
| 13 | `FParse::Param` / `FParse::Value` / `FCommandLine::Get` | S1 |
| 14 | `FPlatformTime::Seconds`, `FPlatformMisc::RequestExit` | S1 |
| 15 | `DEFINE_LOG_CATEGORY_STATIC`, `UE_LOG` | S1 |
| 16 | `GFrameCounter` | S1 (after S2's altitude review) |
| 17 | `UActorComponent::TickComponent`, `PrimaryComponentTick`, tick groups | S2 |
| 18 | `UWorld::SpawnActorDeferred` / `AActor::FinishSpawning` | S2 |
| 19 | `FRandomStream` | S2 |
| 20 | `FCrc::TypeCrc32` | S2 |
| 21 | `ConstructorHelpers::FObjectFinder`, `DirectoriesToAlwaysCook` | S2 |

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
   - The macro `static_assert`s at least one context flag and exactly one filter flag (`AutomationTest.h:4126–4133`).
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
8. **In this project.** 13 tests: six `TestTrust.Sample.*` and seven `TestTrust.Probe.*` (S1), all with `EditorContext | ClientContext | ProductFilter` (the same flags as UE5-UpdateBudget's scheduler suite, the runner's first external target).

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
3. **How it works.** UBT loads the target and module rules, builds or loads a cached makefile, decides which actions are out of date by **timestamps** (`Programs/UnrealBuildTool/Actions/ActionGraph.cs:752–773`), runs UHT only if reflected headers changed (`System/UHTExecution.cs:1013–1030`), compiles and links. `Build.bat` holds a lock file while it runs, `%tmp%\<its own path, mangled>.lock`: per user and per engine install (`Engine/Build/BatchFiles/Build.bat:17–30`).
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

## 10. `UCLASS`, `GENERATED_BODY`, `MinimalAPI` and `UE_INLINE_GENERATED_CPP_BY_NAME`

1. **What it is.** `UCLASS()` marks a class for the reflection system; `GENERATED_BODY()` is where UnrealHeaderTool pastes the generated boilerplate; `MinimalAPI` exports only what the class needs to be used from other modules; `#include UE_INLINE_GENERATED_CPP_BY_NAME(X)` pulls the generated `X.gen.cpp` into our `.cpp`.
2. **Why it exists.** UObjects need run-time type information (class objects, CDOs, garbage-collection data) that C++ doesn't provide; UHT generates it from the markup.
3. **How it works.** UHT parses every header with reflection markup (`01b #2`) and writes `X.generated.h` (which must be the last include of the header) and the `.gen.cpp`. With `MinimalAPI`, the class itself isn't exported; members marked `UE_API` are (`04` §10).
4. **When to use it.** Every class deriving from `UObject` (subsystems, components, actors).
5. **When not to.** Plain data and helpers (`FTTProbeWindow`, `FTTProbeOptions`): no reflection, no GC, cheaper and testable without a world.
6. **Common mistakes.** Including another header after `.generated.h`; forgetting `GENERATED_BODY()`; exporting a whole class with `<MODULE>_API` when only a few members are called from outside.
7. **Example.** `UCLASS(MinimalAPI) class UMySubsystem : public UWorldSubsystem { GENERATED_BODY() public: UE_API virtual void OnWorldBeginPlay(UWorld& W) override; };`
8. **In this project.** `UTTProbeSubsystem` (S1, `MinimalAPI`), `UTTWorkloadSubsystem`, `UTTWorkloadBrainComponent` and `ATTWorkloadAgent` (S2, not exported: nothing outside the game module uses them). Every change to a reflected header re-runs UHT; changes to `TTProbeSubsystem.cpp` don't (the same rule the mutation runner exploits).

## 11. `UWorldSubsystem` and `UTickableWorldSubsystem`

1. **What it is.** A subsystem whose lifetime is one `UWorld`; the tickable variant also derives from `FTickableGameObject` (`Runtime/Engine/Public/Subsystems/WorldSubsystem.h:80`).
2. **Why it exists.** World-level services (managers, directors) without placing an actor in every map.
3. **How it works.** The engine creates one instance per world for every subsystem class whose `DoesSupportWorldType` accepts the world. `OnWorldBeginPlay` runs when play starts. The tickable variant reports `ETickableTickType::Never` until `Initialize` has run, then `Conditional` (`Runtime/Engine/Private/Subsystems/WorldSubsystem.cpp:68–78`); its `Tick` runs on the game thread after `TG_PostPhysics` (`Runtime/Engine/Private/LevelTick.cpp:1821`).
4. **When to use it.** One-per-world logic with no transform and no need for a specific tick group.
5. **When not to.** Per-object state (use a component); logic that must run in a specific tick group (use a custom `FTickFunction`, as UE5-UpdateBudget's scheduler does).
6. **Common mistakes.** Not calling `Super::` in `Initialize`/`Deinitialize`/`Tick` (the tickable base then never ticks, or asserts); accepting editor worlds, so the code runs while maps are edited; forgetting `GetStatId()` (pure virtual).
7. **Example.** `bool DoesSupportWorldType(const EWorldType::Type T) const override { return T == EWorldType::Game || T == EWorldType::PIE; }`
8. **In this project.** `UTTProbeSubsystem`: Game worlds only, and not created at all without `-TTProbe` (it overrides `ShouldCreateSubsystem`, `Runtime/Engine/Public/Subsystems/WorldSubsystem.h:34`, and calls `Super` so the world-type filter still applies); options read in `OnWorldBeginPlay`; the window and the injected cost in `Tick`. `UTTWorkloadSubsystem` (S2): Game and PIE, so the workload can be watched in the editor.

## 12. The CSV profiler: `CSV_DEFINE_CATEGORY`, `CSV_EVENT`, `CSV_METADATA`, `CSV_SCOPED_TIMING_STAT`

1. **What it is.** Macros that write per-frame columns, events and run metadata into a CSV capture (`Runtime/Core/Public/ProfilingDebugging/CsvProfiler.h:50, 56, 85, 120`).
2. **Why it exists.** Frame-by-frame numbers for whole runs, cheap enough to leave on in Development and Test builds.
3. **How it works.** `CSV_DEFINE_CATEGORY(Name, bOnByDefault)` declares a category; `CSV_SCOPED_TIMING_STAT(Cat, Stat)` times its scope into a column named `Cat/<Thread>/Stat` (seen in S1's capture: `TestTrustProbe/GameThread/Injected`); `CSV_EVENT(Cat, Text)` records an event in the frame's `EVENTS` cell and also writes a log line (`CsvProfiler.cpp:4797–4799`); `CSV_EVENT_NOLOG` (`CsvProfiler.h:64`) records it without the log line; `CSV_METADATA(Key, Value)` adds a pair to the trailing metadata row. A capture can start and stop on events: `-csvStartOnEvent=`, `-csvStopOnEvent=` (`Runtime/Core/Private/ProfilingDebugging/CsvProfiler.cpp:5081, 5090`).
4. **When to use it.** Anything a benchmark must read per frame.
5. **When not to.** Per-object stats in a hot loop (UE5-UpdateBudget measured about 50 ns per `CSV_CUSTOM_STAT`); Shipping builds (the profiler is compiled out).
6. **Common mistakes.** A category defined twice in one module (unity builds join files); looking for a timing stat as `Cat/Stat` instead of `Cat/<Thread>/Stat`; expecting the start event inside a capture that it starts (it is on the frame before the first captured row); expecting a column on frames where the stat never ran (the cell is empty); reading metadata keys with their original case (the file lower-cases them).
7. **Example.** `{ CSV_SCOPED_TIMING_STAT(MyCat, Work); DoWork(); }`
8. **In this project.** Category `TestTrustProbe`: events `BenchStart` (`CSV_EVENT`, outside the capture) and `BenchEnd` (`CSV_EVENT_NOLOG`, because its frame is the last measured one) open and close the gate's capture window; column `TestTrustProbe/GameThread/Injected` shows the injected cost; metadata `TTRunTag`, `TTWarmup`, `TTCapture`, `TTInjectMs`, `TTInjectEvery`.

## 13. `FParse::Param`, `FParse::Value` and `FCommandLine::Get`

1. **What it is.** Command-line helpers: `Param` tests for a `-Switch`; `Value` reads `Key=value` into a typed variable (`Runtime/Core/Public/Misc/Parse.h:58, 60, 71, 127`).
2. **Why it exists.** Benchmarks and tools configure a run without editing config files.
3. **How it works.** `Value` searches the string for the key (the key includes the `=`), then parses the token after it; it returns false and leaves the variable alone if the key is missing.
4. **When to use it.** Per-run options of a benchmark or tool.
5. **When not to.** Settings a designer should edit (use `UDeveloperSettings` or config).
6. **Common mistakes.** Forgetting that `Value` is a substring search (`TTWarmup=` would also match `XTTWarmup=`); expecting quotes to group a value with spaces unless the value is quoted on the command line.
7. **Example.** `double Seconds = 5.0; FParse::Value(FCommandLine::Get(), TEXT("TTWarmup="), Seconds);`
8. **In this project.** `FTTProbeOptions::FromCommandLine` takes the string as a parameter, so the test feeds it a fake command line.

## 14. `FPlatformTime::Seconds` and `FPlatformMisc::RequestExit`

1. **What it is.** A high-resolution wall clock (`Runtime/Core/Public/Windows/WindowsPlatformTime.h:23`, QueryPerformanceCounter) and a request to quit the application (`Runtime/Core/Public/GenericPlatform/GenericPlatformMisc.h:1086`).
2. **Why it exists.** Timing that doesn't depend on the game's (possibly fixed) delta; an orderly exit from code.
3. **How it works.** `Seconds()` returns a `double` in seconds since an arbitrary start. `RequestExit(false, CallSite)` asks the engine loop to finish the frame and shut down normally; `true` would force an immediate exit.
4. **When to use it.** Measuring real elapsed time; ending a scripted run.
5. **When not to.** Simulation timing (use the world's delta, which is deterministic under `-deterministic`); forcing an exit while files are still being written.
6. **Common mistakes.** Mixing world time and wall time; exiting on the same frame as the last CSV event, before the profiler has written its file.
7. **Example.** `const double T0 = FPlatformTime::Seconds(); Work(); const double Ms = (FPlatformTime::Seconds() - T0) * 1000.0;`
8. **In this project.** `FTTInjectionSchedule::Spin` busy-waits on `Seconds()`; the probe calls `RequestExit(false, …)` three frames after `BenchEnd`.

## 15. `DEFINE_LOG_CATEGORY_STATIC` and `UE_LOG`

1. **What it is.** A log category visible in one `.cpp` file, and the logging macro.
2. **Why it exists.** Logs that can be filtered by category and verbosity.
3. **How it works.** `DEFINE_LOG_CATEGORY_STATIC(LogX, Log, All)` declares and defines the category with a default verbosity (`Log`) and a compile-time maximum (`All`). `UE_LOG(LogX, Display, TEXT("…"), args)` formats printf-style.
4. **When to use it.** Messages tools parse, and diagnostics.
5. **When not to.** Inside hot per-frame loops (formatting costs time); `Warning` or `Error` for normal events, because the smoke checks count them.
6. **Common mistakes.** `%s` with an `FString` instead of `*MyString`; a `Warning` that fires every run and hides real ones.
7. **Example.** `UE_LOG(LogTTProbe, Display, TEXT("BenchStart on frame %lld"), FrameIndex);`
8. **In this project.** `LogTTProbe`: `Probe active…`, `BenchStart on frame…`, `BenchEnd on frame…`; `LogTTWorkload`: `Spawned N agents…; start-position hash…`, `End-state hash…`. All at `Display`; `run_checks.py` and `run_bench.py` read them back.

## 16. `GFrameCounter`

1. **What it is.** The engine's frame number, a `uint64` (`Runtime/Core/Public/CoreGlobals.h:532`).
2. **Why it exists.** One frame index that every system on the game thread agrees on.
3. **How it works.** `FEngineLoop::Tick` adds 1 once per frame (`Runtime/Launch/Private/LaunchEngineLoop.cpp:6131`), after the engine and every world have ticked (`GEngine->Tick` at `:5859`), so it has the same value in every tick function of one frame.
4. **When to use it.** "Has a frame passed since X?" across objects whose tick order isn't fixed.
5. **When not to.** Time (frames aren't seconds); render-thread code (it has its own counter).
6. **Common mistakes.** Counting frames with a per-object counter that one object increments in its own tick: another object sees the old or the new value depending on tick order.
7. **Example.** `bool bLater = GFrameCounter > RecordedFrame;`
8. **In this project.** `UTTProbeSubsystem` records it on the `BenchEnd` frame; `IsCaptureDone()` is true only on later frames, whatever order the probe and the workload tick in.

## 17. `UActorComponent::TickComponent`, `PrimaryComponentTick` and tick groups

1. **What it is.** A component's per-frame function (`Runtime/Engine/Classes/Components/ActorComponent.h:976`) and its tick settings (`ActorComponent.h:177`): whether it can tick (`bCanEverTick`, `Runtime/Engine/Classes/Engine/EngineBaseTypes.h:213`) and in which group (`TickGroup`, `EngineBaseTypes.h:196`; groups from `:83`).
2. **Why it exists.** Per-object behaviour that the engine schedules, orders and can disable per object.
3. **How it works.** Every registered tick function in a group runs on the game thread before the next group starts; `TG_PrePhysics` runs before the physics step, `TG_PostPhysics` after it. A component ticks only if `bCanEverTick` was set in its constructor.
4. **When to use it.** Per-object logic that must run every frame.
5. **When not to.** Logic that can be event-driven or run less often; thousands of objects whose total cost needs a budget (UE5-UpdateBudget's scheduler is the alternative).
6. **Common mistakes.** Setting `bCanEverTick` after construction (too late); forgetting `Super::TickComponent`; assuming an order between objects in the same group (there is none unless prerequisites are added).
7. **Example.** `PrimaryComponentTick.bCanEverTick = true; PrimaryComponentTick.TickGroup = TG_PrePhysics;`
8. **In this project.** `UTTWorkloadBrainComponent` (S2): one tick per agent in `TG_PrePhysics`; the actor itself has `PrimaryActorTick.bCanEverTick = false`.

## 18. `UWorld::SpawnActorDeferred` and `AActor::FinishSpawning`

1. **What it is.** A spawn split in two: create the actor (`Runtime/Engine/Classes/Engine/World.h:3851`), then finish it (`Runtime/Engine/Classes/GameFramework/Actor.h:3117`).
2. **Why it exists.** To set properties on an actor before its construction script and `BeginPlay` run.
3. **How it works.** `SpawnActorDeferred` returns the actor with its components created but not yet finished; `FinishSpawning(Transform)` runs the rest of the spawn, including `BeginPlay` if the world is already playing.
4. **When to use it.** When `BeginPlay` (or the first tick) must already see configured values.
5. **When not to.** When nothing needs setting first: `SpawnActor` is one call.
6. **Common mistakes.** Forgetting `FinishSpawning` (the actor never begins play); passing a different transform to the two calls without meaning to.
7. **Example.** `AMyActor* A = World.SpawnActorDeferred<AMyActor>(AMyActor::StaticClass(), T); A->Configure(...); A->FinishSpawning(T);`
8. **In this project.** `UTTWorkloadSubsystem::SpawnAgents`: `InitPatrol` and `SetComputeIterations` between the two calls, then `FinishSpawning` at the patrol's time-0 position.

## 19. `FRandomStream`

1. **What it is.** A seeded pseudo-random generator (`Runtime/Core/Public/Math/RandomStream.h:19`), a linear congruential generator (`:364`).
2. **Why it exists.** Repeatable randomness: the same seed gives the same sequence everywhere.
3. **How it works.** Each call advances a 32-bit seed (`Seed * 196314165 + 907633515`) and maps it to the requested range; the stream's state is only its seed.
4. **When to use it.** Procedural layouts, tests and benchmarks that must be identical run to run.
5. **When not to.** Security or anything that needs good statistical quality.
6. **Common mistakes.** Using `FMath::FRand()` (global, unseeded) where repeatability matters; drawing in a different order between runs (the values then differ).
7. **Example.** `FRandomStream R(1); const double X = R.FRandRange(-100.0, 100.0);`
8. **In this project.** The workload's grid jitter and patrol phases, from `-TTSeed=`.

## 20. `FCrc::TypeCrc32`

1. **What it is.** A CRC-32 over the bytes of a value (`Runtime/Core/Public/Misc/Crc.h:36`).
2. **Why it exists.** A quick fingerprint of data.
3. **How it works.** `MemCrc32(&Data, sizeof(T), CRC)`: the previous CRC is the starting value, so calls chain into one CRC over all values.
4. **When to use it.** Comparing state between runs or machines where any bit difference matters.
5. **When not to.** Types with padding bytes or pointers (their bytes are not the value); new code that needs a good hash (the header itself recommends xxhash).
6. **Common mistakes.** Hashing an `FVector` of doubles when the comparison should tolerate rounding; hashing a struct with padding.
7. **Example.** `uint32 H = 0; for (const FVector& P : Points) { H = FCrc::TypeCrc32(FVector3f(P), H); }`
8. **In this project.** The workload's start-position and end-state hashes: bit-equal hashes across runs are the determinism check (`09` S2).

## 21. `ConstructorHelpers::FObjectFinder` and `DirectoriesToAlwaysCook`

1. **What it is.** A helper that loads an asset by path inside a `UObject` constructor (`Runtime/CoreUObject/Public/UObject/ConstructorHelpers.h:77`), and a project setting that cooks a whole content folder.
2. **Why it exists.** Default assets for C++ classes without a Blueprint.
3. **How it works.** The finder loads the object when the constructor runs (for the class default object, at startup). In a packaged build the asset must have been cooked; engine content is cooked only if something references it or a cook rule includes it.
4. **When to use it.** Small engine defaults, such as a basic shape.
5. **When not to.** Outside constructors (a fatal error, `Runtime/CoreUObject/Private/UObject/UObjectGlobals.cpp:4974`); game content that designers should choose (use a property).
6. **Common mistakes.** A non-`static` finder (the lookup repeats per object); a missing cook rule, so the packaged game has an invisible mesh.
7. **Example.** `static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));`
8. **In this project.** `ATTWorkloadAgent`'s cube; `Config\DefaultGame.ini` has `+DirectoriesToAlwaysCook=(Path="/Engine/BasicShapes")`.
