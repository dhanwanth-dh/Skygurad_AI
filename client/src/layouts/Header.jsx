import { useState } from 'react'
import { RefreshCw, Menu, Radio } from 'lucide-react'
import { useHealth, useStations } from '../hooks/useApi'

export function Header({ onMenuClick }) {
  const { data: health, loading, refetch: refetchHealth } = useHealth()
  const { data: stationsData, refetch: refetchStations } = useStations()
  const [isRotating, setIsRotating] = useState(false)

  const isOk = health?.status === 'ok' && health?.model_loaded
  const stationCount = stationsData?.stations?.length ?? stationsData?.total ?? 0

  const handleRefresh = async () => {
    setIsRotating(true)
    await Promise.allSettled([refetchHealth(), refetchStations()])
    setTimeout(() => setIsRotating(false), 600)
  }

  return (
    <header className="h-16 px-6 lg:px-8 flex items-center justify-between border-b border-slate-700/50 bg-slate-950/80 backdrop-blur-2xl z-20 shrink-0 shadow-lg">
      <div className="flex items-center gap-4">
        <button
          className="lg:hidden p-2 rounded-2xl bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 hover:text-white transition-colors shadow-xs"
          onClick={onMenuClick}
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>

        <div className="header-network hidden sm:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-800/90 backdrop-blur-md border border-slate-700/80 text-xs shadow-xs">
          <Radio className="w-3.5 h-3.5 text-sky-400 animate-pulse" />
          <span className="font-bold text-slate-100">Pan-India AWS Network</span>
          <span className="text-slate-400">·</span>
          <span className="text-sky-300 font-mono font-bold">
            {stationCount > 0 ? `${stationCount} Active Stations` : 'Live Telemetry'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3.5">
        {!loading && (
          <div
            className={'flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-bold tracking-wide border backdrop-blur-md shadow-xs transition-all ' +
              (isOk
                ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-300 shadow-emerald-500/10'
                : 'bg-rose-950/80 border-rose-500/50 text-rose-300 shadow-rose-500/10')}
          >
            <span className={'w-2 h-2 rounded-full ' + (isOk ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400')} />
            <span>{isOk ? 'AI Engine Operational' : 'Offline / Standby'}</span>
          </div>
        )}

        <button
          onClick={handleRefresh}
          className="header-sync flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-800/90 hover:bg-slate-700/90 backdrop-blur-md border border-slate-600/80 text-xs font-bold text-white shadow-xs hover:shadow transition-all duration-200 active:scale-95 cursor-pointer"
          aria-label="Refresh telemetry and models"
        >
          <RefreshCw size={13} className={isRotating ? 'text-sky-400 animate-spin' : 'text-sky-400'} />
          <span className="hidden sm:inline text-white">Sync</span>
        </button>
      </div>
    </header>
  )
}
