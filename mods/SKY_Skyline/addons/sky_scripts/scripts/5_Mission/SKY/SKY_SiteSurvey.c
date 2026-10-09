/*
	Site survey for SKY placement (server only, opt-in).

	Drop $profile:SKY_survey_request.json into the server profile folder:
		{ "label": "site1", "center": [x, z], "yaw": 0, "halfW": 13, "halfD": 13,
		  "step": 2.0, "exportRadius": 40 }
	"mode": "scan" runs the whole-map terrain scan instead (SKY_TerrainScan.c; "center" is still required, any value).
	Start the server (with the tower spawned via objectSpawnersArr if you also want
	loot positions). After ~15 s it writes $profile:SKY_survey_result.json with:
	  - ground height samples over the (rotated) footprint (SurfaceY)
	  - every existing object inside the footprint (overlap check)
	and calls GetCEApi().ExportProxyData(center, exportRadius), which writes
	<mission>/storage_N/export/mapgrouppos.xml (authoritative CE entries for spawned modules).
	placement/sky_layout.py consumes the result. No request file -> does nothing.
*/
class SKY_SurveyRequest
{
	string label;
	ref array<float> center;
	float yaw;
	float halfW;
	float halfD;
	float step;
	float exportRadius;
	string mode;				// "" = site survey; "scan" = terrain scan (SKY_TerrainScan.c)
	float x0;
	float z0;
	float x1;
	float z1;
	float win;
	float maxRelief;
	int top;
}

class SKY_SurveyObject
{
	string type;
	ref array<float> pos;
}

class SKY_SurveyResult
{
	string label;
	ref array<float> center;
	float yaw;
	float halfW;
	float halfD;
	float minY;
	float maxY;
	ref array<float> samples;			// flat x, y, z triplets
	ref array<ref SKY_SurveyObject> objects;
	string proxyExport;
}

class SKY_SiteSurvey
{
	static const string REQUEST = "$profile:SKY_survey_request.json";
	static const string RESULT = "$profile:SKY_survey_result.json";
	static const float MAX_STEP_COUNT = 64;	// per axis: bounds the work to 64x64 samples

	static void RunIfRequested()
	{
		if (!g_Game.IsServer() || !FileExist(REQUEST))
			return;
		SKY_SurveyRequest req;
		string err;
		if (!JsonFileLoader<SKY_SurveyRequest>.LoadFile(REQUEST, req, err) || !req.center || req.center.Count() != 2)
		{
			SKY_Log.Warn("survey request invalid: " + err);
			return;
		}
		if (req.mode == "scan")
			SKY_TerrainScan.Start(req);
		else
			Run(req);
	}

	static vector Local(SKY_SurveyRequest req, float u, float v)
	{
		float a = req.yaw * Math.DEG2RAD;
		float c = Math.Cos(a);
		float s = Math.Sin(a);
		vector p;
		p[0] = req.center[0] + u * c + v * s;
		p[2] = req.center[1] - u * s + v * c;
		p[1] = g_Game.SurfaceY(p[0], p[2]);
		return p;
	}

	static void Run(SKY_SurveyRequest req)
	{
		SKY_SurveyResult res = new SKY_SurveyResult();
		res.label = req.label;
		res.center = req.center;
		res.yaw = req.yaw;
		res.samples = new array<float>();
		res.objects = new array<ref SKY_SurveyObject>();
		res.minY = float.MAX;
		res.maxY = -float.MAX;

		// full audit L3: a request file with step <= 0 and zero / huge half-sizes hung the server start loop
		req.halfW = Math.Clamp(req.halfW, 1.0, 1000.0);
		req.halfD = Math.Clamp(req.halfD, 1.0, 1000.0);
		float step = Math.Max(Math.Max(req.step, 0.25), Math.Max(req.halfW, req.halfD) * 2 / MAX_STEP_COUNT);
		res.halfW = req.halfW;
		res.halfD = req.halfD;
		for (float u = -req.halfW; u <= req.halfW + 0.001; u += step)
		{
			for (float v = -req.halfD; v <= req.halfD + 0.001; v += step)
			{
				vector p = Local(req, u, v);
				res.samples.Insert(p[0]);
				res.samples.Insert(p[1]);
				res.samples.Insert(p[2]);
				res.minY = Math.Min(res.minY, p[1]);
				res.maxY = Math.Max(res.maxY, p[1]);
			}
		}

		vector centre = Local(req, 0, 0);
		array<Object> found = new array<Object>();
		g_Game.GetObjectsAtPosition(centre, Math.Sqrt(req.halfW * req.halfW + req.halfD * req.halfD) + 1, found, null);
		foreach (Object o : found)
		{
			if (!o || o.IsMan())
				continue;
			vector rel = o.GetPosition() - centre;
			float a = req.yaw * Math.DEG2RAD;
			float lu = rel[0] * Math.Cos(a) - rel[2] * Math.Sin(a);
			float lv = rel[0] * Math.Sin(a) + rel[2] * Math.Cos(a);
			if (Math.AbsFloat(lu) > req.halfW || Math.AbsFloat(lv) > req.halfD)
				continue;
			SKY_SurveyObject so = new SKY_SurveyObject();
			so.type = o.GetType();
			if (so.type == "")
				so.type = o.GetDebugNameNative();
			vector op = o.GetPosition();
			so.pos = {op[0], op[1], op[2]};
			res.objects.Insert(so);
		}

		if (req.exportRadius > 0 && GetCEApi())
		{
			GetCEApi().ExportProxyData(centre, Math.Min(req.exportRadius, 2000.0));	// D94 security info: clamped
			res.proxyExport = "storage/export/mapgrouppos.xml (mission storage folder)";
		}

		string err;
		if (JsonFileLoader<SKY_SurveyResult>.SaveFile(RESULT, res, err))
			SKY_Log.Info("site survey '" + req.label + "' written: " + RESULT + " (" + res.objects.Count() + " objects, ground " + res.minY + ".." + res.maxY + ")");
		else
			SKY_Log.Warn("site survey save failed: " + err);
	}
}

modded class MissionServer
{
	override void OnMissionStart()
	{
		super.OnMissionStart();
		// Deferred so objectSpawnersArr objects exist before the proxy export.
		g_Game.GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(SKY_SiteSurvey.RunIfRequested, 15000, false);
	}
}
