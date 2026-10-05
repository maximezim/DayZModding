//! Keycard item. Tier comes from config (skyTier) - never from the client.
class SKY_Keycard_Base extends Inventory_Base
{
	protected int m_SkyTier = -1;

	int GetSkyTier()
	{
		if (m_SkyTier < 0)
			m_SkyTier = ConfigGetInt("skyTier");
		return m_SkyTier;
	}

	override void SetActions()
	{
		super.SetActions();
		AddAction(ActionSKY_SwipeKeycard);
	}
}
