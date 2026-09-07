import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Radio, AlertTriangle, Bell,
  BarChart2, Cpu, Activity, X, FlaskConical, Shield
} from 'lucide-react'

const NAV = [
  {
    group: 'INTELLIGENCE',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/stations', label: 'AWS Stations', icon: Radio },
      { to: '/anomalies', label: 'Anomalies', icon: AlertTriangle },
      { to: '/alerts', label: 'Live Alerts', icon: Bell },
      { to: '/analytics', label: 'Analytics', icon: BarChart2 },
      { to: '/test', label: 'Test Observation', icon: FlaskConical },
    ],
  },
  {
    group: 'SYSTEM CORE',
    items: [
      { to: '/model-status', label: 'Model Registry', icon: Cpu },
      { to: '/system-health', label: 'System Health', icon: Activity },
    ],
  },
]

export function Sidebar({ open, onClose }) {
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed top-0 left-0 h-full z-50 flex flex-col
          transition-transform duration-300 ease-out
          lg:static lg:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}
          w-64 bg-white/55 backdrop-blur-2xl border-r border-white/50 shadow-[4px_0_30px_rgba(0,0,0,0.06)]
        `}
      >
        {/* Brand Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/25 text-white">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="text-base font-extrabold tracking-tight text-slate-900 font-heading">
                SKYGUARD<span className="text-sky-500 font-bold ml-1">AI</span>
              </div>
              <div className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase">
                Multi-Model Engine
              </div>
            </div>
          </div>
          <button
            className="lg:hidden p-1.5 rounded-xl hover:bg-white/40 text-slate-500 hover:text-slate-800 transition-colors"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-6 px-4 space-y-6">
          {NAV.map(({ group, items }) => (
            <div key={group}>
              <div className="text-[10px] font-bold tracking-wider text-slate-500 px-3 mb-2 uppercase">
                {group}
              </div>
              <div className="space-y-1">
                {items.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `group flex items-center justify-between px-3.5 py-2.5 rounded-2xl text-xs font-bold tracking-wide transition-all duration-200 ${isActive
                        ? 'bg-white/90 text-sky-700 shadow-sm border border-sky-300/70 backdrop-blur-md'
                        : 'text-slate-700 hover:bg-white/40 hover:text-slate-950'}`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <div className="flex items-center gap-3">
                          <Icon
                            size={17}
                            className={`transition-transform duration-200 group-hover:scale-110 ${isActive ? 'text-sky-600' : 'text-slate-500 group-hover:text-slate-800'}`}
                          />
                          <span>{label}</span>
                        </div>
                        {isActive && (
                          <div className="w-2 h-2 rounded-full bg-sky-500 shadow-xs shadow-sky-500 animate-pulse" />
                        )}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer info badge */}
        <div className="p-4 border-t border-white/40">
          <div className="px-3.5 py-3 rounded-2xl bg-white/45 backdrop-blur-md border border-white/60 text-xs space-y-1 shadow-xs">
            <div className="flex items-center justify-between font-bold text-slate-800">
              <span>Engine Status</span>
              <span className="flex items-center gap-1.5 text-[11px] text-emerald-600 font-semibold">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping inline-block" />
                Active
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-medium">30 AWS Stations Â· v2.0</p>
          </div>
        </div>
      </aside>
    </>
  )
}



