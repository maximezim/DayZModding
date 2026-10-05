/*
	"Exit button" inside the lobby security room: opens the locked keycard door
	from the inside without a card. Server re-validates the player's position
	inside the room (Land_SKY_TowerA_Lobby.SkyServerExit).
*/
class ActionSKY_SecurityExit : ActionInteractBase
{
	void ActionSKY_SecurityExit()
	{
		m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_OPENDOORFW;
		m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
		m_Text = "Press exit button";
	}

	override void CreateConditionComponents()
	{
		m_ConditionItem = new CCINone;
		m_ConditionTarget = new CCTCursor;
	}

	override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
	{
		if (!target)
			return false;
		Land_SKY_TowerA_Lobby building = Land_SKY_TowerA_Lobby.Cast(target.GetObject());
		if (!building)
			return false;
		int doorIdx = building.GetDoorIndex(target.GetComponentIndex());
		if (doorIdx == -1 || !building.SkyIsKeycardDoor(doorIdx) || !building.IsDoorLocked(doorIdx))
			return false;
		return building.SkyIsInSecurityRoom(player) && IsInReach(player, target, UAMaxDistances.DEFAULT);
	}

	override void OnStartServer(ActionData action_data)
	{
		super.OnStartServer(action_data);
		Land_SKY_TowerA_Lobby building = Land_SKY_TowerA_Lobby.Cast(action_data.m_Target.GetObject());
		if (building)
			building.SkyServerExit(action_data.m_Player, building.GetDoorIndex(action_data.m_Target.GetComponentIndex()));
	}

	override bool IsLockTargetOnUse()
	{
		return false;
	}
}
