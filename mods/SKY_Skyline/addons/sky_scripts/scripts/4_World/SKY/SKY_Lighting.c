/*
	SKY building lights (D55): night-only interior point lights at the light_N memory points of
	the tower modules. Client only; nothing is synchronised and nothing runs on the server.

	Verified vanilla pattern (scripts reference, 4_world):
	- light class: entities/scriptedlightbase/pointlightbase/entrancelight.c:1-17
	  (PointLightBase + SetVisibleDuringDaylight / SetRadiusTo / SetBrightnessTo / SetFlareVisible /
	  SetCastShadow / SetAmbientColor / SetDiffuseColor)
	- building owning lights: entities/building/wrecks/staticobj_roadblock_wood_small.c:1-24
	  (House.EEInit creates with ScriptedLightBase.CreateLightAtObjMemoryPoint when not the
	  dedicated server, EEDelete calls Destroy)
	- CreateLightAtObjMemoryPoint returns null when the memory point is missing
	  (entities/scriptedlightbase.c:212-221); CreateLight returns null on the server
	  (scriptedlightbase.c:224-250).
	Untested (PENDING_VERIFICATION P10): script-only light classes spawn without a CfgVehicles entry.
	If not, CreateLight logs an error and returns null; the building stays dark, nothing else breaks.
*/
class SKY_InteriorLight extends PointLightBase
{
	void SKY_InteriorLight()
	{
		SetVisibleDuringDaylight(false);	// night only (vanilla m_NightTimeOnlyLights handling)
		SetRadiusTo(8);
		SetBrightnessTo(0.6);
		SetFlareVisible(false);
		SetCastShadow(false);
		SetAmbientColor(1.0, 0.88, 0.72);
		SetDiffuseColor(1.0, 0.88, 0.72);
	}
}

//! Taller, brighter light for the double-height lobby.
class SKY_HallLight extends SKY_InteriorLight
{
	void SKY_HallLight()
	{
		SetRadiusTo(13);
		SetBrightnessTo(0.9);
	}
}

//! Cool white for offices and plant rooms.
class SKY_OfficeLight extends SKY_InteriorLight
{
	void SKY_OfficeLight()
	{
		SetAmbientColor(0.85, 0.92, 1.0);
		SetDiffuseColor(0.85, 0.92, 1.0);
	}
}

//! D61 hypermarket: cold, over-bright fluorescent wash that stays on by day too (ROADMAP idea 4:
//! "une lumiere blanche qui fait mal aux yeux" - the emergency generators still run).
class SKY_HyperLight extends SKY_InteriorLight
{
	void SKY_HyperLight()
	{
		SetVisibleDuringDaylight(true);
		SetRadiusTo(24);
		SetBrightnessTo(2.2);
		SetAmbientColor(0.9, 0.97, 1.0);
		SetDiffuseColor(0.9, 0.97, 1.0);
	}
}

/*
	Full audit perf H1: buildings no longer create their lights on init. They register with this client-only
	director; one 1 s timer lights the nearest LIGHTS_MAX_BUILDINGS within LIGHTS_ON_RANGE of the camera and
	switches buildings off beyond LIGHTS_OFF_RANGE. Map objects of a terrain city never get EEDelete, so the
	registry is pruned of null entries every tick and bounded (LIGHTS_MAX_REGISTERED).
*/
class SKY_LightDirector
{
	protected static ref array<SKY_LitBuilding> s_All = new array<SKY_LitBuilding>();
	protected static ref array<SKY_LitBuilding> s_Cand = new array<SKY_LitBuilding>();	//!< reused per tick
	protected static ref array<float> s_CandD = new array<float>();
	protected static bool s_Running;

	static void Register(SKY_LitBuilding b)
	{
		if (g_Game.IsDedicatedServer() || !SKY_Const.LIGHTS_ENABLED || !b || s_All.Count() >= SKY_Const.LIGHTS_MAX_REGISTERED)
			return;
		s_All.Insert(b);					// once per building (SKY_LitBuilding.m_SkyRegistered)
	}

	static void Unregister(SKY_LitBuilding b)
	{
		if (!s_All)								// statics torn down first at script unload (re-review L)
			return;
		int i = s_All.Find(b);
		if (i >= 0)
			s_All.Remove(i);
	}

	static void StartClient()
	{
		if (g_Game.IsDedicatedServer() || s_Running || !SKY_Const.LIGHTS_ENABLED)
			return;
		s_Running = true;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SKY_LightDirector.Tick, SKY_Const.LIGHTS_TICK_MS, true);
	}

	static void StopClient()
	{
		if (!s_Running)
			return;
		s_Running = false;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(SKY_LightDirector.Tick);
		foreach (SKY_LitBuilding b : s_All)
		{
			if (b)
				b.SkySetLit(false);
		}
		s_All.Clear();							// re-review perf L: no O(n) Find per destructor at mission end
	}

	static void Tick()
	{
		vector cam = g_Game.GetCurrentCameraPosition();
		// D94 perf audit M: by day the lights are invisible (SetVisibleDuringDaylight false) but would still run their
		// per-frame update - only buildings lit by day (hypermarket generators) stay lit (world.IsNight: roadflare.c:205)
		bool night = g_Game.GetWorld() && g_Game.GetWorld().IsNight();
		float on2 = SKY_Const.LIGHTS_ON_RANGE * SKY_Const.LIGHTS_ON_RANGE;
		float off2 = SKY_Const.LIGHTS_OFF_RANGE * SKY_Const.LIGHTS_OFF_RANGE;
		int lit = 0;
		s_Cand.Clear();
		s_CandD.Clear();
		for (int i = s_All.Count() - 1; i >= 0; i--)
		{
			SKY_LitBuilding b = s_All[i];
			if (!b)
			{
				s_All.Remove(i);
				continue;
			}
			float d = vector.DistanceSq(b.GetPosition(), cam);
			if (!night && !b.SkyLitByDay())
				d = off2 + 1;									// out of range by day
			if (b.SkyIsLit())
			{
				if (d > off2)
					b.SkySetLit(false);
				else
					lit++;
			}
			else if (d < on2)
			{
				int at = s_CandD.Count();					// sorted insert, nearest first, bounded (re-review perf M)
				while (at > 0 && s_CandD[at - 1] > d)
					at--;
				if (at >= SKY_Const.LIGHTS_MAX_BUILDINGS)
					continue;
				s_Cand.InsertAt(b, at);
				s_CandD.InsertAt(d, at);
				if (s_Cand.Count() > SKY_Const.LIGHTS_MAX_BUILDINGS)
				{
					s_Cand.Remove(s_Cand.Count() - 1);
					s_CandD.Remove(s_CandD.Count() - 1);
				}
			}
		}
		int made = 0;									// spread a first tick / teleport over several ticks
		for (int k = 0; k < s_Cand.Count() && lit < SKY_Const.LIGHTS_MAX_BUILDINGS && made < SKY_Const.LIGHTS_CREATE_PER_TICK; k++)
		{
			s_Cand[k].SkySetLit(true);
			lit++;
			made++;
		}
		s_Cand.Clear();									// no stale references between ticks
	}
}

class SKY_LitBuilding extends House
{
	protected ref array<ScriptedLightBase> m_SkyLights;
	protected bool m_SkyLightsDone;
	protected bool m_SkyRegistered;
	protected static ref array<string> s_SkyPts = new array<string>();

	protected void SkyRegister()
	{
		if (m_SkyRegistered)
			return;
		m_SkyRegistered = true;
		SKY_LightDirector.Register(this);
	}

	//! Light memory points in priority order (capped by SkyLightCount()).
	protected void SkyLightPoints(notnull array<string> pts)
	{
		pts.Insert("light_1");
		pts.Insert("light_4");
		pts.Insert("light_2");
		pts.Insert("light_3");
	}

	protected int SkyLightCount()
	{
		return SKY_Const.LIGHTS_PER_MODULE;
	}

	protected typename SkyLightType()
	{
		return SKY_InteriorLight;
	}

	// Same double entry as Land_SKY_TowerA_Lobby: static map objects may only get DeferredInit.
	override void EEInit()
	{
		super.EEInit();
		SkyRegister();
	}

	override void DeferredInit()
	{
		super.DeferredInit();
		SkyRegister();
	}

	override void EEDelete(EntityAI parent)
	{
		super.EEDelete(parent);
		SKY_LightDirector.Unregister(this);
		SkyDestroyLights();
	}

	void ~SKY_LitBuilding()
	{
		SKY_LightDirector.Unregister(this);
	}

	bool SkyIsLit()
	{
		return m_SkyLightsDone;
	}

	//! Lit in daylight too (hypermarket emergency lighting); the rest light up at night only.
	bool SkyLitByDay()
	{
		return false;
	}

	//! Director only (client).
	void SkySetLit(bool lit)
	{
		if (lit)
			SkyCreateLights();
		else
			SkyDestroyLights();
	}

	protected void SkyCreateLights()
	{
		if (m_SkyLightsDone || !SKY_Const.LIGHTS_ENABLED || g_Game.IsDedicatedServer())
			return;
		m_SkyLightsDone = true;
		if (!m_SkyLights)
			m_SkyLights = new array<ScriptedLightBase>();
		array<string> pts = s_SkyPts;					// reused (re-review perf L); filled per class order
		pts.Clear();
		SkyLightPoints(pts);
		int n = SkyLightCount();
		if (n > pts.Count())
			n = pts.Count();
		for (int i = 0; i < n; i++)
		{
			ScriptedLightBase light = ScriptedLightBase.CreateLightAtObjMemoryPoint(SkyLightType(), this, pts[i]);
			if (light)
				m_SkyLights.Insert(light);
		}
	}

	protected void SkyDestroyLights()
	{
		if (!m_SkyLights)
			return;
		foreach (ScriptedLightBase light : m_SkyLights)
		{
			if (light)
				light.Destroy();
		}
		m_SkyLights.Clear();
		m_SkyLightsDone = false;
	}
}

// Lit tower modules (config classes in sky_towera / sky_floors; script class = config class name).
class Land_SKY_TowerA_Floor_Office extends SKY_LitBuilding
{
	override protected typename SkyLightType()
	{
		return SKY_OfficeLight;
	}
}

class Land_SKY_Floor_Apartments extends SKY_LitBuilding {}

class Land_SKY_Floor_Hotel extends SKY_LitBuilding {}

// Office plan with another facade skin (D60): same light_N points as the Tower A office floor.
class Land_SKY_Floor_Office_Concrete extends SKY_LitBuilding
{
	override protected typename SkyLightType()
	{
		return SKY_OfficeLight;
	}
}

class Land_SKY_Floor_Office_Brick extends SKY_LitBuilding
{
	override protected typename SkyLightType()
	{
		return SKY_OfficeLight;
	}
}

class Land_SKY_Floor_HQ extends SKY_LitBuilding
{
	override protected typename SkyLightType()
	{
		return SKY_OfficeLight;
	}
}

class Land_SKY_Floor_Mechanical extends SKY_LitBuilding
{
	override protected typename SkyLightType()
	{
		return SKY_OfficeLight;
	}
}
