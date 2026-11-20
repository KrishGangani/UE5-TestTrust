// P03 TestTrust (sample) - automation tests for FTTSampleRules. Run: Tools\run_tests.bat (filter TestTrust.Sample).
// The mutation runner never mutates this folder (Tests/ is excluded by its configuration).
//
// DELIBERATE GAP: no test puts a target exactly at the range limit, so the mutant "<= becomes <" in IsInRange must
// survive. The Phase 4 smoke test checks that the runner reports it (09, P4 runner smoke test); Phase 7 adds the test.

#include "Misc/AutomationTest.h"
#include "TTSampleRules.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace TTSampleTests
{
	// Editor and client contexts, so the tests run both in the editor and in -game; Product = project-level tests.
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleDamageArmorTest, "TestTrust.Sample.Damage.ArmorSubtracts", TTSampleTests::Flags)
bool FTTSampleDamageArmorTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("10 damage against 3 armour"), FTTSampleRules::ComputeDamage(10, 3, false), 7);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleDamageCriticalTest, "TestTrust.Sample.Damage.CriticalDoubles", TTSampleTests::Flags)
bool FTTSampleDamageCriticalTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("critical 10 against 3 armour"), FTTSampleRules::ComputeDamage(10, 3, true), 14);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleDamageMinimumTest, "TestTrust.Sample.Damage.NeverBelowMinimum", TTSampleTests::Flags)
bool FTTSampleDamageMinimumTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("armour larger than the hit"), FTTSampleRules::ComputeDamage(2, 5, false), FTTSampleRules::MinDamage);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleRangeTest, "TestTrust.Sample.Range.InsideAndOutside", TTSampleTests::Flags)
bool FTTSampleRangeTest::RunTest(const FString& Parameters)
{
	TestTrue(TEXT("5 units away, range 10"), FTTSampleRules::IsInRange(FVector::ZeroVector, FVector(5.0, 0.0, 0.0), 10.0));
	TestFalse(TEXT("20 units away, range 10"), FTTSampleRules::IsInRange(FVector::ZeroVector, FVector(20.0, 0.0, 0.0), 10.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleCooldownTest, "TestTrust.Sample.Cooldown.CountsDown", TTSampleTests::Flags)
bool FTTSampleCooldownTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("1.0 s after 0.25 s"), FTTSampleRules::TickCooldown(1.0f, 0.25f), 0.75f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FTTSampleCooldownZeroTest, "TestTrust.Sample.Cooldown.StopsAtZero", TTSampleTests::Flags)
bool FTTSampleCooldownZeroTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("0.1 s after 0.5 s"), FTTSampleRules::TickCooldown(0.1f, 0.5f), 0.0f);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
