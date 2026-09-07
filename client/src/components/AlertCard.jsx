import { motion } from 'framer-motion'
import { SeverityBadge, StatusBadge } from './StatusBadge'
import { formatTimestamp } from '../utils/format'
import { AlertCircle, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export function AlertCard({ alert, index = 0 }) {
  const navigate = useNavigate()
  const isFault = alert.prediction === 'SENSOR_FAULT'

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
      whileHover={{ x: 4, transition: { duration: 0.2 } }}
      onClick={() => navigate(`/stations/${alert.station_id}`)}
      className="glass-card glass-card-interactive p-5 rounded-2xl flex flex-wrap items-center justify-between gap-4 border-l-4 group"
      style={{ borderLeftColor: isFault ? '#F43F5E' : '#8B5CF6' }}
    >
      <div className="flex items-start gap-3.5">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-xs"
          style={{
            background: isFault ? '#FFE4E6' : '#F3E8FF',
            color: isFault ? '#E11D48' : '#7C3AED',
          }}
        >
          <AlertCircle size={20} />
        </div>

        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-extrabold text-slate-900 font-heading text-sm sm:text-base group-hover:text-sky-600 transition-colors">
              {alert.station_id}
            </span>
            <StatusBadge status={alert.prediction} />
            <SeverityBadge severity={alert.severity} />
          </div>

          <p className="text-xs text-slate-600 font-medium">
            {alert.prediction === 'SENSOR_FAULT'
              ? `${alert.fault_type !== 'NONE' ? alert.fault_type + ' signature diagnosed.' : 'Hardware anomaly detected.'} Recalibration or physical inspection advised.`
              : alert.prediction === 'GENUINE_EXTREME'
              ? 'Multi-station synchronized meteorological front detected.'
              : 'Observation flagged by unsupervised anomaly ensemble.'}
          </p>

          <div className="text-[11px] font-medium text-slate-400">
            {formatTimestamp(alert.timestamp)} · Anomaly Score: <span className="font-bold text-slate-700">{alert.anomaly_score?.toFixed(3)}</span>
          </div>
        </div>
      </div>

      <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-50 hover:bg-sky-50 text-slate-600 hover:text-sky-700 text-xs font-bold transition-colors">
        <span>Inspect</span>
        <ArrowRight size={13} />
      </button>
    </motion.div>
  )
}
