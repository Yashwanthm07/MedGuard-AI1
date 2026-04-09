import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import UploadBox from '../components/UploadBox.jsx';
import Scanner3D from '../components/Scanner3D.jsx';
import { medicineAPI } from '../services/api.js';

function toBase64Payload(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      resolve({
        imageBase64: String(dataUrl).split(',')[1],
        imageUrl: dataUrl,
      });
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function compactHistoryEntry(entry) {
  if (!entry) return entry;
  const { imageUrl, ...rest } = entry;
  return rest;
}

function readHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem('scanHistory') || '[]');
    return Array.isArray(parsed) ? parsed.map(compactHistoryEntry) : [];
  } catch {
    return [];
  }
}

function persistScanHistory(nextEntry, history) {
  const compactEntry = compactHistoryEntry(nextEntry);
  const compactHistory = [compactEntry, ...history].slice(0, 20);

  try {
    localStorage.setItem('latestScan', JSON.stringify(compactEntry));
    localStorage.setItem('scanHistory', JSON.stringify(compactHistory));
  } catch {
    // If storage is near quota, aggressively keep only the most recent compact entry.
    localStorage.removeItem('scanHistory');
    localStorage.setItem('latestScan', JSON.stringify(compactEntry));
    localStorage.setItem('scanHistory', JSON.stringify([compactEntry]));
  }
}

export default function Scan() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const onFileSelected = async (nextFile) => {
    setError('');
    setFile(nextFile);
    const { imageUrl } = await toBase64Payload(nextFile);
    setPreview(imageUrl);
  };

  const runScan = async () => {
    if (!file) return;
    setLoading(true);
    setError('');

    try {
      const { imageBase64, imageUrl } = await toBase64Payload(file);
      const result = await medicineAPI.analyzeMedicine(imageBase64, file.type || 'image/jpeg');

      const history = readHistory();
      const nextEntry = {
        id: Date.now(),
        createdAt: new Date().toISOString(),
        result,
        imageUrl,
      };

      persistScanHistory(nextEntry, history);

      navigate('/result', { state: nextEntry });
    } catch (err) {
      const apiMessage = err?.response?.data?.error || err?.response?.data?.detail;
      setError(apiMessage || err.message || 'Scan failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-grid">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <h1 className="page-title">Medicine Authenticity Scanner</h1>
        <p className="page-subtitle">Real-time OCR, authenticity scoring, and explainable verdicts.</p>

        <UploadBox
          onFileSelected={onFileSelected}
          previewUrl={preview}
          onClear={() => {
            setFile(null);
            setPreview('');
            setError('');
          }}
        />

        <div className="action-row">
          <button className="btn" disabled={!file || loading} onClick={runScan}>
            {loading ? 'Analyzing...' : 'Run Authenticity Scan'}
          </button>
        </div>

        {error && <div className="error-box">{error}</div>}
      </motion.div>

      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5 }}>
        <div className="glass-card scanner-panel">
          <div className="tiny-note">3D Scanner View</div>
          <Scanner3D isAnalyzing={loading} />
        </div>
      </motion.div>

      <AnimatePresence>
        {loading && (
          <motion.div
            className="analysis-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="analysis-modal glass-card"
              initial={{ opacity: 0, y: 20, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.25 }}
            >
              <div className="analysis-title">Analyzing Medicine Image</div>
              <p className="analysis-subtitle">
                Running OCR, field validation, and authenticity checks.
              </p>

              <div className="analysis-3d-wrap">
                <Scanner3D isAnalyzing />
              </div>

              <div className="analysis-steps" aria-hidden="true">
                <span>OCR Scan</span>
                <span>Field Detection</span>
                <span>Decision Engine</span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
