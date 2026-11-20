# 05 · Line By Line Code Explanation: TestTrust

**Rule:** every file that exists in `TestTrust\` and `Tools\` is explained here, in the same step it is written. Sections follow the build order in [03_Implementation_Roadmap.md](03_Implementation_Roadmap.md). C++ and build files are explained line by line; Python is explained block by block (each function's job, its inputs and the decisions inside it).

| Part | Step | Files |
|---|---|---|
| A | Phase 4, F1 (project and modules) | `.uproject`, two `Target.cs`, three `Build.cs`, three module `.cpp`, `.uplugin`, three `.ini` |
| B | Phase 4, F2 (sample rules and tests) | `TTSampleRules.h`, `TTSampleRules.cpp`, `TTSampleRulesTests.cpp` |
| C | Phase 4, F3 (scripts) | `Tools\*.bat` |
| D | Phase 2 and Phase 4, F4 (Python) | `probe_build_cost.py`, `tt_common.py`, `tt_mutants.py`, `tt_mutate.py`, `mutation\sample.json`, `mutation\sample_review.json` |

---

## Part A · Project and modules (Phase 4, F1)

### A1. `TestTrust.uproject`

```json
{
	"FileVersion": 3,
	"EngineAssociation": "5.8",
	"Description": "P03 TestTrust: ...",
	"Modules": [
		{ "Name": "TestTrust",       "Type": "Runtime", "LoadingPhase": "Default" },
		{ "Name": "TestTrustSample", "Type": "Runtime", "LoadingPhase": "Default" }
	],
	"Plugins": [ { "Name": "TestTrustProbe", "Enabled": true }, { "Name": "AndroidFileServer", "Enabled": false } ]
}
```

| Line | What it does, and why |
|---|---|
| `"FileVersion": 3` | The descriptor schema version UE 5.8 expects (the same value UE5-UpdateBudget's hand-written project uses, taken from Epic's templates) |
| `"EngineAssociation": "5.8"` | Which installed engine opens the project. A launcher engine is identified by its version string; blank would make the shell ask |
| `"Modules"` | The C++ modules the project owns. UBT builds exactly these plus plugin modules |
| `"TestTrust"` | The primary game module (the workload, Phase 5). Its name must match `Source\TestTrust\` and the class in `TestTrust.Build.cs` |
| `"TestTrustSample"` | The mutation target M-S. A separate module so mutants never rebuild or test the workload (`02` §3). Also `Runtime`, so its tests exist in the editor and in Development games |
| `"Type": "Runtime"` | Built into game and editor targets. *Alternative:* `Editor` for the sample, which would hide it from `-game` runs; `Runtime` keeps both test contexts usable |
| `"LoadingPhase": "Default"` | Loads after engine start-up and before the first world, early enough for automation tests to be registered before `Automation RunTests` looks for them |
| `"Plugins"` / `"TestTrustProbe"` | Enables the project's own plugin explicitly, so the dependency is visible in one place even though the plugin is `EnabledByDefault` |
| `"AndroidFileServer"`, `"Enabled": false` | The engine plugin is `EnabledByDefault` (`Engine/Plugins/Runtime/AndroidFileServer/AndroidFileServer.uplugin:15`), and its editor module (`:25–26`) writes a `[/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings]` block with a random `SecurityToken` into `DefaultEngine.ini` on the first editor run. This project never deploys to Android, and a token must not reach a public repository (portfolio rule, 2026-11-21). Disabling the plugin stops the write at its source |

### A2. `Source\TestTrust.Target.cs` and `TestTrustEditor.Target.cs`

```csharp
using UnrealBuildTool;

public class TestTrustTarget : TargetRules
{
	public TestTrustTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		ExtraModuleNames.AddRange(new string[] { "TestTrust", "TestTrustSample" });
	}
}
```

| Line | What it does, and why |
|---|---|
| `using UnrealBuildTool;` | Target files are C#, compiled by UBT itself. This brings `TargetRules` and friends into scope |
| `class TestTrustTarget : TargetRules` | UBT finds a target by class name `<Name>Target`: this defines the target `TestTrust`, which is why `build.bat TestTrust` works |
| `Type = TargetType.Game` | A standalone, **monolithic** game executable: the target that gets packaged and that the perf gate runs. The editor file sets `TargetType.Editor`: **modular** DLLs loaded by `UnrealEditor.exe`, which is what the mutation runner builds, because a mutant then relinks one small DLL (`01b #8`) |
| `DefaultBuildSettings = BuildSettingsVersion.V7` | The newest default build settings for 5.8 (the brief's toolchain rule; UE5-UpdateBudget uses the same) |
| `IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8` | Pins 5.8's engine include order, so an engine upgrade can't silently change what our files include |
| `ExtraModuleNames.AddRange(...)` | Both project modules are built. Without `TestTrustSample` here, the editor would not load its tests, and the runner's baseline would find zero tests (it refuses then, `02` §8) |

### A3. `Source\TestTrust\TestTrust.Build.cs`

```csharp
PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
PrivateDependencyModuleNames.AddRange(new string[] { "TestTrustProbe" });
```

| Line | What it does, and why |
|---|---|
| `class TestTrust : ModuleRules` | The class name must equal the module name |
| `PCHUsage = UseExplicitOrSharedPCHs` | Uses a shared precompiled header unless the module names its own: each `.cpp` compiles faster. This matters twice here, because every mutant is one `.cpp` compile |
| `Core`, `CoreUObject`, `Engine` (public) | The workload's public headers (Phase 5) will declare actors and components, which need these headers |
| `TestTrustProbe` (private) | The workload uses the probe only inside `.cpp` files; no public header exposes a probe type, so the rule "private unless a public header needs it" says private |

### A4. `Source\TestTrustSample\TestTrustSample.Build.cs`

```csharp
PublicDependencyModuleNames.AddRange(new string[] { "Core" });
```

| Line | What it does, and why |
|---|---|
| `Core` only | The rules use `FVector` and `int32`; the tests use the Core automation framework (`Misc/AutomationTest.h` lives in Core). Public, because the public header `TTSampleRules.h` includes `CoreMinimal.h`. No `Engine`: a smaller module compiles faster per mutant and can't accidentally depend on a world |
| *Not added:* `CQTest` | The sample's tests use the plain automation macros, the same style as UE5-UpdateBudget's scheduler suite (the runner's first real target). The runner doesn't care which framework a suite uses (`01b #6`) |

### A5. Module registration files

```cpp
// Source\TestTrust\Private\TestTrustModule.cpp
#include "Modules/ModuleManager.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, TestTrust, "TestTrust");

// Source\TestTrustSample\Private\TestTrustSampleModule.cpp
IMPLEMENT_MODULE(FDefaultModuleImpl, TestTrustSample);

// Plugins\TestTrustProbe\Source\TestTrustProbe\Private\TestTrustProbeModule.cpp
IMPLEMENT_MODULE(FDefaultModuleImpl, TestTrustProbe);
```

| Line | What it does, and why |
|---|---|
| `#include "Modules/ModuleManager.h"` | Declares the macros and the default module classes (`Core/Public/Modules/ModuleManager.h:884, 892`) |
| `IMPLEMENT_PRIMARY_GAME_MODULE(...)` | The project's main game module entry point; in packaged (monolithic) builds it also defines the project-name globals (`ModuleManager.h:1100–1136`). Exactly one per project. The third argument is ignored in 5.8 (`DEPRECATED_GameName`, `:1100`) but the macro still takes it |
| `IMPLEMENT_MODULE(FDefaultModuleImpl, X)` | A normal module's entry point (`ModuleManager.h:946, 955`). Used for the sample module and the plugin module |
| `FDefaultGameModuleImpl` / `FDefaultModuleImpl` | Engine classes with empty start-up and shut-down. None of our modules needs start-up logic, so a custom class would be an extra class with no reason |
| The mutation config excludes `*Module.cpp` | A registration file has nothing to mutate; listing it would only cost a lexer pass |

### A6. `Plugins\TestTrustProbe\TestTrustProbe.uplugin` and `TestTrustProbe.Build.cs`

| Field / line | Value | Why |
|---|---|---|
| `FriendlyName`, `Description`, `Category` | "TestTrust Probe", …, "Testing" | Shown in the Plugins window; the description says what makes it reusable: any workload becomes gate-able |
| `EnabledByDefault` | `true` | A project that copies the plugin gets it without editing its `.uproject` (the reuse path for later portfolio projects) |
| `CanContainContent` | `false` | Code only |
| `IsBetaVersion`, `IsExperimentalVersion` | `false`, `false` | No warning badge. It is small, tested code; not a claim of production readiness |
| `Modules[0]` | `TestTrustProbe`, `Runtime`, `Default` | Must run in packaged games, where the gate measures |
| `Build.cs`: `Core`, `CoreUObject`, `Engine` (public) | | Its subsystem (Phase 5) derives from `UTickableWorldSubsystem`, an Engine type, in a public header |
| No game-module dependency | | The plugin must work in any project; the dependency goes game → plugin only |

### A7. `Config\DefaultEngine.ini`, `DefaultGame.ini` and `DefaultInput.ini`

| Key | Why |
|---|---|
| `GameDefaultMap`, `EditorStartupMap` = `/Engine/Maps/Templates/Template_Default` | An engine map with a floor and lights. No map is authored: the workload spawns everything from code (as in UE5-UpdateBudget). The editor also opens this map when the runner starts `UnrealEditor-Cmd` |
| `bSmoothFrameRate=False`, `bUseFixedFrameRate=False` | Restate engine defaults on purpose: a later change can't silently cap or smooth frame times. Gate runs use `-deterministic` anyway, where smoothing is skipped (`01b` B-1) |
| `r.VSync=0` under `[SystemSettings]` | Present never blocks the frame |
| `r.AllowStaticLighting=False` | No baked lighting is needed, so no lighting-build warnings for the template map |
| `DefaultGraphicsRHI_DX12`, SM6 only | One shader format to compile and cook (the RTX 5070 supports SM6), so packaging is shorter |
| *(no Android File Server block)* | The first uncooked run (F-3) appended an `AndroidFileServerEditor` block with a random `SecurityToken`. It was deleted, and the plugin is now disabled in the `.uproject` (A1) so it can't come back |
| `DefaultGame.ini`: `ProjectName`, `Description` | The project's display name |
| `+DirectoriesToAlwaysCook=(Path="/Engine/BasicShapes")` | The workload's agents (Phase 5) will use the engine cube referenced only from C++; a cooker follows references from maps, not from C++ strings, so the folder is cooked explicitly (UE5-UpdateBudget found this the hard way) |
| `DefaultInput.ini`: `DefaultPlayerInputClass=/Script/EnhancedInput.EnhancedPlayerInput`, `DefaultInputComponentClass=/Script/EnhancedInput.EnhancedInputComponent` | The engine's default player input class is the legacy `UPlayerInput` (`Runtime/Engine/Private/UserInterface/InputSettings.cpp:52–53`). The Enhanced Input plugin, on by default, casts it to `UEnhancedPlayerInput` (`Engine/Plugins/EnhancedInput/Source/EnhancedInput/Private/EnhancedInputSubsystems.cpp:79`) and logs a warning on every map load when that fails (`:118`). These are the two values Epic's 5.8 templates ship with. Learned from a sibling portfolio project's Phase 4 log and re-checked in the source here; added before this project's first run |

## Part B · Sample rules and tests (Phase 4, F2)

### B1. `Source\TestTrustSample\Public\TTSampleRules.h`

| Line | What it does, and why |
|---|---|
| `#pragma once` | Include this header at most once per `.cpp` (`04` §6) |
| `#include "CoreMinimal.h"` | `int32`, `FVector`, `FMath`. Core's standard "minimal" header |
| `#define UE_API TESTTRUSTSAMPLE_API` | The 5.8 export alias (`04` §10). `TESTTRUSTSAMPLE_API` is generated by UBT from the module name |
| `struct FTTSampleRules` | `F` prefix: a plain C++ type, not a UObject. No reflection, no GC, no world needed: tests are microseconds |
| `static constexpr int32 MinDamage = 1;` | The floor of damage. In the header so tests use the same constant (`04` §2). The runner never mutates headers, so this value can't be a mutant |
| `static UE_API int32 ComputeDamage(int32 BaseDamage, int32 Armor, bool bCritical);` | `int32`: UE's fixed-width integer, the same size on every platform. `bCritical`: UE's `b` prefix for booleans |
| `static UE_API bool IsInRange(const FVector& Origin, const FVector& Target, double Range);` | `const FVector&`: no copy (`04` §3). `double`: UE 5's `FVector` is double precision, so the range is too, avoiding a float/double mix |
| `static UE_API float TickCooldown(float Remaining, float DeltaSeconds);` | `float` like engine delta times |
| `#undef UE_API` | Ends the alias so it doesn't leak into includers |

### B2. `Source\TestTrustSample\Private\TTSampleRules.cpp`

```cpp
int32 FTTSampleRules::ComputeDamage(int32 BaseDamage, int32 Armor, bool bCritical)
{
	int32 Damage = BaseDamage - Armor;
	if (Damage < MinDamage)
	{
		Damage = MinDamage;
	}
	if (bCritical)
	{
		Damage *= 2;
	}
	return Damage;
}
```

| Line | What it does, and why | Mutants the runner makes here (`02` §7) |
|---|---|---|
| `#include "TTSampleRules.h"` | Its own header first: proves the header compiles on its own (UE's include-what-you-use rule) | — |
| `int32 Damage = BaseDamage - Armor;` | Flat armour. A declaration, so it is never deleted (SDL skips declarations) | AOR `-` → `+` |
| `if (Damage < MinDamage)` | The floor | ROR `<` → `<=` (**equivalent**: when `Damage == MinDamage` both set it to the same value), `<` → `>=`; COND `!(…)` |
| `Damage = MinDamage;` | Clamp | SDL (delete) |
| `if (bCritical)` | Critical hit | COND `!(bCritical)` |
| `Damage *= 2;` | Double | AOR `*=` → `/=`; SDL |
| `return Damage;` | Result. `return` statements are never deleted | — |

```cpp
bool FTTSampleRules::IsInRange(const FVector& Origin, const FVector& Target, double Range)
{
	return FVector::DistSquared(Origin, Target) <= Range * Range;
}
```

| Line | What it does, and why | Mutants |
|---|---|---|
| `FVector::DistSquared(Origin, Target)` | Static `TVector<T>::DistSquared` (`Core/Public/Math/Vector.h:1041`). Squared distance avoids a square root; both sides are non-negative, so comparing squares gives the same answer | — |
| `<= Range * Range` | Inclusive limit: a target exactly at the range counts. **No test checks the exact limit** (B3) | ROR `<=` → `<` (**the deliberate survivor**), `<=` → `>`; AOR `*` → `/` |

```cpp
float FTTSampleRules::TickCooldown(float Remaining, float DeltaSeconds)
{
	const float Next = Remaining - DeltaSeconds;
	return Next > 0.f ? Next : 0.f;
}
```

| Line | What it does, and why | Mutants |
|---|---|---|
| `const float Next = Remaining - DeltaSeconds;` | Time left after this frame | AOR `-` → `+` |
| `return Next > 0.f ? Next : 0.f;` | Clamp at zero (`04` §4) | ROR `>` → `>=` (**equivalent**: at exactly zero both return zero, `04` §11), `>` → `<=` |

**Total: 14 mutants**, listed by `python -I Tools\tt_mutants.py <file>` and predicted in `09` before the run.

### B3. `Source\TestTrustSample\Private\Tests\TTSampleRulesTests.cpp`

| Line | What it does, and why |
|---|---|
| File comment "DELIBERATE GAP" | States in the code itself which test is missing and why, so nobody "fixes" it before the smoke test has shown the survivor. Phase 7 adds the boundary test and re-runs (`03` S8) |
| `#include "Misc/AutomationTest.h"` | The automation framework: macros, `FAutomationTestBase`, `TestEqual`/`TestTrue`/`TestFalse` |
| `#include "TTSampleRules.h"` | The code under test |
| `#if WITH_DEV_AUTOMATION_TESTS` … `#endif` | Compile the tests only where dev tests exist: Development, not Test/Shipping (`01b #7`, `04` §7) |
| `namespace TTSampleTests { constexpr EAutomationTestFlags Flags = EditorContext \| ClientContext \| ProductFilter; }` | One place for the flags. **Contexts:** the tests run in the editor *and* in `-game` (`01b #7`); the runner uses the editor. **Filter:** exactly one filter flag is required (the macro's `static_assert`, `AutomationTest.h:4127–4133`); `ProductFilter` is the one for project-level tests. The named namespace avoids clashes in unity builds (`04` §8) |
| `IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleDamageArmorTest, "TestTrust.Sample.Damage.ArmorSubtracts", TTSampleTests::Flags)` | Declares a test class and one static instance that registers it under that dotted name when the module loads (`04` §9). The name's prefix `TestTrust.Sample.` is what the runner's filter `StartsWith:TestTrust.Sample` selects (`01b #5`) |
| `bool F…::RunTest(const FString& Parameters)` | The test body. `Parameters` is used only by complex tests; returning `true` means "the test ran to the end": failures are recorded by the `Test…` calls, not by the return value |
| `TestEqual(TEXT("10 damage against 3 armour"), FTTSampleRules::ComputeDamage(10, 3, false), 7);` | Records a failure (with the description) if the values differ (`AutomationTest.h:1985` for `int32`). Kills `-`→`+` (13 ≠ 7) and `<`→`>=` (1 ≠ 7) |
| `CriticalDoubles`: `ComputeDamage(10, 3, true) == 14` | Kills `*=`→`/=` (3), deleting `Damage *= 2;` (7), and inverting `if (bCritical)` |
| `NeverBelowMinimum`: `ComputeDamage(2, 5, false) == MinDamage` | Kills deleting the clamp (−3 ≠ 1) |
| `Range.InsideAndOutside`: `TestTrue(5 units, range 10)`, `TestFalse(20 units, range 10)` | Kills `<=`→`>` and `*`→`/` (25 ≤ 1 is false). **Doesn't** test 10 units at range 10: `<=`→`<` survives |
| `Cooldown.CountsDown`: `TickCooldown(1.0f, 0.25f) == 0.75f` | `TestEqual` for `float` uses a tolerance (`AutomationTest.h:1988`). Kills `-`→`+` (1.25) and `>`→`<=` (0) |
| `Cooldown.StopsAtZero`: `TickCooldown(0.1f, 0.5f) == 0.0f` | Checks the clamp |

## Part C · Scripts (Phase 4, F3)

All of them are adapted from UE5-UpdateBudget's scripts and must be run **through the machine queue**.

| File | Lines that matter | Why |
|---|---|---|
| `build.bat` | `call "%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" %TARGET% Win64 %CONFIG% -Project="%PROJECT%" -WaitMutex -NoHotReloadFromIDE` | Builds from the command line, reproducibly. `-WaitMutex` waits for UBT's single-instance mutex instead of failing; `-NoHotReloadFromIDE` keeps a running editor from being patched. `Build.bat` also holds its own machine-wide lock file (`01b` B4) |
| `package.bat` | `RunUAT.bat BuildCookRun ... -clientconfig=%CONFIG% -build -cook -stage -pak -archive` | Packaged Development is the gate's build (the launcher engine can't build Test) |
| `smoke_game.bat` | `UnrealEditor-Cmd.exe "%PROJECT%" -game -nullrhi -nosound -unattended -nosplash -traceautostart=0 -ExecCmds="quit"` | The uncooked project loads its modules and the default map, then quits. UE5-UpdateBudget's version also passed `-ExitAfterSeconds=0`; nothing in 5.8.4's `Engine/Source/Runtime`, `Editor` or `Developer` reads that switch (grep, 2026-11-21), so it was dropped: the run exits because of `quit` |
| `smoke_packaged.bat` | `nullrhi`: `TestTrust.exe -nullrhi ... -ExecCmds="quit"`; `gpu`: `-windowed -ResX=960 -ResY=540 ...` | The packaged build starts with and without the GPU; the GPU run's log names the chosen adapter |
| `run_tests.bat` | `UnrealEditor-Cmd.exe "%PROJECT%" -ExecCmds="Automation RunTests %FILTER%;Quit" -unattended -nullrhi ... -ReportExportPath="%REPORT%"` | The suite by hand. Exit 0 = all passed (`01b #4`). Default filter `StartsWith:TestTrust` |
| `phase4_checks.bat` | `call :step F-1 ... \|\| exit /b` seven times | Every foundation check in one queue job, stopping at the first failure. `:step` prints start/end and the exit code so the queue log is self-explanatory |

## Part D · Python tools

### D1. `Tools\probe_build_cost.py` (Phase 2 instrumentation)

| Part | What, why |
|---|---|
| Module docstring | How to run it (only through the queue) and the five things it does. It is research instrumentation: the runner was designed from its numbers |
| `TARGET_*` constants | UE5-UpdateBudget at commit `c25a996`, its UE subfolder, project file and editor target. Read-only for this project |
| `MUTATIONS` | One exact text change per code path: a game-module `.cpp` (`<` → `<=`), a plugin `.cpp` (`!=` → `==`), a UObject header default (`300.f` → `301.f`). `mutate()` insists the original text occurs exactly once, so a changed file can't be silently mis-mutated |
| `snapshot()` | Refuses a destination inside the target; `git rev-parse <commit>^{commit}` (a full hash, and proof the commit exists); `git archive` of the UE subfolder piped into Python's `tarfile` with `filter="data"` (no absolute paths or links escaping the folder). The target's working tree is never read: it is being developed in parallel |
| `run_logged()` | One command string (quoted by hand, as UE5-UpdateBudget's runner does, so `-ExecCmds="..."` reaches Unreal as written), its output into a step log, a timeout, and the wall time |
| `build()` | `Build.bat <EditorTarget> Win64 Development "-Project=..." -WaitMutex -NoHotReloadFromIDE "-Log=<step>_ubt.txt"`. Parses the console output for action lines (`[n/m] Compile …`, `Link …`) and the UBT debug log for "Parsing headers for" (UHT ran) and "Generated code is up to date" (`01b #2`), and for working-set messages (`01b #3`) |
| `editor_tests()` | `UnrealEditor-Cmd <uproject> [-game] -nullrhi ... -ExecCmds="Automation RunTests StartsWith:System.Core.HAL.FileManager;Quit" -ReportExportPath=...`: a fast engine test (`Core/Private/Tests/HAL/FileManagerTest.cpp:9`, all contexts) that exists in every Development editor, so the launch cost is measured even before the target has tests. Reads `index.json` |
| `main()` | Cold build, no-op build, three mutate/restore pairs, three test launches (editor cold, editor warm, `-game`); the manifest is rewritten after every step |
| What it does **not** do | Pin to the P-cores: the probe ran before the pinning rule existed, and its test launches measure cost, not performance. Builds are never pinned. Recorded in `09` |

### D2. `Tools\tt_common.py`

| Part | What, why |
|---|---|
| `performance_core_mask()` | Copied from UE5-UpdateBudget's `run_bench.py`: `GetLogicalProcessorInformationEx(RelationProcessorCore)` lists physical cores with an efficiency class; the P-cores have the higher class; their group-0 masks are OR-ed. On this i7-14650HX: `0xFFFF` (logical CPUs 0–15). Returns `None` on a non-hybrid CPU, so the code still works elsewhere |
| `pinned(command, console)` | Wraps a command as `cmd /v:on /s /c "start "" [/B] /wait /affinity <MASK> <command> & exit !errorlevel!"`. **Why this exact form:** a plain `cmd /c start "" /wait …` returns 0 whatever the program returns (tested: exit 3 and −1 both gave 0). `start` does set `ERRORLEVEL`, so the line ends with `exit !errorlevel!`; `/v:on` enables delayed expansion so the value is read *after* `start` returns (`%errorlevel%` would be expanded before); `/s` strips exactly the outer quotes. `/B` keeps a console program's output in our log. Tested: 3 → 3, −1 → 4294967295, quoted arguments intact (`01b #14`). Because delayed expansion would rewrite any `!…!` in the command, `pinned()` refuses a command containing `!` (self-review) |
| `pin_self(mask)`, `applied_mask()` | Copied from UE5-UpdateBudget's `run_bench.py`: `SetProcessAffinityMask` on the current process, so every child inherits the mask from its first instruction; `GetProcessAffinityMask` reads back what Windows actually applied (tested: a child process pinned itself and read back `0xFFFF`). For the Phase 5 gate script, whose every child is a timed run. **The mutation runner doesn't pin itself**, because it also starts builds, which keep all 24 logical CPUs; it pins each test launch with `pinned()` |
| `sanitize()` | Replaces the user profile path with `%USERPROFILE%`, so committed manifests never contain a personal path |
| `environment_record()` | Engine version from `Build.version`, compiler, CPU, GPU and driver, RAM, OS build, power plan, AC power, **CPU affinity**: written into every manifest (`Benchmarks/README.md`) |

### D3. `Tools\tt_mutants.py` (the mutant generator)

| Part | What, why |
|---|---|
| `OPERATORS` (longest first) | So `>>=` is one token, not `>` `>` `=`; `->`, `::`, `++` are single tokens and can never be mistaken for `-`, `:` or `+` |
| `SKIP_MACROS` | Arguments of `check`, `ensure`, `verify`, `UE_LOG`, `TEXT`, `CSV_*`, `TRACE_*`, `SCOPE_*`, `DECLARE_*`, `DEFINE_*`, `IMPLEMENT_*`, … are never mutated: assertions and logging aren't behaviour, and mutating a test-registration macro would mutate the tests |
| `NOT_DELETABLE_START` | Statement deletion never removes control flow (`return`, `break`, `if`, …) or a declaration (`const`, `auto`, built-in types) |
| `ROR`, `AOR`, `LCR` tables | The replacements per operator (`02` §7). ROR gives two mutants per operator: a boundary shift and a negation, the reduced set that keeps the mutant count low while covering both kinds of comparison bug |
| `Mutant` (frozen dataclass) | File, operator, `start`/`end` offsets, original and replacement text, line, column, and a stable `id` = first 10 hex digits of SHA-1 of `file|start|end|operator|replacement`. Same commit → same ids, so reviews of equivalent mutants carry over between campaigns. `apply()` refuses if the text at the offsets is not the expected original |
| `tokenize()` | One pass over the source: skips whitespace, `//` and `/* */` comments and whole preprocessor lines (with `\` continuations); keeps string, char and raw-string literals (`R"x(...)x"`) as single tokens so nothing inside them is mutated; records each token's line and column, and whether whitespace touches it on either side |
| `mark_mutable()` | A token can be mutated only inside a code block: a brace whose head (tokens since the last `;`, `{` or `}`) contains `namespace` is a namespace scope, `class`/`struct`/`enum`/`union` without `(` is a type body, anything else is code. Namespace-scope initialisers and class bodies are therefore never mutated. Tokens inside a skipped macro's parentheses and lines with a `tt-nomutate` comment are excluded |
| `generate()` | Walks the mutable tokens. ROR/AOR/LCR only for **binary** operators, defined as whitespace on both sides (UE style), which excludes `TArray<int32>`, `AActor* A`, `T&& V` and unary minus. COND wraps an `if`/`while` condition in `!(…)`, unless it declares a variable or has an init-statement. SDL deletes assignment, increment and call statements |
| `_statement_level()` | **Fixed during F4:** the first version treated `I < N;` inside `for (…; I < N; ++I)` as a statement and planned to delete it. Each `{` now remembers the bracket depth it opened at; a statement must start at exactly that depth. Lambda bodies passed as arguments still count, because their `{` records the deeper level |
| `_deletable()` | An expression statement with a visible effect: a top-level assignment operator, `++`/`--`, or ending in `)` (a call). `Type Name …`, `TArray<…> X` and `AActor* X` patterns are declarations and are skipped |
| `--selftest` | A source with a define, a namespace-scope constant, `check`, `UE_LOG`, a template, a pointer, a declaration-condition `if`, a `for` loop, a raw string and a unary minus. The expected mutant list is written out by hand; any lexer change that alters it fails |

### D4. `Tools\tt_mutate.py` (the runner)

| Part | What, why |
|---|---|
| Module docstring | The five commands, the safety rules and the fates, in one place |
| `manifest_path`, `load`, `save` | One JSON manifest per campaign in `Benchmarks/Raw/`. `save` writes a temporary file and `os.replace`s it: atomic on Windows and POSIX, so a batch killed by the queue's timeout never leaves half a manifest |
| `check_destination()` | Allowed: outside the target repository, or inside it only if `git check-ignore` says the path is ignored (this project's own `Tools/_work/`). Anything else is refused |
| `snapshot()` | As in the probe: a commit object via `git archive`, never the working tree |
| `files_to_mutate()` | `.cpp` files under the UE project that match a `mutate` glob and no `exclude` glob, sorted (a stable order means stable batches) |
| `cmd_plan()` | Campaign id = timestamp + `_mut-<name>`, or `--campaign <id>` to **re-plan** an existing campaign that has no result and no baseline yet (it keeps the campaign's place in the machine queue; refused once anything ran, so results from two commits can never mix; used once, `09` P4-R); snapshot; a pristine copy of each target file in `_pristine/`; every mutant with `fate = None`; the environment record (with a `pinning` note: `cpu_affinity` applies to test launches, while builds stay unpinned); the config without the local repository path |
| `run_step()` | `Popen` with output to a log; on timeout `taskkill /PID <pid> /T /F` kills the whole tree (cmd → UnrealEditor-Cmd → any shader workers) |
| `build()` | Same command as the probe. Counts compile actions and looks for `error Cxxxx` / `error LNKxxxx`: a compile error makes the mutant *stillborn*; a failure without one is an infrastructure *error* |
| `run_tests()` | A fresh `UnrealEditor-Cmd` per mutant, pinned (`tt_common.pinned(..., console=True)`), with `-ExecCmds="Automation Now;RunTests <filter>;Quit"`: `Now` first skips the controller's fixed 5 s start delay (`01b #9`; the probe measured it in every launch), and its report in the snapshot's `Saved\TestTrustReports\` folder (git-ignored, and skipped by the portfolio link checker, because the engine also writes an HTML page with absolute asset links). Reads `succeeded`, `succeededWithWarnings`, `failed`, `notRun` and the names of failed tests from `index.json` (`01b #5`) |
| `classify()` | The fate table of `02` §9 as a pure function. Order matters: a hung build is an error; a non-zero build exit is stillborn only with a compile error; a test timeout beats everything else; a missing report is a crash; then killed if anything failed, fewer tests completed than in the baseline, or the exit code was non-zero; otherwise survived |
| `restore()` | Writes every target file back from `_pristine/` if it differs. Called at the start of every batch (undoes a batch killed mid-mutant) and after every mutant (in a `finally`) |
| `pending()` | Mutants without a fate, plus *error* fates with fewer than two attempts |
| `estimate_seconds()` | The median cost of mutants already run, or baseline + 60 s before any has run; used to stop **before** the budget would be exceeded |
| `cmd_batch()` | Restore → build and test the unmutated snapshot → refuse (exit 3) unless it built, exited 0, ran ≥ 1 test and failed none → test timeout = max(120 s, 3 × baseline) → for each pending mutant while the budget allows: apply, build, test, restore, classify, save. The build result starts as "nothing ran", and `OSError`/`ValueError` (a locked file, a file that changed since planning) are caught and stored in `detail`, so such a mutant becomes an *error* (retried once) instead of crashing the batch (found in the Phase 4 self-review, `07`) |
| Stop reason | `record["stopped"]` is `None` while the batch runs and is set when the loop ends ("time budget reached", "all mutants have a fate", or errors with no attempts left). **Fixed after P4-R:** the first version set it before the loop, so a running batch already claimed a reason |
| `cmd_queue()` | Submits `batch` jobs to `tools\ue_queue.py` until nothing is pending; the command is passed as one pre-quoted string because the queue joins its arguments with spaces (a lesson from the first probe submission, `09` P2). Stops if a batch makes no progress |
| `scores()` | M1, M1 before review, M1-naive (`02` §9) |
| `cmd_report()` | The summary page: fates, the three scores, a per-operator table, cost per mutant and per batch, and the survivor table with review verdicts from `Tools/mutation/<name>_review.json` |
| `main()` | Reconfigures `stdout` to UTF-8 with `errors="replace"`. **Fixed after P4-R:** the Windows console's cp1252 couldn't print the report's `→`, and the driver crashed *after* a successful batch |
| `cmd_selftest()` / `safety_selftest()` | Eight classification cases (including the 4294967295 exit code of a failed run); the three scores on a known example; and SC2: a throwaway repository with an **uncommitted edit** is snapshotted; its tree hash, status and file time must be unchanged and the edit must not appear in the snapshot |

### D5. `Tools\mutation\sample.json`

| Key | Value | Why |
|---|---|---|
| `name` | `sample` | Campaign ids and the review file name |
| `repo_name`, `repo`, `commit` | `UE5-TestTrust`, this folder, `HEAD` | The sample lives in this repository. `HEAD` is resolved to a full hash at plan time and stored, so the campaign stays pinned. The local path is not copied into the manifest |
| `project_subdir`, `uproject`, `editor_target` | `TestTrust`, `TestTrust.uproject`, `TestTrustEditor` | What to snapshot and build |
| `mutate` / `exclude` | `Source/TestTrustSample/Private/*.cpp` / `*/Tests/*`, `*Module.cpp` | Only the rules file remains |
| `test_filter` | `StartsWith:TestTrust.Sample` | Exactly this suite (`01b #5`) |
| `operators` | all six | |

### D6. `Tools\mutation\sample_review.json`

| Key | Why |
|---|---|
| `8125da701a`, `1c78e5d36c`: `equivalent` | The two equivalent survivors predicted in `09` P4-R, each with the reason no input can tell it from the original. `report` removes them from both sides of M1 and still prints M1 before the review |
| `62c038c366`: `real gap` | The deliberate boundary gap. Recorded, never excluded: it stays a survivor in M1 |
| Keys are mutant ids | Ids hash the file path, offsets, operator and replacement (D3), so the review carries over to any later campaign at a commit where that file is unchanged |


---

## Part H · Step S7: tests written from survivors, applied as a patch

### H1. `Tools\mutation\patches\updatebudget_boundary_tests.patch`

A unified diff against UE5-UpdateBudget's `UpdateBudgetSchedulerTests.cpp` at `b890bc6`, adding three tests before the file's `#endif`. It is applied **only to this project's snapshot**; UE5-UpdateBudget's repository is never edited (owner rule). Its maintainer can apply the same file with `git apply --ignore-whitespace` (see "How it was made").

| Test | The survivor it targets | Why the expected values are exact |
|---|---|---|
| `UpdateBudget.Scheduler.DeadlineAtNextFrameIsOptional` | line 47, `Deadline < NextFrameTime` → `<=` | One client with deadline 1.0, `NextFrameTime` 1.0, budget 0: a deadline exactly at the next frame can still wait, so it is not mandatory and doesn't run (`MandatoryRuns` 0, `Runs` 0, `Deferred` 1). The header defines mandatory as "deadline before the next frame", so this pins the documented meaning |
| `UpdateBudget.Scheduler.ExactFitStillRuns` | line 56, `SpentMs + Predicted > BudgetMs` → `>=` | Predicted and measured cost 0.25 ms, budget 0.5 ms, four optional clients: 0.25 and 0.5 are exact binary fractions, so the second update fills the budget **exactly** (0.25 + 0.25 = 0.5 with no rounding) and must still run; the third must not (`Runs` 2) |
| `UpdateBudget.Scheduler.ExactlyOnBudgetIsNotOverBudget` | line 70, `bOverBudget = SpentMs > BudgetMs` → `>=` (and line 56 again) | One update costing exactly the 0.5 ms budget runs and leaves `bOverBudget` false |

**How it was made:** the pinned test file was copied out of the S6 snapshot (CRLF line endings, as `git archive` wrote it), the tests were inserted before `#endif // WITH_DEV_AUTOMATION_TESTS`, and `git diff --no-index` produced the patch. **Found in the code review:** the patch came out with LF line endings, because `git diff` ran inside this repository and its `* text=auto` attribute normalised the text; so the runner applies it with `--ignore-whitespace`, which lets the LF context match the CRLF file; git then writes the added lines with CRLF as well (checked: all 265 lines of the patched file end in CRLF). To apply it in UE5-UpdateBudget: `git apply --ignore-whitespace <patch>`. `.gitattributes` gains `*.patch -text`, so the committed bytes never change in any checkout and the SHA-256 that the campaign manifest records (`38b3f333…`) keeps matching the file.

**Skipped review finding:** `ExactFitStillRuns` checks the counts, not which two clients ran. Asserting the order too would change the patch, and with it the measured campaign; the order is already pinned by UE5-UpdateBudget's own `DeadlineOrder` and `BudgetCutOff` tests, which record the run order, and every comparator mutant on line 42 except the reviewed-equivalent tie-break was killed in both campaigns.

### H2. `Tools\tt_mutate.py`: `apply_patches()`, and `Tools\mutation\updatebudget_after.json`

| Part | What, why |
|---|---|
| `"patches": ["patches/updatebudget_boundary_tests.patch"]` in the config | The "after" campaign is the "before" campaign plus this key; the commit, files, filter and operators are identical, so the 39 mutants and their ids are identical and the review file (`updatebudget_review.json`, keyed by id) applies to both |
| `apply_patch(path, root)` (one patch) and `apply_patches(config, root)` (the config's list) | Runs `git apply -p1 --ignore-whitespace --whitespace=nowarn <patch>` in the campaign folder, **with `GIT_CEILING_DIRECTORIES` set to the folder's parent**. **Found while building it:** the campaign folder lies inside this repository's ignored tree, and there a plain `git apply` resolves paths against this repository and silently changes nothing (tested: exit 0, file unchanged). The ceiling stops git's repository search at the snapshot, so it patches like a plain `patch` tool. **Code review:** an inherited `GIT_DIR` or `GIT_WORK_TREE` would override the search, so they are removed from the child's environment; a failed apply now raises with git's own message (which hunk failed) instead of a bare exit status |
| `git apply --numstat -z` | Lists the files the patch touches before applying it. **Code review:** the first version read the `+++ b/` lines with a regex that cut paths at a space and missed deleted files; git's own list has neither problem |
| The "every target really changed" check | Each listed file must differ after the patch (or appear, or disappear), or planning stops. A silent no-op patch would otherwise produce an "after" score identical to "before" and look like a result |
| `target.patches` in the manifest | Each patch's file name, SHA-256 and target files, so the "after" campaign records exactly which tests it measured |
| Order: snapshot → patch → pristine copies | Mutants are planned on the patched tree. The patch here touches only the test file, which is never mutated, but the order keeps any future patch to a mutated file consistent |
| `patch_selftest()` (in `selftest`) | **Code review:** the ceiling trick had been tested only by hand. The self-test applies an LF patch with a space in its path to a CRLF file inside `Tools\_work\`, checks that the file changed and this repository's `git status` didn't, and that applying it twice raises |
| `main()` removes `GIT_DIR` and `GIT_WORK_TREE` | **Altitude review:** an inherited value would redirect every git call of the runner (the snapshot's `git archive` too), not only the patch, so it is cleared once for the whole process instead of in `apply_patch` |
| After the reviews | The final code re-applied the patch to a copy of the S6 snapshot's test file: same SHA-256, same target, and a byte-identical result to the file the S7 campaign measured |
