// P03 TestTrust - primary game module: the deterministic perf-gate workload and its benchmark director (Phase 5).
// The reusable capture/injection code lives in the TestTrustProbe plugin; this module depends on it, never the reverse.

using UnrealBuildTool;

public class TestTrust : ModuleRules
{
	public TestTrust(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });

		// The probe is private: no public header of this module exposes a probe type.
		PrivateDependencyModuleNames.AddRange(new string[] { "TestTrustProbe" });
	}
}
