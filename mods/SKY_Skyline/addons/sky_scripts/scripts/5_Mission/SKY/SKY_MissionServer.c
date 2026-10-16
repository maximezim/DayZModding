//! Starts / stops the D61 city life director (hordes + alarm, 4_World SKY_CityLife.c) the D62 creature director and the D63 sewer flood with the server mission.
//! Hooks: MissionServer.OnMissionStart (5_mission/mission/missionserver.c:94), Mission.OnMissionFinish (3_game/gameplay.c:702).
modded class MissionServer
{
	override void OnMissionStart()
	{
		super.OnMissionStart();
		SKY_CityLife.Start();
		SKY_CreatureLife.Start();
		SKY_Underground.Start();
	}

	override void OnMissionFinish()
	{
		SKY_CityLife.Stop();
		SKY_CreatureLife.Stop();
		SKY_Underground.Stop();
		SKY_TerrainCapture.Abort();		// D104 perf M3: close a capture cut short by the mission end
		super.OnMissionFinish();
	}
}
