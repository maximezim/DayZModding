/*
	Search a bin / dumpster / garbage truck / landfill mound / costume rail / bar stock (D61).
	A player action (like vanilla ActionOpenDoors, PlayerBase.SetActions playerbase.c:1670) so no
	per-building script class is needed: the target only has to carry `skySearch` in its config.
	Continuous 6 s, full body (vanilla crafting animation, CMD_ACTIONFB_CRAFTING dayzplayer.c:826).
	The client condition is cosmetic; the server re-validates everything in SKY_SearchService.Search.
	D72: the condition also hides the action without line of sight (same InSight raycast as the server). It runs
	every frame while aiming, so the result is cached per target / spot for 0.5 s or until the player moves 0.3 m.
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
	protected Object m_SkyLosObj;			//!< D72 line-of-sight cache (client cosmetics only)
	protected int m_SkyLosIdx = -2;
	protected int m_SkyLosTime;
	protected vector m_SkyLosPos;
	protected bool m_SkyLosOk;

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
		if (!SKY_SearchService.FindSpot(obj, player.GetPosition(), spot, idx))
			return false;
		if (idx < 0)
			return true;												// object-origin spots: no line-of-sight test (as the server)
		int now = g_Game.GetTime();
		vector pos = player.GetPosition();
		if (obj != m_SkyLosObj || idx != m_SkyLosIdx || now - m_SkyLosTime > SKY_Life.SEARCH_LOS_CACHE_MS
			|| vector.DistanceSq(pos, m_SkyLosPos) > 0.09)
		{
			m_SkyLosObj = obj;
			m_SkyLosIdx = idx;
			m_SkyLosTime = now;
			m_SkyLosPos = pos;
			m_SkyLosOk = SKY_SearchService.InSight(player, spot);
		}
		return m_SkyLosOk;
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
