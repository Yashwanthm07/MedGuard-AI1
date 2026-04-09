import { NavLink, Route, Routes } from 'react-router-dom';
import Home from './pages/Home.jsx';
import Scan from './pages/Scan.jsx';
import Result from './pages/Result.jsx';
import PatientSafety from './pages/PatientSafety.jsx';
import Dashboard from './pages/Dashboard.jsx';

function App() {
  const navItems = [
    { to: '/', label: 'Home', end: true },
    { to: '/scan', label: 'Scanner' },
    { to: '/patient-safety', label: 'Patient Safety' },
    { to: '/dashboard', label: 'Dashboard' },
  ];

  return (
    <div className="app-shell">
      <nav className="top-nav">
        <div className="top-nav-brand" aria-label="MedGuard AI">
          <span className="top-nav-brand-mark" aria-hidden="true" />
          <div>
            <div className="top-nav-brand-name">MedGuard</div>
            <div className="top-nav-brand-sub">AI</div>
          </div>
        </div>

        <div className="top-nav-links">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `top-nav-link ${isActive ? 'active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        <div className="top-nav-right">
          <div className="top-nav-status">
            <span className="top-nav-status-dot" aria-hidden="true" />
            AI Online
          </div>
          <button className="top-nav-menu-btn" type="button" aria-label="More menu">
            ...
          </button>
        </div>
      </nav>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/scan" element={<Scan />} />
        <Route path="/result" element={<Result />} />
        <Route path="/patient-safety" element={<PatientSafety />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </div>
  );
}

export default App;
