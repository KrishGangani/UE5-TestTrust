// TestTrustProbe - automation tests for the window and injection arithmetic and the option parsing (no world needed).
// Run: Tools\run_tests.bat StartsWith:TestTrust.Probe

#include "Misc/AutomationTest.h"
#include "TTProbeSubsystem.h"
#include "TTProbeWindow.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace TTProbeTests
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter;

	/** The fixed step the engine really hands out for -FPS=60: 1/60 rounded to float (UE5-UpdateBudget's 01b B-1). */
	const double FixedStep60 = static_cast<double>(1.0f / 60.0f);

	struct FWindowTrace
	{
		int32 StartFrame = -1;	// 1-based frame number that returned Start
		int32 StopFrame = -1;	// 1-based frame number that returned Stop
		int32 Events = 0;		// total non-None results
	};

	/** Advances a window for up to MaxFrames, frame N (1-based) getting DeltaOf(N), and records where its events landed. */
	FWindowTrace Run(FTTProbeWindow& Window, TFunctionRef<double(int32 Frame)> DeltaOf, int32 MaxFrames)
	{
		FWindowTrace Trace;
		for (int32 Frame = 1; Frame <= MaxFrames; ++Frame)
		{
			const ETTProbeEvent Event = Window.Advance(DeltaOf(Frame));
			if (Event == ETTProbeEvent::Start)
			{
				Trace.StartFrame = Frame;
			}
			else if (Event == ETTProbeEvent::Stop)
			{
				Trace.StopFrame = Frame;
			}
			Trace.Events += (Event != ETTProbeEvent::None) ? 1 : 0;
		}
		return Trace;
	}

	/** The same with a constant delta. */
	FWindowTrace Run(FTTProbeWindow& Window, double Delta, int32 MaxFrames)
	{
		return Run(Window, [Delta](int32) { return Delta; }, MaxFrames);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTProbeWindowFixedStepTest, "TestTrust.Probe.Window.FixedStepFrames", TTProbeTests::Flags)
bool FTTProbeWindowFixedStepTest::RunTest(const FString& Parameters)
{
	// 5 s warm-up and 20 s capture at the engine's float 1/60 s step: exactly 300 and 1,200 frames.
	FTTProbeWindow Window;
	Window.WarmupSeconds = 5.0;
	Window.CaptureSeconds = 20.0;
	const TTProbeTests::FWindowTrace Trace = TTProbeTests::Run(Window, TTProbeTests::FixedStep60, 2000);

	TestEqual(TEXT("Start on frame 300"), Trace.StartFrame, 300);
	TestEqual(TEXT("Stop 1200 frames later"), Trace.StopFrame, 1500);
	TestEqual(TEXT("captured frames"), Window.GetCapturedFrames(), 1200);
	TestEqual(TEXT("exactly two events"), Trace.Events, 2);
	TestTrue(TEXT("done"), Window.IsDone());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTProbeWindowZeroWarmupTest, "TestTrust.Probe.Window.ZeroWarmup", TTProbeTests::Flags)
bool FTTProbeWindowZeroWarmupTest::RunTest(const FString& Parameters)
{
	FTTProbeWindow Window;
	Window.WarmupSeconds = 0.0;
	Window.CaptureSeconds = 0.1;
	const TTProbeTests::FWindowTrace Trace = TTProbeTests::Run(Window, TTProbeTests::FixedStep60, 100);

	TestEqual(TEXT("Start on the first frame"), Trace.StartFrame, 1);
	TestEqual(TEXT("0.1 s = 6 frames of capture"), Window.GetCapturedFrames(), 6);
	TestEqual(TEXT("Stop on frame 7"), Trace.StopFrame, 7);

	// The documented minimum: a zero-length capture still contains its Stop frame.
	FTTProbeWindow Empty;
	Empty.WarmupSeconds = 0.0;
	Empty.CaptureSeconds = 0.0;
	const TTProbeTests::FWindowTrace EmptyTrace = TTProbeTests::Run(Empty, TTProbeTests::FixedStep60, 10);
	TestEqual(TEXT("0 s capture: Stop one frame after Start"), EmptyTrace.StopFrame, 2);
	TestEqual(TEXT("0 s capture: one captured frame"), Empty.GetCapturedFrames(), 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTProbeWindowVariableStepTest, "TestTrust.Probe.Window.VariableStep", TTProbeTests::Flags)
bool FTTProbeWindowVariableStepTest::RunTest(const FString& Parameters)
{
	// Real-time runs: alternating 10 ms (odd frames) and 30 ms (even frames). Elapsed + half a frame after frames 1..6:
	// 0.015, 0.055, 0.055, 0.095, 0.095, 0.135, so the 0.1 s warm-up ends on frame 6; the capture repeats the pattern
	// and ends on frame 12. (Values chosen with a clear margin: 10/20 ms would put a sum exactly on 0.1 s, a float tie.)
	FTTProbeWindow Window;
	Window.WarmupSeconds = 0.1;
	Window.CaptureSeconds = 0.1;
	const TTProbeTests::FWindowTrace Trace = TTProbeTests::Run(Window, [](int32 Frame) { return (Frame % 2 == 1) ? 0.010 : 0.030; }, 40);
	TestEqual(TEXT("Start on frame 6"), Trace.StartFrame, 6);
	TestEqual(TEXT("Stop on frame 12"), Trace.StopFrame, 12);
	TestEqual(TEXT("exactly two events"), Trace.Events, 2);
	TestEqual(TEXT("captured frames"), Window.GetCapturedFrames(), 6);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTProbeWindowNegativeDeltaTest, "TestTrust.Probe.Window.IgnoresNegativeDelta", TTProbeTests::Flags)
bool FTTProbeWindowNegativeDeltaTest::RunTest(const FString& Parameters)
{
	FTTProbeWindow Window;
	Window.WarmupSeconds = 0.05;
	Window.CaptureSeconds = 1.0;
	TestEqual(TEXT("time never runs backwards into the window"), TTProbeTests::Run(Window, -0.1, 100).Events, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTProbeInjectionScheduleTest, "TestTrust.Probe.Injection.Schedule", TTProbeTests::Flags)
bool FTTProbeInjectionScheduleTest::RunTest(const FString& Parameters)
{
	FTTInjectionSchedule Off;
	TestFalse(TEXT("0 ms never injects"), Off.ShouldInject(0));

	FTTInjectionSchedule EveryFrame;
	EveryFrame.Milliseconds = 0.25;
	TestTrue(TEXT("frame 0"), EveryFrame.ShouldInject(0));
	TestTrue(TEXT("frame 1"), EveryFrame.ShouldInject(1));

	FTTInjectionSchedule EveryThird;
	EveryThird.Milliseconds = 1.0;
	EveryThird.Every = 3;
	TestTrue(TEXT("frame 0"), EveryThird.ShouldInject(0));
	TestFalse(TEXT("frame 1"), EveryThird.ShouldInject(1));
	TestFalse(TEXT("frame 2"), EveryThird.ShouldInject(2));
	TestTrue(TEXT("frame 3"), EveryThird.ShouldInject(3));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTProbeInjectionSpinTest, "TestTrust.Probe.Injection.Spin", TTProbeTests::Flags)
bool FTTProbeInjectionSpinTest::RunTest(const FString& Parameters)
{
	// The spin must never be shorter than asked. The upper bound is loose on purpose: a test must not be flaky because
	// Windows preempted the thread once.
	const double Spent = FTTInjectionSchedule::Spin(0.5);
	TestTrue(TEXT("at least 0.5 ms"), Spent >= 0.5);
	TestTrue(TEXT("well under 50 ms"), Spent < 50.0);
	TestTrue(TEXT("0 ms returns at once"), FTTInjectionSchedule::Spin(0.0) < 1.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTProbeOptionsParseTest, "TestTrust.Probe.Options.Parse", TTProbeTests::Flags)
bool FTTProbeOptionsParseTest::RunTest(const FString& Parameters)
{
	const FTTProbeOptions Full = FTTProbeOptions::FromCommandLine(
		TEXT("Game.uproject -TTProbe -TTWarmup=2 -TTCapture=3.5 -TTInjectMs=0.25 -TTInjectEvery=4 -TTRunTag=abc -TTExit"));
	TestTrue(TEXT("enabled"), Full.bEnabled);
	TestEqual(TEXT("warm-up"), Full.WarmupSeconds, 2.0);
	TestEqual(TEXT("capture"), Full.CaptureSeconds, 3.5);
	TestEqual(TEXT("inject ms"), Full.Injection.Milliseconds, 0.25);
	TestEqual(TEXT("inject every"), Full.Injection.Every, 4);
	TestEqual(TEXT("run tag"), Full.RunTag, FString(TEXT("abc")));
	TestTrue(TEXT("exit"), Full.bExitWhenDone);

	const FTTProbeOptions Clamped = FTTProbeOptions::FromCommandLine(TEXT("-TTProbe -TTWarmup=-1 -TTInjectMs=500 -TTInjectEvery=0"));
	TestEqual(TEXT("negative warm-up becomes 0"), Clamped.WarmupSeconds, 0.0);
	TestEqual(TEXT("injection capped at 100 ms"), Clamped.Injection.Milliseconds, 100.0);
	TestEqual(TEXT("every at least 1"), Clamped.Injection.Every, 1);
	TestFalse(TEXT("no exit unless asked"), Clamped.bExitWhenDone);

	const FTTProbeOptions NotFinite = FTTProbeOptions::FromCommandLine(TEXT("-TTProbe -TTWarmup=inf -TTCapture=nan -TTRunTag=B0,N2000,r1"));
	TestEqual(TEXT("infinite warm-up falls back to the default"), NotFinite.WarmupSeconds, FTTProbeOptions().WarmupSeconds);
	TestEqual(TEXT("NaN capture falls back to the default"), NotFinite.CaptureSeconds, FTTProbeOptions().CaptureSeconds);
	TestEqual(TEXT("a run tag keeps its commas"), NotFinite.RunTag, FString(TEXT("B0,N2000,r1")));

	const FTTProbeOptions Off = FTTProbeOptions::FromCommandLine(TEXT("-TTWarmup=2 -TTInjectMs=1"));
	TestFalse(TEXT("off without -TTProbe"), Off.bEnabled);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
