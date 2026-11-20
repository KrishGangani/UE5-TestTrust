// P03 TestTrust - ATTWorkloadAgent.

#include "TTWorkloadAgent.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "TTWorkloadBrainComponent.h"
#include "UObject/ConstructorHelpers.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(TTWorkloadAgent)

ATTWorkloadAgent::ATTWorkloadAgent()
{
	// The actor itself has no per-frame work.
	PrimaryActorTick.bCanEverTick = false;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetCastShadow(false);
	Mesh->SetRelativeScale3D(FVector(0.5)); // A 50 cm cube.

	// Engine content, cooked through DirectoriesToAlwaysCook in DefaultGame.ini. The finder is static: the lookup
	// runs once per class, not once per constructed agent.
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		Mesh->SetStaticMesh(CubeMesh.Object);
	}

	Brain = CreateDefaultSubobject<UTTWorkloadBrainComponent>(TEXT("Brain"));
}
