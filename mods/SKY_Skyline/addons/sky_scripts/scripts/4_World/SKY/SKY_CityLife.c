/*
	D61 city life, server side (ROADMAP ideas 3 and 20):
	- Hordes downtown: every Land_SKY_SirenTower (placed downtown by the layout) is a horde anchor.
	  When a player comes within HORDE_ACTIVATE, a group of HORDE_GROUP city infected spawns on a
	  ring round the anchor, at least HORDE_MIN_PLAYER from every player (never in sight range),
	  capped per anchor and globally; a group despawns when no player is within HORDE_DESPAWN.
	- City alarm: every 45-90 min one siren with a player near it wails for a minute. The siren
	  sound is sent (server -> client RPC) to players within ALARM_HEAR; an AI noise target is
	  refreshed at the siren every ALARM_PULSE_MS (vanilla alarm clock noise x ALARM_NOISE_MULT, P14)
	  and ALARM_HORDES extra groups spawn on a wider ring and walk in to the noise.
	One repeating HORDE_TICK_MS timer (CallLater, removed in Stop; at most one group spawned per tick) does all of it: no per-frame work; bounded
	arrays (sirens <= HORDE_MAX_ANCHORS, members <= HORDE_GLOBAL_MAX + ALARM_EXTRA_CAP).
	APIs: CGame.GetPlayers (3_game/global/game.c:947), CreateObjectEx + ECE_PLACE_ON_SURFACE |
	ECE_INITAI | ECE_EQUIP_ATTACHMENTS (as plugindeveloper.c:405), SurfaceY / SurfaceIsSea / SurfaceIsPond
	(game.c:1162-1182), ObjectDelete (game.c:704), RPCSingleParam (game.c:1015), NoiseSystem
	.AddNoiseTarget (3_game/noise.c:10), NoiseParams.LoadFromPath as AlarmClock_ColorBase (alarmclock.c:21-22).
	Infected class names: vanilla events.xml InfectedCity children.
*/
class Land_SKY_SirenTower extends House
{
	int m_SkyNextHorde;		//!< server: earliest next horde spawn at this anchor (ms)

	void Land_SKY_SirenTower()
	{
		if (g_Game.IsServer())
			SKY_CityLife.RegisterSiren(this);
	}

	void ~Land_SKY_SirenTower()
	{
		SKY_CityLife.UnregisterSiren(this);
	}

	vector SkySirenPos()
	{
		if (MemoryPointExists("siren"))
			return ModelToWorld(GetMemoryPointPos("siren"));
		return GetPosition();
	}
}

class SKY_HordeMember
{
	ZombieBase m_Zombie;
	Land_SKY_SirenTower m_Anchor;
	int m_DeadSince;
}

class SKY_CityLife
{
	static const bool HORDES_ENABLED = true;
	static const bool ALARM_ENABLED = true;

	protected static ref array<Land_SKY_SirenTower> s_Sirens = new array<Land_SKY_SirenTower>();
	protected static ref SKY_CityLife s_Instance;

	protected ref array<ref SKY_HordeMember> m_Members = new array<ref SKY_HordeMember>();
	protected int m_Pending;			//!< infected scheduled by SpawnGroup, not yet created (staggered)
	protected ref array<Man> m_Players = new array<Man>();
	protected ref array<string> m_Infected;
	protected ref NoiseParams m_Noise;
	protected int m_NextAlarm;
	protected int m_AlarmEnd;
	protected int m_AlarmNextPulse;
	protected Land_SKY_SirenTower m_AlarmSiren;
	protected int m_AlarmGroupsLeft;		//!< alarm groups still to spawn, one per tick

	static void RegisterSiren(Land_SKY_SirenTower siren)
	{
		if (s_Sirens && s_Sirens.Count() < SKY_Life.HORDE_MAX_ANCHORS && s_Sirens.Find(siren) == -1)
			s_Sirens.Insert(siren);
	}

	static void UnregisterSiren(Land_SKY_SirenTower siren)
	{
		if (s_Sirens)
			s_Sirens.RemoveItem(siren);
	}

	static void Start()
	{
		if (!g_Game.IsServer() || s_Instance || !(HORDES_ENABLED || ALARM_ENABLED))
			return;
		s_Instance = new SKY_CityLife();
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(s_Instance.Tick, SKY_Life.HORDE_TICK_MS, true);
		SKY_Log.Info("city life started (" + s_Sirens.Count().ToString() + " sirens)");
	}

	static void Stop()
	{
		if (!s_Instance)
			return;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(s_Instance.Tick);
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(s_Instance.SpawnOne);
		s_Instance = null;
	}

	void SKY_CityLife()
	{
		array<string> infected = {"ZmbF_BlueCollarFat_White", "ZmbF_CitizenANormal_Beige", "ZmbF_CitizenANormal_Blue", "ZmbF_CitizenBSkinny",
			"ZmbF_Clerk_Normal_Blue", "ZmbF_Clerk_Normal_Red", "ZmbF_JournalistNormal_Blue", "ZmbF_ShortSkirt_beige",
			"ZmbF_ShortSkirt_checks", "ZmbF_SkaterYoung_Striped", "ZmbF_SurvivorNormal_Blue", "ZmbF_SurvivorNormal_Red",
			"ZmbM_CitizenASkinny_Blue", "ZmbM_CitizenASkinny_Grey", "ZmbM_CitizenASkinny_Red", "ZmbM_CitizenBFat_Blue",
			"ZmbM_CitizenBFat_Green", "ZmbM_CitizenBFat_Red", "ZmbM_ClerkFat_Grey", "ZmbM_ClerkFat_White",
			"ZmbM_CommercialPilotOld_Blue", "ZmbM_Gamedev_Black", "ZmbM_Gamedev_Gray", "ZmbM_JournalistSkinny",
			"ZmbM_MotobikerFat_Beige", "ZmbM_SkaterYoung_Brown", "ZmbM_SkaterYoung_Grey"};
		m_Infected = infected;
		m_Noise = new NoiseParams();
		m_Noise.LoadFromPath("cfgVehicles AlarmClock_Blue NoiseAlarmClock");
		m_NextAlarm = g_Game.GetTime() + Math.RandomIntInclusive(SKY_Life.ALARM_MIN_MS, SKY_Life.ALARM_MAX_MS);
	}

	void Tick()
	{
		int now = g_Game.GetTime();
		g_Game.GetPlayers(m_Players);
		UpdateMembers(now);
		if (HORDES_ENABLED)
			UpdateHordes(now);
		if (ALARM_ENABLED)
			UpdateAlarm(now);
	}

	protected bool PlayerNear(vector pos, float radius)
	{
		foreach (Man m : m_Players)
		{
			if (m && m.IsAlive() && vector.DistanceSq(m.GetPosition(), pos) <= radius * radius)
				return true;
		}
		return false;
	}

	protected void UpdateMembers(int now)
	{
		for (int i = m_Members.Count() - 1; i >= 0; i--)
		{
			SKY_HordeMember mb = m_Members[i];
			ZombieBase z = mb.m_Zombie;
			if (!z)
			{
				m_Members.Remove(i);
				continue;
			}
			vector zp = z.GetPosition();
			if (!z.IsAlive())
			{
				if (mb.m_DeadSince == 0)
					mb.m_DeadSince = now;
				else if (now - mb.m_DeadSince > SKY_Life.HORDE_CORPSE_MS && !PlayerNear(zp, 100.0))
				{
					g_Game.ObjectDelete(z);
					m_Members.Remove(i);
				}
				continue;
			}
			if (!PlayerNear(zp, SKY_Life.HORDE_DESPAWN))
			{
				g_Game.ObjectDelete(z);
				m_Members.Remove(i);
			}
		}
	}

	protected int CountFor(Land_SKY_SirenTower anchor)
	{
		int n = 0;
		foreach (SKY_HordeMember mb : m_Members)
		{
			if (mb.m_Anchor == anchor && mb.m_Zombie && mb.m_Zombie.IsAlive())
				n++;
		}
		return n;
	}

	protected void UpdateHordes(int now)
	{
		foreach (Land_SKY_SirenTower s : s_Sirens)
		{
			if (!s || now < s.m_SkyNextHorde)
				continue;
			vector ap = s.GetPosition();
			if (!PlayerNear(ap, SKY_Life.HORDE_ACTIVATE))
				continue;
			if (CountFor(s) + SKY_Life.HORDE_GROUP > SKY_Life.HORDE_PER_ANCHOR)
				continue;
			SpawnGroup(s, ap, SKY_Life.HORDE_RING_MIN, SKY_Life.HORDE_RING_MAX, SKY_Life.HORDE_GROUP, SKY_Life.HORDE_GLOBAL_MAX);
			s.m_SkyNextHorde = now + SKY_Life.HORDE_RESPAWN_MS;
			return;									// at most one group per tick (spawn hitch, perf review D62)
		}
	}

	//! One group on a ring round `center`, out of every player's close range. Returns the number spawned.
	protected int SpawnGroup(Land_SKY_SirenTower anchor, vector center, float rmin, float rmax, int count, int cap)
	{
		// full audit perf H2: the cap scales with the players online (the CE does not count these infected);
		// an alarm keeps its extra headroom on top of the scaled base
		int scaled = SKY_Life.HORDE_BASE_CAP + SKY_Life.HORDE_PER_PLAYER * m_Players.Count();
		cap = Math.Min(cap, scaled + (cap - SKY_Life.HORDE_GLOBAL_MAX));
		int room = cap - m_Members.Count() - m_Pending;
		if (room <= 0)
			return 0;
		count = Math.Min(count, room);
		vector p;
		bool ok = false;
		for (int t = 0; t < 6 && !ok; t++)
		{
			float a = Math.RandomFloat(0, Math.PI2);
			float r = Math.RandomFloatInclusive(rmin, rmax);
			p = Vector(center[0] + Math.Cos(a) * r, 0, center[2] + Math.Sin(a) * r);
			if (g_Game.SurfaceIsSea(p[0], p[2]) || g_Game.SurfaceIsPond(p[0], p[2]))
				continue;
			p[1] = g_Game.SurfaceY(p[0], p[2]);
			ok = !PlayerNear(p, SKY_Life.HORDE_MIN_PLAYER);
		}
		if (!ok)
			return 0;
		for (int i = 0; i < count; i++)
		{
			vector zp = Vector(p[0] + Math.RandomFloatInclusive(-4, 4), 0, p[2] + Math.RandomFloatInclusive(-4, 4));
			zp[1] = g_Game.SurfaceY(zp[0], zp[2]);
			m_Pending++;
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SpawnOne, i * SKY_Life.HORDE_STAGGER_MS, false, anchor, zp);
		}
		return count;
	}

	//! One infected of a staggered group (perf H2: no 6-AI hitch in one frame).
	protected void SpawnOne(Land_SKY_SirenTower anchor, vector zp)
	{
		if (s_Instance != this)						// stopped: a queued call left over (re-review perf L)
			return;
		if (m_Pending > 0)
			m_Pending--;
		Object obj = g_Game.CreateObjectEx(m_Infected.GetRandomElement(), zp, ECE_PLACE_ON_SURFACE | ECE_INITAI | ECE_EQUIP_ATTACHMENTS);
		ZombieBase z = ZombieBase.Cast(obj);
		if (!z)
		{
			if (obj)
				g_Game.ObjectDelete(obj);
			return;
		}
		SKY_HordeMember mb = new SKY_HordeMember();
		mb.m_Zombie = z;
		mb.m_Anchor = anchor;
		m_Members.Insert(mb);
	}

	protected void UpdateAlarm(int now)
	{
		if (m_AlarmSiren)
		{
			if (m_AlarmGroupsLeft > 0)
			{
				m_AlarmGroupsLeft--;
				int alarmCap = SKY_Life.HORDE_GLOBAL_MAX + SKY_Life.ALARM_EXTRA_CAP;
				SpawnGroup(m_AlarmSiren, m_AlarmSiren.GetPosition(), SKY_Life.ALARM_RING_MIN, SKY_Life.ALARM_RING_MAX, SKY_Life.HORDE_GROUP, alarmCap);
			}
			if (now >= m_AlarmEnd)
			{
				m_AlarmSiren = null;
				m_AlarmGroupsLeft = 0;
			}
			else if (now >= m_AlarmNextPulse)
				Pulse(now);
			return;
		}
		if (now < m_NextAlarm)
			return;
		m_NextAlarm = now + Math.RandomIntInclusive(SKY_Life.ALARM_MIN_MS, SKY_Life.ALARM_MAX_MS);
		array<Land_SKY_SirenTower> live = new array<Land_SKY_SirenTower>();
		foreach (Land_SKY_SirenTower s : s_Sirens)
		{
			if (s && PlayerNear(s.GetPosition(), SKY_Life.ALARM_NEED_PLAYER))
				live.Insert(s);
		}
		if (live.Count() == 0)
		{
			m_NextAlarm = now + 600000;				// nobody around: try again in 10 min
			return;
		}
		m_AlarmSiren = live.GetRandomElement();
		m_AlarmEnd = now + SKY_Life.ALARM_DURATION_MS;
		vector sp = m_AlarmSiren.SkySirenPos();
		Param1<vector> sirenParam = new Param1<vector>(sp);
		foreach (Man m : m_Players)
		{
			PlayerBase pb = PlayerBase.Cast(m);
			if (pb && pb.GetIdentity() && vector.DistanceSq(pb.GetPosition(), sp) <= SKY_Life.ALARM_HEAR * SKY_Life.ALARM_HEAR)
				g_Game.RPCSingleParam(pb, SKY_Life.RPC_SIREN, sirenParam, true, pb.GetIdentity());
		}
		if (!g_Game.IsMultiplayer())
			SKY_CityAlarm.ClientPlaySiren(sp);					// offline mission: same process
		Pulse(now);
		m_AlarmGroupsLeft = SKY_Life.ALARM_HORDES;			// spawned one per tick from the next tick
		SKY_Log.Info("city alarm at " + sp.ToString());
	}

	protected void Pulse(int now)
	{
		m_AlarmNextPulse = now + SKY_Life.ALARM_PULSE_MS;
		NoiseSystem ns = g_Game.GetNoiseSystem();
		if (ns && m_Noise && m_AlarmSiren)
			ns.AddNoiseTarget(m_AlarmSiren.GetPosition(), SKY_Life.ALARM_PULSE_MS * 0.001 + 2.0, m_Noise, SKY_Life.ALARM_NOISE_MULT);
	}
}

//! Client half of the alarm: the sound (sky_sounds config: SKY_Siren_SoundSet, 60 s, heard to ~2.5 km).
class SKY_CityAlarm
{
	static void ClientPlaySiren(vector pos)
	{
		EffectSound snd = SEffectManager.PlaySound("SKY_Siren_SoundSet", pos);
		if (snd)
			snd.SetAutodestroy(true);
	}
}
