import { lazy, Suspense, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, AlertTriangle, Radio, ShieldCheck, Zap, CloudLightning, Activity } from 'lucide-react'
import { useStations, useAnomalies } from '../hooks/useApi'
import { api } from '../services/api'
import { MOCK_STATIONS_RESPONSE, MOCK_ANOMALIES_RESPONSE } from '../data/mockData'
import { KpiCard } from '../components/KpiCard'
import { AnomalyCenter } from '../components/AnomalyCenter'
import { StationCard } from '../components/StationCard'
import { AlertCard } from '../components/AlertCard'
import { CardSkeleton, LoadingSkeleton } from '../components/LoadingSkeleton'
import { ErrorState } from '../components/EmptyState'

const AwsNetworkMap = lazy(() =>
  import('../components/AwsNetworkMap').then(m => ({ default: m.AwsNetworkMap }))
)

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true'

function useDashboardData() {
  const stationsHook = useStations()
  const anomaliesHook = useAnomalies()

  if (USE_MOCK) {
    return {
      stations: MOCK_STATIONS_RESPONSE.stations,
      anomalies: MOCK_ANOMALIES_RESPONSE.anomalies,
      anomalyMeta: {
        sensor_faults: MOCK_ANOMALIES_RESPONSE.sensor_faults,
        genuine_events: MOCK_ANOMALIES_RESPONSE.genuine_events,
      },
      loading: false,
      error: null,
      refetch: () => {},
      lastSync: new Date(),
    }
  }

  return {
    stations: stationsHook.data?.stations ?? [],
    anomalies: anomaliesHook.data?.anomalies ?? [],
    anomalyMeta: {
      sensor_faults: anomaliesHook.data?.sensor_faults ?? 0,
      genuine_events: anomaliesHook.data?.genuine_events ?? 0,
    },
    loading: stationsHook.loading || anomaliesHook.loading,
    error: stationsHook.error || anomaliesHook.error,
    refetch: () => { stationsHook.refetch(); anomaliesHook.refetch() },
    lastSync: new Date(),
  }
}

export default function Dashboard() {
  const { stations, anomalies, anomalyMeta, loading, error, refetch } = useDashboardData()

  const healthyCount = stations.filter(s => s.prediction === 'NORMAL').length
  const anomalyRate = stations.length > 0 ? Math.round((anomalies.length / stations.length) * 100) : 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-7xl mx-auto pb-8"
    >
      {/* Top Hero Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-6 sm:p-8 rounded-3xl glass-panel relative overflow-hidden">
        <div className="relative z-10 space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-50 border border-sky-200/80 text-xs font-bold text-sky-700 mb-2">
            <span className="w-2 h-2 rounded-full bg-sky-500 animate-pulse" />
            AI Multi-Model Meteorological Engine
          </div>
          <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900 font-heading">
            Weather Station Intelligence
          </h1>
          <p className="text-sm text-slate-500 font-medium max-w-2xl">
            Real-time quality control, automated sensor fault isolation, and genuine extreme weather detection across {stations.length > 0 ? `${stations.length} Pan-India AWS stations` : 'Pan-India AWS stations'}.
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-3">
          <button
            onClick={refetch}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-md hover:shadow-lg transition-all active:scale-95 disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Sync Telemetry</span>
          </button>
        </div>

        {/* Soft background ambient light spot */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-br from-sky-400/10 to-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      </div>

      {error && <ErrorState message={error} />}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} />)
        ) : (
          <>
            <KpiCard label="Active Stations" value={stations.length} sub="Pan-India Network" color="#0284C7" icon={Radio} />
            <KpiCard label="Healthy Sensors" value={healthyCount} sub={stations.length > 0 ? Math.round((healthyCount / stations.length) * 100) + '% verified' : '100% verified'} color="#10B981" icon={ShieldCheck} />
            <KpiCard label="Active Anomalies" value={anomalies.length} sub={anomalyRate + '% network rate'} color={anomalies.length > 0 ? '#F59E0B' : '#10B981'} icon={AlertTriangle} />
            <KpiCard label="Hardware Faults" value={anomalyMeta.sensor_faults} sub="Drift / Freeze / Spike" color={anomalyMeta.sensor_faults > 0 ? '#F43F5E' : '#10B981'} icon={Zap} />
            <KpiCard label="Weather Events" value={anomalyMeta.genuine_events} sub="Atmospheric Fronts" color={anomalyMeta.genuine_events > 0 ? '#8B5CF6' : '#10B981'} icon={CloudLightning} />
          </>
        )}
      </div>

      {/* Historical Data & Continuous Training Status Bar */}
      <HistoricalDataConsole stationsCount={stations.length} />

      {/* Geospatial Map */}
      <section className="space-y-3">
        <SectionHeader title="Geospatial Telemetry Distribution" sub="Live operational health and atmospheric pressure residuals" icon={<Radio className="w-4 h-4 text-sky-600" />} />
        <Suspense fallback={<CardSkeleton />}>
          <AwsNetworkMap stations={stations} loading={loading} />
        </Suspense>
      </section>

      {/* Anomaly Command Center */}
      <section className="space-y-3">
        <SectionHeader title="Anomaly Command Center" sub="Real-time multi-detector consensus & classification breakdown" icon={<AlertTriangle className="w-4 h-4 text-amber-500" />} />
        {loading ? <LoadingSkeleton rows={3} height="h-20" /> : <AnomalyCenter anomalies={anomalies} loading={loading} />}
      </section>

      {/* All Stations Grid */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionHeader title="Monitored AWS Stations" sub={`${stations.length || 'All'} stations spanning coastal, Himalayan high-altitude, and plains environments`} icon={<Activity className="w-4 h-4 text-emerald-600" />}  />
          <div className="text-xs font-bold text-slate-500 bg-white/70 px-3 py-1.5 rounded-full border border-slate-200/80 shadow-xs">Showing all {stations.length} stations</div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">{Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}</div>
        ) : stations.length === 0 ? (
          <div className="glass-panel p-8 text-center rounded-3xl"><p className="text-sm font-semibold text-slate-500">No station telemetry found. Please verify the backend API server is running.</p></div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">{stations.map((s, i) => <StationCard key={s.station_id} station={s} prediction={s} index={i} />)}</div>
        )}
      </section>

      {!loading && anomalies.length > 0 && (
        <section className="space-y-4">
          <SectionHeader title="Priority Operational Alerts" sub="Flagged observations requiring immediate technician dispatch or calibration audit" icon={<AlertTriangle className="w-4 h-4 text-rose-500" />} />
          <div className="space-y-3">{anomalies.slice(0, 4).map((a, i) => <AlertCard key={a.station_id + '-' + i} alert={a} index={i} />)}</div>
        </section>
      )}
    </motion.div>
  )
}

function SectionHeader({ title, sub, icon }) {
  return (
    <div className="flex items-center gap-3">
      {icon && <div className="w-8 h-8 rounded-xl bg-white border border-slate-200/80 flex items-center justify-center shadow-xs shrink-0">{icon}</div>}
      <div>
        <h2 className="text-lg font-bold text-white font-heading tracking-tight">{title}</h2>
        {sub && <p className="text-xs font-medium text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function HistoricalDataConsole({ stationsCount }) {
  const [histStatus, setHistStatus] = useState(null)
  const [modelInfo, setModelInfo] = useState(null)

  useEffect(() => {
    api.getHistoricalStatus()
      .then(setHistStatus)
      .catch(() => {})

    api.getModelInfo()
      .then(setModelInfo)
      .catch(() => {})
  }, [])

  const stations = histStatus?.stations || stationsCount || 1152
  const records = histStatus?.records || 0
  const oldest = histStatus?.oldest_observation?.slice(0, 10) || '2011'
  const latest = histStatus?.latest_observation?.slice(0, 10) || '2026'
  const coverage = `${oldest.slice(0, 4)}–${latest.slice(0, 4)}`
  const lastSync = histStatus?.last_sync ? histStatus.last_sync.slice(11, 16) + ' UTC' : 'Real-Time'
  const modelVer = modelInfo?.model_version || 'v2.0-multimodel'

  const exportUrl = api.getHistoricalExportUrl({ format: 'xlsx' })

  return (
    <div className="glass-panel p-5 rounded-3xl flex flex-wrap items-center justify-between gap-4 border border-slate-200/80">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-2xl bg-indigo-50 border border-indigo-200/80 flex items-center justify-center text-indigo-600 font-bold">
          <Activity size={20} />
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-heading">
            Historical Data & Intelligence Archive
          </div>
          <div className="text-sm font-extrabold text-slate-900 font-heading flex items-center gap-2">
            <span>{stations.toLocaleString()} Stations Active</span>
            <span className="text-slate-300">·</span>
            <span className="text-sky-700">{records > 0 ? `${(records / 1_000_000).toFixed(1)}M Observations` : 'Live Synced'}</span>
            <span className="text-slate-300">·</span>
            <span className="text-slate-500 font-medium">Coverage: {coverage}</span>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs">
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200/80 text-slate-600 font-medium">
          <span className="text-[11px] font-bold text-slate-400">Latest Sync:</span>
          <span className="font-semibold text-slate-800">{lastSync}</span>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200/80 text-slate-600 font-medium">
          <span className="text-[11px] font-bold text-slate-400">Model:</span>
          <span className="font-semibold text-indigo-700">{modelVer}</span>
        </div>

        <a
          href={exportUrl}
          target="_blank"
          rel="noreferrer"
          className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs shadow-xs transition-all active:scale-95"
        >
          Export Archive (.xlsx)
        </a>
      </div>
    </div>
  )
}


