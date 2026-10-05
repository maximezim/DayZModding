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

class SKY_LitBuilding extends House
{
	protected ref array<ScriptedLightBase> m_SkyLights;
	protected bool m_SkyLightsDone;

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
		SkyCreateLights();
	}

	override void DeferredInit()
	{
		super.DeferredInit();
		SkyCreateLights();
	}

	override void EEDelete(EntityAI parent)
	{
		super.EEDelete(parent);
		SkyDestroyLights();
	}

	protected void SkyCreateLights()
	{
		if (m_SkyLightsDone || !SKY_Const.LIGHTS_ENABLED || g_Game.IsDedicatedServer())
			return;
		m_SkyLightsDone = true;
		m_SkyLights = new array<ScriptedLightBase>();
		array<string> pts = new array<string>();
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

class Land_SKY_Floor_Mechanical extends SKY_LitBuilding
{
	override protected typename SkyLightType()
	{
		return SKY_OfficeLight;
	}
}
