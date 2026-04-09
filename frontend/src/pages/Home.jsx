import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';

const providerChips = [
  { label: 'Claude (Active)', tone: 'cyan' },
  { label: 'OpenAI GPT-4o', tone: 'amber' },
  { label: 'Gemini Fallback', tone: 'green' },
  { label: 'Groq Speed Layer', tone: 'violet' },
];

const featureItems = [
  {
    icon: 'OCR',
    title: 'Real OCR Extraction',
    overline: 'Tesseract + OpenCV',
    desc: 'Tesseract + OpenCV pipeline dynamically extracts medicine name, batch, expiry, and dosage from images.',
    tone: 'cyan',
  },
  {
    icon: 'DEC',
    title: 'Decision Engine',
    overline: 'Multi-signal AI',
    desc: 'Multi-signal AI classification: Genuine / Suspicious / Fake with deterministic scoring and explainable output.',
    tone: 'pink',
  },
  {
    icon: 'SAFE',
    title: 'Drug Interaction AI',
    overline: 'Patient-specific safety',
    desc: 'Patient-specific safety analysis across allergies, age, comorbidities, and concurrent medications.',
    tone: 'sunset',
  },
];

export default function Home() {
  return (
    <section className="home-shell">
      <motion.div
        className="home-hero"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55 }}
      >
        <div className="home-kicker">
          <span className="home-kicker-dot" aria-hidden="true" />
          MULTI-AI PROVIDER SYSTEM - v2.0
        </div>
        <h1 className="home-title">
          Detect Fake Medicine
          <span>with Real AI</span>
        </h1>
        <p className="home-subtitle">
          Production-grade pharmaceutical authentication powered by local OCR and deterministic AI scoring for real-world screening.
        </p>

        <div className="home-cta-row">
          <Link to="/scan" className="home-btn home-btn-primary">Scan Medicine</Link>
          <Link to="/patient-safety" className="home-btn home-btn-ghost">Patient Safety Check</Link>
        </div>

        <div className="home-scroll-cue" aria-hidden="true">v</div>
      </motion.div>

      <motion.div
        className="home-provider-row"
        initial={{ opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.4 }}
        transition={{ duration: 0.4 }}
      >
        {providerChips.map((chip) => (
          <div key={chip.label} className={`home-provider-chip tone-${chip.tone}`}>
            <span className="home-provider-dot" aria-hidden="true" />
            {chip.label}
          </div>
        ))}
      </motion.div>

      <div className="home-feature-grid">
        {featureItems.map((item, idx) => (
          <motion.article
            key={item.title}
            className="home-feature-card"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.4, delay: idx * 0.08 }}
          >
            <div className={`home-feature-icon tone-${item.tone}`}>{item.icon}</div>
            <h3>{item.title}</h3>
            <div className="home-feature-overline">{item.overline}</div>
            <p>{item.desc}</p>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
