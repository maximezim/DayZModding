//! Starts / stops the D61 city life director (hordes + alarm, 4_World SKY_CityLife.c) and the D62 creature director with the server mission.
//! Hooks: MissionServer.OnMissionStart (5_mission/mission/missionserver.c:94), Mission.OnMissionFinish (3_game/gameplay.c:702).
modded class MissionServer
{
	override void OnMissionStart()
	{
		super.OnMissionStart();
		SKY_CityLife.Start();
		SKY_CreatureLife.Start();
	}

	override void OnMissionFinish()
	{
		SKY_CityLife.Stop();
		SKY_CreatureLife.Stop();
		super.OnMissionFinish();
	}
}
