//! Bounded per-identity rate limiter (server side). Keys are PlayerIdentity ids.
class SKY_RateLimiter
{
	protected ref map<string, int> m_Last = new map<string, int>();
	protected int m_IntervalMs;

	void SKY_RateLimiter(int intervalMs)
	{
		m_IntervalMs = intervalMs;
	}

	//! True (and records the hit) if `key` may act now.
	bool Allow(string key, int nowMs)
	{
		int last;
		if (m_Last.Find(key, last) && nowMs - last < m_IntervalMs)
			return false;

		if (m_Last.Count() >= SKY_Const.RATE_LIMIT_MAX_ENTRIES)
			Prune(nowMs);

		m_Last.Set(key, nowMs);
		return true;
	}

	//! Drop entries older than the interval; if still full, clear (worst case: one extra allowed hit).
	protected void Prune(int nowMs)
	{
		array<string> stale = new array<string>();
		foreach (string k, int t : m_Last)
		{
			if (nowMs - t >= m_IntervalMs)
				stale.Insert(k);
		}
		foreach (string s : stale)
			m_Last.Remove(s);

		if (m_Last.Count() >= SKY_Const.RATE_LIMIT_MAX_ENTRIES)
			m_Last.Clear();
	}

	int Count()
	{
		return m_Last.Count();
	}
}
