import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { safetyAPI } from '../services/api.js';

export default function PatientSafety() {
  const [age, setAge] = useState('');
  const [allergies, setAllergies] = useState('');
  const [medications, setMedications] = useState('');
  const [conditions, setConditions] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const meds = useMemo(() => medications.split(',').map((m) => m.trim()).filter(Boolean), [medications]);

  const runAnalysis = async () => {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const data = await safetyAPI.analyzePatientSafety(
        age ? Number(age) : undefined,
        allergies,
        medications,
        conditions
      );
      setResult(data);
    } catch (err) {
      const apiMessage = err?.response?.data?.error || err?.response?.data?.detail;
      setError(apiMessage || err.message || 'Safety analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-stack">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="page-title">Patient Safety Engine</h1>
        <p className="page-subtitle">Drug interactions, allergy checks, age-specific cautions, and recommendations.</p>
      </motion.div>

      <div className="glass-card form-grid">
        <label>
          Age
          <input value={age} onChange={(e) => setAge(e.target.value)} placeholder="e.g. 45" />
        </label>
        <label>
          Allergies
          <input value={allergies} onChange={(e) => setAllergies(e.target.value)} placeholder="Penicillin, Sulfa" />
        </label>
        <label>
          Current Medicines
          <input value={medications} onChange={(e) => setMedications(e.target.value)} placeholder="Warfarin, Aspirin" />
        </label>
        <label>
          Medical Conditions
          <input value={conditions} onChange={(e) => setConditions(e.target.value)} placeholder="Hypertension" />
        </label>

        <button className="btn" onClick={runAnalysis} disabled={loading}>
          {loading ? 'Analyzing...' : 'Analyze Patient Safety'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="glass-card">
          <div className="compare-grid">
            <div>
              <div className="tiny-note">Risk Level</div>
              <strong>{result.risk_level}</strong>
            </div>
            <div>
              <div className="tiny-note">Risk Score</div>
              <strong>{result.risk_score}</strong>
            </div>
            <div>
              <div className="tiny-note">Immediate Attention</div>
              <strong>{String(result.requires_immediate_attention)}</strong>
            </div>
          </div>

          <h3>Interactions</h3>
          <ul>
            {(result.interactions || []).map((it, idx) => (
              <li key={`${it.drug1}-${it.drug2}-${idx}`}>{it.drug1} + {it.drug2} ({it.severity}): {it.description}</li>
            ))}
          </ul>

          <h3>Recommendations</h3>
          <ul>
            {(result.recommendations || []).map((rec, idx) => <li key={idx}>{rec}</li>)}
          </ul>

          <h3>Drug Info Assistant</h3>
          <p>{meds.length ? `Monitoring ${meds.length} active medicine entries: ${meds.join(', ')}` : 'No medication list provided.'}</p>
          <p>{result.clinical_summary}</p>
        </div>
      )}
    </section>
  );
}
