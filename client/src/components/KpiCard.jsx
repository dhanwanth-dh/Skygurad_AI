import { motion } from 'framer-motion'

export function KpiCard({ label, value, sub, color = '#0284C7', icon: Icon, trend }) {
  return (
    <motion.div
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="glass-card glass-card-interactive p-6 rounded-3xl relative flex flex-col justify-between"
    >
      {/* Top row */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-bold tracking-wider text-slate-500 uppercase">
          {label}
        </span>
        {Icon && (
          <div
            className="w-10 h-10 rounded-2xl flex items-center justify-center shadow-xs backdrop-blur-md border border-white/60"
            style={{ background: `${color}18`, color: color }}
          >
            <Icon size={18} />
          </div>
        )}
      </div>

      {/* Main KPI value */}
      <div className="text-3xl sm:text-4xl font-black tracking-tight font-heading mb-1 text-slate-900">
        {value ?? '—'}
      </div>

      {/* Subtitle / trend */}
      <div className="flex items-center gap-2 mt-1">
        {trend && (
          <span
            className="text-[11px] font-bold px-2.5 py-0.5 rounded-full border border-emerald-200/80 backdrop-blur-xs"
            style={{
              background: trend > 0 ? 'rgba(236, 253, 245, 0.85)' : 'rgba(254, 242, 242, 0.85)',
              color: trend > 0 ? '#059669' : '#DC2626',
            }}
          >
            {trend > 0 ? `+${trend}%` : `${trend}%`}
          </span>
        )}
        {sub && <span className="text-xs font-semibold text-slate-500">{sub}</span>}
      </div>

      {/* Subtle bottom gradient accent bar */}
      <div
        className="absolute bottom-0 left-0 right-0 h-1 rounded-b-3xl opacity-80"
        style={{ background: `linear-gradient(90deg, ${color}, ${color}22)` }}
      />
    </motion.div>
  )
}
