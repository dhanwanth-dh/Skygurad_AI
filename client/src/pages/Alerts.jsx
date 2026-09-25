import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Bell, RefreshCw } from 'lucide-react'
import { api } from '../services/api'
import { MOCK_ANOMALIES_RESPONSE } from '../data/mockData'
import { AlertCard } from '../components/AlertCard'
import { LoadingSkeleton } from '../components/LoadingSkeleton'
import { ErrorState, EmptyState } from '../components/EmptyState'

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true'
const FILTERS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export default function Alerts() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('ALL')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (USE_MOCK) {
        setPredictions(MOCK_ANOMALIES_RESPONSE.anomalies)
      } else {
        const data = await api.getAnomalies()
        setPredictions(data?.anomalies ?? [])
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = filter === 'ALL' ? predictions : predictions.filter(p => p.severity === filter)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-5xl mx-auto pb-12"
    >
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-6 sm:p-8 rounded-3xl glass-panel">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-50 border border-rose-200 text-xs font-bold text-rose-700 mb-2">
            <Bell size={13} className="text-rose-500" />
            Live Priority Notifications
          </div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 font-heading">
            Operational Alerts
          </h1>
          <p className="text-sm text-slate-500 font-medium mt-1">
            {predictions.length} active notifications requiring review or field maintenance.
          </p>
        </div>

        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-xs font-bold text-slate-700 shadow-xs transition-all disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Alerts</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2 p-1.5 rounded-2xl bg-white/80 border border-slate-200/80 shadow-xs w-fit">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
              filter === f
                ? 'bg-slate-900 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {error && <ErrorState message={error} />}

      {loading ? (
        <LoadingSkeleton rows={4} height="h-24" />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="Zero Active Alerts"
          description="All station readings are currently within nominal tolerances."
        />
      ) : (
        <div className="space-y-3.5">
          {filtered.map((a, i) => (
            <AlertCard key={`${a.station_id}-${i}`} alert={a} index={i} />
          ))}
        </div>
      )}
    </motion.div>
  )
}
