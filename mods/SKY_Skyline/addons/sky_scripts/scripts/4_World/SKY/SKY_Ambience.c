/*
	Client ambience director (D65): procedural loops (assets/sounds/gen_ambience.py, sky_sounds config)
	on nearby sources - hypermarket tube hum, sewer drips, Ferris-wheel creak.
	Sources register on clients only (static, bounded MAX_SOURCES). One 2 s timer (CallLater, removed in
	StopClient) picks the MAX_ACTIVE nearest sources within their range of the camera
	(CGame.GetCurrentCameraPosition game.c:730), starts looped EffectSounds for new ones
	(SEffectManager.PlaySoundCachedParams effectmanager.c:207, loop = true) and destroys the ones that left
	(SEffectManager.DestroySound effectmanager.c:432). No per-frame work, no network.
*/
class SKY_AmbientSource
{
	Object m_Obj;
	string m_SoundSet;
	vector m_Pos;			//!< cached on the first tick after the object got its position (static map objects)
	bool m_PosSet;
	float m_Range2;			//!< range squared
	EffectSound m_Sound;
}

class SKY_Ambience
{
	static const int MAX_SOURCES = 2048;
	static const int MAX_ACTIVE = 3;
	static const int TICK_MS = 2000;
	protected static ref array<ref SKY_AmbientSource> s_Sources = new array<ref SKY_AmbientSource>();
	protected static bool s_Running;
	protected static ref array<int> s_Best = new array<int>();		//!< reused per tick (perf review D65)
	protected static ref array<float> s_BestD = new array<float>();

	static void Register(Object obj, string soundSet, float range)
	{
		if (g_Game.IsDedicatedServer() || !obj || s_Sources.Count() >= MAX_SOURCES)
			return;
		SKY_AmbientSource s = new SKY_AmbientSource();
		s.m_Obj = obj;
		s.m_SoundSet = soundSet;
		s.m_Range2 = range * range;					// position: lazily, constructors run before placement
		s_Sources.Insert(s);
	}

	static void Unregister(Object obj)
	{
		for (int i = s_Sources.Count() - 1; i >= 0; i--)
		{
			if (s_Sources[i].m_Obj == obj)
			{
				if (s_Sources[i].m_Sound)
					SEffectManager.DestroySound(s_Sources[i].m_Sound);
				s_Sources.Remove(i);
			}
		}
	}

	static void StartClient()
	{
		if (g_Game.IsDedicatedServer() || s_Running)
			return;
		s_Running = true;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SKY_Ambience.Tick, TICK_MS, true);
	}

	static void StopClient()
	{
		if (!s_Running)
			return;
		s_Running = false;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(SKY_Ambience.Tick);
		foreach (SKY_AmbientSource s : s_Sources)
		{
			if (s.m_Sound)
				SEffectManager.DestroySound(s.m_Sound);
			s.m_Sound = null;
		}
	}

	static void Tick()
	{
		vector cam = g_Game.GetCurrentCameraPosition();
		// pick the MAX_ACTIVE nearest sources in range (simple insertion into a tiny sorted list)
		array<int> best = s_Best;
		array<float> bestD = s_BestD;
		best.Clear();
		bestD.Clear();
		for (int i = 0; i < s_Sources.Count(); i++)
		{
			SKY_AmbientSource s = s_Sources[i];
			if (!s.m_Obj)
				continue;
			if (!s.m_PosSet)
			{
				s.m_Pos = s.m_Obj.GetPosition();
				s.m_PosSet = s.m_Pos != vector.Zero;
				if (!s.m_PosSet)
					continue;
			}
			float d = vector.DistanceSq(s.m_Pos, cam);
			if (d > s.m_Range2)
				continue;
			int at = bestD.Count();
			while (at > 0 && bestD[at - 1] > d)
				at--;
			if (at >= MAX_ACTIVE)
				continue;
			best.InsertAt(i, at);
			bestD.InsertAt(d, at);
			if (best.Count() > MAX_ACTIVE)
			{
				best.Remove(MAX_ACTIVE);
				bestD.Remove(MAX_ACTIVE);
			}
		}
		for (int k = 0; k < s_Sources.Count(); k++)
		{
			SKY_AmbientSource src = s_Sources[k];
			bool want = best.Find(k) != -1;
			if (want && !src.m_Sound)
			{
				src.m_Sound = SEffectManager.PlaySoundCachedParams(src.m_SoundSet, src.m_Pos, 1.0, 1.0, true);
			}
			else if (!want && src.m_Sound)
			{
				SEffectManager.DestroySound(src.m_Sound);
				src.m_Sound = null;
			}
		}
	}
}

//! Ferris wheel (D61 landmark): creak + wind loop.
class Land_SKY_Fair_FerrisWheel extends House
{
	void Land_SKY_Fair_FerrisWheel()
	{
		SKY_Ambience.Register(this, "SKY_Creak_SoundSet", 60.0);
	}

	void ~Land_SKY_Fair_FerrisWheel()
	{
		SKY_Ambience.Unregister(this);
	}
}
