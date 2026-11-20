// P03 TestTrust - editor target (the mutation runner builds this one: modular, so a mutant relinks one module DLL).

using UnrealBuildTool;

public class TestTrustEditorTarget : TargetRules
{
	public TestTrustEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		ExtraModuleNames.AddRange(new string[] { "TestTrust", "TestTrustSample" });
	}
}
