export default function ConfidenceGauge({ value = 0, label = 'Confidence' }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  const r = 44;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  const color = pct >= 80 ? '#15d684' : pct >= 50 ? '#ffb200' : '#ff4d6d';

  return (
    <div className="gauge-card">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={r} className="gauge-track" />
        <circle
          cx="60"
          cy="60"
          r={r}
          className="gauge-fill"
          style={{ stroke: color, strokeDasharray: c, strokeDashoffset: offset }}
        />
        <text x="60" y="58" textAnchor="middle" className="gauge-value">{Math.round(pct)}</text>
        <text x="60" y="74" textAnchor="middle" className="gauge-unit">%</text>
      </svg>
      <div className="gauge-label">{label}</div>
    </div>
  );
}
