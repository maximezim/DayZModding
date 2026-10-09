/*
	PlayerBase additions for D61 city life:
	- player action ActionSKY_Search (search targets carry `skySearch` in config), registered like the
	  vanilla door actions in PlayerBase.SetActions (playerbase.c:1670);
	- alcohol dose model (ROADMAP idea 10, P16). Server: Consume (playerbase.c:7346) adds ethanol for
	  LIQUID_VODKA / LIQUID_BEER (constants.c:546-547); OnScheduledTick (playerbase.c:2821, server via
	  OnTick playerbase.c:2932) decays it and applies the effects only while > 0. Levels:
	    1 tipsy  : slow health regen + shock regen ("heals")
	    2 drunk  : shock regen, client blur
	    3 wasted : strong blur, vanilla vomit symptom (SymptomIDs.SYMPTOM_VOMIT, emoteclasses.c:764) with a cooldown
	  One synced int (m_SkyDrunk, 0..3, SetSynchDirty only on change); the client applies the
	  PPERequester_SKY_Drunk blur for its own player in OnVariablesSynchronized. Not persisted:
	  relogging sobers you up.
	- the siren and kennel-bark RPCs (server -> client only): SKY_CityAlarm sends the siren position; the client plays
	  the SKY_Siren_SoundSet there. A client cannot trigger anything with it (handled only on clients).
*/
modded class PlayerBase
{
	protected float m_SkyAlcohol;		//!< server: ml of ethanol
	protected float m_SkyHealLeft;		//!< server: health the alcohol may still restore (D94)
	protected int m_SkyDrunk;			//!< synced level 0..3
	protected int m_SkyNextVomit;		//!< server: earliest next vomit (ms)
	protected int m_SkyDrunkShown;		//!< client: level currently applied to the PPE

	override void Init()
	{
		super.Init();
		RegisterNetSyncVariableInt("m_SkyDrunk", 0, 3);
	}

	override void SetActions(out TInputActionMap InputActionMap)
	{
		super.SetActions(InputActionMap);
		AddAction(ActionSKY_Search, InputActionMap);
	}

	override bool Consume(PlayerConsumeData data)
	{
		int liquid = 0;
		float amount = 0;
		if (g_Game.IsServer() && data && (data.m_Type == EConsumeType.ITEM_SINGLE_TIME || data.m_Type == EConsumeType.ITEM_CONTINUOUS))
		{
			Edible_Base edible = Edible_Base.Cast(data.m_Source);
			if (edible && edible.IsLiquidContainer())
			{
				liquid = edible.GetLiquidType();
				amount = data.m_Amount;
			}
		}
		bool consumed = super.Consume(data);
		if (consumed && liquid == LIQUID_VODKA)
			SkyAddAlcohol(amount * SKY_Life.ALCOHOL_VODKA);
		else if (consumed && liquid == LIQUID_BEER)
			SkyAddAlcohol(amount * SKY_Life.ALCOHOL_BEER);
		return consumed;
	}

	void SkyAddAlcohol(float ml)
	{
		if (ml <= 0)
			return;
		m_SkyAlcohol = Math.Min(m_SkyAlcohol + ml, SKY_Life.ALCOHOL_MAX);
		m_SkyHealLeft = Math.Min(m_SkyHealLeft + ml * SKY_Life.ALCOHOL_HEAL_PER_ML, SKY_Life.ALCOHOL_HEAL_MAX);
		SkyUpdateDrunkLevel();
	}

	override void OnScheduledTick(float deltaTime)
	{
		super.OnScheduledTick(deltaTime);
		if (m_SkyAlcohol > 0 && g_Game.IsServer() && IsAlive())
			SkyAlcoholTick(deltaTime);
	}

	protected void SkyAlcoholTick(float dt)
	{
		m_SkyAlcohol = Math.Max(0, m_SkyAlcohol - SKY_Life.ALCOHOL_DECAY * dt);
		if (m_SkyAlcohol <= 0)
			m_SkyHealLeft = 0;									// re-review L: sober again, the budget is gone
		SkyUpdateDrunkLevel();
		if (m_SkyDrunk == 1 && m_SkyHealLeft > 0)					// D94 security L4: heal bounded by what was drunk
		{
			float h = Math.Min(SKY_Life.ALCOHOL_HEAL * dt, m_SkyHealLeft);
			m_SkyHealLeft -= h;
			AddHealth("GlobalHealth", "Health", h);
		}
		if (m_SkyDrunk == 1 || m_SkyDrunk == 2)
			AddHealth("", "Shock", SKY_Life.ALCOHOL_SHOCK * dt);
		if (m_SkyDrunk >= 3)
		{
			int now = g_Game.GetTime();
			if (now >= m_SkyNextVomit && GetSymptomManager())
			{
				GetSymptomManager().QueueUpPrimarySymptom(SymptomIDs.SYMPTOM_VOMIT);
				m_SkyNextVomit = now + SKY_Life.ALCOHOL_VOMIT_MS;
				m_SkyAlcohol = m_SkyAlcohol * 0.8;		// part of it comes back up
			}
		}
	}

	protected void SkyUpdateDrunkLevel()
	{
		int level = 0;
		if (m_SkyAlcohol >= SKY_Life.ALCOHOL_WASTED)
			level = 3;
		else if (m_SkyAlcohol >= SKY_Life.ALCOHOL_DRUNK)
			level = 2;
		else if (m_SkyAlcohol >= SKY_Life.ALCOHOL_TIPSY)
			level = 1;
		if (level != m_SkyDrunk)
		{
			m_SkyDrunk = level;
			SetSynchDirty();
		}
	}

	int SkyGetDrunkLevel()
	{
		return m_SkyDrunk;
	}

	override void OnVariablesSynchronized()
	{
		super.OnVariablesSynchronized();
		if (m_SkyDrunk != m_SkyDrunkShown && this == g_Game.GetPlayer())
			SkyApplyDrunkEffect();
	}

	protected void SkyApplyDrunkEffect()
	{
		m_SkyDrunkShown = m_SkyDrunk;
		PPERequester_SKY_Drunk req = PPERequester_SKY_Drunk.Cast(PPERequesterBank.GetRequester(PPERequester_SKY_Drunk));
		if (!req)
			return;
		if (m_SkyDrunk <= 0)
			req.Stop();
		else
			req.SkySetLevel(m_SkyDrunk);
	}

	override void EEKilled(Object killer)
	{
		m_SkyAlcohol = 0;
		super.EEKilled(killer);
	}

	override void OnRPC(PlayerIdentity sender, int rpc_type, ParamsReadContext ctx)
	{
		super.OnRPC(sender, rpc_type, ctx);
		if ((rpc_type != SKY_Life.RPC_SIREN && rpc_type != SKY_Beasts.RPC_BARK) || g_Game.IsDedicatedServer() || g_Game.IsServer())
			return;									// server -> client only; never acted on by a server
		Param1<vector> p = new Param1<vector>(vector.Zero);
		if (!ctx.Read(p))
			return;
		if (rpc_type == SKY_Life.RPC_SIREN)
			SKY_CityAlarm.ClientPlaySiren(p.param1);
		else
			SKY_KennelSound.ClientPlayBark(p.param1);
	}
}
