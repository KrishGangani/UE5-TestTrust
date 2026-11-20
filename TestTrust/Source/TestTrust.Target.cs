// P03 TestTrust - game target (standalone/packaged builds: the perf-gate workload runs in this one).

using UnrealBuildTool;

public class TestTrustTarget : TargetRules
{
	public TestTrustTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		ExtraModuleNames.AddRange(new string[] { "TestTrust", "TestTrustSample" });
	}
}
