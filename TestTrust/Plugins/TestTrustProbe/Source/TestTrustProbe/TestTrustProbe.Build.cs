// TestTrustProbe - the reusable runtime module (capture window, run metadata, regression injector; Phase 5).
// It must not depend on any game module, so any project can drop it in.

using UnrealBuildTool;

public class TestTrustProbe : ModuleRules
{
	public TestTrustProbe(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
	}
}
