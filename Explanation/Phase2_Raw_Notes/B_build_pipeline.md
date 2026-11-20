> **Raw Phase 2 research notes (B_build_pipeline), UE 5.8.4, 2026-11-21.** Evidence trail; restated with consequences in [../01b_Research_Findings.md](../01b_Research_Findings.md). Paths are relative to `Engine/Source/Programs/UnrealBuildTool/` unless they start with `Engine/`.

# B. What a mutant costs to rebuild: UBT, UHT and unity builds

The question: if one line in one `.cpp` file changes, what does UnrealBuildTool redo?

## B1. How UBT decides an action is out of date

- **Timestamps, not content.** An action re-runs if any prerequisite "has a newer timestamp than the last execution time of this action" (`Actions/ActionGraph.cs:752–773`). Produced items whose recorded command line changed are also out of date (`:719–723`, `ActionHistory`).
- **Consequence for mutation:** restoring a file's original text still gives it a new timestamp, so it is compiled again. Faking the old timestamp back would be wrong: the `.obj` on disk was compiled from the mutant, and an old timestamp would make UBT link that mutant object into the "restored" build. The runner never touches timestamps **[inferred from the rule above]**.

## B2. When UHT runs

UHT runs only if something it reads changed (`System/UHTExecution.cs:1388–1430`):
- the UHT assembly, the CoreUObject headers or the engine version header are newer than the module's last run (`:961–989`);
- the module's `.Build.cs` changed (`:991–999`);
- the module hash changed (`:1002–1011`);
- **any header with reflection markup in the module is newer than the last run** (`:1013–1030`).
It also re-creates the makefile if the *set* of files with reflection markup changes ("UHT files changed", `System/TargetMakefile.cs:1104–1121`).

UHT logs "Parsing headers for ..." and "Generated code is up to date." only at **debug** level (`UHTExecution.cs:1427, 1518`). They appear in the UBT log file, which `-Log=<path>` redirects per build (`GlobalOptions.cs:30–34`), not on the console.

**Consequence:** a mutation inside a `.cpp` file never re-runs UHT. A mutation in a `UCLASS`/`USTRUCT` header does, and every file including that header recompiles. The probe measures both (`09`, P2).

## B3. Unity builds and adaptive unity

- `bUseUnityBuild` defaults to the intermediate environment's setting, which is unity for the default environment (`Configuration/Rules/TargetRules.cs:1838–1842`; `Configuration/UEBuildTarget.cs:1231–1241`). `-DisableUnity` switches to a separate `NonUnity` intermediate environment (`Configuration/Descriptors/TargetDescriptor.cs:138–139`, `:162–186`).
- **Small game modules are never unity-built:** for a module whose `.Build.cs` is under `<Project>/Source`, the minimum is `MinGameModuleSourceFilesForUnityBuild = 32` source files (`Rules/TargetRules.cs:1930–1936`; `Configuration/UEBuildModuleCPP.cs:944–953, 980–983`).
- **Plugin modules are not covered by that rule.** Their `.Build.cs` is under `<Project>/Plugins/...`, not `<Project>/Source`, so the minimum stays 0 and they *are* unity-built (`UEBuildModuleCPP.cs:943–953` **[inferred: the `else if` only matches `Source`]**). UE5-UpdateBudget's scheduler lives in such a plugin.
- **Adaptive unity** (`bUseAdaptiveUnityBuild = true` by default, `-DisableAdaptiveUnity` to turn it off; `Rules/TargetRules.cs:1870–1877`) takes files "currently being iterated on" out of the unity blobs (`System/Unity.cs:366, 413`).
- **Which files count as "being iterated on"** (`System/SourceFileWorkingSet.cs:335–411`):
  - if the engine root, the project folder **or the project folder's parent** contains `.git`, UBT runs `git status` there (`:378–396`, message at `:118`);
  - otherwise, **on an installed (launcher) engine, every writable file counts** (the "Perforce" rule: a file is in the working set unless it is read-only) (`:405–411`, `:69–85`).
- When the working set changes, the makefile is rebuilt so the unity blobs are regenerated (`System/TargetMakefile.cs:1123–1150`).

**Consequence for the snapshot:** the runner's snapshot (`Tools/_work/<campaign>/<Project>/`) has no `.git` in the project folder or its parent, and its files are writable. So, on this launcher engine, every source file is in the working set from the start, every file compiles on its own (no unity blob to rebuild), and the working set never changes between mutants **[inferred from the code above; checked by the probe's action counts, `09` P2]**. A snapshot placed where `git status` applies would instead pull the mutated file out of its blob on the first change and push it back on restore, rebuilding the blob each time.

## B4. Other build facts used

- `Engine/Build/BatchFiles/Build.bat` holds a machine-wide lock file in `%tmp%` while it runs (`Build.bat:17–30`), so two `Build.bat` calls never overlap. The queue already serialises UE jobs; the lock is a second guard.
- `-WaitMutex` makes UBT wait for its own single-instance mutex instead of failing (UE5-UpdateBudget's build scripts use it).
- **Deterministic compiler output** (`bDeterministic`, MSVC `/Brepro`) defaults to on only for Shipping and carries `[RequiresUniqueBuildEnvironment]` (`Rules/TargetRules.cs:2155–2167`; `Platform/Windows/VCToolChain.cs:786–799`). An editor target on the launcher engine uses the shared build environment, so this can't be switched on **[inferred]**. That rules out cheap "same object file = equivalent mutant" detection (trivial compiler equivalence) for now.
- Dev automation tests are compiled into Development (`Configuration/UEBuildTarget.cs:6315–6331`).

## B5. Editor target vs game target for mutants

- The editor target is **modular**: each module is its own DLL, so a mutant relinks one small DLL.
- The game target is **monolithic**: one executable linked from every engine library. UE5-UpdateBudget's packaged Development build took 142.6 s end to end (its `09`, F-3b), which includes cooking but shows the scale.
- Tests run in the editor binary (`UnrealEditor-Cmd`) either as the editor or with `-game`. **Decision (02):** mutants build the editor target and run tests in `UnrealEditor-Cmd`. The probe measures the editor and `-game` launch costs.
