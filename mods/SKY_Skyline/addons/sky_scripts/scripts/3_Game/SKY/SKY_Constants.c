// Shared constants for SKY_Skyline (3_Game: no world entities here).

enum SKY_ElevatorCmd
{
	CALL = 0,	// call/open from the landing (outside the cab)
	UP,		// one stop up
	DOWN,		// one stop down
	LOBBY,		// first stop
	ROOF,		// last stop
	OPEN		// open the doors from inside the cab (also rescues players stranded at another stop)
}

enum SKY_ElevatorState
{
	IDLE = 0,	// doors closed, car parked at m_SkyCarLevel
	OPEN,		// doors open at m_SkyCarLevel
	CLOSING,	// doors closing before departure
	TRAVEL		// moving; occupants teleported on arrival
}

class SKY_Const
{
	static const string LOG_TAG = "[SKY] ";
	//! Per-player minimum interval between elevator/keycard requests (ms).
	static const int PLAYER_REQUEST_INTERVAL_MS = 1500;
	//! Per-player minimum interval between logged keycard denials (ms).
	static const int DENIAL_LOG_INTERVAL_MS = 5000;
	//! Upper bound of tracked identities before the rate limiter prunes.
	static const int RATE_LIMIT_MAX_ENTRIES = 512;
	//! Keycard wear per successful swipe (health points of 100).
	static const float KEYCARD_WEAR = 10.0;
	//! Max distance (m) from player to a door / panel memory point (server check).
	static const float DOOR_REACH = 2.5;
	//! Door close animation time before locking / departing (ms).
	static const int DOOR_ANIM_MS = 1300;
	//! Building lights (client only, night only, no shadows; D55). Each light is a vanilla
	//! ScriptedLightBase with its own EOnFrame: keep the count low and measure (FPS_PROTOCOL).
	static const bool LIGHTS_ENABLED = true;
	//! Max lights per building module (memory points light_1..light_4 in priority order).
	static const int LIGHTS_PER_MODULE = 2;
	//! Lights in the double-height lobby.
	static const int LIGHTS_LOBBY = 4;
}

class SKY_Log
{
	static void Info(string msg)
	{
		Print(SKY_Const.LOG_TAG + msg);
	}

	static void Warn(string msg)
	{
		PrintToRPT(SKY_Const.LOG_TAG + "WARNING: " + msg);
	}
}

//! D61 city life (ROADMAP.md ideas 3, 10, 13, 16, 17, 19, 20). Every value is a gameplay hypothesis
//! tracked in PENDING_VERIFICATION.md (P14 alarm, P15 hordes, P16 alcohol, P17 search).
class SKY_Life
{
	//! RPC id (server -> client only): city siren started at a position. Prefix 0x534B59 = "SKY".
	static const int RPC_SIREN = 0x534B5901;

	// ---- search (bins, dumpsters, garbage trucks, landfill, costume racks, bar stock) - P17
	//! Search duration (s).
	static const float SEARCH_TIME = 6.0;
	//! Max distance (m) from the player to a search memory point (client condition + server check).
	static const float SEARCH_REACH = 2.0;
	//! A searched spot stays empty this long (ms): 30 min.
	static const int SEARCH_COOLDOWN_MS = 1800000;
	//! Per-player minimum interval between searches (ms), on top of the 6 s action.
	static const int SEARCH_PLAYER_INTERVAL_MS = 4000;
	//! Upper bound of tracked searched spots.
	static const int SEARCH_MAX_SPOTS = 4096;
	//! Highest search_N memory point read (matches build_city.SEARCH_MAX).
	static const int SEARCH_POINTS = 8;
	//! Chance (0..1) to cut a hand on trash without gloves.
	static const float SEARCH_CUT_CHANCE = 0.125;

	// ---- alcohol - P16 (ml of ethanol in the blood)
	static const float ALCOHOL_VODKA = 0.40;		//!< ethanol fraction of vodka
	static const float ALCOHOL_BEER = 0.05;			//!< ethanol fraction of beer
	static const float ALCOHOL_TIPSY = 8.0;			//!< level 1: pain relief, slow heal
	static const float ALCOHOL_DRUNK = 30.0;		//!< level 2: blur and sway
	static const float ALCOHOL_WASTED = 60.0;		//!< level 3: vomiting
	static const float ALCOHOL_MAX = 200.0;
	static const float ALCOHOL_DECAY = 0.05;		//!< ml/s (40 ml clears in about 13 min)
	static const float ALCOHOL_HEAL = 0.04;			//!< health/s while tipsy
	static const float ALCOHOL_SHOCK = 0.5;			//!< shock regen/s while tipsy or drunk
	static const int ALCOHOL_VOMIT_MS = 90000;		//!< min interval between vomits

	// ---- hordes downtown - P15
	static const int HORDE_TICK_MS = 20000;			//!< director period (server)
	static const float HORDE_ACTIVATE = 350.0;		//!< a player this close wakes an anchor
	static const float HORDE_DESPAWN = 550.0;		//!< no player this close: the horde despawns
	static const float HORDE_MIN_PLAYER = 70.0;		//!< spawn at least this far from every player
	static const float HORDE_RING_MIN = 60.0;		//!< spawn ring round the anchor (m)
	static const float HORDE_RING_MAX = 140.0;
	static const int HORDE_GROUP = 6;				//!< infected per spawn
	static const int HORDE_PER_ANCHOR = 18;
	static const int HORDE_GLOBAL_MAX = 72;
	static const int HORDE_RESPAWN_MS = 300000;		//!< per-anchor interval between spawns
	static const int HORDE_MAX_ANCHORS = 64;
	static const int HORDE_CORPSE_MS = 600000;		//!< tracked corpses deleted after this (no player near)

	// ---- city alarm - P14
	static const int ALARM_MIN_MS = 2700000;		//!< 45 min
	static const int ALARM_MAX_MS = 5400000;		//!< 90 min
	static const int ALARM_DURATION_MS = 60000;		//!< length of one siren run (= sound sample)
	static const int ALARM_PULSE_MS = 10000;		//!< noise refresh period while the siren runs
	static const float ALARM_NOISE_MULT = 25.0;		//!< x vanilla alarm clock noise (P14: measure reach)
	static const float ALARM_HEAR = 2500.0;			//!< players this close get the sound RPC
	static const float ALARM_NEED_PLAYER = 1500.0;	//!< only sirens with a player this close fire
	static const int ALARM_HORDES = 3;				//!< extra groups converging on the siren
	static const float ALARM_RING_MIN = 180.0;
	static const float ALARM_RING_MAX = 320.0;
	static const int ALARM_EXTRA_CAP = 36;			//!< global cap raised by this during an alarm
}
