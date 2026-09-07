import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { HealthGauge } from './HealthGauge'
import { StatusBadge, SeverityBadge } from './StatusBadge'
import { fmt } from '../utils/format'
import { ArrowUpRight, MapPin, Radio } from 'lucide-react'

export function StationCard({ station, prediction, index = 0 }) {
  const navigate = useNavigate()
  const sid = station.station_id

  const pred = station.prediction ? station : prediction
  const health = pred?.sensor_health ?? 100
  const status = pred?.prediction ?? 'UNKNOWN'
  const severity = pred?.severity ?? null

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.03 }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      onClick={() => navigate(`/stations/${sid}`)}
      className="glass-card glass-card-interactive p-6 rounded-3xl flex flex-col justify-between group"
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base font-extrabold text-slate-900 font-heading tracking-tight group-hover:text-sky-600 transition-colors">
              {sid}
            </span>
            <ArrowUpRight size={16} className="text-slate-400 group-hover:text-sky-600 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
          </div>
          {station.station_name && (
            <div className="text-xs font-semibold text-slate-600 mb-1.5 flex items-center gap-1">
              <Radio size={12} className="text-sky-500" />
              {station.station_name}
            </div>
          )}
          {station.latitude != null && (
            <div className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
              <MapPin size={11} />
              {station.latitude.toFixed(4)}°N, {station.longitude.toFixed(4)}°E
            </div>
          )}
        </div>

        <div className="flex flex-col items-center">
          <HealthGauge score={health} size={68} />
          <span className="text-[10px] font-bold text-slate-500 mt-1 uppercase tracking-wider">Health</span>
        </div>
      </div>

      {/* Telemetry pill grid */}
      <div className="grid grid-cols-3 gap-2.5 p-3.5 rounded-2xl bg-white/45 backdrop-blur-md border border-white/60 mb-4 shadow-xs">
        {[
          { label: 'Temp', val: fmt(station.temperature_c), unit: '°C' },
          { label: 'Humidity', val: fmt(station.relative_humidity_pct), unit: '%' },
          { label: 'Pressure', val: fmt(station.pressure_hpa), unit: 'hPa' },
        ].map(({ label, val, unit }) => (
          <div key={label} className="text-center">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-0.5">{label}</div>
            <div className="text-xs sm:text-sm font-extrabold text-slate-900 font-heading">
              {val} <span className="text-[10px] font-normal text-slate-400">{unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Status footer */}
      <div className="flex items-center justify-between pt-3 border-t border-white/50">
        <StatusBadge status={status} />
        {severity && <SeverityBadge severity={severity} />}
      </div>
    </motion.div>
  )
}
