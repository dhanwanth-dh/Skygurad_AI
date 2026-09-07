import { fmt, fmtDeviation, deviation } from '../utils/format'
import { ArrowDownRight, ArrowUpRight, CheckCircle2 } from 'lucide-react'

const SENSORS = [
  { key: 'temperature_c', label: 'Temperature', unit: '°C' },
  { key: 'relative_humidity_pct', label: 'Relative Humidity', unit: '%' },
  { key: 'pressure_hpa', label: 'Barometric Pressure', unit: ' hPa' },
]

function DeviationBadge({ val, unit }) {
  if (val == null) return <span className="text-slate-400 font-medium">—</span>
  const abs = Math.abs(val)
  const isHealthy = abs < 1.0
  const isModerate = abs < 3.5

  const bg = isHealthy ? '#ECFDF5' : isModerate ? '#FEF3C7' : '#FFE4E6'
  const text = isHealthy ? '#059669' : isModerate ? '#D97706' : '#E11D48'
  const Icon = val > 0 ? ArrowUpRight : val < 0 ? ArrowDownRight : CheckCircle2

  return (
    <span
      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold border"
      style={{ background: bg, borderColor: `${text}30`, color: text }}
    >
      <Icon size={13} />
      <span>{fmtDeviation(val, unit)}</span>
    </span>
  )
}

export function ExpectedObservedCard({ observed, expected }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {SENSORS.map(({ key, label, unit }) => {
        const obs = observed?.[key]
        const exp = expected?.[key]
        const dev = deviation(obs, exp)

        return (
          <div
            key={key}
            className="rounded-2xl p-5 border border-slate-200/80 bg-white/80 shadow-xs flex flex-col justify-between"
          >
            <div className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-3">
              {label}
            </div>

            <div className="space-y-3">
              <div className="flex items-baseline justify-between">
                <span className="text-xs font-medium text-slate-500">Observed</span>
                <span className="text-xl font-extrabold text-slate-900 font-heading">
                  {fmt(obs)} <span className="text-xs font-normal text-slate-400">{unit}</span>
                </span>
              </div>

              <div className="flex items-baseline justify-between pt-2 border-t border-slate-100">
                <span className="text-xs font-medium text-slate-500">Ensemble Expected</span>
                <span className="text-sm font-bold text-slate-600 font-heading">
                  {exp != null ? fmt(exp) : '—'} <span className="text-xs font-normal text-slate-400">{unit}</span>
                </span>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                <span className="text-xs font-medium text-slate-500">Atmospheric Residual</span>
                <DeviationBadge val={dev} unit={unit} />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
