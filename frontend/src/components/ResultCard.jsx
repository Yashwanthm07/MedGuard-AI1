import { motion } from 'framer-motion';

function tone(verdict) {
  if (verdict === 'GENUINE') return { color: '#16d28f', glow: 'rgba(22,210,143,0.25)' };
  if (verdict === 'SUSPICIOUS') return { color: '#ffbf3d', glow: 'rgba(255,191,61,0.25)' };
  if (verdict === 'FAKE') return { color: '#ff4d6d', glow: 'rgba(255,77,109,0.25)' };
  return { color: '#8ca4bf', glow: 'rgba(140,164,191,0.25)' };
}

export default function ResultCard({ result, imageUrl }) {
  const t = tone(result?.verdict);

  const imageSize = result?.image_size || { width: 1, height: 1 };
  const boxes = result?.text_boxes || [];
  const displayBoxes = boxes
    .filter((b) => Number(b?.conf ?? 0) >= 45)
    .filter((b) => {
      const token = String(b?.text || '').trim();
      if (!token || token.length < 2) return false;
      return !/(VERDICT|CONFIDENCE|MISSING|BLOCKCHAIN|VOICE|OCR|SCAN|RESULT|CURRENT|PREVIOUS|DELTA|COMPARISON|DETECTED)/i.test(token);
    })
    .slice(0, 30);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="glass-card"
      style={{ boxShadow: `0 20px 48px ${t.glow}` }}
    >
      <div className="result-header">
        <div>
          <div className="tiny-note">Verdict</div>
          <div className="result-verdict" style={{ color: t.color }}>{result?.verdict || 'UNKNOWN'}</div>
        </div>
        <div className="tiny-note">{result?.medicine_name || 'Unknown medicine'}</div>
      </div>

      <p className="result-explanation">{result?.explanation}</p>

      {imageUrl && (
        <div className="bbox-stage">
          <img src={imageUrl} alt="scan" className="bbox-image" />
          <div className="bbox-layer">
            {displayBoxes.map((b, i) => (
              <div
                key={`${b.text}-${i}`}
                className="bbox"
                style={{
                  left: `${(b.x / imageSize.width) * 100}%`,
                  top: `${(b.y / imageSize.height) * 100}%`,
                  width: `${(b.w / imageSize.width) * 100}%`,
                  height: `${(b.h / imageSize.height) * 100}%`,
                }}
                title={`${b.text} (${Math.round(b.conf)}%)`}
              >
                <span className="bbox-tag">{b.text?.slice(0, 18) || 'text'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {boxes.length > 0 && (
        <div className="tiny-note">OCR detections: {displayBoxes.length}/{boxes.length} likely text regions highlighted on image</div>
      )}

      <div className="kv-grid">
        <div><span>Manufacturer:</span><strong>{result?.manufacturer || 'N/A'}</strong></div>
        <div><span>Batch:</span><strong>{result?.batch_number || 'N/A'}</strong></div>
        <div><span>Expiry:</span><strong>{result?.expiry_date || 'N/A'}</strong></div>
        <div><span>Dosage:</span><strong>{result?.dosage || 'N/A'}</strong></div>
      </div>
    </motion.div>
  );
}
