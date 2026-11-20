// P03 TestTrust (sample) - FTTSampleRules.

#include "TTSampleRules.h"

int32 FTTSampleRules::ComputeDamage(int32 BaseDamage, int32 Armor, bool bCritical)
{
	int32 Damage = BaseDamage - Armor;
	if (Damage < MinDamage)
	{
		Damage = MinDamage;
	}
	if (bCritical)
	{
		Damage *= 2;
	}
	return Damage;
}

bool FTTSampleRules::IsInRange(const FVector& Origin, const FVector& Target, double Range)
{
	// Squared distances avoid a square root; both sides are non-negative, so the comparison is unchanged.
	return FVector::DistSquared(Origin, Target) <= Range * Range;
}

float FTTSampleRules::TickCooldown(float Remaining, float DeltaSeconds)
{
	const float Next = Remaining - DeltaSeconds;
	return Next > 0.f ? Next : 0.f;
}
