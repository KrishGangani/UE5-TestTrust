// TestTrustProbe - FTTProbeWindow and FTTInjectionSchedule: the arithmetic of a gate run, with no UObject and no world,
// so automation tests can step it frame by frame (02 section 4.2).

#pragma once

#include "CoreMinimal.h"

#define UE_API TESTTRUSTPROBE_API

/** What the probe must do on the frame that was just advanced. */
enum class ETTProbeEvent : uint8
{
	None,
	Start,	// fire BenchStart: the capture window opens on this frame
	Stop	// fire BenchEnd: the capture window closes on this frame
};

/**
 * A warm-up, then a capture window of fixed length, both measured in the frames' own delta times.
 * A boundary counts as reached once the elapsed time is within half a frame of it. A fixed 1/60 s step reaches the
 * engine as a float (0.016666668 s), so plain ">=" could land one frame early or late; with the half-frame rule the
 * window opens after exactly round(WarmupSeconds / Delta) frames and lasts exactly round(CaptureSeconds / Delta) frames.
 * A capture always contains at least one frame (the Stop frame), so CaptureSeconds = 0 captures one frame.
 */
struct FTTProbeWindow
{
	double WarmupSeconds = 5.0;
	double CaptureSeconds = 20.0;

	/** Call once per frame with that frame's delta. Returns Start, then Stop, exactly once each; None otherwise. */
	UE_API ETTProbeEvent Advance(double DeltaSeconds);

	bool IsDone() const { return Phase == EPhase::Done; }

	/** Frames advanced after the Start frame, up to and including the Stop frame. */
	int32 GetCapturedFrames() const { return CapturedFrames; }

private:
	enum class EPhase : uint8
	{
		Warmup,
		Capture,
		Done
	};

	EPhase Phase = EPhase::Warmup;
	double PhaseElapsed = 0.0;
	int32 CapturedFrames = 0;
};

/** A known, repeatable game-thread cost: Milliseconds of busy-waiting on every Every-th frame (frame 0 included). */
struct FTTInjectionSchedule
{
	double Milliseconds = 0.0;
	int32 Every = 1;

	bool IsActive() const { return Milliseconds > 0.0; }

	/** True if the frame with this index (0 = first ticked frame) gets the injected cost. */
	UE_API bool ShouldInject(int64 FrameIndex) const;

	/** Busy-waits on the calling thread for Milliseconds of wall time. Returns the time actually spent, in ms. */
	static UE_API double Spin(double Milliseconds);
};

#undef UE_API
