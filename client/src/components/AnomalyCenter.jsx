import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, ArrowRight, Zap, CloudLightning } from 'lucide-react'
import { StatusBadge, SeverityBadge } from './StatusBadge'
import { AnomalyScoreMeter } from './AnomalyScoreMeter'
import { EvidenceCard } from './EvidenceCard'
import { ExpectedObservedCard } from './ExpectedObservedCard'
import { fmt, fmtPct, formatTimestamp } from '../utils/format'

const FILTERS = ['ALL', 'SENSOR_FAULT', 'GENUINE_EXTREME', 'HIGH', 'CRITICAL']

export function AnomalyCenter({ anomalies = [], loading = false }) {
  const [filter, setFilter] = useState('ALL')
  const [expanded, setExpanded] = useState(null)
  const navigate = useNavigate()

  const filtered = anomalies.filter(a => {
    if (filter === 'ALL') return true
    if (filter === 'HIGH') return a.severity === 'HIGH'
    if (filter === 'CRITICAL') return a.severity === 'CRITICAL'
    return a.prediction === filter
  })

  if (!loading && anomalies.length === 0) {
    return (
      <div className="glass-panel p-12 rounded-3xl flex flex-col items-center justify-center text-center gap-3">
        <div className="w-14 h-14 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-xs">
          <CheckCircle2 size={32} />
        </div>
        <div className="text-base font-bold text-slate-900 font-heading">
          All Stations Operational & Verified
        </div>
        <p className="text-xs text-slate-500 max-w-md font-medium">
          Zero active telemetry anomalies flagged. All monitored Pan-India AWS stations are operating within standard historical bounds.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5 p-1 rounded-2xl bg-white/80 border border-slate-200/80 shadow-xs">
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all duration-200 ${
                filter === f
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              {f.replace('_', ' ')}
              {f === 'ALL' && anomalies.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] bg-rose-500 text-white font-mono">
                  {anomalies.length}
                </span>
              )}
            </button>
          ))}
        </div>

        <span className="text-xs font-semibold text-slate-400">
          Showing {filtered.length} of {anomalies.length} observations
        </span>
      </div>

      {filtered.length === 0 && (
        <div className="glass-panel p-8 text-center rounded-2xl text-xs font-semibold text-slate-400">
          No observations match the "{filter}" filter.
        </div>
      )}

      {filtered.map((a, i) => {
        const isExpanded = expanded === a.station_id
        const isFault = a.prediction === 'SENSOR_FAULT'
        const borderAccent = isFault ? '#F43F5E' : '#8B5CF6'

        return (
          <motion.div
            key={`${a.station_id}-${i}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: i * 0.03 }}
            className="glass-card rounded-2xl overflow-hidden border-l-4 shadow-xs"
            style={{ borderLeftColor: borderAccent }}
          >
            {/* Summary card */}
            <div className="p-5 sm:p-6 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-lg font-extrabold text-slate-900 font-heading">
                      {a.station_id}
                    </span>
                    {a.station_name && (
                      <span className="text-xs font-medium text-slate-500">
                        ({a.station_name})
                      </span>
                    )}
                    <StatusBadge status={a.prediction} />
                    <SeverityBadge severity={a.severity} />
                  </div>
                  <div className="text-[11px] font-medium text-slate-400">
                    {formatTimestamp(a.timestamp)}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-2xl font-black font-heading" style={{ color: borderAccent }}>
                    {a.anomaly_score?.toFixed(3)}
                  </div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    Score
                  </div>
                </div>
              </div>

              {/* Metrics grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-slate-50/80 border border-slate-100">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">Confidence</span>
                  <span className="text-xs sm:text-sm font-bold text-slate-800 font-heading">{fmtPct(a.confidence)}</span>
                </div>
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">Fault Type</span>
                  <span className="text-xs sm:text-sm font-bold font-heading text-rose-600">{a.fault_type || 'NONE'}</span>
                </div>
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">Station Health</span>
                  <span className="text-xs sm:text-sm font-bold text-slate-800 font-heading">{a.sensor_health?.toFixed(1)} / 100</span>
                </div>
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">Temperature</span>
                  <span className="text-xs sm:text-sm font-bold text-slate-800 font-heading">{fmt(a.temperature_c)} °C</span>
                </div>
              </div>

              {/* Diagnosis Box */}
              {isFault && (
                <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200/80 flex items-start gap-3">
                  <Zap size={16} className="text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-bold text-rose-900">
                      Hardware Fault: {a.fault_type}
                    </div>
                    <p className="text-xs text-rose-700 mt-0.5 leading-relaxed font-medium">
                      Sensor reading deviated from regional neighbor consensus and station baselines.
                    </p>
                  </div>
                </div>
              )}

              {a.prediction === 'GENUINE_EXTREME' && (
                <div className="p-3.5 rounded-xl bg-purple-50 border border-purple-200/80 flex items-start gap-3">
                  <CloudLightning size={16} className="text-purple-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-bold text-purple-900">
                      Genuine Weather Event Signature
                    </div>
                    <p className="text-xs text-purple-700 mt-0.5 leading-relaxed font-medium">
                      Spatial neighbor residuals and front dynamics confirm a synchronized natural weather extreme.
                    </p>
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={() => setExpanded(isExpanded ? null : a.station_id)}
                  className="flex items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
                >
                  <span>{isExpanded ? 'Hide Deep Audit' : 'Expand AI Audit'}</span>
                  {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>

                <button
                  onClick={() => navigate(`/stations/${a.station_id}`)}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-xs font-bold text-sky-600 shadow-xs transition-all"
                >
                  <span>Station History</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </div>

            {/* Expandable Deep Audit Panel */}
            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="border-t border-slate-200/80 p-5 sm:p-6 bg-slate-50/70 space-y-5"
                >
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    <div>
                      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                        Evidence & Top AI Drivers
                      </div>
                      <EvidenceCard reasons={a.top_reasons} />
                    </div>

                    <div>
                      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                        Observed vs Regression Ensembles
                      </div>
                      <ExpectedObservedCard
                        observed={a.observed_values}
                        expected={a.expected_values}
                      />
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )
      })}
    </div>
  )
}
