// P03 TestTrust (sample) - FTTSampleRules: three small gameplay rules for the mutation runner to mutate.

#pragma once

#include "CoreMinimal.h"

#define UE_API TESTTRUSTSAMPLE_API

/**
 * Pure functions with no UObject and no world, so their tests run in microseconds.
 * Each rule has a branch or a boundary, which is where mutation operators find something to change.
 */
struct FTTSampleRules
{
	/** The smallest damage any hit deals after armour. */
	static constexpr int32 MinDamage = 1;

	/** Damage after armour: armour subtracts a flat amount, never below MinDamage; a critical hit doubles the result. */
	static UE_API int32 ComputeDamage(int32 BaseDamage, int32 Armor, bool bCritical);

	/** True if Target is within Range of Origin. A target exactly at Range counts as in range. */
	static UE_API bool IsInRange(const FVector& Origin, const FVector& Target, double Range);

	/** Counts a cooldown down by DeltaSeconds and returns the time left, never below zero. */
	static UE_API float TickCooldown(float Remaining, float DeltaSeconds);
};

#undef UE_API
