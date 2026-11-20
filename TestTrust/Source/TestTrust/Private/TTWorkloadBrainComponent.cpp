// P03 TestTrust - UTTWorkloadBrainComponent.

#include "TTWorkloadBrainComponent.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(TTWorkloadBrainComponent)

UTTWorkloadBrainComponent::UTTWorkloadBrainComponent()
{
	// Components don't tick unless asked (bCanEverTick defaults to false), and default to TG_DuringPhysics; the
	// workload runs in TG_PrePhysics like UE5-UpdateBudget's native baseline, before physics and the probe's tick.
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void UTTWorkloadBrainComponent::InitPatrol(const FVector& InCenter, double InPhaseRadians)
{
	PatrolCenter = InCenter;
	PhaseRadians = InPhaseRadians;
	PatrolTime = 0.0;
}

FVector UTTWorkloadBrainComponent::GetPatrolPosition(double TotalTime) const
{
	const double Angle = GetPatrolAngle(TotalTime);
	return PatrolCenter + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0) * PatrolRadius;
}

void UTTWorkloadBrainComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// Accumulated time: the patrol position is a closed-form function of it, so it is the same in every run.
	PatrolTime += DeltaTime;

	// Position and walking direction from one angle (the tangent of a counter-clockwise circle).
	const double Angle = GetPatrolAngle(PatrolTime);
	const double Cos = FMath::Cos(Angle);
	const double Sin = FMath::Sin(Angle);
	const FVector Position = PatrolCenter + FVector(Cos, Sin, 0.0) * PatrolRadius;
	const FVector Forward(-Sin, Cos, 0.0);

	// Sense: can this agent see the player's camera? Asked per agent, as real perception code would.
	FVector ToPlayer = FVector::ZeroVector;
	bool bSeesPlayer = false;
	const APlayerController* PlayerController = GetWorld()->GetFirstPlayerController();
	if (const APlayerCameraManager* CameraManager = PlayerController ? PlayerController->PlayerCameraManager.Get() : nullptr)
	{
		ToPlayer = CameraManager->GetCameraLocation() - Position;
		const double DistanceSquared = ToPlayer.SizeSquared();
		// Cone test without normalising: dot(F, v) > cos * |v| is the same as dot(F, v / |v|) > cos.
		bSeesPlayer = DistanceSquared < FMath::Square(AlertRadius)
			&& FVector::DotProduct(Forward, ToPlayer) > AlertConeCos * FMath::Sqrt(DistanceSquared);
	}

	// Decide.
	const ETTBrainState NewState = bSeesPlayer ? ETTBrainState::Alert : ETTBrainState::Patrol;
	if (NewState != State)
	{
		State = NewState;
		++StateChanges;
	}

	// Act: one transform update per frame (location and rotation together).
	const FVector FacingDirection = (State == ETTBrainState::Alert) ? ToPlayer : Forward;
	GetOwner()->SetActorLocationAndRotation(Position, FacingDirection.Rotation());

	// Stand-in for heavier logic: a fixed amount of floating-point work, stored so it can't be optimised away.
	float Sink = ComputeSink;
	for (int32 Iteration = 0; Iteration < ComputeIterations; ++Iteration)
	{
		Sink = FMath::Fmod(Sink * 1.000123f + FMath::Sin(Sink + static_cast<float>(Iteration)), 1000.f);
	}
	ComputeSink = Sink;
}
