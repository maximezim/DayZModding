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
	static const int HORDE_TICK_MS = 10000;			//!< director period (server; also the alarm pulse grain)
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

//! D62 creatures (ROADMAP ideas 5, 8, 9; DECISIONS D62). Hypotheses: PENDING_VERIFICATION P21-P24.
class SKY_Beasts
{
	static const int RPC_BARK = 0x534B5902;			//!< server -> client: a kennel dog barks at a position

	// ---- guard kennel - P21
	static const int TICK_MS = 5000;				//!< creature director period (server)
	static const int KENNEL_CHECK_EVERY = 6;		//!< kennel owner/guard check every 6 ticks (30 s)
	static const int KENNEL_GUARD_S = 172800;		//!< guards for 48 h after the owner was last seen
	static const float KENNEL_BARK_RADIUS = 8.0;	//!< a stranger this close makes the dog bark
	static const int KENNEL_BARK_MS = 20000;		//!< min interval between barks per kennel
	static const float KENNEL_BARK_HEAR = 150.0;	//!< players this close get the bark sound
	static const float KENNEL_BARK_NOISE = 3.0;		//!< x vanilla alarm-clock noise (infected come to look)
	static const int MAX_KENNELS = 1024;			//!< all kennels (placed or carried); see M1 in reviews/d62_gates.md
	static const int KENNEL_STORE_VERSION = 1;

	// ---- rats - P22
	static const float RAT_BITE_RADIUS = 2.5;		//!< from the nest centre (rats sit up to 1.4 m out + 1.1 m reach)
	static const float RAT_BITE_CHANCE = 0.3;		//!< per player standing in a nest, per tick
	static const float RAT_DMG_MIN = 3.0;
	static const float RAT_DMG_MAX = 6.0;
	static const float RAT_BLEED_CHANCE = 0.2;		//!< 1 bite in 5
	static const float RAT_DISEASE_CHANCE = 0.17;	//!< 1 bite in 6 -> SALMONELLA
	static const float DOG_REPEL_PLAYER = 15.0;		//!< a guard dog this close: no bites
	static const float DOG_REPEL_BASE = 30.0;		//!< a guard dog this close to a base part: no gnawing
	static const int RAT_GNAW_EVERY = 120;			//!< ticks between base gnawing (10 min)
	static const float RAT_GNAW_RADIUS = 25.0;
	static const float RAT_GNAW_FRACTION = 0.005;	//!< of the part's max health per gnaw
	static const float RAT_FIRE_BLOCK = 10.0;		//!< a burning fireplace this close to the nest stops the gnawing
	static const int MAX_NESTS = 128;
}

//! UTC wall clock in seconds since 2020-01-01 (survives restarts; for persisted timers).
class SKY_Time
{
	static int NowUtc()
	{
		int y, mo, d, h, mi, s;
		GetYearMonthDayUTC(y, mo, d);
		GetHourMinuteSecondUTC(h, mi, s);
		return DaysFrom2020(y, mo, d) * 86400 + h * 3600 + mi * 60 + s;
	}

	static int DaysFrom2020(int y, int m, int d)
	{
		// days from civil (Howard Hinnant), shifted to 2020-01-01 = 0
		if (m <= 2)
			y = y - 1;
		int era = y / 400;
		int yoe = y - era * 400;
		int mp = m + 9;
		if (m > 2)
			mp = m - 3;
		int doy = (153 * mp + 2) / 5 + d - 1;
		int doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
		return era * 146097 + doe - 737730;
	}
}

//! D63 underground (ROADMAP idea 18; DECISIONS D63). Hypotheses: PENDING_VERIFICATION P25-P29.
class SKY_Under
{
	static const int TICK_MS = 10000;				//!< flood director period (server)
	static const float RAIN_START = 0.6;			//!< rain above this starts flooding (ROADMAP: clamp(rain - 0.6, 0, 0.4) / 0.4)
	static const float RAIN_SPAN = 0.4;
	static const float RISE_PER_S = 0.00167;		//!< 0 -> 1 in 10 min
	static const float DRAIN_PER_S = 0.00056;		//!< 1 -> 0 in 30 min
	static const float PHASE_STEP = 0.05;			//!< push a new animation phase only when it moved this much (animPeriod 20 s smooths it)
	static const float WATER_BASE = -0.45;			//!< water plane above the walkway floor at phase 0 (m, model)
	static const float WATER_RISE = 1.6;			//!< = skyspec UNDERGROUND flood_rise
	static const float HALF_WIDTH = 2.4;			//!< sewer piece half width (model X)
	static const float HALF_LENGTH = 6.0;			//!< sewer piece half length (model Y; junction = square)
	static const float WALKWAY = -6.0;				//!< = skyspec UNDERGROUND sewer_floor (model)
	static const float WET_DEPTH = 0.3;				//!< water this deep over the feet soaks legs and feet
	static const float BODY_DEPTH = 1.0;			//!< ... and the body
	static const float DROWN_DEPTH = 1.55;			//!< over the head: damage
	static const float DROWN_DMG = 4.0;				//!< health per tick under water
	static const int MAX_PIECES = 512;
	static const float REACH_H = 9.0;				//!< horizontal radius round a piece centre (junction corner 8.5 m)
	static const int DROWN_GRACE_MS = 60000;		//!< no drowning damage in the first minute after a player is seen
}

