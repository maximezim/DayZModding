/*
	Sewer flooding (D63, ROADMAP idea 18). The sewer pieces (Sewer_Straight / Access / End / Junction, built
	by assets/blender/build_underground.py) carry the channel water as selection `flood`, moved up by a
	model.cfg translation on the user animation source `flood` (config AnimationSources, gen_configs.py).
	Server, one 10 s timer (no per-frame work):
	- target = clamp((rain - RAIN_START) / RAIN_SPAN, 0, 1) from Weather.GetRain().GetActual()
	  (3_game/weather.c:38/189, CGame.GetWeather game.c:1349); the level rises to it in 10 min and drains
	  in 30 min; SetAnimationPhase("flood", level) (3_game/entities/entity.c:15) on every registered
	  sewer piece only when the level moved by PHASE_STEP;
	- players inside a sewer piece (WorldToModel, object.c:870) below the water: clothes on feet / legs
	  (and body when deeper) get wet (ItemBase.AddWet itembase.c:3721, so the vanilla Environment turns the
	  player wet, environment.c:264-271); over the head: DROWN_DMG health per tick.
	Pieces register themselves (bounded MAX_PIECES); only pieces within 10 m of a player are tested.
*/
class Land_SKY_Sewer_Base extends House
{
	void Land_SKY_Sewer_Base()
	{
		if (g_Game.IsServer())
			SKY_Underground.Register(this);
	}

	void ~Land_SKY_Sewer_Base()
	{
		SKY_Underground.Unregister(this);
	}

	//! Square pieces (junction) are as long as they are wide.
	float SkyHalfLength()
	{
		return SKY_Under.HALF_LENGTH;
	}

	float SkyHalfWidth()
	{
		return SKY_Under.HALF_WIDTH;
	}
}

class Land_SKY_Sewer_Straight extends Land_SKY_Sewer_Base {}
class Land_SKY_Sewer_Access extends Land_SKY_Sewer_Base {}
class Land_SKY_Sewer_End extends Land_SKY_Sewer_Base {}
class Land_SKY_Sewer_Junction extends Land_SKY_Sewer_Base
{
	override float SkyHalfWidth()
	{
		return SKY_Under.HALF_LENGTH;
	}
}

class SKY_Underground
{
	protected static ref array<Land_SKY_Sewer_Base> s_Pieces = new array<Land_SKY_Sewer_Base>();
	protected static ref SKY_Underground s_Instance;

	protected ref array<Man> m_Players = new array<Man>();
	protected float m_Level;			//!< 0..1
	protected float m_Applied = -1.0;	//!< last phase pushed to the pieces

	static void Register(Land_SKY_Sewer_Base p)
	{
		if (s_Pieces && s_Pieces.Count() < SKY_Under.MAX_PIECES && s_Pieces.Find(p) == -1)
			s_Pieces.Insert(p);
	}

	static void Unregister(Land_SKY_Sewer_Base p)
	{
		if (s_Pieces)
			s_Pieces.RemoveItem(p);
	}

	static void Start()
	{
		if (!g_Game.IsServer() || s_Instance)
			return;
		s_Instance = new SKY_Underground();
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(s_Instance.Tick, SKY_Under.TICK_MS, true);
	}

	static void Stop()
	{
		if (!s_Instance)
			return;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(s_Instance.Tick);
		s_Instance = null;
	}

	void Tick()
	{
		if (s_Pieces.Count() == 0)
			return;
		float dt = SKY_Under.TICK_MS * 0.001;
		float rain = 0;
		Weather w = g_Game.GetWeather();
		if (w && w.GetRain())
			rain = w.GetRain().GetActual();
		float target = Math.Clamp((rain - SKY_Under.RAIN_START) / SKY_Under.RAIN_SPAN, 0, 1);
		if (target > m_Level)
			m_Level = Math.Min(target, m_Level + SKY_Under.RISE_PER_S * dt);
		else
			m_Level = Math.Max(target, m_Level - SKY_Under.DRAIN_PER_S * dt);
		if (Math.AbsFloat(m_Level - m_Applied) >= SKY_Under.PHASE_STEP || (m_Level == 0 && m_Applied != 0))
		{
			m_Applied = m_Level;
			foreach (Land_SKY_Sewer_Base p : s_Pieces)
			{
				if (p)
					p.SetAnimationPhase("flood", m_Level);
			}
		}
		if (m_Level <= 0)
			return;
		float water = SKY_Under.WALKWAY + SKY_Under.WATER_BASE + m_Level * SKY_Under.WATER_RISE;	// model z of the surface
		g_Game.GetPlayers(m_Players);
		foreach (Man m : m_Players)
		{
			PlayerBase pb = PlayerBase.Cast(m);
			if (!pb || !pb.IsAlive())
				continue;
			vector pp = pb.GetPosition();
			foreach (Land_SKY_Sewer_Base piece : s_Pieces)
			{
				if (!piece || vector.DistanceSq(piece.GetPosition(), pp) > 100.0)
					continue;
				vector lp = piece.WorldToModel(pp);
				if (Math.AbsFloat(lp[0]) > piece.SkyHalfWidth() || Math.AbsFloat(lp[2]) > piece.SkyHalfLength() || lp[1] > -2.0)
					continue;										// model: x across, z along (engine Y-up), y height
				float depth = water - lp[1];
				if (depth > SKY_Under.WET_DEPTH)
					Soak(pb, depth);
				if (depth > SKY_Under.DROWN_DEPTH)
				{
					pb.AddHealth("GlobalHealth", "Health", -SKY_Under.DROWN_DMG);
					pb.MessageImportant("The sewer water is over your head.");
				}
				break;
			}
		}
	}

	protected void Soak(PlayerBase pb, float depth)
	{
		Wet(pb, "Feet");
		Wet(pb, "Legs");
		if (depth > SKY_Under.BODY_DEPTH)
			Wet(pb, "Body");
	}

	protected void Wet(PlayerBase pb, string slot)
	{
		ItemBase it = ItemBase.Cast(pb.GetItemOnSlot(slot));
		if (it)
			it.AddWet(it.GetWetMax());
	}
}
