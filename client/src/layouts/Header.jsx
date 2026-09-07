import { useState } from 'react'
import { RefreshCw, Menu, Radio } from 'lucide-react'
import { useHealth } from '../hooks/useApi'

export function Header({ onMenuClick }) {
  const { data: health, loading, refetch } = useHealth()
  const [isRotating, setIsRotating] = useState(false)

  const isOk = health?.status === 'ok' && health?.model_loaded

  const handleRefresh = async () => {
    setIsRotating(true)
    await refetch()
    setTimeout(() => setIsRotating(false), 600)
  }

  return (
    <header className="h-16 px-6 lg:px-8 flex items-center justify-between border-b border-white/40 bg-white/45 backdrop-blur-2xl z-20 shrink-0 shadow-xs">
      <div className="flex items-center gap-4">
        <button
          className="lg:hidden p-2 rounded-2xl bg-white/50 hover:bg-white/70 text-slate-600 hover:text-slate-900 transition-colors shadow-xs"
          onClick={onMenuClick}
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>

        <div className="header-network hidden sm:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/50 backdrop-blur-md border border-white/60 text-xs text-slate-700 shadow-xs">
          <Radio className="w-3.5 h-3.5 text-sky-500 animate-pulse" />
          <span className="font-bold text-slate-800">Pan-India AWS Network</span>
          <span className="text-slate-400">·</span>
          <span className="text-slate-600 font-mono font-semibold">30 Active Stations</span>
        </div>
      </div>

      <div className="flex items-center gap-3.5">
        {!loading && (
          <div
            className={'flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-bold tracking-wide border backdrop-blur-md shadow-xs transition-all ' +
              (isOk
                ? 'bg-emerald-50/80 border-emerald-300/80 text-emerald-800 shadow-emerald-500/10'
                : 'bg-rose-50/80 border-rose-300/80 text-rose-800 shadow-rose-500/10')}
          >
            <span className={'w-2 h-2 rounded-full ' + (isOk ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500')} />
            <span>{isOk ? 'AI Engine Operational' : 'Offline / Standby'}</span>
          </div>
        )}

        <button
          onClick={handleRefresh}
          className="header-sync flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/70 hover:bg-white/90 backdrop-blur-md border border-white/80 text-xs font-bold text-slate-800 shadow-xs hover:shadow transition-all duration-200 active:scale-95"
          aria-label="Refresh telemetry and models"
        >
          <RefreshCw size={13} className={isRotating ? 'text-sky-600 animate-spin' : 'text-sky-600'} />
          <span className="hidden sm:inline">Sync</span>
        </button>
      </div>
    </header>
  )
}
