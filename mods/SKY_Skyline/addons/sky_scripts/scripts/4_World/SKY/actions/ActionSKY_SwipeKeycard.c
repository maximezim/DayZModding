/*
	Swipe a keycard (in hands) at a keycard door. Pattern: vanilla
	ActionUseUndergroundPanel (single use, item in hands, cursor target).
	ActionCondition runs on the client for the prompt AND again on the server
	(ActionManagerServer.StartDeliveredAction -> Can); the server then calls
	Land_SKY_TowerA_Lobby.SkyServerSwipe which re-validates everything.
	The prompt is shown for any tier so that insufficient cards are denied
	(and logged) server-side instead of silently hidden.
*/
class ActionSKY_SwipeKeycard : ActionSingleUseBase
{
	void ActionSKY_SwipeKeycard()
	{
		m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_OPENDOORFW;
		m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
		m_Text = "Swipe keycard";
	}

	override void CreateConditionComponents()
	{
		m_ConditionItem = new CCINonRuined;
		m_ConditionTarget = new CCTCursor;
	}

	override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
	{
		if (!target || !item)
			return false;
		Land_SKY_TowerA_Lobby building = Land_SKY_TowerA_Lobby.Cast(target.GetObject());
		SKY_Keycard_Base card = SKY_Keycard_Base.Cast(item);
		if (!building || !card)
			return false;
		int doorIdx = building.GetDoorIndex(target.GetComponentIndex());
		if (doorIdx == -1 || !building.SkyIsKeycardDoor(doorIdx))
			return false;
		if (!IsInReach(player, target, UAMaxDistances.DEFAULT))
			return false;
		return building.IsDoorLocked(doorIdx);
	}

	override void OnStartServer(ActionData action_data)
	{
		super.OnStartServer(action_data);
		Land_SKY_TowerA_Lobby building = Land_SKY_TowerA_Lobby.Cast(action_data.m_Target.GetObject());
		SKY_Keycard_Base card = SKY_Keycard_Base.Cast(action_data.m_MainItem);
		if (!building || !card)
			return;
		building.SkyServerSwipe(action_data.m_Player, card, building.GetDoorIndex(action_data.m_Target.GetComponentIndex()));
	}

	override bool IsLockTargetOnUse()
	{
		return false;
	}
}
