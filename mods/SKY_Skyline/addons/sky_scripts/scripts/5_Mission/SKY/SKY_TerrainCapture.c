/*
	Terrain capture for the terrain mapper (D104, server only, opt-in, development tool).

	Drop $profile:SKY_survey_request.json into the server profile folder with "mode": "capture":
		{ "mode": "capture", "label": "cher_ne", "center": [0, 0], "x0": 11000, "z0": 11500, "x1": 13500, "z1": 13500,
		  "cell": 7.5, "surfaces": 1, "objects": 1 }
	About 15 s after mission start the capture samples the rectangle in slices (no stall) and writes, under
	$profile:SKY_capture/:
		<label>_heights.txt   one line per grid row, NORTH row first, heights in integer centimetres (SurfaceY)
		<label>_surfaces.txt  same grid, one surface index per cell (legend in the meta file)  [surfaces = 1]
		<label>_objects.txt   type;model;x;y;z;yaw;pitch;roll;scale for every map object in the rectangle  [objects = 1]
		<label>_meta.json     origin, cell, grid size, surface legend, counts; written LAST with "complete": true
	terrain/terrain_mapper.py reads these and builds a modified copy of the map region for a custom terrain
	(MOD_DEVELOPMENT_GUIDE 4.3 Level 2). Nothing here changes the running map: it only reads.

	Run it on a vanilla mission WITHOUT the SKY city in objectSpawnersArr, or the city is captured as map objects.
	Loot, vehicles, players, animals and infected are skipped (dynamic entities, not map objects).

	Safety (D104 security M1): the request file is DELETED when a capture starts, so a forgotten file never re-runs
	on the next restart; a capture refuses to start while players are connected. Bounds: cell clamped to
	[0.5, 50] m, at most MAX_CELLS per axis and MAX_TOTAL cells, CELLS_PER_TICK samples and LINES_PER_TICK object
	lines per tick, MAX_OBJECTS lines, MAX_SURFACES legend entries. The label is reduced to [A-Za-z0-9_-], max 32
	characters, so the request cannot choose a path outside $profile:SKY_capture. A mission end mid-capture closes
	the files (Abort) and leaves no meta file, so the mapper refuses the partial capture.
*/
class SKY_CaptureMeta
{
	int version;
	string label;
	float x0;
	float z0;
	float cell;
	int nx;
	int nz;
	float worldSize;
	ref array<string> surfaces;
	int surfaceOverflow;
	int objects;
	bool objectsTruncated;
	string rowOrder;
	string heightUnit;
	bool complete;
}

class SKY_TerrainCapture
{
	static const string DIR = "$profile:SKY_capture";
	static const string LABEL_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
	static const int MAX_CELLS = 4096;				//!< per axis
	static const int MAX_TOTAL = 4300000;			//!< cells in all: a whole 15360 m map at 7.5 m (2049^2)
	static const int CELLS_PER_TICK = 4096;			//!< grid cells sampled per timer tick (SurfaceY + surface type)
	static const int CHUNK = 64;					//!< values joined per FPrint call
	static const float OBJ_TILE = 50.0;				//!< object query tile edge (m)
	static const int LINES_PER_TICK = 1500;			//!< objects examined per tick (a tile can span several ticks)
	static const int MAX_OBJECTS = 1500000;
	static const int MAX_SURFACES = 250;

	protected static ref SKY_TerrainCapture s_Active;

	protected ref SKY_CaptureMeta m_Meta;
	protected ref map<string, int> m_SurfIndex;
	protected ref array<Object> m_Found;
	protected int m_FoundIdx;
	protected bool m_Surfaces;
	protected bool m_Objects;
	protected string m_Base;
	protected FileHandle m_FH;
	protected FileHandle m_FS;
	protected FileHandle m_FO;
	protected int m_Phase;
	protected int m_Row;
	protected int m_Tile;
	protected int m_TilesX;
	protected int m_TilesZ;

	static void Start(SKY_SurveyRequest req)
	{
		if (s_Active)
			return;
		array<Man> players = new array<Man>();
		g_Game.GetPlayers(players);
		if (players.Count() > 0)
		{
			SKY_Log.Warn("terrain capture refused: " + players.Count() + " player(s) connected (run it on an empty server)");
			return;
		}
		s_Active = new SKY_TerrainCapture();
		if (!s_Active.Init(req))
			s_Active = null;
	}

	//! Mission end: stop the timer, close the files, no meta file (the capture stays incomplete).
	static void Abort()
	{
		if (!s_Active)
			return;
		g_Game.GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(s_Active.Tick);
		s_Active.CloseAll();
		SKY_Log.Warn("terrain capture aborted by the mission end (incomplete, no meta file)");
		s_Active = null;
	}

	static string SafeLabel(string label)
	{
		string res = "";
		for (int i = 0; i < label.Length() && res.Length() < 32; i++)
		{
			string ch = label.Get(i);
			if (LABEL_CHARS.IndexOf(ch) != -1)
				res += ch;
		}
		if (res == "")
			res = "capture";
		return res;
	}

	void ~SKY_TerrainCapture()
	{
		CloseAll();
	}

	protected void CloseAll()
	{
		if (m_FH)
			CloseFile(m_FH);
		if (m_FS)
			CloseFile(m_FS);
		if (m_FO)
			CloseFile(m_FO);
		m_FH = null;
		m_FS = null;
		m_FO = null;
	}

	protected bool Init(SKY_SurveyRequest req)
	{
		float world = g_Game.GetWorld().GetWorldSize();
		float cell = req.cell;
		if (cell <= 0)
			cell = 7.5;
		cell = Math.Clamp(cell, 0.5, 50.0);
		float x0 = Math.Clamp(req.x0, 0.0, world);
		float z0 = Math.Clamp(req.z0, 0.0, world);
		float x1 = Math.Clamp(req.x1, x0 + cell, world);
		float z1 = Math.Clamp(req.z1, z0 + cell, world);
		m_Meta = new SKY_CaptureMeta();
		m_Meta.version = 1;
		m_Meta.label = SafeLabel(req.label);
		m_Meta.x0 = x0;
		m_Meta.z0 = z0;
		m_Meta.cell = cell;
		int wantX = Math.Floor((x1 - x0) / cell) + 1;
		int wantZ = Math.Floor((z1 - z0) / cell) + 1;
		m_Meta.nx = Math.Clamp(wantX, 2, MAX_CELLS);
		m_Meta.nz = Math.Clamp(wantZ, 2, MAX_CELLS);
		if (m_Meta.nx * m_Meta.nz > MAX_TOTAL)
		{
			SKY_Log.Warn("terrain capture refused: " + m_Meta.nx + " x " + m_Meta.nz + " cells is over " + MAX_TOTAL + " (raise cell or shrink the rectangle)");
			return false;
		}
		if (m_Meta.nx != wantX || m_Meta.nz != wantZ)
			SKY_Log.Warn("terrain capture: grid clamped to " + m_Meta.nx + " x " + m_Meta.nz + " cells (asked " + wantX + " x " + wantZ + ")");
		m_Meta.worldSize = world;
		m_Meta.surfaces = new array<string>();
		m_Meta.rowOrder = "north_first";
		m_Meta.heightUnit = "cm";
		m_SurfIndex = new map<string, int>();
		m_Found = new array<Object>();
		m_FoundIdx = -1;
		m_Surfaces = req.surfaces != 0;
		m_Objects = req.objects != 0;
		m_TilesX = Math.Ceil((m_Meta.nx - 1) * cell / OBJ_TILE);
		m_TilesZ = Math.Ceil((m_Meta.nz - 1) * cell / OBJ_TILE);
		if (!FileExist(DIR))
			MakeDirectory(DIR);
		m_Base = DIR + "/" + m_Meta.label;
		DeleteFile(m_Base + "_meta.json");			// an old meta must not mark this run's files complete
		m_FH = OpenFile(m_Base + "_heights.txt", FileMode.WRITE);
		if (!m_FH)
		{
			SKY_Log.Warn("terrain capture: cannot write " + m_Base + "_heights.txt");
			return false;
		}
		if (m_Surfaces)
		{
			m_FS = OpenFile(m_Base + "_surfaces.txt", FileMode.WRITE);
			if (!m_FS)
				SKY_Log.Warn("terrain capture: cannot write " + m_Base + "_surfaces.txt (heights only)");
		}
		if (m_Objects)
		{
			m_FO = OpenFile(m_Base + "_objects.txt", FileMode.WRITE);
			if (!m_FO)
				SKY_Log.Warn("terrain capture: cannot write " + m_Base + "_objects.txt (no objects)");
		}
		DeleteFile(SKY_SiteSurvey.REQUEST);			// one run per request: a forgotten file never re-runs on restart
		m_Phase = 0;
		m_Row = 0;
		m_Tile = 0;
		SKY_Log.Info("terrain capture '" + m_Meta.label + "' started: " + m_Meta.nx + " x " + m_Meta.nz + " cells of " + cell + " m (request file consumed)");
		Schedule();
		return true;
	}

	protected void Schedule()
	{
		g_Game.GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, 10, false);
	}

	protected void Tick()
	{
		if (m_Phase == 0)
			CaptureRows();
		else if (m_Phase == 1)
			CaptureObjects();
		else
		{
			Finish();
			return;
		}
		Schedule();
	}

	//! Rows from north (z max) to south, columns west to east: the ESRI ASCII order.
	protected void CaptureRows()
	{
		int rows = Math.Max(1, CELLS_PER_TICK / m_Meta.nx);
		int last = Math.Min(m_Row + rows, m_Meta.nz);
		for (int r = m_Row; r < last; r++)
		{
			float z = m_Meta.z0 + (m_Meta.nz - 1 - r) * m_Meta.cell;
			string hs = "";
			string ss = "";
			for (int c = 0; c < m_Meta.nx; c++)
			{
				float x = m_Meta.x0 + c * m_Meta.cell;
				int cm = Math.Round(g_Game.SurfaceY(x, z) * 100.0);
				hs += cm.ToString() + " ";
				if (m_FS)
					ss += SurfaceIndex(x, z).ToString() + " ";
				if ((c + 1) % CHUNK == 0)
				{
					FPrint(m_FH, hs);
					hs = "";
					if (m_FS)
					{
						FPrint(m_FS, ss);
						ss = "";
					}
				}
			}
			FPrintln(m_FH, hs);
			if (m_FS)
				FPrintln(m_FS, ss);
		}
		m_Row = last;
		if (m_Row >= m_Meta.nz)
		{
			CloseFile(m_FH);
			m_FH = null;
			if (m_FS)
			{
				CloseFile(m_FS);
				m_FS = null;
			}
			m_Phase = 1;
			if (!m_FO)
				m_Phase = 2;
		}
	}

	protected int SurfaceIndex(float x, float z)
	{
		string surf;
		g_Game.SurfaceGetType(x, z, surf);
		int idx;
		if (m_SurfIndex.Find(surf, idx))
			return idx;
		if (m_Meta.surfaces.Count() >= MAX_SURFACES)
		{
			m_Meta.surfaceOverflow++;				// written as index 0; the mapper reports the count
			return 0;
		}
		idx = m_Meta.surfaces.Count();
		m_Meta.surfaces.Insert(surf);
		m_SurfIndex.Insert(surf, idx);
		return idx;
	}

	//! Objects of one tile at a time; a dense (forest) tile is written over several ticks (LINES_PER_TICK).
	protected void CaptureObjects()
	{
		int total = m_TilesX * m_TilesZ;
		float xe = m_Meta.x0 + (m_Meta.nx - 1) * m_Meta.cell;
		float ze = m_Meta.z0 + (m_Meta.nz - 1) * m_Meta.cell;
		int budget = LINES_PER_TICK;
		while (budget > 0 && m_Tile < total && !m_Meta.objectsTruncated)
		{
			float tx0 = m_Meta.x0 + (m_Tile % m_TilesX) * OBJ_TILE;
			float tz0 = m_Meta.z0 + (m_Tile / m_TilesX) * OBJ_TILE;
			float tx1 = Math.Min(tx0 + OBJ_TILE, xe);
			float tz1 = Math.Min(tz0 + OBJ_TILE, ze);
			if (m_FoundIdx < 0)
			{
				vector centre = Vector(tx0 + OBJ_TILE * 0.5, 0, tz0 + OBJ_TILE * 0.5);
				centre[1] = g_Game.SurfaceY(centre[0], centre[2]);
				m_Found.Clear();
				g_Game.GetObjectsAtPosition(centre, OBJ_TILE * 0.7072 + 1.0, m_Found, null);
				m_FoundIdx = 0;
			}
			while (m_FoundIdx < m_Found.Count() && budget > 0)
			{
				Object o = m_Found[m_FoundIdx];
				m_FoundIdx++;
				budget--;
				if (!o || o.IsMan() || o.IsInherited(ItemBase) || o.IsInherited(Transport) || o.IsInherited(DayZCreature))
					continue;
				vector p = o.GetPosition();
				// half-open tile rectangle so an object on a tile edge is written once; the last tile keeps the far edge
				bool inX = p[0] >= tx0 && (p[0] < tx1 || (tx1 >= xe && p[0] <= xe));
				bool inZ = p[2] >= tz0 && (p[2] < tz1 || (tz1 >= ze && p[2] <= ze));
				if (!inX || !inZ)
					continue;
				string type = o.GetType();
				string model = o.GetShapeName();
				if (type == "" && model == "")
					type = o.GetDebugNameNative();
				if (type == "" && model == "")
					continue;
				vector ypr = o.GetOrientation();
				FPrintln(m_FO, type + ";" + model + ";" + p[0] + ";" + p[1] + ";" + p[2] + ";" + ypr[0] + ";" + ypr[1] + ";" + ypr[2] + ";" + o.GetScale());
				m_Meta.objects++;
				if (m_Meta.objects >= MAX_OBJECTS)
				{
					m_Meta.objectsTruncated = true;
					break;
				}
			}
			if (m_FoundIdx >= m_Found.Count())
			{
				m_FoundIdx = -1;
				m_Tile++;
			}
		}
		if (m_Tile >= total || m_Meta.objectsTruncated)
		{
			m_Found.Clear();
			CloseFile(m_FO);
			m_FO = null;
			m_Phase = 2;
		}
	}

	protected void Finish()
	{
		m_Meta.complete = true;
		string err;
		if (JsonFileLoader<SKY_CaptureMeta>.SaveFile(m_Base + "_meta.json", m_Meta, err))
			SKY_Log.Info("terrain capture '" + m_Meta.label + "' written: " + m_Base + "_*.txt (" + m_Meta.surfaces.Count() + " surfaces, " + m_Meta.objects + " objects, " + m_Meta.surfaceOverflow + " cells over the surface legend)");
		else
			SKY_Log.Warn("terrain capture meta save failed: " + err);
		s_Active = null;
	}
}
