// P03 TestTrust - the perf-gate workload: one agent's "sense -> decide -> act" update, every frame (02 section 4.2).
// Copied and adapted from UE5-UpdateBudget's UUBDemoBrainComponent (commit b890bc6): the same logic and calibration
// knob, but a plain UActorComponent with a native tick, because the gate only needs a deterministic, game-thread-bound
// workload, not a budget scheduler.

#pragma once

#include "Components/ActorComponent.h"
#include "TTWorkloadBrainComponent.generated.h"

/** What the agent is doing. */
UENUM()
enum class ETTBrainState : uint8
{
	Patrol,
	Alert
};

/**
 * Deterministic stand-in for AI-style gameplay logic, run every frame in TG_PrePhysics:
 *  - sense:  distance and view-cone check against the player's camera;
 *  - decide: Patrol <-> Alert;
 *  - act:    move along a patrol circle (a closed-form function of the accumulated patrol time) and face the
 *            walking direction or the player;
 *  - a calibrated compute step standing in for heavier logic.
 * Under -deterministic every run receives the same deltas, so every run simulates the same frames.
 */
UCLASS(ClassGroup = (TestTrust))
class UTTWorkloadBrainComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UTTWorkloadBrainComponent();

	/** Sets the patrol circle. Call before the owning actor finishes spawning. */
	void InitPatrol(const FVector& InCenter, double InPhaseRadians);

	/** Sets the size of the compute step (loop iterations per update). */
	void SetComputeIterations(int32 InIterations) { ComputeIterations = FMath::Max(0, InIterations); }
	int32 GetComputeIterations() const { return ComputeIterations; }

	/** Position on the patrol circle after TotalTime seconds of patrol. */
	FVector GetPatrolPosition(double TotalTime) const;

	int32 GetStateChanges() const { return StateChanges; }

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	double GetPatrolAngle(double TotalTime) const { return PhaseRadians + PatrolAngularSpeed * TotalTime; }

	/** Radius of the patrol circle, in cm. */
	UPROPERTY(EditAnywhere, Category = "Workload", meta = (ClampMin = "0"))
	float PatrolRadius = 300.f;

	/** Patrol speed in radians per second (0.5 rad/s at 3 m radius = 1.5 m/s walking pace). */
	UPROPERTY(EditAnywhere, Category = "Workload")
	float PatrolAngularSpeed = 0.5f;

	/** The agent notices the player within this distance, in cm... */
	UPROPERTY(EditAnywhere, Category = "Workload", meta = (ClampMin = "0"))
	float AlertRadius = 1500.f;

	/** ...and only inside this cone around its forward direction (cosine: 0.5 = 60 degrees). */
	UPROPERTY(EditAnywhere, Category = "Workload", meta = (ClampMin = "-1", ClampMax = "1"))
	float AlertConeCos = 0.5f;

	/** Loop iterations of the stand-in compute step; calibrated in S2 so the frame is game-thread bound (09, S2). */
	UPROPERTY(EditAnywhere, Category = "Workload", meta = (ClampMin = "0"))
	int32 ComputeIterations = 128;

	FVector PatrolCenter = FVector::ZeroVector;
	double PhaseRadians = 0.0;
	double PatrolTime = 0.0;
	ETTBrainState State = ETTBrainState::Patrol;
	int32 StateChanges = 0;

	/** Result of the compute step, stored so the optimiser cannot remove the work. */
	float ComputeSink = 0.f;
};
