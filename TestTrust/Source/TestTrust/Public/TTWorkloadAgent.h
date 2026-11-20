// P03 TestTrust - one workload agent: a visible mesh plus its brain (adapted from UE5-UpdateBudget's AUBDemoAgent).

#pragma once

#include "GameFramework/Actor.h"
#include "TTWorkloadAgent.generated.h"

class UStaticMeshComponent;
class UTTWorkloadBrainComponent;

/** A minimal agent. The actor itself never ticks: all per-frame work lives in its brain component. */
UCLASS()
class ATTWorkloadAgent : public AActor
{
	GENERATED_BODY()

public:
	ATTWorkloadAgent();

	UTTWorkloadBrainComponent* GetBrain() const { return Brain; }

private:
	/** A small cube so agents are visible. No collision: the workload measures gameplay logic, not physics. */
	UPROPERTY(VisibleAnywhere, Category = "Agent")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, Category = "Agent")
	TObjectPtr<UTTWorkloadBrainComponent> Brain;
};
