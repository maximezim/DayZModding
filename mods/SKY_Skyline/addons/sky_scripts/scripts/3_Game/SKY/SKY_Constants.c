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
