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
		SKY_Underground.Register(this);		// both sides: the client fallback animates its own copy (re-review H)
		SKY_Ambience.Register(this, "SKY_Drips_SoundSet", 25.0, Vector(0, SKY_Under.WALKWAY + SKY_Under.EAR, 0), SKY_Ambience.UNDER_DY);	// client only (D65; floor D68)
	}

	void ~Land_SKY_Sewer_Base()
	{
		SKY_Underground.Unregister(this);
		SKY_Ambience.Unregister(this);
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
class Land_SKY_Sewer_Collapsed extends Land_SKY_Sewer_Base {}		// D67
class Land_SKY_Sewer_FloodedEnd extends Land_SKY_Sewer_Base {}		// D67: the modelled water is decor; flooding/drowning still follow the server flood level
class Land_SKY_Sewer_Junction extends Land_SKY_Sewer_Base
{
	override float SkyHalfWidth()
	{
		return SKY_Under.HALF_LENGTH;
	}
}

//! Metro pieces (D68): no flooding (dry, deeper than the sewers), only the tunnel draught loop on clients.
class Land_SKY_Metro_Base extends House
{
	void Land_SKY_Metro_Base()
	{
		SKY_Ambience.Register(this, "SKY_Wind_SoundSet", 40.0, Vector(0, SKY_Under.METRO_FLOOR + SKY_Under.EAR, 0), SKY_Ambience.UNDER_DY);	// client only
	}

	void ~Land_SKY_Metro_Base()
	{
		SKY_Ambience.Unregister(this);
	}
}

class Land_SKY_Metro_Tunnel extends Land_SKY_Metro_Base {}
class Land_SKY_Metro_End extends Land_SKY_Metro_Base {}
class Land_SKY_Metro_Collapsed extends Land_SKY_Metro_Base {}
class Land_SKY_Metro_Station extends Land_SKY_Metro_Base {}
class Land_SKY_Metro_Station_B extends Land_SKY_Metro_Base {}
class Land_SKY_Metro_Station_C extends Land_SKY_Metro_Base {}
class Land_SKY_Metro_Station_D extends Land_SKY_Metro_Base {}

class SKY_Underground
{
	protected static ref array<Land_SKY_Sewer_Base> s_Pieces = new array<Land_SKY_Sewer_Base>();
	protected static bool s_CapWarned;
	protected static ref SKY_Underground s_Instance;
	protected static ref SKY_Underground s_Client;		//!< full audit perf M5: client-side water animation
	protected bool m_Snapped;							//!< client: first tick jumps to the weather level

	protected ref array<Man> m_Players = new array<Man>();
	protected float m_Level;			//!< 0..1
	protected float m_Applied;			//!< last phase pushed to the pieces (pieces start at initPhase 0)
	protected ref map<string, int> m_FirstSeen = new map<string, int>();	//!< identity -> first tick seen (grace)
	protected ref map<string, bool> m_Under = new map<string, bool>();		//!< identity -> was under water last tick

	static void Register(Land_SKY_Sewer_Base p)
	{
		if (!s_Pieces)
			return;
		if (s_Pieces.Count() >= SKY_Under.MAX_PIECES)
		{
			if (!s_CapWarned)
				SKY_Log.Warn("sewer piece cap " + SKY_Under.MAX_PIECES.ToString() + " reached: extra pieces will not flood");
			s_CapWarned = true;
			return;
		}
		s_Pieces.Insert(p);					// constructors register each piece once
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

	//! Full audit perf M5 / P29: map objects of a custom terrain are not networked, so the server's
	//! SetAnimationPhase may never reach clients. Each client derives the same level from the synced rain and
	//! animates the water locally (visual only; soaking and drowning stay server-side).
	static void StartClient()
	{
		if (g_Game.IsDedicatedServer() || s_Client || (g_Game.IsServer() && !g_Game.IsMultiplayer()))
			return;										// offline: the server instance already animates
		s_Client = new SKY_Underground();
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(s_Client.TickClient, SKY_Under.TICK_MS, true);
	}

	static void StopClient()
	{
		if (!s_Client)
			return;
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(s_Client.TickClient);
		s_Client = null;
	}

	protected float WeatherTarget()
	{
		float rain = 0;
		Weather w = g_Game.GetWeather();
		if (w && w.GetRain())
			rain = w.GetRain().GetActual();
		return Math.Clamp((rain - SKY_Under.RAIN_START) / SKY_Under.RAIN_SPAN, 0, 1);
	}

	protected void Integrate(float target, float dt)
	{
		if (target > m_Level)
			m_Level = Math.Min(target, m_Level + SKY_Under.RISE_PER_S * dt);
		else
			m_Level = Math.Max(target, m_Level - SKY_Under.DRAIN_PER_S * dt);
	}

	protected void ApplyPhase()
	{
		if (Math.AbsFloat(m_Level - m_Applied) >= SKY_Under.PHASE_STEP || (m_Level == 0 && m_Applied > 0))
		{
			m_Applied = m_Level;
			foreach (Land_SKY_Sewer_Base p : s_Pieces)
			{
				if (p)
					p.SetAnimationPhase("flood", m_Level);
			}
		}
	}

	void TickClient()
	{
		if (s_Pieces.Count() == 0)
			return;
		float target = WeatherTarget();
		if (!m_Snapped)
		{
			m_Level = target;							// a client that joins mid-flood sees it at once
			m_Snapped = true;
		}
		else
			Integrate(target, SKY_Under.TICK_MS * 0.001);
		ApplyPhase();
	}

	void Tick()
	{
		if (s_Pieces.Count() == 0)
			return;
		Integrate(WeatherTarget(), SKY_Under.TICK_MS * 0.001);
		ApplyPhase();
		if (m_Level <= 0)
			return;
		float water = SKY_Under.WALKWAY + SKY_Under.WATER_BASE + m_Level * SKY_Under.WATER_RISE;	// model z of the surface
		int now = g_Game.GetTime();
		float reach2 = SKY_Under.REACH_H * SKY_Under.REACH_H;
		g_Game.GetPlayers(m_Players);
		if (m_FirstSeen.Count() > 4 * m_Players.Count() + 64)		// bounded: forget players who left
			m_FirstSeen.Clear();
		if (m_Under.Count() > m_Players.Count() + 16)				// full audit info: same bound (re-added next tick)
			m_Under.Clear();
		foreach (Man m : m_Players)
		{
			PlayerBase pb = PlayerBase.Cast(m);
			if (!pb || !pb.IsAlive() || !pb.GetIdentity())
				continue;
			string id = pb.GetIdentity().GetId();
			int first;
			if (!m_FirstSeen.Find(id, first))
			{
				first = now;
				m_FirstSeen.Set(id, now);
			}
			vector pp = pb.GetPosition();
			if (pp[1] > g_Game.SurfaceY(pp[0], pp[2]) - 1.5)		// on the surface: nothing to do (perf review D65)
				continue;
			bool under = false;
			foreach (Land_SKY_Sewer_Base piece : s_Pieces)
			{
				if (!piece)
					continue;
				vector cp = piece.GetPosition();
				float dx = cp[0] - pp[0];
				float dz = cp[2] - pp[2];
				if (dx * dx + dz * dz > reach2)
					continue;
				vector lp = piece.WorldToModel(pp);
				if (Math.AbsFloat(lp[0]) > piece.SkyHalfWidth() || Math.AbsFloat(lp[2]) > piece.SkyHalfLength() || lp[1] > -2.0)
					continue;										// model: x across, z along (engine Y-up), y height
				float depth = water - lp[1];
				if (depth > SKY_Under.WET_DEPTH)
					Soak(pb, depth);
				// no damage right after connecting, nor to players who cannot get out (security review D65)
				if (depth > SKY_Under.DROWN_DEPTH && now - first > SKY_Under.DROWN_GRACE_MS && !pb.IsUnconscious() && !pb.IsRestrained())
				{
					under = true;
					pb.AddHealth("GlobalHealth", "Health", -SKY_Under.DROWN_DMG);
				}
				break;
			}
			bool was = m_Under.Contains(id);
			if (under && !was)
			{
				m_Under.Set(id, true);
				pb.MessageImportant("The sewer water is over your head.");
				SKY_Log.Info("sewer drowning damage: " + id);
			}
			else if (!under && was)
				m_Under.Remove(id);
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
