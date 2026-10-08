//! Client: starts / stops the D65 ambience director (4_World SKY_Ambience.c) with the gameplay mission.
//! Hooks: MissionGameplay.OnMissionStart / OnMissionFinish (5_mission/mission/missiongameplay.c:186/257).
modded class MissionGameplay
{
	override void OnMissionStart()
	{
		super.OnMissionStart();
		SKY_Ambience.StartClient();
		SKY_LightDirector.StartClient();						// full audit perf H1
		SKY_Underground.StartClient();							// full audit perf M5 (P29 fallback)
	}

	override void OnMissionFinish()
	{
		SKY_Ambience.StopClient();
		SKY_LightDirector.StopClient();
		SKY_Underground.StopClient();
		super.OnMissionFinish();
	}
}
