/*
	Client post-process for alcohol (D61, ROADMAP idea 10). Registered through the vanilla hook
	PPERequesterRegistrations.RegisterAdditionalRequesters (3_game/ppemanager/pperequesterbank.c:229-248).
	Same shape as PPERequester_FeverEffects (3_game/ppemanager/requesters/pperfever.c): one blur value,
	set only when the synced drunk level changes (PlayerBase.OnVariablesSynchronized), never per frame.
*/
class PPERequester_SKY_Drunk extends PPERequester_GameplayBase
{
	void SkySetLevel(int level)
	{
		float blur = 0.0;
		if (level == 1)
			blur = 0.08;
		else if (level == 2)
			blur = 0.35;
		else if (level >= 3)
			blur = 0.6;
		SetTargetValueFloat(PostProcessEffectType.GaussFilter, PPEGaussFilter.PARAM_INTENSITY, true, blur, PPEGaussFilter.L_0_FEVER, PPOperators.ADD_RELATIVE);
	}
}

modded class PPERequesterRegistrations
{
	override protected void RegisterAdditionalRequesters()
	{
		super.RegisterAdditionalRequesters();
		PPERequesterBank.RegisterRequester(PPERequester_SKY_Drunk);
	}
}
