import { motion } from 'framer-motion'

const LEVELS = [
  { label: 'LOW', min: 0, max: 0.4, color: '#10B981', bg: '#ECFDF5' },
  { label: 'MEDIUM', min: 0.4, max: 0.65, color: '#F59E0B', bg: '#FEF3C7' },
  { label: 'HIGH', min: 0.65, max: 0.85, color: '#F43F5E', bg: '#FFE4E6' },
  { label: 'CRITICAL', min: 0.85, max: 1.0, color: '#DC2626', bg: '#FEE2E2' },
]

function getLevel(score) {
  for (const l of LEVELS) if (score <= l.max) return l
  return LEVELS[LEVELS.length - 1]
}

export function AnomalyScoreMeter({ score }) {
  const s = Math.min(Math.max(score || 0, 0), 1)
  const pct = s * 100
  const lvl = getLevel(s)

  return (
    <div className="rounded-2xl p-5 border border-slate-200/80 bg-white/80 shadow-xs flex flex-col justify-between">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold tracking-wider text-slate-500 uppercase">
          Anomaly Score
        </span>
        <span
          className="text-xs font-bold px-2.5 py-0.5 rounded-full border"
          style={{ background: lvl.bg, borderColor: `${lvl.color}40`, color: lvl.color }}
        >
          {lvl.label}
        </span>
      </div>

      <div className="my-2">
        <div className="text-3xl sm:text-4xl font-extrabold font-heading text-slate-900 tracking-tight">
          {s.toFixed(3)}
        </div>
      </div>

      {/* Modern segmented progress bar */}
      <div className="space-y-1.5 mt-2">
        <div className="relative h-2.5 rounded-full overflow-hidden bg-slate-100 border border-slate-200/60 p-0.5">
          <motion.div
            className="h-full rounded-full"
            style={{ background: `linear-gradient(90deg, #10B981, #F59E0B 50%, #F43F5E)` }}
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 1.0, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>

        <div className="flex justify-between text-[10px] font-bold text-slate-400">
          <span>0.0 Normal</span>
          <span>0.50 Threshold</span>
          <span>1.0 Severe</span>
        </div>
      </div>
    </div>
  )
}
