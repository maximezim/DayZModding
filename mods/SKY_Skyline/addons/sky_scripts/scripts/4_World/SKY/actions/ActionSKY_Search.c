/*
	Search a bin / dumpster / garbage truck / landfill mound / costume rail / bar stock (D61).
	A player action (like vanilla ActionOpenDoors, PlayerBase.SetActions playerbase.c:1670) so no
	per-building script class is needed: the target only has to carry `skySearch` in its config.
	Continuous 6 s, full body (vanilla crafting animation, CMD_ACTIONFB_CRAFTING dayzplayer.c:826).
	The client condition is cosmetic; the server re-validates everything in SKY_SearchService.Search.
*/
class ActionSKY_SearchCB : ActionContinuousBaseCB
{
	override void CreateActionComponent()
	{
		m_ActionData.m_ActionComponent = new CAContinuousTime(SKY_Life.SEARCH_TIME);
	}
}

class ActionSKY_Search : ActionContinuousBase
{
	void ActionSKY_Search()
	{
		m_CallbackClass = ActionSKY_SearchCB;
		m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_CRAFTING;
		m_FullBody = true;
		m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
		m_Text = "Search";
	}

	override typename GetInputType()
	{
		return ContinuousInteractActionInput;
	}

	override void CreateConditionComponents()
	{
		m_ConditionItem = new CCINone();
		m_ConditionTarget = new CCTCursor(UAMaxDistances.DEFAULT);
	}

	override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
	{
		if (!target || !target.GetObject())
			return false;
		if (item && item.IsHeavyBehaviour())
			return false;
		Object obj = target.GetObject();
		if (SKY_SearchService.TableOf(obj) == "")
			return false;
		vector spot;
		int idx;
		return SKY_SearchService.FindSpot(obj, player.GetPosition(), spot, idx);
	}

	override void OnFinishProgressServer(ActionData action_data)
	{
		SKY_SearchService.Get().Search(action_data.m_Player, action_data.m_Target.GetObject());
	}

	override bool IsLockTargetOnUse()
	{
		return false;
	}
}
