import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import ResultCard from '../components/ResultCard.jsx';
import VoiceButton from '../components/VoiceButton.jsx';
import ConfidenceGauge from '../components/ConfidenceGauge.jsx';

async function sha256(text) {
  const bytes = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export default function Result() {
  const location = useLocation();
  const navigate = useNavigate();
  const [blockHash, setBlockHash] = useState('');

  const payload = useMemo(() => {
    if (location.state?.result) return location.state;
    const latest = localStorage.getItem('latestScan');
    return latest ? JSON.parse(latest) : null;
  }, [location.state]);

  useEffect(() => {
    if (!payload?.result) return;
    sha256(JSON.stringify(payload.result)).then(setBlockHash);
  }, [payload]);

  if (!payload?.result) {
    return (
      <div className="glass-card">
        <h2>No scan result available</h2>
        <button className="btn" onClick={() => navigate('/scan')}>Go to Scanner</button>
      </div>
    );
  }

  const result = payload.result;
  const spokenText = `${result.verdict}. ${result.explanation}`;
  const missingFields = result.missing_fields || [];
  const suspiciousSigns = result.suspicious_signs || [];

  const history = JSON.parse(localStorage.getItem('scanHistory') || '[]');
  const compare = history.length > 1 ? history[1]?.result : null;

  return (
    <section className="page-stack">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <h1 className="page-title">Scan Result</h1>
        <p className="page-subtitle">Dynamic verdict from OCR extraction and visual checks.</p>
        {result.ai_assisted && (
          <div className="text-green-400">✨ Enhanced OCR (Hybrid Mode)</div>
        )}
      </motion.div>

      <ResultCard result={result} imageUrl={payload.imageUrl} />

      <div className="metrics-grid">
        <ConfidenceGauge value={result.overall_confidence} label="Overall" />
        <ConfidenceGauge value={result.visual_authenticity_score} label="Visual" />
        <ConfidenceGauge value={result.text_clarity_score} label="Text Clarity" />
        <ConfidenceGauge value={result.data_completeness_score} label="Data Completeness" />
      </div>

      <div className="glass-card">
        <div className="tiny-note">Voice Output</div>
        <VoiceButton text={spokenText} />
      </div>

      <div className="glass-card">
        <div className="tiny-note">Why This Verdict</div>
        <div className="why-grid">
          <div className="why-panel">
            <h4>Detected Data</h4>
            <ul>
              <li>Medicine: {result.medicine_name || 'Not detected'}</li>
              <li>Manufacturer: {result.manufacturer || 'Not detected'}</li>
              <li>Batch: {result.batch_number || 'Not detected'}</li>
              <li>Expiry: {result.expiry_date || 'Not detected'}</li>
              <li>Dosage: {result.dosage || 'Not detected'}</li>
            </ul>
          </div>

          <div className="why-panel">
            <h4>Missing Fields</h4>
            {missingFields.length ? (
              <ul>
                {missingFields.map((item, idx) => (
                  <li key={`${item}-${idx}`}>❌ {item}</li>
                ))}
              </ul>
            ) : (
              <p>✔ No critical fields missing.</p>
            )}
          </div>

          <div className="why-panel">
            <h4>Suspicious Signals</h4>
            {suspiciousSigns.length ? (
              <ul>
                {suspiciousSigns.map((item, idx) => (
                  <li key={`${item}-${idx}`}>⚠ {item}</li>
                ))}
              </ul>
            ) : (
              <p>✔ No suspicious signals detected.</p>
            )}
          </div>
        </div>
      </div>

      <div className="glass-card">
        <div className="tiny-note">Blockchain Verification (Mock)</div>
        <div className="hash-line">{blockHash ? `scan:${blockHash.slice(0, 36)}...` : 'Calculating hash...'}</div>
      </div>

      {compare && (
        <div className="glass-card">
          <div className="tiny-note">Multi-image Comparison</div>
          <div className="compare-grid">
            <div>
              <div className="tiny-note">Current</div>
              <strong>{result.verdict}</strong>
              <div>{Math.round(result.overall_confidence)}%</div>
            </div>
            <div>
              <div className="tiny-note">Previous</div>
              <strong>{compare.verdict}</strong>
              <div>{Math.round(compare.overall_confidence)}%</div>
            </div>
            <div>
              <div className="tiny-note">Delta</div>
              <strong>{Math.round((result.overall_confidence || 0) - (compare.overall_confidence || 0))}%</strong>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
