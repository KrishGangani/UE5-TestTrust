// TestTrustProbe - UTTProbeSubsystem: makes any gameplay workload gate-able (02 section 4.2).
//
// Created only when the command line contains -TTProbe, and only in Game worlds (never PIE). In the first such world of
// the process it:
//   - writes the run options into the CSV capture's metadata;
//   - fires CSV_EVENT(TestTrustProbe, BenchStart) after the warm-up and BenchEnd after the capture, so a run started with
//     -csvStartOnEvent=BenchStart -csvStopOnEvent=BenchEnd captures exactly the window;
//   - optionally spins the game thread for a known number of milliseconds per frame (the injected regression);
//   - optionally quits a few frames after BenchEnd (-TTExit).
// One window per process: map travel during a run is not supported (the gate's workload never changes map).

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "TTProbeWindow.h"

#include "TTProbeSubsystem.generated.h"

#define UE_API TESTTRUSTPROBE_API

/** Run options, read once from the command line. Values are clamped to safe ranges (see FromCommandLine). */
struct FTTProbeOptions
{
	bool bEnabled = false;				// -TTProbe
	double WarmupSeconds = 5.0;			// -TTWarmup=<s>, finite, at most 3600
	double CaptureSeconds = 20.0;		// -TTCapture=<s>, finite, at most 3600 (at least one frame is always captured)
	FTTInjectionSchedule Injection;		// -TTInjectMs=<ms> (finite, at most 100), -TTInjectEvery=<frames> (at least 1)
	FString RunTag;						// -TTRunTag=<text> (up to the next space), copied into the CSV metadata
	bool bExitWhenDone = false;			// -TTExit

	static UE_API FTTProbeOptions FromCommandLine(const TCHAR* CommandLine);
};

UCLASS(MinimalAPI)
class UTTProbeSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	UE_API virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	UE_API virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
	UE_API virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	UE_API virtual void Tick(float DeltaTime) override;
	UE_API virtual TStatId GetStatId() const override;

	const FTTProbeOptions& GetOptions() const { return Options; }

	/** True from the first frame after the BenchEnd frame on, whatever order the tickables run in: a workload can write
	 *  its end-of-run report as soon as this is true, and the report is outside the capture. */
	bool IsCaptureDone() const { return Window.IsDone() && GFrameCounter > EndFrame; }

private:
	FTTProbeOptions Options;
	FTTProbeWindow Window;
	int64 FrameIndex = 0;
	/** GFrameCounter on the BenchEnd frame (the engine adds 1 per frame, after every world has ticked). */
	uint64 EndFrame = 0;
	bool bRunning = false;
};

#undef UE_API
