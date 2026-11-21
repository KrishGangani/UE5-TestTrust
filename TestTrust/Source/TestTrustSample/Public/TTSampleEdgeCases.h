// P03 TestTrust (sample) - FTTSampleEdgeCases: two functions written so that the runner's rarer fates really occur
// (Phase 7). TotalPrice's mutants don't compile (stillborn); two of TicksToDrain's mutants loop forever (timeout).

#pragma once

#include "CoreMinimal.h"

#define UE_API TESTTRUSTSAMPLE_API

/**
 * An amount of money in whole cents. It can be added and multiplied by a count, and deliberately nothing else:
 * a mutant that turns + into - or * into / names an operator that doesn't exist, so it fails to compile.
 * Defined in the header, which the runner never mutates, so its own operators are never mutated.
 */
struct FTTSampleMoney
{
	int32 Cents = 0;

	FTTSampleMoney operator+(const FTTSampleMoney& Other) const { return FTTSampleMoney{ Cents + Other.Cents }; }
	FTTSampleMoney operator*(int32 Count) const { return FTTSampleMoney{ Cents * Count }; }
};

struct FTTSampleEdgeCases
{
	/** The price of Count items at Unit each, plus a fixed Fee. */
	static UE_API FTTSampleMoney TotalPrice(FTTSampleMoney Unit, int32 Count, FTTSampleMoney Fee);

	/** How many steps of Step drain Remaining to zero or below. Step must be positive. */
	static UE_API int32 TicksToDrain(float Remaining, float Step);
};

#undef UE_API
