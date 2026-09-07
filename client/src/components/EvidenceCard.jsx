import { AlertCircle, CheckCircle, Info } from 'lucide-react'

export function EvidenceCard({ reasons }) {
  if (!reasons || reasons.length === 0) {
    return (
      <div className="rounded-2xl p-5 border border-slate-200/80 bg-white/70 flex items-center gap-3">
        <Info size={16} className="text-slate-400 shrink-0" />
        <p className="text-xs font-medium text-slate-500">
          All sensor observations are in statistical equilibrium with historical baselines.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      {reasons.map((reason, i) => (
        <div
          key={i}
          className="rounded-xl p-3.5 border border-slate-200/80 bg-white/85 shadow-xs flex items-start gap-3 transition-all hover:border-slate-300"
        >
          <AlertCircle size={16} className="text-amber-500 shrink-0 mt-0.5" />
          <p className="text-xs font-semibold text-slate-700 leading-relaxed">{reason}</p>
        </div>
      ))}
    </div>
  )
}
