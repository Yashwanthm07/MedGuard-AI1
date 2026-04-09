import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { dashboardAPI } from '../services/api.js';

function toGrid(history) {
  const cells = Array.from({ length: 30 }, () => 0);
  history.forEach((h, i) => {
    const s = `${h.medicine_name || 'unknown'}-${h.verdict}-${i}`;
    const hash = Array.from(s).reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    cells[hash % cells.length] += 1;
  });
  return cells;
}

function buildSparklinePath(values) {
  if (!values.length) return '';

  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;
  const lastIndex = Math.max(1, values.length - 1);

  return values
    .map((value, index) => {
      const x = (index / lastIndex) * 100;
      const y = 100 - ((value - minVal) / range) * 100;
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');
}

function formatTimestamp(value) {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

function verdictPillClass(verdict) {
  const v = (verdict || '').toUpperCase();
  if (v === 'GENUINE') return 'is-genuine';
  if (v === 'SUSPICIOUS') return 'is-suspicious';
  if (v === 'FAKE') return 'is-fake';
  return 'is-invalid';
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('ALL');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState('');

  const loadDashboard = useCallback(async (showSpinner = true) => {
    try {
      if (showSpinner) {
        setLoading(true);
      }
      setError('');
      const [s, b, h] = await Promise.all([
        dashboardAPI.getStats(),
        dashboardAPI.getVerdictBreakdown(),
        dashboardAPI.getHistory(20),
      ]);

      setStats(s || null);
      setBreakdown(b || null);
      setHistory(h?.recent || []);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.message || 'Dashboard load failed');
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadDashboard(true);
  }, [loadDashboard]);

  useEffect(() => {
    if (!autoRefresh) return undefined;

    const timer = setInterval(() => {
      loadDashboard(false);
    }, 20000);

    return () => clearInterval(timer);
  }, [autoRefresh, loadDashboard]);

  const filteredHistory = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return history.filter((item) => {
      const verdictOk = verdictFilter === 'ALL' || (item.verdict || '').toUpperCase() === verdictFilter;
      const medicine = (item.medicine_name || '').toLowerCase();
      const queryOk = !needle || medicine.includes(needle);
      return verdictOk && queryOk;
    });
  }, [history, query, verdictFilter]);

  const geoGrid = useMemo(() => toGrid(history), [history]);

  const percentages = useMemo(() => ({
    genuine: Number(breakdown?.genuine_percent || 0),
    suspicious: Number(breakdown?.suspicious_percent || 0),
    fake: Number(breakdown?.fake_percent || 0),
    invalid: Number(breakdown?.invalid_percent || 0),
  }), [breakdown]);

  const donutStyle = useMemo(() => {
    const { genuine, suspicious, fake, invalid } = percentages;
    const sum = genuine + suspicious + fake + invalid;

    if (sum <= 0) {
      return { background: 'conic-gradient(#2f435c 0 100%)' };
    }

    const s1 = genuine;
    const s2 = genuine + suspicious;
    const s3 = genuine + suspicious + fake;

    return {
      background: `conic-gradient(#15d684 0 ${s1}%, #ffbf3d ${s1}% ${s2}%, #ff4d6d ${s2}% ${s3}%, #8ca4bf ${s3}% 100%)`,
    };
  }, [percentages]);

  const recentConfidence = useMemo(() => {
    const values = history
      .slice(0, 12)
      .reverse()
      .map((item) => Math.max(0, Math.min(100, Number(item.confidence || 0))));
    return values;
  }, [history]);

  const sparklinePath = useMemo(() => buildSparklinePath(recentConfidence), [recentConfidence]);

  const avgRecentConfidence = useMemo(() => {
    if (!recentConfidence.length) return 0;
    const total = recentConfidence.reduce((acc, n) => acc + n, 0);
    return total / recentConfidence.length;
  }, [recentConfidence]);

  const statCards = useMemo(() => {
    if (!stats) return [];
    const total = Math.max(1, Number(stats.total_scans || 0));

    return [
      {
        label: 'Total Scans',
        value: Number(stats.total_scans || 0),
        meter: total > 0 ? 100 : 0,
        tone: 'tone-cyan',
      },
      {
        label: 'Genuine',
        value: Number(stats.genuine_count || 0),
        meter: (Number(stats.genuine_count || 0) / total) * 100,
        tone: 'tone-green',
      },
      {
        label: 'Suspicious',
        value: Number(stats.suspicious_count || 0),
        meter: (Number(stats.suspicious_count || 0) / total) * 100,
        tone: 'tone-amber',
      },
      {
        label: 'Fake',
        value: Number(stats.fake_count || 0),
        meter: (Number(stats.fake_count || 0) / total) * 100,
        tone: 'tone-rose',
      },
      {
        label: 'Invalid',
        value: Number(stats.invalid_count || 0),
        meter: (Number(stats.invalid_count || 0) / total) * 100,
        tone: 'tone-slate',
      },
      {
        label: 'Avg Confidence',
        value: `${Math.round(Number(stats.average_confidence || 0))}%`,
        meter: Number(stats.average_confidence || 0),
        tone: 'tone-blue',
      },
    ];
  }, [stats]);

  return (
    <section className="page-stack">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="page-title">Analytics Dashboard</h1>
        <p className="page-subtitle">Operational telemetry for scan quality, verdict distribution, and risk patterns.</p>
      </motion.div>

      <div className="glass-card dashboard-toolbar">
        <div>
          <div className="tiny-note">Live Monitor</div>
          <div className="dashboard-heading">{loading ? 'Refreshing dashboard...' : 'Operational analytics stream'}</div>
          <div className="tiny-note">{lastUpdated ? `Last update: ${lastUpdated}` : 'Waiting for first update...'}</div>
        </div>

        <div className="dashboard-actions">
          <label className="dashboard-toggle">
            <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
            Auto refresh
          </label>
          <button className="btn-mini is-active" onClick={() => loadDashboard(true)} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh now'}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {stats && (
        <div className="stats-grid">
          {statCards.map((card) => (
            <div key={card.label} className={`glass-card stat-card ${card.tone}`}>
              <div className="tiny-note">{card.label}</div>
              <div className="stat-value">{card.value}</div>
              <div className="stat-meter">
                <span className="stat-meter-fill" style={{ width: `${Math.max(2, Math.min(100, card.meter || 0))}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="dashboard-analytics-grid">
        <div className="glass-card">
          <div className="tiny-note">Verdict Breakdown</div>
          <div className="donut-wrap">
            <div className="donut-chart" style={donutStyle}>
              <span>{Number(breakdown?.total_scans || stats?.total_scans || 0)} scans</span>
            </div>

            <div className="donut-legend">
              <div className="legend-item">
                <span className="legend-key"><span className="legend-swatch is-genuine" />Genuine</span>
                <strong>{percentages.genuine}%</strong>
              </div>
              <div className="legend-item">
                <span className="legend-key"><span className="legend-swatch is-suspicious" />Suspicious</span>
                <strong>{percentages.suspicious}%</strong>
              </div>
              <div className="legend-item">
                <span className="legend-key"><span className="legend-swatch is-fake" />Fake</span>
                <strong>{percentages.fake}%</strong>
              </div>
              <div className="legend-item">
                <span className="legend-key"><span className="legend-swatch is-invalid" />Invalid</span>
                <strong>{percentages.invalid}%</strong>
              </div>
            </div>
          </div>
        </div>

        <div className="glass-card">
          <div className="tiny-note">Confidence Trend (Recent)</div>
          <div className="trend-chart">
            <svg className="trend-svg" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Confidence trend">
              {sparklinePath && <path className="trend-path" d={sparklinePath} />}
            </svg>
            <div className="tiny-note">Average recent confidence: {Math.round(avgRecentConfidence)}%</div>
          </div>
        </div>
      </div>

      <div className="glass-card">
        <div className="tiny-note">Geo Heatmap (Derived from scan distribution)</div>
        <div className="heatmap-grid">
          {geoGrid.map((v, i) => (
            <div key={i} className="heat-cell" style={{ opacity: Math.min(1, 0.2 + v * 0.18) }} title={`Risk density: ${v}`} />
          ))}
        </div>
      </div>

      <div className="glass-card">
        <div className="history-controls">
          <div>
            <div className="tiny-note">Recent Scans</div>
            <div className="tiny-note">{filteredHistory.length} shown / {history.length} loaded</div>
          </div>

          <div className="history-controls-right">
            <input
              className="dashboard-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search medicine"
            />
            <select className="dashboard-select" value={verdictFilter} onChange={(e) => setVerdictFilter(e.target.value)}>
              <option value="ALL">All verdicts</option>
              <option value="GENUINE">Genuine</option>
              <option value="SUSPICIOUS">Suspicious</option>
              <option value="FAKE">Fake</option>
              <option value="INVALID">Invalid</option>
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Medicine</th>
                <th>Verdict</th>
                <th>Confidence</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.map((item, idx) => (
                <tr key={`${item.timestamp}-${idx}-${item.medicine_name || 'unknown'}`}>
                  <td>{item.medicine_name || 'Unknown'}</td>
                  <td><span className={`scan-verdict-pill ${verdictPillClass(item.verdict)}`}>{item.verdict || 'UNKNOWN'}</span></td>
                  <td>{Math.round(item.confidence || 0)}%</td>
                  <td>{formatTimestamp(item.timestamp)}</td>
                </tr>
              ))}
              {!filteredHistory.length && (
                <tr className="empty-row">
                  <td colSpan={4}>No scans match the current filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
