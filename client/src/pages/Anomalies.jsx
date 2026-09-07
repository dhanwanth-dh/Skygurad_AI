import { motion } from 'framer-motion'
import { useAnomalies } from '../hooks/useApi'
import { MOCK_ANOMALIES_RESPONSE } from '../data/mockData'
import { AnomalyCenter } from '../components/AnomalyCenter'
import { KpiCard } from '../components/KpiCard'
import { CardSkeleton, LoadingSkeleton } from '../components/LoadingSkeleton'
import { ErrorState } from '../components/EmptyState'
import { AlertTriangle, Zap, CloudLightning, ShieldAlert, RefreshCw } from 'lucide-react'

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true'

export default function Anomalies() {
  const hook = useAnomalies()
  const data = USE_MOCK ? MOCK_ANOMALIES_RESPONSE : hook.data
  const loading = USE_MOCK ? false : hook.loading
  const error = USE_MOCK ? null : hook.error

  const anomalies = data?.anomalies ?? []
  const high = anomalies.filter(a => a.severity === 'HIGH').length
  const critical = anomalies.filter(a => a.severity === 'CRITICAL').length

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-6xl mx-auto pb-12"
    >
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-6 sm:p-8 rounded-3xl glass-panel">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-xs font-bold text-amber-700 mb-2">
            <AlertTriangle size={13} className="text-amber-500" />
            Active Incident Feed
          </div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 font-heading">
            Anomaly Command Center
          </h1>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Real-time isolation of physical sensor malfunctions vs genuine atmospheric frontal events.
          </p>
        </div>

        <button
          onClick={hook.refetch}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-xs font-bold text-slate-700 shadow-xs transition-all disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Incidents</span>
        </button>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} />)
        ) : (
          <>
            <KpiCard label="Total Flagged" value={data?.total ?? 0} icon={AlertTriangle} color="#F59E0B" />
            <KpiCard label="High Severity" value={high} color="#F43F5E" icon={ShieldAlert} />
            <KpiCard label="Critical" value={critical} color="#DC2626" icon={ShieldAlert} />
            <KpiCard label="Sensor Faults" value={data?.sensor_faults ?? 0} color="#F43F5E" icon={Zap} />
            <KpiCard label="Weather Events" value={data?.genuine_events ?? 0} color="#8B5CF6" icon={CloudLightning} />
          </>
        )}
      </div>

      {error && <ErrorState message={error} />}

      {loading ? (
        <LoadingSkeleton rows={4} height="h-24" />
      ) : (
        <AnomalyCenter anomalies={anomalies} loading={loading} />
      )}
    </motion.div>
  )
}
