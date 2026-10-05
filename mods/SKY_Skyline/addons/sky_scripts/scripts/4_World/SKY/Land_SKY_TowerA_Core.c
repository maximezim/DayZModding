/*
	Tower core: stairs + one teleport-style elevator.

	Trust model
	- No custom RPC. Requests arrive as vanilla user actions; the server re-runs
	  ActionCondition (ActionManagerServer.StartDeliveredAction -> ActionBase.Can)
	  and SkyServerRequest() validates everything again from server state.
	- The client never sends a floor. The command (CALL/UP/DOWN/LOBBY/ROOF) is
	  only a direction; the source stop is derived from the player's server-side
	  position, the target from the config'd stop list.
	- Occupants are recomputed from server positions at departure and arrival.

	Replicated state: car level, state, doors-open flag (net sync vars); clients
	apply the door animation in OnVariablesSynchronized (same pattern as the
	vanilla Land_Underground_EntranceBase).
*/
class Land_SKY_TowerA_Core extends House
{
	protected int m_SkyCarLevel;
	protected int m_SkyState;
	protected bool m_SkyDoorsOpen;

	// server only
	protected int m_SkyTargetLevel;
	protected int m_SkyNextUseMs;
	protected ref SKY_RateLimiter m_SkyPlayerLimiter;

	// config cache (both sides)
	protected ref array<float> m_SkyStops;
	protected int m_SkyMaxOccupants;
	protected int m_SkyCooldownMs;
	protected int m_SkyDoorOpenMs;
	protected int m_SkyTravelMsBase;
	protected int m_SkyTravelMsPerStop;
	protected float m_SkyCabHalfX;
	protected float m_SkyCabHalfY;
	protected float m_SkyCabHeight;
	protected float m_SkyPanelReach;
	protected ref array<vector> m_SkyCabPos;	// model-space memory points, cached per stop
	protected ref array<vector> m_SkyPanelPos;
	protected ref array<vector> m_SkyCallPos;

	void Land_SKY_TowerA_Core()
	{
		RegisterNetSyncVariableInt("m_SkyCarLevel", 0, 31);
		RegisterNetSyncVariableInt("m_SkyState", 0, SKY_ElevatorState.TRAVEL);
		RegisterNetSyncVariableBool("m_SkyDoorsOpen");
		SkyLoadConfig();
	}

	void ~Land_SKY_TowerA_Core()
	{
		if (g_Game)
		{
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(SkyDepart);
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(SkyArrive);
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(SkyAutoClose);
		}
	}

	protected void SkyLoadConfig()
	{
		m_SkyStops = new array<float>();
		ConfigGetFloatArray("skyStops", m_SkyStops);
		m_SkyMaxOccupants   = ConfigGetInt("skyMaxOccupants");
		m_SkyCooldownMs     = ConfigGetInt("skyCooldownMs");
		m_SkyDoorOpenMs     = ConfigGetInt("skyDoorOpenMs");
		m_SkyTravelMsBase   = ConfigGetInt("skyTravelMsBase");
		m_SkyTravelMsPerStop = ConfigGetInt("skyTravelMsPerStop");
		m_SkyCabHalfX       = ConfigGetFloat("skyCabHalfX");
		m_SkyCabHalfY       = ConfigGetFloat("skyCabHalfY");
		m_SkyCabHeight      = ConfigGetFloat("skyCabHeight");
		m_SkyPanelReach     = ConfigGetFloat("skyPanelReach");
		if (m_SkyStops.Count() < 2 || m_SkyMaxOccupants < 1)
			SKY_Log.Warn(GetType() + ": invalid elevator config (skyStops / skyMaxOccupants)");
	}

	//! Memory points are cached once (model space); missing points disable that stop.
	protected void SkyCachePoints()
	{
		if (m_SkyCabPos)
			return;
		m_SkyCabPos = new array<vector>();
		m_SkyPanelPos = new array<vector>();
		m_SkyCallPos = new array<vector>();
		for (int i = 0; i < m_SkyStops.Count(); i++)
		{
			m_SkyCabPos.Insert(SkyPoint("elev_cab_l" + i));
			m_SkyPanelPos.Insert(SkyPoint("elev_panel_l" + i));
			m_SkyCallPos.Insert(SkyPoint("elev_call_l" + i));
		}
	}

	protected vector SkyPoint(string name)
	{
		if (MemoryPointExists(name))
			return GetMemoryPointPos(name);
		SKY_Log.Warn(GetType() + ": missing memory point " + name);
		return "0 -10000 0";	// unreachable sentinel
	}

	override void EEInit()
	{
		super.EEInit();
		if (g_Game.IsServer())
		{
			m_SkyPlayerLimiter = new SKY_RateLimiter(SKY_Const.PLAYER_REQUEST_INTERVAL_MS);
			m_SkyCarLevel = 0;
			m_SkyState = SKY_ElevatorState.IDLE;
			m_SkyDoorsOpen = false;
			SetSynchDirty();
		}
		SkyApplyDoors();
	}

	override void OnVariablesSynchronized()
	{
		super.OnVariablesSynchronized();
		SkyApplyDoors();
	}

	//! Animate every landing door to match (car level, doors open). Server needs it for collisions.
	protected void SkyApplyDoors()
	{
		for (int i = 0; i < m_SkyStops.Count(); i++)
		{
			float phase = 0;
			if (m_SkyDoorsOpen && i == m_SkyCarLevel)
				phase = 1;
			SetAnimationPhase("elev_door_l" + i, phase);
		}
	}

	// ------------------------------------------------------------ geometry queries (both sides)
	int SkyStopCount()
	{
		return m_SkyStops.Count();
	}

	//! Stop index whose floor the player stands on (model-space height), or -1.
	int SkyLevelOfPlayer(PlayerBase player)
	{
		vector ms = WorldToModel(player.GetPosition());
		for (int i = 0; i < m_SkyStops.Count(); i++)
		{
			if (Math.AbsFloat(ms[1] - m_SkyStops[i]) < 1.0)
				return i;
		}
		return -1;
	}

	//! Player is inside the cab volume at stop `level` (doors line excluded).
	bool SkyIsInCab(PlayerBase player, int level)
	{
		if (level < 0 || level >= m_SkyStops.Count())
			return false;
		SkyCachePoints();
		vector c = m_SkyCabPos[level];
		vector p = WorldToModel(player.GetPosition());
		if (Math.AbsFloat(p[0] - c[0]) > m_SkyCabHalfX)
			return false;
		if (Math.AbsFloat(p[2] - c[2]) > m_SkyCabHalfY)
			return false;
		return p[1] > m_SkyStops[level] - 0.5 && p[1] < m_SkyStops[level] + m_SkyCabHeight;
	}

	//! Player (chest height) within `reach` of a cached model-space point.
	bool SkyIsNear(PlayerBase player, vector modelPoint, float reach)
	{
		vector target = ModelToWorld(modelPoint);
		vector chest = player.GetPosition() + "0 1.2 0";
		return vector.DistanceSq(target, chest) <= reach * reach;
	}

	protected int SkyTargetFor(int cmd, int level)
	{
		switch (cmd)
		{
			case SKY_ElevatorCmd.CALL:  return level;
			case SKY_ElevatorCmd.UP:    return level + 1;
			case SKY_ElevatorCmd.DOWN:  return level - 1;
			case SKY_ElevatorCmd.LOBBY: return 0;
			case SKY_ElevatorCmd.ROOF:  return m_SkyStops.Count() - 1;
			case SKY_ElevatorCmd.OPEN:  return level;
		}
		return -1;
	}

	/*!
		Pure check used by ActionCondition on both sides (server re-runs it).
		Uses only replicated state + positions, never client-provided numbers.
	*/
	bool SkyCanRequest(PlayerBase player, int cmd)
	{
		if (!player || !player.IsAlive() || player.IsUnconscious() || player.IsRestrained())
			return false;
		if (m_SkyState != SKY_ElevatorState.IDLE && m_SkyState != SKY_ElevatorState.OPEN)
			return false;

		int level = SkyLevelOfPlayer(player);
		if (level < 0)
			return false;
		int target = SkyTargetFor(cmd, level);
		if (target < 0 || target >= m_SkyStops.Count())
			return false;
		SkyCachePoints();

		if (cmd == SKY_ElevatorCmd.CALL)
		{
			// From the landing: car elsewhere, or here with doors closed.
			if (SkyIsInCab(player, level))
				return false;
			if (m_SkyCarLevel == level && m_SkyDoorsOpen)
				return false;
			return SkyIsNear(player, m_SkyCallPos[level], m_SkyPanelReach);
		}

		// Everything else is pressed on the cab panel, from inside the cab.
		if (!SkyIsInCab(player, level) || !SkyIsNear(player, m_SkyPanelPos[level], m_SkyPanelReach))
			return false;
		if (cmd == SKY_ElevatorCmd.OPEN)
			return !(level == m_SkyCarLevel && m_SkyDoorsOpen);	// works at ANY stop: rescue path
		return level == m_SkyCarLevel && target != level;
	}

	// ------------------------------------------------------------ server state machine
	protected array<PlayerBase> SkyOccupants(int level)
	{
		array<PlayerBase> result = new array<PlayerBase>();
		array<Man> players = new array<Man>();
		g_Game.GetPlayers(players);
		foreach (Man m : players)
		{
			PlayerBase pb = PlayerBase.Cast(m);
			if (pb && pb.IsAlive() && SkyIsInCab(pb, level))
				result.Insert(pb);
		}
		return result;
	}

	protected void SkyNotify(PlayerBase player, string text)
	{
		if (player && player.GetIdentity())
			NotificationSystem.SendNotificationToPlayerExtended(player, 4, "Elevator", text, "");
	}

	protected void SkySetState(int state, bool doorsOpen)
	{
		m_SkyState = state;
		m_SkyDoorsOpen = doorsOpen;
		SkyApplyDoors();
		SetSynchDirty();
	}

	//! Entry point from the elevator actions (server only).
	void SkyServerRequest(PlayerBase player, int cmd)
	{
		if (!g_Game.IsServer() || !player || !player.GetIdentity())
			return;

		int now = g_Game.GetTime();
		if (!m_SkyPlayerLimiter.Allow(player.GetIdentity().GetId(), now))
			return;	// silent: action spam
		if (!SkyCanRequest(player, cmd))
			return;	// state changed or position invalid since the client checked
		if (now < m_SkyNextUseMs)
		{
			SkyNotify(player, "Please wait...");
			return;
		}

		int level = SkyLevelOfPlayer(player);
		int target = SkyTargetFor(cmd, level);
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(SkyAutoClose);

		if ((cmd == SKY_ElevatorCmd.CALL || cmd == SKY_ElevatorCmd.OPEN) && target == m_SkyCarLevel)
		{
			SkySetState(SKY_ElevatorState.OPEN, true);
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyAutoClose, m_SkyDoorOpenMs, false);
			return;
		}

		if (cmd == SKY_ElevatorCmd.CALL || cmd == SKY_ElevatorCmd.OPEN)
		{
			// Fetching the car from another stop must not drag people who are riding it.
			if (SkyOccupants(m_SkyCarLevel).Count() > 0)
			{
				SkyNotify(player, "Elevator in use");
				return;
			}
		}
		else if (SkyOccupants(m_SkyCarLevel).Count() > m_SkyMaxOccupants)
		{
			SkyNotify(player, "Overloaded (max " + m_SkyMaxOccupants + ")");
			return;
		}

		m_SkyTargetLevel = target;
		m_SkyNextUseMs = now + m_SkyCooldownMs;
		SkySetState(SKY_ElevatorState.CLOSING, false);
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyDepart, SKY_Const.DOOR_ANIM_MS, false);
	}

	protected void SkyDepart()
	{
		// Re-check capacity with doors shut: someone may have squeezed in while closing.
		if (SkyOccupants(m_SkyCarLevel).Count() > m_SkyMaxOccupants)
		{
			foreach (PlayerBase p : SkyOccupants(m_SkyCarLevel))
				SkyNotify(p, "Overloaded (max " + m_SkyMaxOccupants + ")");
			SkySetState(SKY_ElevatorState.OPEN, true);
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyAutoClose, m_SkyDoorOpenMs, false);
			return;
		}
		SkySetState(SKY_ElevatorState.TRAVEL, false);
		int stops = Math.AbsInt(m_SkyTargetLevel - m_SkyCarLevel);
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyArrive, m_SkyTravelMsBase + stops * m_SkyTravelMsPerStop, false);
	}

	protected void SkyArrive()
	{
		int from = m_SkyCarLevel;
		int to = m_SkyTargetLevel;
		if (to < 0 || to >= m_SkyStops.Count())
		{
			SKY_Log.Warn(GetType() + ": invalid target level " + to);
			SkySetState(SKY_ElevatorState.IDLE, false);
			return;
		}

		float dy = m_SkyStops[to] - m_SkyStops[from];
		PluginAdminLog adminLog = PluginAdminLog.Cast(GetPlugin(PluginAdminLog));
		foreach (PlayerBase p : SkyOccupants(from))
		{
			// Same exclusions as vanilla DeveloperTeleport.GetPlayerRootForTeleporting: never move
			// a player that is in a vehicle or attached to another object.
			if (p.GetCommand_Vehicle() || p.GetParent())
				continue;
			// Same spot in the cab, `dy` higher/lower in the building's own frame.
			vector ms = WorldToModel(p.GetPosition());
			ms[1] = ms[1] + dy;
			vector dst = ModelToWorld(ms);
			vector src = p.GetPosition();
			p.SetPosition(dst);
			if (adminLog)
				adminLog.PlayerTeleportedLog(p, src, dst, "SKY elevator " + from + "->" + to);
		}

		m_SkyCarLevel = to;
		SkySetState(SKY_ElevatorState.OPEN, true);
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyAutoClose, m_SkyDoorOpenMs, false);
	}

	protected void SkyAutoClose()
	{
		if (m_SkyState == SKY_ElevatorState.OPEN)
			SkySetState(SKY_ElevatorState.IDLE, false);
	}

	override void SetActions()
	{
		super.SetActions();
		AddAction(ActionSKY_ElevatorCall);
		AddAction(ActionSKY_ElevatorUp);
		AddAction(ActionSKY_ElevatorDown);
		AddAction(ActionSKY_ElevatorLobby);
		AddAction(ActionSKY_ElevatorRoof);
		AddAction(ActionSKY_ElevatorOpen);
	}
}
