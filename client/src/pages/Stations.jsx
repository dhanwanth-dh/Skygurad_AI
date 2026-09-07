import { lazy, Suspense, useState } from 'react'
import { motion } from 'framer-motion'
import { useStations } from '../hooks/useApi'
import { MOCK_STATIONS_RESPONSE } from '../data/mockData'
import { StationCard } from '../components/StationCard'
import { CardSkeleton } from '../components/LoadingSkeleton'
import { ErrorState, EmptyState } from '../components/EmptyState'
import { Radio, Search, RefreshCw, Filter } from 'lucide-react'
import { StatusBadge, SeverityBadge } from '../components/StatusBadge'

const AwsNetworkMap = lazy(() =>
  import('../components/AwsNetworkMap').then(m => ({ default: m.AwsNetworkMap }))
)

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true'

export default function Stations() {
  const hook = useStations()
  const stations = USE_MOCK
    ? MOCK_STATIONS_RESPONSE.stations
    : (hook.data?.stations ?? [])
  const loading = USE_MOCK ? false : hook.loading
  const error = USE_MOCK ? null : hook.error

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('ALL')

  const filteredStations = stations.filter(s => {
    const matchesSearch =
      s.station_id.toLowerCase().includes(search.toLowerCase()) ||
      (s.station_name && s.station_name.toLowerCase().includes(search.toLowerCase()))
    if (!matchesSearch) return false
    if (filter === 'ALL') return true
    if (filter === 'NORMAL') return s.prediction === 'NORMAL'
    if (filter === 'ANOMALY') return s.prediction !== 'NORMAL'
    return true
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-7xl mx-auto pb-12"
    >
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-6 sm:p-8 rounded-3xl glass-panel">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-xs font-bold text-sky-700 mb-2">
            <Radio size={13} className="text-sky-500" />
            Sensor Network Directory
          </div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 font-heading">
            Pan-India AWS Stations
          </h1>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Monitoring {stations.length} automated stations across meteorological regimes in India.
          </p>
        </div>

        <button
          onClick={hook.refetch}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-xs font-bold text-slate-700 shadow-xs transition-all disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Network</span>
        </button>
      </div>

      {error && <ErrorState message={error} />}

      {/* Geospatial Map */}
      <Suspense fallback={<CardSkeleton />}>
        <AwsNetworkMap stations={stations} loading={loading} />
      </Suspense>

      {/* Search & Filter Controls */}
      <div className="glass-panel p-4 rounded-2xl flex flex-wrap items-center justify-between gap-4">
        <div className="relative flex-1 min-w-[240px]">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by station ID (e.g. AWS_TN_01) or location name..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-white/90 border border-slate-200 text-xs font-semibold text-slate-800 placeholder-slate-400 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100 transition-all"
          />
        </div>

        <div className="flex items-center gap-2">
          {['ALL', 'NORMAL', 'ANOMALY'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                filter === f
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white/80 text-slate-600 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              {f === 'ALL' ? 'All Stations' : f === 'NORMAL' ? 'Healthy Only' : 'Flagged Anomalies'}
            </button>
          ))}
        </div>
      </div>

      {/* Grid of Station Cards */}
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs font-bold text-slate-500">
          <span>Active Stations ({filteredStations.length})</span>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}
          </div>
        ) : filteredStations.length === 0 ? (
          <EmptyState
            icon={Radio}
            title="No matching stations"
            description="Try changing your search term or filter selection."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredStations.map((s, i) => (
              <StationCard key={s.station_id} station={s} index={i} />
            ))}
          </div>
        )}
      </div>

      {/* Desktop Summary Table */}
      {!loading && filteredStations.length > 0 && (
        <div className="hidden lg:block glass-card rounded-3xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-slate-200/80 bg-white/60 font-bold text-xs uppercase tracking-wider text-slate-900 font-heading">
            Network Telemetry Matrix
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200/80 bg-slate-50/80 text-slate-500 uppercase tracking-wider font-bold">
                  {['Station ID', 'Location', 'Latitude', 'Longitude', 'Temp', 'Humidity', 'Pressure', 'Observation', 'Score', 'Health'].map(h => (
                    <th key={h} className="py-3 px-4">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                {filteredStations.map(s => (
                  <tr key={s.station_id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-900">{s.station_id}</td>
                    <td className="py-3 px-4 text-slate-500">{s.station_name || '—'}</td>
                    <td className="py-3 px-4 font-mono text-slate-500">{s.latitude?.toFixed(4)}°N</td>
                    <td className="py-3 px-4 font-mono text-slate-500">{s.longitude?.toFixed(4)}°E</td>
                    <td className="py-3 px-4 font-bold text-slate-800">{s.temperature_c?.toFixed(1)} °C</td>
                    <td className="py-3 px-4 font-bold text-slate-800">{s.relative_humidity_pct?.toFixed(1)} %</td>
                    <td className="py-3 px-4 font-bold text-slate-800">{s.pressure_hpa?.toFixed(1)} hPa</td>
                    <td className="py-3 px-4"><StatusBadge status={s.prediction} /></td>
                    <td className="py-3 px-4 font-mono font-bold text-sky-600">{s.anomaly_score?.toFixed(3)}</td>
                    <td className="py-3 px-4 font-bold text-emerald-600">{s.sensor_health?.toFixed(1)}/100</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </motion.div>
  )
}
