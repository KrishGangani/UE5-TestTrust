> **Raw Phase 2 research notes (C_perf_measurement), UE 5.8.4, 2026-11-21.** Evidence trail; restated in [../01b_Research_Findings.md](../01b_Research_Findings.md). Engine paths are relative to `Engine/Source/`.

# C. Measuring gameplay performance for a gate

## C1. The engine facts reused from UE5-UpdateBudget, re-opened here

UE5-UpdateBudget's Phase 2 verified the measurement chain. These are the lines this project depends on, each opened again on 5.8.4:

| Fact | Evidence |
|---|---|
| `-deterministic` = `-UseFixedTimeStep` + `-FixedSeed` | `Runtime/Launch/Private/LaunchEngineLoop.cpp:2455–2462` |
| Fixed step: `DeltaTime = FixedDeltaTime` every frame and the engine doesn't wait | `Runtime/Engine/Private/UnrealEngine.cpp:3004–3023` |
| CSV global columns `GameThreadTime`, `RenderThreadTime`, `GPUTime`, `*_CriticalPath` are set from real timers each frame | `LaunchEngineLoop.cpp:1515–1527` |
| Capture on an event and exit after it | `-csvStartOnEvent=` (`Runtime/Core/Private/ProfilingDebugging/CsvProfiler.cpp:5081`), `-csvStopOnEvent=` (`:5090`), `-csvCaptureOnEventFrameCount=` (`:5078`), `-ExitAfterCsvProfiling` (`:4309–4312`) |
| Macros `CSV_DEFINE_CATEGORY`, `CSV_EVENT`, `CSV_METADATA`, `CSV_SCOPED_TIMING_STAT`, `CSV_CUSTOM_STAT` | `Runtime/Core/Public/ProfilingDebugging/CsvProfiler.h:50, 56, 85, 120, 155` |

UE5-UpdateBudget's measured protocol notes, used as design input (not re-measured here): under `-nullrhi`, `GameThreadTime` is 0, so gate runs need the real GPU; per-run medians of `GameThreadTime` at N = 1,000 agents and 128 compute iterations were 5.211 ms [5.209–5.214] over two runs; unpinned runs on this hybrid CPU sometimes landed on an E-core and ran about 1.6× slower. These come from that project's `09`; this project re-measures its own copy of the workload in Phase 5.

## C2. What the Automated Perf Testing plugin does and doesn't do

- `AutomatedPerfTesting.uplugin`: `IsExperimentalVersion: true`; it "provides Gauntlet Test Controllers"; depends on `Gauntlet` (`Engine/Plugins/Performance/AutomatedPerfTesting/AutomatedPerfTesting.uplugin:6, 15, 26`).
- Test controllers: `UAutomatedStaticCameraPerfTestBase`, `UAutomatedPlacedStaticCameraPerfTest`, `UAutomatedSequencePerfTest`, `UAutomatedReplayPerfTest`, `UAutomatedMaterialPerfTest`, `UAutomatedProfileGoTest`, all deriving `UAutomatedPerfTestControllerBase : public UGauntletTestController` (`Public/AutomatedPerfTestControllerBase.h:77` and the headers under `Public/`).
- The base controller can start and stop Insights traces, the CSV profiler, the FPS chart and video capture (`AutomatedPerfTestControllerBase.h:100–116`).
- A grep of the plugin's C++ for `baseline|threshold|regression|budget|percentile|median` finds **nothing**.
- The plugin folder in the launcher install has `Binaries`, `Config`, `Content`, `Intermediate`, `Resources`, `Source` and **no `Build` folder**, yet its BuildGraph template includes `Engine/Plugins/Performance/AutomatedPerfTesting/Build/Inc/TestConfigs.xml` and `.../AutomatedPerfTestProjectSettings.xml` (`Resources/TemplatesForHookup/AutoPerfTests.xml:25, 30`). The UAT side ships only as a compiled DLL: `Engine/Binaries/DotNET/AutomationTool/AutomationScripts/AutomatedPerfTesting/net10.0/AutomatedPerfTesting.Automation.dll`.
- The DLL's strings mention `GenerateLocalPerfReport`, a "historic report", `-summaryTable`, `GenerateHordePerfReportTelemetry`, and "Horde Telemetry is currently not possible for events outside of ClientPerf reports (when using KeyStats summary table type)". No string mentions a baseline, threshold or regression **[inferred from a string scan of a compiled DLL; not source]**.
- The hookup command `AddAutomatedPerfTestToProject` copies these templates into a project (`Engine/Source/Programs/AutomationTool/Scripts/AddAutomatedPerfTestToProject.cs:21, 46, 66`).

**Reading:** APT captures and reports. The decision "did this build regress?" is left to a person reading PerfReportTool output or a Horde dashboard. On the launcher engine its BuildGraph flow references files that aren't installed **[verified absence; whether the flow still runs without them was not tested]**.

## C3. PerfReportTool, CSV tools, Horde

- CSV tools in `Engine/Binaries/DotNET/CsvTools/`: `CsvInfo`, `CSVStats`, `CSVCollate`, `CSVFilter`, `CSVSplit`, `CSVToSVG`, `CsvConvert`, `PerfreportTool`. UE5-UpdateBudget found no percentiles in `CsvInfo` or PerfReportTool; re-checked by listing only.
- `EpicGames.Analytics.PerformanceTrends.xml` (the doc file of the trends telemetry library) describes a record of metadata: engine version, test id and name, platform, changelist, CPU, GPU, device profile (lines 112–255). Nothing about regression detection.
- Horde's dashboard source is not installed: `Engine/Source/Programs/Horde/HordeDashboard/` contains only `Horde_Dashboard_Packages.tps`. Its regression logic, if any, can't be read here.
- Epic's docs: the Horde Automation Hub surfaces Gauntlet results (`-WriteTestResultsForHorde`) as tiles with relative test health, with historical data per test and cross-stream comparison: https://dev.epicgames.com/documentation/en-us/unreal-engine/horde-automation-hub-for-unreal-engine. A 2026 forum thread shows APT data reaching Horde's Performance Trends with a ClickHouse telemetry store: https://forums.unrealengine.com/t/how-to-set-up-the-automated-performance-testing-to-send-and-view-results-in-horde-performance-trends-dashboard-and-not-having-to-look-through-it-via-the-summarytable-html-locally/2738594.

## C4. Statistics: choosing the sampling unit and the rule

- **Frames are not independent.** Consecutive frames share caches, thermal state and simulation phase. A frame-level test treats 1,200 frames as 1,200 samples and reports confidence the data doesn't have. This is hypothesis H5, tested with configuration N3 rather than assumed.
- **The run is the unit.** One run gives one median and one p95. Run-to-run variation (thermal state, background load, scheduling) is the noise a gate has to beat.
- **Robust centre and spread.** Median and MAD (median absolute deviation, scaled by 1.4826 so it estimates σ for normal data) are not dragged by one bad run, unlike mean and standard deviation. A threshold of median + 3 × scaled MAD is a robust version of a three-sigma control limit. For normal noise, one metric at three sigma would give a one-sided false-positive rate of about 0.13%, so two metrics stay well under the 5% target even with estimation error from m = 10 baseline runs and moderately heavy tails **[inferred; measured in Phase 8]**.
- **A practical floor.** If the baseline spread is tiny, three MADs could be smaller than any change worth acting on. The rule uses max(0.10 ms, 3 × MAD). 0.10 ms is 0.6% of a 60 fps frame and well below the smallest injected regression (0.25 ms).
- **Precision of the evaluation.** With 32 unchanged runs, a single false alarm is 3.1% and two are 6.3%. A rate estimated from 32 trials has a wide confidence interval, so counts are always reported next to rates.
- **No tuning on the evaluation data.** z = 3 and the 0.10 ms floor are fixed now. If Phase 8 changes them, the change is made on a separate calibration batch and the evaluation batches are re-run, so the reported rates are never fitted to the data that measures them.

## C5. The injected regression

- A spin-wait of exactly X ms on the game thread per frame: the loop reads `FPlatformTime::Seconds()` until X ms have passed. Its cost is wall time, so it doesn't depend on CPU frequency, and it is wrapped in its own CSV timing stat so every capture shows how much was injected.
- It runs inside the same frame as the workload, in a tick, so it lands in `GameThreadTime` **[inferred; checked in Phase 5 by comparing the injected stat with the shift in `GameThreadTime`]**.
- Limitation: real regressions can be spiky (a hitch every few seconds) rather than a constant shift. The probe also supports "every Nth frame" injection, used in an exploratory run only.
