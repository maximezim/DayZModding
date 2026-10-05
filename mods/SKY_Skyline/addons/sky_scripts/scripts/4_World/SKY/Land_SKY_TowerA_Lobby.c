/*
	Lobby with keycard security door(s).

	Config (generated):  skyKeycardDoors[] = {"door_sec"};  skyKeycardTiers[] = {2};  skyKeycardRelockMs
	Door indices follow the order of classes inside `class Doors` (index lookup below).

	Security
	- Keycard doors report no compatible lock type (EBuildingLockType.NONE) so
	  vanilla lockpicks cannot unlock/lock them; only SkyServerSwipe() unlocks.
	- Locked doors keep using the vanilla "locked" path (ActionLockedDoors only
	  rattles a locked door; Building.CanDoorBeOpened).
	- The door damage zone takes 0 damage (config), so it cannot be shot open.
	- The server re-validates hands, tier, ruin state, door state and distance;
	  denials are written to the admin log (rate limited per identity).
*/
class Land_SKY_TowerA_Lobby extends SKY_LitBuilding
{
	protected ref array<string> m_SkyKeycardDoorNames;
	protected ref array<int> m_SkyKeycardTiers;
	protected ref array<int> m_SkyKeycardDoorIdx;	// resolved door indices, same order
	protected int m_SkyRelockMs;
	protected ref array<float> m_SkyRoom;		// security room bounds, model space {x0, x1, z0, z1}
	protected bool m_SkySetupDone;
	protected ref SKY_RateLimiter m_SkySwipeLimiter;
	protected ref SKY_RateLimiter m_SkyDenyLogLimiter;

	void Land_SKY_TowerA_Lobby()
	{
		m_SkyKeycardDoorNames = new array<string>();
		m_SkyKeycardTiers = new array<int>();
		m_SkyKeycardDoorIdx = new array<int>();
		ConfigGetTextArray("skyKeycardDoors", m_SkyKeycardDoorNames);
		ConfigGetIntArray("skyKeycardTiers", m_SkyKeycardTiers);
		m_SkyRelockMs = ConfigGetInt("skyKeycardRelockMs");
		m_SkyRoom = new array<float>();
		ConfigGetFloatArray("skySecurityRoom", m_SkyRoom);
		SkyResolveDoorIndices();
	}

	void ~Land_SKY_TowerA_Lobby()
	{
		if (g_Game)
		{
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).RemoveByName(this, "SkyRelock");
			g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).Remove(SkyLockAll);
		}
	}

	//! Map Doors class names -> door index (config order of `class Doors` children).
	protected void SkyResolveDoorIndices()
	{
		string path = "CfgVehicles " + GetType() + " Doors";
		int count = g_Game.ConfigGetChildrenCount(path);
		foreach (string wanted : m_SkyKeycardDoorNames)
		{
			int found = -1;
			for (int i = 0; i < count; i++)
			{
				string child;
				g_Game.ConfigGetChildName(path, i, child);
				if (child == wanted)
				{
					found = i;
					break;
				}
			}
			if (found == -1)
				SKY_Log.Warn(GetType() + ": keycard door '" + wanted + "' not found in Doors");
			m_SkyKeycardDoorIdx.Insert(found);
		}
		if (m_SkyKeycardDoorIdx.Count() != m_SkyKeycardTiers.Count())
			SKY_Log.Warn(GetType() + ": skyKeycardDoors / skyKeycardTiers length mismatch");
	}

	// Setup runs from BOTH EEInit and DeferredInit (static map objects may only get the
	// latter); it is idempotent, so a keycard door can never be left unlocked at start.
	override void EEInit()
	{
		super.EEInit();
		SkyServerSetup();
	}

	override void DeferredInit()
	{
		super.DeferredInit();
		SkyServerSetup();
	}

	protected void SkyServerSetup()
	{
		if (!g_Game.IsServer() || m_SkySetupDone)
			return;
		m_SkySetupDone = true;
		m_SkySwipeLimiter = new SKY_RateLimiter(SKY_Const.PLAYER_REQUEST_INTERVAL_MS);
		m_SkyDenyLogLimiter = new SKY_RateLimiter(SKY_Const.DENIAL_LOG_INTERVAL_MS);
		SkyLockAll();
		// And once more after the door system has settled.
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyLockAll, 1000, false);
	}

	protected void SkyLockAll()
	{
		foreach (int idx : m_SkyKeycardDoorIdx)
		{
			if (idx < 0 || idx >= GetDoorCount())
				continue;
			if (!IsDoorLocked(idx))
				LockDoor(idx, true);
		}
	}

	//! Required tier for door index, 0 when it is not a keycard door.
	int SkyRequiredTier(int doorIdx)
	{
		int k = m_SkyKeycardDoorIdx.Find(doorIdx);
		if (k == -1 || doorIdx < 0 || k >= m_SkyKeycardTiers.Count())
			return 0;
		return m_SkyKeycardTiers[k];
	}

	bool SkyIsKeycardDoor(int doorIdx)
	{
		return SkyRequiredTier(doorIdx) > 0;
	}

	// Lobby lights (D55): four hall lights at light_1..light_4 (SKY_LitBuilding).
	override protected int SkyLightCount()
	{
		return SKY_Const.LIGHTS_LOBBY;
	}

	override protected typename SkyLightType()
	{
		return SKY_HallLight;
	}

	override int GetLockCompatibilityType(int doorIdx)
	{
		if (SkyIsKeycardDoor(doorIdx))
			return EBuildingLockType.NONE;	// 0: no key/lockpick fits, script-only
		return super.GetLockCompatibilityType(doorIdx);
	}

	protected void SkyDeny(PlayerBase player, string reason, int tier, int required)
	{
		NotificationSystem.SendNotificationToPlayerExtended(player, 4, "Access denied", reason, "");
		if (!m_SkyDenyLogLimiter.Allow(player.GetIdentity().GetId(), g_Game.GetTime()))
			return;
		PluginAdminLog adminLog = PluginAdminLog.Cast(GetPlugin(PluginAdminLog));
		string msg = "SKY keycard denied (" + reason + ") tier " + tier + "/" + required + " at " + GetType() + " " + GetPosition();
		if (adminLog)
			adminLog.DirectAdminLogPrint(adminLog.GetPlayerPrefix(player, player.GetIdentity()) + " " + msg);
		SKY_Log.Info(msg + " by " + player.GetIdentity().GetId());
	}

	//! Entry point from ActionSKY_SwipeKeycard (server only). Everything re-validated here.
	void SkyServerSwipe(PlayerBase player, SKY_Keycard_Base card, int doorIdx)
	{
		if (!g_Game.IsServer() || !player || !player.GetIdentity() || !card)
			return;
		if (!m_SkySwipeLimiter.Allow(player.GetIdentity().GetId(), g_Game.GetTime()))
			return;
		if (!player.IsAlive() || player.IsUnconscious() || player.IsRestrained())
			return;

		int required = SkyRequiredTier(doorIdx);
		if (required <= 0 || doorIdx >= GetDoorCount())
			return;	// not a keycard door: forged/stale target, ignore silently
		if (player.GetItemInHands() != card)
			return;	// card must be in the swiping player's hands on the server
		if (!SkyIsNearDoor(player, doorIdx))
			return;

		int tier = card.GetSkyTier();
		if (card.IsRuined())
		{
			SkyDeny(player, "card damaged", tier, required);
			return;
		}
		if (tier < required)
		{
			SkyDeny(player, "insufficient clearance", tier, required);
			return;
		}
		if (!IsDoorLocked(doorIdx))
			return;

		UnlockDoor(doorIdx);
		OpenDoor(doorIdx);
		card.DecreaseHealth("", "", SKY_Const.KEYCARD_WEAR);
		SKY_Log.Info("keycard T" + tier + " opened door " + doorIdx + " at " + GetType() + " by " + player.GetIdentity().GetId());
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).RemoveByName(this, "SkyRelock");	// one pending relock
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyRelock, m_SkyRelockMs, false, doorIdx);
	}

	//! Player stands inside the security room (server/client, model space).
	bool SkyIsInSecurityRoom(PlayerBase player)
	{
		if (!player || m_SkyRoom.Count() != 4)
			return false;
		vector p = WorldToModel(player.GetPosition());
		return p[0] > m_SkyRoom[0] && p[0] < m_SkyRoom[1] && p[2] > m_SkyRoom[2] && p[2] < m_SkyRoom[3] && p[1] > -0.5 && p[1] < 3.0;
	}

	//! Exit button: anyone INSIDE the room may open the door (no card needed) - avoids trapping players.
	void SkyServerExit(PlayerBase player, int doorIdx)
	{
		if (!g_Game.IsServer() || !player || !player.GetIdentity())
			return;
		if (!m_SkySwipeLimiter.Allow(player.GetIdentity().GetId(), g_Game.GetTime()))
			return;
		if (!player.IsAlive() || !SkyIsKeycardDoor(doorIdx) || doorIdx >= GetDoorCount())
			return;
		if (!SkyIsInSecurityRoom(player) || !SkyIsNearDoor(player, doorIdx) || !IsDoorLocked(doorIdx))
			return;
		UnlockDoor(doorIdx);
		OpenDoor(doorIdx);
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).RemoveByName(this, "SkyRelock");
		g_Game.GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(SkyRelock, m_SkyRelockMs, false, doorIdx);
	}

	override void SetActions()
	{
		super.SetActions();
		AddAction(ActionSKY_SecurityExit);
	}

	protected bool SkyIsNearDoor(PlayerBase player, int doorIdx)
	{
		vector doorPos = GetDoorSoundPos(doorIdx);	// world-space position of the door's soundPos memory point
		return vector.DistanceSq(doorPos, player.GetPosition() + "0 1 0") <= SKY_Const.DOOR_REACH * SKY_Const.DOOR_REACH;
	}

	protected void SkyRelock(int doorIdx)
	{
		// force = true closes the door first if it is open (Building.LockDoor doc).
		if (!IsDoorLocked(doorIdx))
			LockDoor(doorIdx, true);
	}
}
