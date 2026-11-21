// P03 TestTrust (sample) - FTTSampleEdgeCases. Predicted mutants and fates: 09, Phase 7.

#include "TTSampleEdgeCases.h"

FTTSampleMoney FTTSampleEdgeCases::TotalPrice(FTTSampleMoney Unit, int32 Count, FTTSampleMoney Fee)
{
	return Unit * Count + Fee;
}

int32 FTTSampleEdgeCases::TicksToDrain(float Remaining, float Step)
{
	int32 Ticks = 0;
	while (Remaining > 0.0f)
	{
		Remaining -= Step;
		++Ticks;
	}
	return Ticks;
}
