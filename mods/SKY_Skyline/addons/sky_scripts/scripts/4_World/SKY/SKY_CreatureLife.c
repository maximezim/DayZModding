/*
	D62 creature director, server side (ROADMAP ideas 5, 8, 9). One repeating TICK_MS timer (CallLater,
	removed in Stop); no per-frame work; bounded registries (kennels <= MAX_KENNELS, nests <= MAX_NESTS).
	- Kennels (SKY_Kennel.c): every KENNEL_CHECK_EVERY ticks, owner online? -> guard state; strangers
	  near a guarding kennel -> bark (server -> client RPC_BARK to players within KENNEL_BARK_HEAR, AI noise
	  target as AlarmClock_ColorBase noise, alarmclock.c:21-22, NoiseSystem.AddNoiseTarget noise.c:10).
	- Rat nests (Land_SKY_RatNest): a player standing in a nest (RAT_BITE_RADIUS), not in a vehicle
	  (DayZPlayerImplement.IsInVehicle, dayzplayerimplement.c:465) and with no guard dog within
	  DOG_REPEL_PLAYER, is bitten with RAT_BITE_CHANCE per tick: 3-6 health, a light foot bleed 1 in 5
	  (BleedingSourcesManagerServer.AttemptAddBleedingSourceBySelection "LeftFoot"/"RightFoot",
	  bleedingsourcesmanagerbase.c:57-60/211), SALMONELLA 1 in 6 (PlayerBase.InsertAgent playerbase.c:7768,
	  as playerbase.c:9748).
	- Every RAT_GNAW_EVERY ticks each nest gnaws base parts (BaseBuildingBase basebuildingbase.c:2,
	  TentBase tentbase.c:1) within RAT_GNAW_RADIUS by RAT_GNAW_FRACTION of their max health, unless a
	  fireplace burns within RAT_FIRE_BLOCK of the nest (FireplaceBase.IsBurning fireplacebase.c:1623) or a
	  guard dog is within DOG_REPEL_BASE of the part. One GetObjectsAtPosition (game.c:922) per nest per 10 min,
	  spread over the cycle (perf review D62).
	- External dog mods: add their class names to s_ExtraDogTypes (checked with IsKindOf near a bite only);
	  empty by default, so nothing depends on another mod.
*/
class Land_SKY_RatNest extends House
{
	void Land_SKY_RatNest()
	{
		if (g_Game.IsServer())
			SKY_CreatureLife.RegisterNest(this);
	}

	void ~Land_SKY_RatNest()
	{
		SKY_CreatureLife.UnregisterNest(this);
	}
}

class SKY_CreatureLife
{
	protected static ref array<SKY_Kennel> s_Kennels = new array<SKY_Kennel>();
	protected static ref array<Land_SKY_RatNest> s_Nests = new array<Land_SKY_RatNest>();
	//! Class names of dogs from optional external mods (server owners may add; IsKindOf, no compile dependency).
	protected static ref array<string> s_ExtraDogTypes = new array<string>();
	protected static ref SKY_CreatureLife s_Instance;

	protected ref array<Man> m_Players = new array<Man>();
	protected ref map<string, bool> m_Online = new map<string, bool>();
	protected ref NoiseParams m_Noise;
	protected ref array<Object> m_Objs = new array<Object>();		//!< reused query buffer
	protected ref array<vector> m_Dogs = new array<vector>();		//!< reused dog positions (one nest)
	protected int m_Ticks;

	static void RegisterKennel(SKY_Kennel k)
	{
		if (s_Kennels && s_Kennels.Count() < SKY_Beasts.MAX_KENNELS && s_Kennels.Find(k) == -1)
			s_Kennels.Insert(k);
	}

	static bool IsKennelRegistered(SKY_Kennel k)
	{
		return s_Kennels && s_Kennels.Find(k) != -1;
	}

	static void UnregisterKennel(SKY_Kennel k)
	{
		if (s_Kennels)
			s_Kennels.RemoveItem(k);
	}

	static void RegisterNest(Land_SKY_RatNest n)
	{
		if (s_Nests && s_Nests.Count() < SKY_Beasts.MAX_NESTS && s_Nests.Find(n) == -1)
			s_Nests.Insert(n);
	}

	static void UnregisterNest(Land_SKY_RatNest n)
	{
		if (s_Nests)
			s_Nests.RemoveItem(n);
	}

	static void Start()
	{
		if (!g_Game.IsServer() || s_Instance)
			return;
		s_Instance = new SKY_CreatureLife();
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(s_Instance.Tick, SKY_Beasts.TICK_MS, true);
		SKY_Log.Info("creature life started (" + s_Nests.Count().ToString() + " rat nests)");
	}

	static void Stop()
	{
		if (!s_Instance)
			return;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(s_Instance.Tick);
		s_Instance = null;
	}

	void SKY_CreatureLife()
	{
		m_Noise = new NoiseParams();
		m_Noise.LoadFromPath("cfgVehicles AlarmClock_Blue NoiseAlarmClock");
	}

	void Tick()
	{
		m_Ticks++;
		g_Game.GetPlayers(m_Players);
		int now = g_Game.GetTime();
		if (s_Kennels.Count() > 0)
		{
			if (m_Ticks % SKY_Beasts.KENNEL_CHECK_EVERY == 0)
				UpdateKennels();
			Barks(now);
		}
		if (s_Nests.Count() > 0)
		{
			Bites();
			Gnaw();
		}
	}

	protected void UpdateKennels()
	{
		m_Online.Clear();
		foreach (Man m : m_Players)
		{
			if (m && m.GetIdentity())
				m_Online.Set(m.GetIdentity().GetId(), true);
		}
		int nowUtc = SKY_Time.NowUtc();
		foreach (SKY_Kennel k : s_Kennels)
		{
			if (k)
				k.SkyUpdateGuard(m_Online.Contains(k.SkyOwner()), nowUtc);
		}
	}

	protected void Barks(int now)
	{
		float r2 = SKY_Beasts.KENNEL_BARK_RADIUS * SKY_Beasts.KENNEL_BARK_RADIUS;
		foreach (SKY_Kennel k : s_Kennels)
		{
			if (!k || !k.SkyIsGuarding())
				continue;
			vector kp = k.GetPosition();
			bool stranger = false;
			foreach (Man m : m_Players)
			{
				if (m && vector.DistanceSq(m.GetPosition(), kp) <= r2 && m.IsAlive() && m.GetIdentity() && m.GetIdentity().GetId() != k.SkyOwner())	// D94 perf L: distance first
				{
					stranger = true;
					break;
				}
			}
			if (!stranger || !k.SkyTryBark(now))
				continue;
			vector bp = k.SkyBarkPos();
			float h2 = SKY_Beasts.KENNEL_BARK_HEAR * SKY_Beasts.KENNEL_BARK_HEAR;
			Param1<vector> barkParam = new Param1<vector>(bp);
			foreach (Man lm : m_Players)
			{
				PlayerBase pb = PlayerBase.Cast(lm);
				if (pb && pb.GetIdentity() && vector.DistanceSq(pb.GetPosition(), bp) <= h2)
					g_Game.RPCSingleParam(pb, SKY_Beasts.RPC_BARK, barkParam, true, pb.GetIdentity());
			}
			NoiseSystem ns = g_Game.GetNoiseSystem();
			if (ns && m_Noise)
				ns.AddNoiseTarget(bp, 5.0, m_Noise, SKY_Beasts.KENNEL_BARK_NOISE);
		}
	}

	//! A guard dog (kennel, or an external dog class) within `radius` of `pos`.
	protected bool DogNear(vector pos, float radius)
	{
		float r2 = radius * radius;
		foreach (SKY_Kennel k : s_Kennels)
		{
			if (k && !k.GetHierarchyParent() && vector.DistanceSq(k.GetPosition(), pos) <= r2)
				return true;
		}
		if (s_ExtraDogTypes.Count() == 0)
			return false;
		m_Objs.Clear();
		g_Game.GetObjectsAtPosition(pos, radius, m_Objs, null);
		foreach (Object o : m_Objs)
		{
			if (IsExtraDog(o))
				return true;
		}
		return false;
	}

	protected void Bites()
	{
		float r2 = SKY_Beasts.RAT_BITE_RADIUS * SKY_Beasts.RAT_BITE_RADIUS;
		foreach (Man m : m_Players)
		{
			PlayerBase pb = PlayerBase.Cast(m);
			if (!pb || !pb.IsAlive() || pb.IsInVehicle())
				continue;
			vector pp = pb.GetPosition();
			bool inNest = false;
			foreach (Land_SKY_RatNest n : s_Nests)
			{
				if (n && vector.DistanceSq(n.GetPosition(), pp) <= r2)
				{
					inNest = true;
					break;
				}
			}
			if (!inNest || Math.RandomFloat01() >= SKY_Beasts.RAT_BITE_CHANCE || DogNear(pp, SKY_Beasts.DOG_REPEL_PLAYER))
				continue;
			pb.AddHealth("GlobalHealth", "Health", -Math.RandomFloatInclusive(SKY_Beasts.RAT_DMG_MIN, SKY_Beasts.RAT_DMG_MAX));
			if (Math.RandomFloat01() < SKY_Beasts.RAT_BLEED_CHANCE && pb.GetBleedingManagerServer())
			{
				string foot = "LeftFoot";
				if (Math.RandomFloat01() < 0.5)
					foot = "RightFoot";
				pb.GetBleedingManagerServer().AttemptAddBleedingSourceBySelection(foot);
			}
			if (Math.RandomFloat01() < SKY_Beasts.RAT_DISEASE_CHANCE)
				pb.InsertAgent(eAgents.SALMONELLA, 1);
			pb.MessageImportant("A rat bites your ankle.");
		}
	}

	//! Gnaw: each nest once per RAT_GNAW_EVERY ticks, spread over the cycle (nest i on ticks where
	//! i % RAT_GNAW_EVERY == tick % RAT_GNAW_EVERY), so at most ceil(nests / 120) queries per tick.
	protected void Gnaw()
	{
		int slot = m_Ticks % SKY_Beasts.RAT_GNAW_EVERY;
		for (int i = slot; i < s_Nests.Count(); i += SKY_Beasts.RAT_GNAW_EVERY)
		{
			Land_SKY_RatNest n = s_Nests[i];
			if (n)
				GnawAt(n.GetPosition());
		}
	}

	protected void GnawAt(vector np)
	{
		m_Objs.Clear();
		g_Game.GetObjectsAtPosition(np, SKY_Beasts.RAT_GNAW_RADIUS + SKY_Beasts.DOG_REPEL_BASE, m_Objs, null);
		// one pass: burning fire near the nest stops everything; collect dog positions once
		m_Dogs.Clear();
		float fire2 = SKY_Beasts.RAT_FIRE_BLOCK * SKY_Beasts.RAT_FIRE_BLOCK;
		foreach (Object o : m_Objs)
		{
			FireplaceBase fp = FireplaceBase.Cast(o);
			if (fp && fp.IsBurning() && vector.DistanceSq(fp.GetPosition(), np) <= fire2)
				return;
			if (SKY_Kennel.Cast(o) || IsExtraDog(o))
			{
				EntityAI dogEnt = EntityAI.Cast(o);
				if (dogEnt && !dogEnt.GetHierarchyParent())
					m_Dogs.Insert(o.GetPosition());
			}
		}
		float gnaw2 = SKY_Beasts.RAT_GNAW_RADIUS * SKY_Beasts.RAT_GNAW_RADIUS;
		float dog2 = SKY_Beasts.DOG_REPEL_BASE * SKY_Beasts.DOG_REPEL_BASE;
		foreach (Object part : m_Objs)
		{
			if (!BaseBuildingBase.Cast(part) && !TentBase.Cast(part))
				continue;
			EntityAI ent = EntityAI.Cast(part);
			if (!ent || ent.GetHierarchyParent())
				continue;
			vector pp = ent.GetPosition();
			if (vector.DistanceSq(pp, np) > gnaw2)
				continue;
			bool guarded = false;
			foreach (vector dp : m_Dogs)
			{
				if (vector.DistanceSq(dp, pp) <= dog2)
				{
					guarded = true;
					break;
				}
			}
			if (!guarded)
				ent.AddHealth("", "Health", -SKY_Beasts.RAT_GNAW_FRACTION * ent.GetMaxHealth("", "Health"));
		}
	}

	protected bool IsExtraDog(Object o)
	{
		foreach (string t : s_ExtraDogTypes)
		{
			if (o.IsKindOf(t) && o.IsAlive())
				return true;
		}
		return false;
	}
}

//! Client half of the kennel bark (sky_sounds config: SKY_Bark_SoundSet).
class SKY_KennelSound
{
	static void ClientPlayBark(vector pos)
	{
		EffectSound snd = SEffectManager.PlaySound("SKY_Bark_SoundSet", pos);
		if (snd)
			snd.SetAutodestroy(true);
	}
}
