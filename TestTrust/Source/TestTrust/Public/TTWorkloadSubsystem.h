// P03 TestTrust - UTTWorkloadSubsystem: spawns the deterministic perf-gate workload and drives its camera (02 section 4.2).
// Adapted from UE5-UpdateBudget's UUBBenchmarkSubsystem (commit b890bc6): seeded grid spawn and an analytic camera
// path; the capture window, metadata and exit now belong to the TestTrustProbe plugin.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "TTWorkloadSubsystem.generated.h"

class ACameraActor;
class ATTWorkloadAgent;

/** Workload options, read once from the command line. */
struct FTTWorkloadOptions
{
	int32 NumAgents = 0;			// -TTAgents=<N>; 0 = no workload (a normal empty map)
	int32 Seed = 1;					// -TTSeed=<n>
	int32 ComputeIterations = 0;	// -TTWork=<iterations>, at least 0; default: the brain component's calibrated value

	static FTTWorkloadOptions FromCommandLine(const TCHAR* CommandLine);
};

UCLASS()
class UTTWorkloadSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

private:
	/** Spawns Options.NumAgents agents on a jittered grid from Options.Seed. Returns a CRC of their start positions. */
	uint32 SpawnAgents(UWorld& World);

	/** CRC of every agent's location, rotation and state-change count: equal in two runs only if they simulated the same
	 *  frames and made the same decisions. OutStateChanges is the sum of all agents' state changes. */
	uint32 HashState(int32& OutStateChanges) const;

	/** Moves the camera along a fixed circle, one lap per TTWorkload::CameraLapSeconds of world time. */
	void UpdateCamera(double SecondsSinceBeginPlay);

	UPROPERTY()
	TArray<TObjectPtr<ATTWorkloadAgent>> Agents;

	UPROPERTY()
	TObjectPtr<ACameraActor> Camera;

	FTTWorkloadOptions Options;
	double BeginPlayTime = 0.0;
	double CameraRadius = 0.0;
	bool bEndReported = false;
};
