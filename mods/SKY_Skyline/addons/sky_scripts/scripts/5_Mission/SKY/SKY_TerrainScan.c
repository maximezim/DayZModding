/*
	Terrain scan for city placement (server only, opt-in, development tool).

	Drop $profile:SKY_survey_request.json into the server profile folder with "mode": "scan":
		{ "mode": "scan", "label": "scan1", "x0": 0, "z0": 0, "x1": 15360, "z1": 15360,
		  "win": 192, "maxRelief": 1.0, "top": 30 }
	About 15 s after mission start the scan runs in slices (a few ms per timer tick, no stall) and writes
	$profile:SKY_scan_result.json: the `top` flattest, non-overlapping win x win m windows whose ground
	relief (max - min of SurfaceY) is <= maxRelief and that are not at sea level, each with a count of the
	existing objects inside (trees / bushes / other, and the first types of the "other" ones), so a treeless
	field with no vanilla buildings can be picked for a city quarter. The result feeds a normal survey of the
	chosen window (mode absent) and then placement/sky_layout.py.

	Cost: blocks of BLOCK m are sampled on a (SAMPLES + 1)^2 grid (about 5 M SurfaceY calls for all of Chernarus),
	BLOCKS_PER_TICK blocks per CallLater tick. No request file or no "scan" mode -> nothing runs. Bounded: at most
	MAX_BLOCKS blocks per axis, MAX_CANDIDATES windows kept, 60 sites reported.
*/
class SKY_ScanSite
{
	float x;
	float z;
	float relief;
	float minY;
	float maxY;
	int objects;
	int trees;
	int other;
	ref array<string> otherTypes;
}

class SKY_ScanResult
{
	string label;
	float win;
	float maxRelief;
	int blocks;
	int candidates;
	ref array<ref SKY_ScanSite> sites;
}

class SKY_TerrainScan
{
	static const string RESULT = "$profile:SKY_scan_result.json";
	static const float BLOCK = 48.0;				//!< block edge (m); windows are made of whole blocks
	static const int SAMPLES = 6;					//!< sample intervals per block edge
	static const int BLOCKS_PER_TICK = 250;
	static const int ROWS_PER_TICK = 16;
	static const int MAX_BLOCKS = 400;				//!< per axis
	static const int MAX_CANDIDATES = 20000;
	static const int MAX_SITES = 60;
	static const float MIN_GROUND = 3.0;			//!< lowest ground (m) that counts as land: sea level and the shore are skipped

	protected static ref SKY_TerrainScan s_Active;

	protected ref SKY_SurveyRequest m_Req;
	protected ref array<float> m_Min;
	protected ref array<float> m_Max;
	protected ref array<ref SKY_ScanSite> m_Cand;
	protected int m_Nx;
	protected int m_Nz;
	protected int m_Wb;
	protected int m_Phase;
	protected int m_Next;
	protected float m_Win;
	protected float m_MaxRelief;
	protected int m_Top;

	static void Start(SKY_SurveyRequest req)
	{
		if (s_Active)
			return;
		s_Active = new SKY_TerrainScan();
		s_Active.Init(req);
	}

	protected void Init(SKY_SurveyRequest req)
	{
		m_Req = req;
		float world = g_Game.GetWorld().GetWorldSize();
		req.x0 = Math.Clamp(req.x0, 0.0, world);
		req.z0 = Math.Clamp(req.z0, 0.0, world);
		req.x1 = Math.Clamp(req.x1, req.x0 + BLOCK, world + BLOCK);
		req.z1 = Math.Clamp(req.z1, req.z0 + BLOCK, world + BLOCK);
		m_Nx = Math.Clamp(Math.Ceil((req.x1 - req.x0) / BLOCK), 1, MAX_BLOCKS);
		m_Nz = Math.Clamp(Math.Ceil((req.z1 - req.z0) / BLOCK), 1, MAX_BLOCKS);
		m_Win = Math.Clamp(req.win, BLOCK, 400.0);
		m_Wb = Math.Ceil(m_Win / BLOCK);
		m_MaxRelief = Math.Clamp(req.maxRelief, 0.05, 10.0);
		m_Top = Math.Clamp(req.top, 1, MAX_SITES);
		m_Min = new array<float>();
		m_Max = new array<float>();
		m_Cand = new array<ref SKY_ScanSite>();
		m_Phase = 0;
		m_Next = 0;
		SKY_Log.Info("terrain scan '" + req.label + "' started: " + m_Nx + " x " + m_Nz + " blocks, window " + m_Win + " m, max relief " + m_MaxRelief);
		Schedule();
	}

	protected void Schedule()
	{
		g_Game.GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, 10, false);
	}

	protected void Tick()
	{
		if (m_Phase == 0)
			ScanBlocks();
		else if (m_Phase == 1)
			ScanWindows();
		else
		{
			Finish();
			return;
		}
		Schedule();
	}

	protected void ScanBlocks()
	{
		int total = m_Nx * m_Nz;
		int last = Math.Min(m_Next + BLOCKS_PER_TICK, total);
		float step = BLOCK / SAMPLES;
		for (int b = m_Next; b < last; b++)
		{
			int bi = b % m_Nx;
			int bj = b / m_Nx;
			float bx = m_Req.x0 + bi * BLOCK;
			float bz = m_Req.z0 + bj * BLOCK;
			float lo = float.MAX;
			float hi = -float.MAX;
			for (int sx = 0; sx <= SAMPLES; sx++)
			{
				for (int sz = 0; sz <= SAMPLES; sz++)
				{
					float y = g_Game.SurfaceY(bx + sx * step, bz + sz * step);
					lo = Math.Min(lo, y);
					hi = Math.Max(hi, y);
				}
			}
			m_Min.Insert(lo);
			m_Max.Insert(hi);
		}
		m_Next = last;
		if (m_Next >= total)
		{
			m_Phase = 1;
			m_Next = 0;
		}
	}

	protected void ScanWindows()
	{
		int rows = m_Nz - m_Wb + 1;
		int lastRow = Math.Min(m_Next + ROWS_PER_TICK, rows);
		for (int wj = m_Next; wj < lastRow; wj++)
		{
			for (int wi = 0; wi <= m_Nx - m_Wb; wi++)
			{
				if (m_Cand.Count() >= MAX_CANDIDATES)
					break;
				float lo = float.MAX;
				float hi = -float.MAX;
				for (int dj = 0; dj < m_Wb; dj++)
				{
					int row = (wj + dj) * m_Nx + wi;
					for (int di = 0; di < m_Wb; di++)
					{
						lo = Math.Min(lo, m_Min[row + di]);
						hi = Math.Max(hi, m_Max[row + di]);
					}
				}
				if (lo < MIN_GROUND || hi - lo > m_MaxRelief)
					continue;
				SKY_ScanSite cand = new SKY_ScanSite();
				cand.x = m_Req.x0 + (wi + m_Wb * 0.5) * BLOCK;
				cand.z = m_Req.z0 + (wj + m_Wb * 0.5) * BLOCK;
				cand.relief = hi - lo;
				cand.minY = lo;
				cand.maxY = hi;
				m_Cand.Insert(cand);
			}
		}
		m_Next = lastRow;
		if (m_Next >= rows)
			m_Phase = 2;
	}

	protected void Finish()
	{
		SKY_ScanResult res = new SKY_ScanResult();
		res.label = m_Req.label;
		res.win = m_Win;
		res.maxRelief = m_MaxRelief;
		res.blocks = m_Nx * m_Nz;
		res.candidates = m_Cand.Count();
		res.sites = new array<ref SKY_ScanSite>();
		for (int n = 0; n < m_Top; n++)
		{
			int best = -1;
			float bestRelief = float.MAX;
			for (int i = 0; i < m_Cand.Count(); i++)
			{
				SKY_ScanSite c = m_Cand[i];
				if (c && c.relief < bestRelief)
				{
					bestRelief = c.relief;
					best = i;
				}
			}
			if (best < 0)
				break;
			SKY_ScanSite pick = m_Cand[best];
			res.sites.Insert(pick);
			for (int k = 0; k < m_Cand.Count(); k++)
			{
				SKY_ScanSite other = m_Cand[k];
				if (other && Math.AbsFloat(other.x - pick.x) < m_Win && Math.AbsFloat(other.z - pick.z) < m_Win)
					m_Cand.Set(k, null);
			}
		}
		foreach (SKY_ScanSite site : res.sites)
			CountObjects(site);
		string err;
		if (JsonFileLoader<SKY_ScanResult>.SaveFile(RESULT, res, err))
			SKY_Log.Info("terrain scan '" + m_Req.label + "' written: " + RESULT + " (" + res.sites.Count() + " sites of " + res.candidates + " flat windows)");
		else
			SKY_Log.Warn("terrain scan save failed: " + err);
		s_Active = null;
	}

	protected void CountObjects(SKY_ScanSite site)
	{
		site.otherTypes = new array<string>();
		vector centre = Vector(site.x, site.maxY, site.z);
		array<Object> found = new array<Object>();
		g_Game.GetObjectsAtPosition(centre, m_Win * 0.71, found, null);
		foreach (Object o : found)
		{
			if (!o || o.IsMan())
				continue;
			string type = o.GetType();
			if (type == "")
				type = o.GetDebugNameNative();		// unclassed map objects (runway decals, taxiways, kerbs) have no class name
			if (type == "")
				continue;
			site.objects++;
			if (type.IndexOf("Tree") == 0 || type.IndexOf("Bush") == 0 || type.IndexOf("Mushroom") != -1)
			{
				site.trees++;
				continue;
			}
			site.other++;
			if (site.otherTypes.Count() < 8 && site.otherTypes.Find(type) == -1)
				site.otherTypes.Insert(type);
		}
	}
}
