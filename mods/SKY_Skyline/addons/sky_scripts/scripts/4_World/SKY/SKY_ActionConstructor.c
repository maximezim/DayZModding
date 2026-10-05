modded class ActionConstructor
{
	override void RegisterActions(TTypenameArray actions)
	{
		super.RegisterActions(actions);
		actions.Insert(ActionSKY_SwipeKeycard);
		actions.Insert(ActionSKY_ElevatorCall);
		actions.Insert(ActionSKY_ElevatorUp);
		actions.Insert(ActionSKY_ElevatorDown);
		actions.Insert(ActionSKY_ElevatorLobby);
		actions.Insert(ActionSKY_ElevatorRoof);
		actions.Insert(ActionSKY_ElevatorOpen);
		actions.Insert(ActionSKY_SecurityExit);
	}
}
