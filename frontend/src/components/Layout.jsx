import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/vehicles', label: 'Vehicles' },
  { to: '/people', label: 'People' },
  { to: '/logs', label: 'Access Logs' },
  { to: '/devices', label: 'Devices', adminOnly: true },
  { to: '/users', label: 'Users', adminOnly: true },
  { to: '/ocr', label: 'OCR Tester' },
];

export default function Layout() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark" />
          <div>
            <p className="eyebrow">Access Control</p>
            <h1>Gatekeeper</h1>
          </div>
        </div>

        <nav className="side-nav">
          {NAV.filter((item) => !item.adminOnly || isAdmin).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="panel status-panel side-user">
          <span className="panel-kicker">Signed in</span>
          <strong className="side-user-name">{user?.username}</strong>
          <span className={`badge ${isAdmin ? 'good' : 'neutral'}`}>{user?.role}</span>
          <button type="button" className="btn btn-secondary" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main-shell">
        <Outlet />
      </main>
    </div>
  );
}
