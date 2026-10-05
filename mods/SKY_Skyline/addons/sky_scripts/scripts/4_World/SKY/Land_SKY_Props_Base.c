/*
	Script base of every SKY interior prop with Doors (config Land_SKY_Props_Base, generated
	by assets/gen_configs.py; child config classes resolve to this script class).

	Security (batch-3 L2): vanilla Building.GetLockCompatibilityType (3_game/entities/building.c:167)
	makes every door lockpickable; EBuildingLockType.NONE = 0 (3_game/enums/ebuildinglocktypes.c:3)
	masks out every tool in ActionLockDoors (actionlockdoors.c:39). Prop doors (lockers,
	extinguisher cabinet, vending flap) therefore report NONE: nobody can lock loot away in
	them. Same pattern as Land_SKY_TowerA_Lobby.GetLockCompatibilityType.
*/
class Land_SKY_Props_Base extends House
{
	override int GetLockCompatibilityType(int doorIdx)
	{
		return EBuildingLockType.NONE;
	}
}
