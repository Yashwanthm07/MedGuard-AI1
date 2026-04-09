import { useEffect, useMemo, useState } from 'react';

const PERSONALITIES = {
  clinical: { rate: 0.92, pitch: 1.0, label: 'Clinical' },
  calm: { rate: 0.86, pitch: 0.9, label: 'Calm' },
  alert: { rate: 1.0, pitch: 1.1, label: 'Alert' },
};

export default function VoiceButton({ text }) {
  const [mode, setMode] = useState('clinical');
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const config = useMemo(() => PERSONALITIES[mode], [mode]);

  const speak = () => {
    if (!text || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = config.rate;
    utterance.pitch = config.pitch;

    const voices = window.speechSynthesis.getVoices?.() || [];
    const preferred = voices.find((v) => v.lang === 'en-US') || voices[0];
    if (preferred) utterance.voice = preferred;

    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  return (
    <div className="voice-wrap">
      <div className="voice-modes">
        {Object.entries(PERSONALITIES).map(([key, value]) => (
          <button
            key={key}
            className={`btn-mini ${mode === key ? 'is-active' : ''}`}
            onClick={() => setMode(key)}
          >
            {value.label}
          </button>
        ))}
      </div>

      <div className="voice-actions">
        <button className="btn" onClick={speak} disabled={!text}>Explain Result 🔊</button>
        <button
          className="btn btn-danger"
          onClick={() => {
            window.speechSynthesis?.cancel();
            setSpeaking(false);
          }}
        >
          Stop
        </button>
      </div>

      <div className="tiny-note">{speaking ? 'Speaking...' : 'Idle'}</div>
    </div>
  );
}
