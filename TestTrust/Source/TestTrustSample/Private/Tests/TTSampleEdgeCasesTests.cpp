// P03 TestTrust (sample) - automation tests for FTTSampleEdgeCases. Run: Tools\run_tests.bat StartsWith:TestTrust.Sample.Edge

#include "Misc/AutomationTest.h"
#include "TTSampleEdgeCases.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace TTSampleEdgeTests
{
	// Its own namespace: in a unity build this file and TTSampleRulesTests.cpp can share one translation unit.
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleEdgeTotalPriceTest, "TestTrust.Sample.Edge.TotalPrice", TTSampleEdgeTests::Flags)
bool FTTSampleEdgeTotalPriceTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("3 items at 2.50 plus a 1.00 fee"), FTTSampleEdgeCases::TotalPrice(FTTSampleMoney{ 250 }, 3, FTTSampleMoney{ 100 }).Cents, 850);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleEdgeTicksTest, "TestTrust.Sample.Edge.TicksToDrain", TTSampleEdgeTests::Flags)
bool FTTSampleEdgeTicksTest::RunTest(const FString& Parameters)
{
	// 0.25 is an exact binary fraction, so 1.0 reaches exactly 0.0 after four steps.
	TestEqual(TEXT("1.0 in steps of 0.25"), FTTSampleEdgeCases::TicksToDrain(1.0f, 0.25f), 4);
	TestEqual(TEXT("nothing to drain"), FTTSampleEdgeCases::TicksToDrain(0.0f, 0.25f), 0);
	return true;
}

#endif
