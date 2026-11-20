// TestTrustProbe - FTTProbeWindow and FTTInjectionSchedule.

#include "TTProbeWindow.h"

#include "HAL/PlatformTime.h"

ETTProbeEvent FTTProbeWindow::Advance(double DeltaSeconds)
{
	if (Phase == EPhase::Done)
	{
		return ETTProbeEvent::None;
	}

	const double Step = FMath::Max(DeltaSeconds, 0.0);
	const double HalfFrame = 0.5 * Step;
	PhaseElapsed += Step;

	if (Phase == EPhase::Warmup)
	{
		if (PhaseElapsed + HalfFrame >= WarmupSeconds)
		{
			Phase = EPhase::Capture;
			PhaseElapsed = 0.0;
			return ETTProbeEvent::Start;
		}
		return ETTProbeEvent::None;
	}

	++CapturedFrames;
	if (PhaseElapsed + HalfFrame >= CaptureSeconds)
	{
		Phase = EPhase::Done;
		return ETTProbeEvent::Stop;
	}
	return ETTProbeEvent::None;
}

bool FTTInjectionSchedule::ShouldInject(int64 FrameIndex) const
{
	return IsActive() && (Every <= 1 || FrameIndex % Every == 0);
}

double FTTInjectionSchedule::Spin(double Milliseconds)
{
	// Wall time, not a loop count: the cost is the same at any CPU clock, which is what makes the injected size known.
	// The loop compares the same expression it returns, so the result can't come out a rounding error short.
	const double Start = FPlatformTime::Seconds();
	double SpentMs = 0.0;
	while (SpentMs < Milliseconds)
	{
		SpentMs = (FPlatformTime::Seconds() - Start) * 1000.0;
	}
	return SpentMs;
}
