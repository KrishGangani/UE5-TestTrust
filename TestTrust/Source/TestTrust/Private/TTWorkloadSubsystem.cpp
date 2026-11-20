// P03 TestTrust - UTTWorkloadSubsystem.

#include "TTWorkloadSubsystem.h"

#include "Camera/CameraActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "Math/RandomStream.h"
#include "Misc/CommandLine.h"
#include "Misc/Crc.h"
#include "Misc/Parse.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "Stats/Stats.h"
#include "TTProbeSubsystem.h"
#include "TTWorkloadAgent.h"
#include "TTWorkloadBrainComponent.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(TTWorkloadSubsystem)

DEFINE_LOG_CATEGORY_STATIC(LogTTWorkload, Log, All);

namespace TTWorkload
{
	/** Distance between grid cells, in cm (4 m: 1,000 agents fit in a 124 m square). */
	constexpr double GridSpacing = 400.0;
	/** Random offset of each grid cell, in cm, so the layout isn't perfectly regular. */
	constexpr double GridJitter = 100.0;
	/** Height of agent centres: the 50 cm cubes rest on the floor at z = 0. */
	constexpr double AgentHeight = 25.0;
	/** Camera path: a circle at half the arena's half-width (at least 15 m), 4 m up, pitched down 15 degrees. */
	constexpr double CameraHeight = 400.0;
	constexpr double CameraMinRadius = 1500.0;
	constexpr double CameraPitchDegrees = -15.0;
	/** One camera lap per 20 s of world time, from BeginPlay: the path depends only on time, never on the run. */
	constexpr double CameraLapSeconds = 20.0;

	/** Half the width of the square grid that holds Count agents, from the centre row to the outer row, in cm. */
	double ArenaHalfExtent(int32 Count)
	{
		const int32 Side = FMath::CeilToInt32(FMath::Sqrt(static_cast<double>(Count)));
		return 0.5 * GridSpacing * (Side - 1);
	}
}

FTTWorkloadOptions FTTWorkloadOptions::FromCommandLine(const TCHAR* CommandLine)
{
	FTTWorkloadOptions Read;
	Read.ComputeIterations = GetDefault<UTTWorkloadBrainComponent>()->GetComputeIterations();
	FParse::Value(CommandLine, TEXT("TTAgents="), Read.NumAgents);
	FParse::Value(CommandLine, TEXT("TTSeed="), Read.Seed);
	FParse::Value(CommandLine, TEXT("TTWork="), Read.ComputeIterations);
	Read.NumAgents = FMath::Clamp(Read.NumAgents, 0, 20000);
	Read.ComputeIterations = FMath::Max(0, Read.ComputeIterations);
	return Read;
}

bool UTTWorkloadSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	// No workload requested: no subsystem at all, so a normal game or PIE session pays nothing for it.
	return Super::ShouldCreateSubsystem(Outer) && FTTWorkloadOptions::FromCommandLine(FCommandLine::Get()).NumAgents > 0;
}

bool UTTWorkloadSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UTTWorkloadSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);

	Options = FTTWorkloadOptions::FromCommandLine(FCommandLine::Get());

	const double SpawnStart = FPlatformTime::Seconds();
	const uint32 StartHash = SpawnAgents(InWorld);
	UE_LOG(LogTTWorkload, Display, TEXT("Spawned %d agents (seed %d, work %d) in %.1f ms; start-position hash 0x%08X"),
		Agents.Num(), Options.Seed, Options.ComputeIterations, (FPlatformTime::Seconds() - SpawnStart) * 1000.0, StartHash);

	Camera = InWorld.SpawnActor<ACameraActor>();
	BeginPlayTime = InWorld.GetTimeSeconds();
	CameraRadius = FMath::Max(TTWorkload::CameraMinRadius, 0.5 * TTWorkload::ArenaHalfExtent(Options.NumAgents));

	// The workload's parameters inside the capture itself, next to the probe's (TTRunTag, TTInjectMs, ...).
	CSV_METADATA(TEXT("TTAgents"), *FString::FromInt(Agents.Num()));
	CSV_METADATA(TEXT("TTSeed"), *FString::FromInt(Options.Seed));
	CSV_METADATA(TEXT("TTWork"), *FString::FromInt(Options.ComputeIterations));
}

void UTTWorkloadSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (Agents.IsEmpty())
	{
		return;
	}

	UpdateCamera(GetWorld()->GetTimeSeconds() - BeginPlayTime);

	// The determinism check (09 S2): on the first frame after the capture, record every agent's state. The probe
	// reports "done" only from that frame on, so the hash and its log line are never part of the capture.
	if (bEndReported)
	{
		return;
	}
	const UTTProbeSubsystem* Probe = GetWorld()->GetSubsystem<UTTProbeSubsystem>();
	if (Probe && Probe->IsCaptureDone())
	{
		bEndReported = true;
		int32 StateChanges = 0;
		const uint32 Hash = HashState(StateChanges);
		UE_LOG(LogTTWorkload, Display, TEXT("End-state hash 0x%08X (%d state changes) at world time %.6f s"),
			Hash, StateChanges, GetWorld()->GetTimeSeconds());
	}
}

uint32 UTTWorkloadSubsystem::SpawnAgents(UWorld& World)
{
	FRandomStream Random(Options.Seed);
	const int32 Count = Options.NumAgents;
	const int32 Side = FMath::CeilToInt32(FMath::Sqrt(static_cast<double>(Count)));
	const double ArenaHalfExtent = TTWorkload::ArenaHalfExtent(Count);

	uint32 PositionHash = 0;
	Agents.Reserve(Count);
	for (int32 Index = 0; Index < Count; ++Index)
	{
		const int32 Column = Index % Side;
		const int32 Row = Index / Side;
		const FVector Center(
			Column * TTWorkload::GridSpacing - ArenaHalfExtent + Random.FRandRange(-TTWorkload::GridJitter, TTWorkload::GridJitter),
			Row * TTWorkload::GridSpacing - ArenaHalfExtent + Random.FRandRange(-TTWorkload::GridJitter, TTWorkload::GridJitter),
			TTWorkload::AgentHeight);
		const double Phase0 = Random.FRandRange(0.0, 2.0 * UE_DOUBLE_PI);

		// Deferred spawn: the brain's patrol is set before BeginPlay runs.
		ATTWorkloadAgent* Agent = World.SpawnActorDeferred<ATTWorkloadAgent>(ATTWorkloadAgent::StaticClass(), FTransform(Center),
			nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
		if (!Agent)
		{
			UE_LOG(LogTTWorkload, Error, TEXT("Spawning agent %d failed; the workload is incomplete."), Index);
			continue;
		}

		UTTWorkloadBrainComponent* Brain = Agent->GetBrain();
		Brain->InitPatrol(Center, Phase0);
		Brain->SetComputeIterations(Options.ComputeIterations);

		const FVector StartPosition = Brain->GetPatrolPosition(0.0);
		Agent->FinishSpawning(FTransform(StartPosition));
		Agents.Add(Agent);

		// Running CRC: chaining equals one CRC over all positions, without buffering them.
		PositionHash = FCrc::TypeCrc32(FVector3f(StartPosition), PositionHash);
	}
	return PositionHash;
}

uint32 UTTWorkloadSubsystem::HashState(int32& OutStateChanges) const
{
	// Location, rotation and the brain's state-change count of every agent: the position alone is a closed-form
	// function of time, so it would not notice runs whose sensing or decisions differed (code review, S2).
	uint32 Hash = 0;
	OutStateChanges = 0;
	for (const ATTWorkloadAgent* Agent : Agents)
	{
		if (IsValid(Agent))
		{
			const int32 Changes = Agent->GetBrain()->GetStateChanges();
			Hash = FCrc::TypeCrc32(FVector3f(Agent->GetActorLocation()), Hash);
			Hash = FCrc::TypeCrc32(FRotator3f(Agent->GetActorRotation()), Hash);
			Hash = FCrc::TypeCrc32(Changes, Hash);
			OutStateChanges += Changes;
		}
	}
	return Hash;
}

void UTTWorkloadSubsystem::UpdateCamera(double SecondsSinceBeginPlay)
{
	if (!Camera)
	{
		return;
	}

	const double Angle = 2.0 * UE_DOUBLE_PI * SecondsSinceBeginPlay / TTWorkload::CameraLapSeconds;
	const FVector Location(CameraRadius * FMath::Cos(Angle), CameraRadius * FMath::Sin(Angle), TTWorkload::CameraHeight);
	const FVector Forward(-FMath::Sin(Angle), FMath::Cos(Angle), 0.0);
	FRotator Rotation = Forward.Rotation();
	Rotation.Pitch = TTWorkload::CameraPitchDegrees;
	Camera->SetActorLocationAndRotation(Location, Rotation);

	// Re-applied every frame: the default pawn or a possession would otherwise reset the view target.
	APlayerController* PlayerController = GetWorld()->GetFirstPlayerController();
	if (PlayerController && PlayerController->GetViewTarget() != Camera)
	{
		PlayerController->SetViewTarget(Camera);
	}
}

TStatId UTTWorkloadSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UTTWorkloadSubsystem, STATGROUP_Tickables);
}
