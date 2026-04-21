import { BarChart3, Bot, FolderCog, LineChart, Moon, Sparkles, SunMedium } from 'lucide-react';
import { Outlet, NavLink } from 'react-router-dom';
import { useTheme } from '../theme';

const NAV = [
  {
    to: '/query',
    label: 'Assistant',
    description: 'Ask, inspect, and trace answers',
    icon: Bot,
  },
  {
    to: '/evaluation',
    label: 'Evaluation',
    description: 'Monitor retrieval and response quality',
    icon: LineChart,
  },
  {
    to: '/analytics',
    label: 'Analytics',
    description: 'Review filings, trends, and coverage',
    icon: BarChart3,
  },
  {
    to: '/admin',
    label: 'Admin',
    description: 'Upload documents and manage pipeline health',
    icon: FolderCog,
  },
];

export default function Layout() {
  const { isDark, toggleTheme } = useTheme();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <div className="app-brand-mark">
            <Sparkles size={20} />
          </div>
          <div className="app-brand-text">
            <div className="app-brand-title">Financial Intelligence Suite</div>
          </div>
        </div>

        <nav className="app-nav" aria-label="Primary">
          {NAV.map(({ to, label, description, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              title={`${label} — ${description}`}
              data-tooltip={label}
              className={({ isActive }) => `app-nav-link${isActive ? ' active' : ''}`}
            >
              <span className="app-nav-icon">
                <Icon size={18} />
              </span>
              <span className="app-nav-meta">
                <span className="app-nav-label">{label}</span>
                <span className="app-nav-copy">{description}</span>
              </span>
            </NavLink>
          ))}
        </nav>

        <button
          type="button"
          className="app-theme-toggle"
          onClick={toggleTheme}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          data-tooltip={isDark ? 'Light mode' : 'Dark mode'}
        >
          <span className="app-nav-icon">
            {isDark ? <SunMedium size={18} /> : <Moon size={18} />}
          </span>
          <span className="app-nav-meta">
            <span className="app-nav-label">{isDark ? 'Light Mode' : 'Dark Mode'}</span>
          </span>
        </button>
      </aside>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
