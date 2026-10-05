/*
	Elevator interactions on Land_SKY_TowerA_Core. One action per command so
	the client never submits a floor number; see Land_SKY_TowerA_Core header
	for the trust model. Pattern: vanilla ActionUseUndergroundLever.
*/
class ActionSKY_ElevatorBase : ActionInteractBase
{
	protected int m_SkyCmd;

	void ActionSKY_ElevatorBase()
	{
		m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_OPENDOORFW;
		m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
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
		Land_SKY_TowerA_Core core = Land_SKY_TowerA_Core.Cast(target.GetObject());
		if (!core)
			return false;
		return core.SkyCanRequest(player, m_SkyCmd);
	}

	override void OnStartServer(ActionData action_data)
	{
		super.OnStartServer(action_data);
		Land_SKY_TowerA_Core core = Land_SKY_TowerA_Core.Cast(action_data.m_Target.GetObject());
		if (core)
			core.SkyServerRequest(action_data.m_Player, m_SkyCmd);
	}

	override bool IsLockTargetOnUse()
	{
		return false;
	}
}

class ActionSKY_ElevatorCall : ActionSKY_ElevatorBase
{
	void ActionSKY_ElevatorCall()
	{
		m_SkyCmd = SKY_ElevatorCmd.CALL;
		m_Text = "Call elevator";
	}
}

class ActionSKY_ElevatorUp : ActionSKY_ElevatorBase
{
	void ActionSKY_ElevatorUp()
	{
		m_SkyCmd = SKY_ElevatorCmd.UP;
		m_Text = "Elevator: up one floor";
	}
}

class ActionSKY_ElevatorDown : ActionSKY_ElevatorBase
{
	void ActionSKY_ElevatorDown()
	{
		m_SkyCmd = SKY_ElevatorCmd.DOWN;
		m_Text = "Elevator: down one floor";
	}
}

class ActionSKY_ElevatorLobby : ActionSKY_ElevatorBase
{
	void ActionSKY_ElevatorLobby()
	{
		m_SkyCmd = SKY_ElevatorCmd.LOBBY;
		m_Text = "Elevator: lobby";
	}
}

class ActionSKY_ElevatorOpen : ActionSKY_ElevatorBase
{
	void ActionSKY_ElevatorOpen()
	{
		m_SkyCmd = SKY_ElevatorCmd.OPEN;
		m_Text = "Elevator: open doors";
	}
}

class ActionSKY_ElevatorRoof : ActionSKY_ElevatorBase
{
	void ActionSKY_ElevatorRoof()
	{
		m_SkyCmd = SKY_ElevatorCmd.ROOF;
		m_Text = "Elevator: roof";
	}
}
