import { Outlet, NavLink } from 'react-router-dom';

const NAV = [
  { to: '/query', label: 'RAG Chat', icon: '✦' },
  { to: '/evaluation', label: 'Eval Metrics', icon: '◈' },
  { to: '/analytics', label: 'Knowledge Base', icon: '⊙' },
  { to: '/admin', label: 'Admin', icon: '⚙' },
];

export default function Layout() {
  return (
    <div className="flex h-screen bg-[#0A0C10] text-[#E8EAF0] font-sans overflow-hidden">
      <div className="w-[58px] flex flex-col items-center pt-4 gap-1 border-r border-[#1E2330] bg-[#111318] shrink-0">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4F8EF7] to-[#00C9A7] flex items-center justify-center text-sm font-bold text-white mb-3">R</div>
        {NAV.map(n => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) =>
            `w-10 h-10 rounded-lg flex items-center justify-center text-base transition-all border ${isActive ? 'border-[#00C9A7] bg-[#00C9A720] text-[#00C9A7]' : 'border-transparent text-[#454E66] hover:text-[#8891A8]'}`
          } title={n.label}>
            {n.icon}
          </NavLink>
        ))}
      </div>
      <div className="flex-1 overflow-hidden flex flex-col">
        <Outlet />
      </div>
    </div>
  );
}
