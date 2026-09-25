import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Radio, AlertTriangle, Bell,
  BarChart2, Cpu, Activity, X, FlaskConical, Shield
} from 'lucide-react'
import { useStations } from '../hooks/useApi'

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
  const { data: stationsData } = useStations()
  const stationCount = stationsData?.stations?.length ?? stationsData?.total ?? 0

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed top-0 left-0 h-full z-50 flex flex-col
          transition-transform duration-300 ease-out
          lg:static lg:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}
          w-64 bg-slate-950/90 backdrop-blur-2xl border-r border-slate-800/80 shadow-[4px_0_30px_rgba(0,0,0,0.3)]
        `}
      >
        {/* Brand Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/25 text-white">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="text-base font-extrabold tracking-tight text-white font-heading">
                SKYGUARD<span className="text-sky-400 font-bold ml-1">AI</span>
              </div>
              <div className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase">
                Multi-Model Engine
              </div>
            </div>
          </div>
          <button
            className="lg:hidden p-1.5 rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
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
              <div className="text-[10px] font-bold tracking-wider text-slate-400 px-3 mb-2 uppercase">
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
                        ? 'bg-sky-500/20 text-sky-300 shadow-sm border border-sky-400/40 backdrop-blur-md'
                        : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'}`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <div className="flex items-center gap-3">
                          <Icon
                            size={17}
                            className={`transition-transform duration-200 group-hover:scale-110 ${isActive ? 'text-sky-400' : 'text-slate-400 group-hover:text-white'}`}
                          />
                          <span>{label}</span>
                        </div>
                        {isActive && (
                          <div className="w-2 h-2 rounded-full bg-sky-400 shadow-xs shadow-sky-400 animate-pulse" />
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
        <div className="p-4 border-t border-slate-800/80">
          <div className="px-3.5 py-3 rounded-2xl bg-slate-900/90 backdrop-blur-md border border-slate-700/70 text-xs space-y-1 shadow-xs">
            <div className="flex items-center justify-between font-bold text-slate-100">
              <span>Engine Status</span>
              <span className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-semibold">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block" />
                Active
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium font-mono">
              {stationCount > 0 ? `${stationCount} AWS Stations` : 'Live Stream'} · v2.0
            </p>
          </div>
        </div>
      </aside>
    </>
  )
}



