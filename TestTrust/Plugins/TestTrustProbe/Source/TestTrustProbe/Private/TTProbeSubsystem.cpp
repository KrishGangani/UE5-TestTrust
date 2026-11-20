// TestTrustProbe - UTTProbeSubsystem.

#include "TTProbeSubsystem.h"

#include "Engine/World.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "Stats/Stats.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(TTProbeSubsystem)

DEFINE_LOG_CATEGORY_STATIC(LogTTProbe, Log, All);

// CSV category for the run's events and the injected cost; enabled by default so every capture contains it.
CSV_DEFINE_CATEGORY(TestTrustProbe, true);

namespace TTProbe
{
	/** Frames to wait after BenchEnd before quitting, so the CSV profiler finishes writing its file (as in UE5-UpdateBudget). */
	constexpr int32 ExitDelayFrames = 3;
	/** Upper bound for -TTInjectMs: a typo such as 500 must not freeze a batch. */
	constexpr double MaxInjectMs = 100.0;
	/** Upper bound for -TTWarmup and -TTCapture, so a typo can't keep a run open for days. */
	constexpr double MaxWindowSeconds = 3600.0;

	/** A finite value clamped to [0, Max]; anything else (nan, inf) falls back to the default. */
	double ClampFinite(double Value, double Default, double Max)
	{
		return FMath::IsFinite(Value) ? FMath::Clamp(Value, 0.0, Max) : Default;
	}

	/** One capture window per process: a second world (a map change) must not open a second one. */
	bool GWindowStartedThisProcess = false;
}

FTTProbeOptions FTTProbeOptions::FromCommandLine(const TCHAR* CommandLine)
{
	const FTTProbeOptions Defaults;
	FTTProbeOptions Read;
	Read.bEnabled = FParse::Param(CommandLine, TEXT("TTProbe"));
	FParse::Value(CommandLine, TEXT("TTWarmup="), Read.WarmupSeconds);
	FParse::Value(CommandLine, TEXT("TTCapture="), Read.CaptureSeconds);
	FParse::Value(CommandLine, TEXT("TTInjectMs="), Read.Injection.Milliseconds);
	FParse::Value(CommandLine, TEXT("TTInjectEvery="), Read.Injection.Every);
	FParse::Value(CommandLine, TEXT("TTRunTag="), Read.RunTag, /*bShouldStopOnSeparator*/ false);
	Read.bExitWhenDone = FParse::Param(CommandLine, TEXT("TTExit"));

	Read.WarmupSeconds = TTProbe::ClampFinite(Read.WarmupSeconds, Defaults.WarmupSeconds, TTProbe::MaxWindowSeconds);
	Read.CaptureSeconds = TTProbe::ClampFinite(Read.CaptureSeconds, Defaults.CaptureSeconds, TTProbe::MaxWindowSeconds);
	Read.Injection.Milliseconds = TTProbe::ClampFinite(Read.Injection.Milliseconds, 0.0, TTProbe::MaxInjectMs);
	Read.Injection.Every = FMath::Max(1, Read.Injection.Every);
	return Read;
}

bool UTTProbeSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	// Not a gate run: no subsystem at all, so a normal game pays nothing for the plugin (not even a tick).
	return Super::ShouldCreateSubsystem(Outer) && FParse::Param(FCommandLine::Get(), TEXT("TTProbe"));
}

bool UTTProbeSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	// Game worlds only. In PIE, -TTExit would quit the whole editor, and every PIE client would open its own window.
	return WorldType == EWorldType::Game;
}

void UTTProbeSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);

	if (TTProbe::GWindowStartedThisProcess)
	{
		UE_LOG(LogTTProbe, Display, TEXT("Probe already ran its window in an earlier world of this process; inactive here."));
		return;
	}
	TTProbe::GWindowStartedThisProcess = true;

	Options = FTTProbeOptions::FromCommandLine(FCommandLine::Get());
	Window.WarmupSeconds = Options.WarmupSeconds;
	Window.CaptureSeconds = Options.CaptureSeconds;
	bRunning = true;

	// The run's description inside the capture itself, so every CSV is self-describing.
	CSV_METADATA(TEXT("TTRunTag"), *Options.RunTag);
	CSV_METADATA(TEXT("TTWarmup"), *FString::SanitizeFloat(Options.WarmupSeconds));
	CSV_METADATA(TEXT("TTCapture"), *FString::SanitizeFloat(Options.CaptureSeconds));
	CSV_METADATA(TEXT("TTInjectMs"), *FString::SanitizeFloat(Options.Injection.Milliseconds));
	CSV_METADATA(TEXT("TTInjectEvery"), *FString::FromInt(Options.Injection.Every));

	UE_LOG(LogTTProbe, Display, TEXT("Probe active: warm-up %.3f s, capture %.3f s, inject %.3f ms every %d frame(s), tag '%s'"),
		Options.WarmupSeconds, Options.CaptureSeconds, Options.Injection.Milliseconds, Options.Injection.Every, *Options.RunTag);
}

void UTTProbeSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (!bRunning)
	{
		return;
	}

	// The injected cost runs on the game thread inside the frame, so it is part of GameThreadTime (01b #12).
	// From the first frame to BenchEnd: the warm-up reaches the injected steady state; nothing after the window.
	if (!Window.IsDone() && Options.Injection.ShouldInject(FrameIndex))
	{
		CSV_SCOPED_TIMING_STAT(TestTrustProbe, Injected);
		FTTInjectionSchedule::Spin(Options.Injection.Milliseconds);
	}
	++FrameIndex;

	switch (Window.Advance(DeltaTime))
	{
	case ETTProbeEvent::Start:
		// The capture starts at the next frame, so logging here costs nothing that is measured.
		CSV_EVENT(TestTrustProbe, TEXT("BenchStart"));
		UE_LOG(LogTTProbe, Display, TEXT("BenchStart on frame %lld (world time %.3f s)"), FrameIndex, GetWorld()->GetTimeSeconds());
		break;

	case ETTProbeEvent::Stop:
		// This frame is the last captured one: no log line here (CSV_EVENT would log one, CsvProfiler.cpp:4797).
		CSV_EVENT_NOLOG(TestTrustProbe, TEXT("BenchEnd"));
		EndFrame = GFrameCounter;
		break;

	default:
		if (Window.IsDone())
		{
			const uint64 FramesSinceEnd = GFrameCounter - EndFrame;
			if (FramesSinceEnd == 1)
			{
				UE_LOG(LogTTProbe, Display, TEXT("BenchEnd on frame %lld after %d captured frames"), FrameIndex - 1, Window.GetCapturedFrames());
			}
			if (Options.bExitWhenDone && FramesSinceEnd == TTProbe::ExitDelayFrames)
			{
				FPlatformMisc::RequestExit(false, TEXT("UTTProbeSubsystem"));
			}
		}
		break;
	}
}

TStatId UTTProbeSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UTTProbeSubsystem, STATGROUP_Tickables);
}
