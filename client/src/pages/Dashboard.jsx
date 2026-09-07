import { lazy, Suspense } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, AlertTriangle, Radio, ShieldCheck, Zap, CloudLightning, Activity } from 'lucide-react'
import { useStations, useAnomalies } from '../hooks/useApi'
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
            Real-time quality control, automated sensor fault isolation, and genuine extreme weather detection across 30 Pan-India AWS stations.
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
          <SectionHeader title="Monitored AWS Stations" sub="30 stations spanning coastal, Himalayan high-altitude, and plains environments" icon={<Activity className="w-4 h-4 text-emerald-600" />} />
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
        <h2 className="text-lg font-bold text-slate-900 font-heading tracking-tight">{title}</h2>
        {sub && <p className="text-xs font-medium text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

