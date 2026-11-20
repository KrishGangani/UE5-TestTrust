// P03 TestTrust - sample module: small, pure gameplay rules plus their automation tests.
// It exists so the mutation runner has a target of known size inside this repository (Phase 4 smoke test, M-S).
// Nothing else depends on it, so mutating it can never break the perf-gate workload.

using UnrealBuildTool;

public class TestTrustSample : ModuleRules
{
	public TestTrustSample(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Core is enough: the rules use only FVector and FMath, and the tests use the Core automation framework.
		PublicDependencyModuleNames.AddRange(new string[] { "Core" });
	}
}
