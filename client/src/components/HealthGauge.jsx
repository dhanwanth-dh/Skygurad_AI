import { motion } from 'framer-motion'
import { healthColor } from '../utils/format'

export function HealthGauge({ score, size = 96 }) {
  const r = (size / 2) - 8
  const circ = 2 * Math.PI * r
  const pct = Math.min(Math.max(score || 0, 0), 100)
  const dash = (pct / 100) * circ
  const color = healthColor(pct)

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={size >= 90 ? 7 : 5}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={size >= 90 ? 7 : 5}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - dash }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <div className="absolute text-center flex flex-col items-center justify-center">
        <div className="text-base sm:text-lg font-black tracking-tight text-slate-900 font-heading leading-none">
          {pct.toFixed(0)}
        </div>
        <div className="text-[10px] font-bold text-slate-400 mt-0.5">/ 100</div>
      </div>
    </div>
  )
}
