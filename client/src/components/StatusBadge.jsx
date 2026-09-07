export function StatusBadge({ status }) {
  const map = {
    NORMAL: { bg: '#ECFDF5', border: '#A7F3D0', text: '#059669', label: 'NORMAL' },
    SENSOR_FAULT: { bg: '#FFF1F2', border: '#FECDD3', text: '#E11D48', label: 'SENSOR FAULT' },
    GENUINE_EXTREME: { bg: '#F5F3FF', border: '#DDD6FE', text: '#7C3AED', label: 'GENUINE EXTREME' },
    HEALTHY: { bg: '#ECFDF5', border: '#A7F3D0', text: '#059669', label: 'HEALTHY' },
    'NEEDS ATTENTION': { bg: '#FFFBEB', border: '#FDE68A', text: '#D97706', label: 'NEEDS ATTENTION' },
    DEGRADED: { bg: '#FFF1F2', border: '#FECDD3', text: '#E11D48', label: 'DEGRADED' },
    CRITICAL: { bg: '#FEF2F2', border: '#FCA5A5', text: '#DC2626', label: 'CRITICAL' },
    UNKNOWN: { bg: '#F8FAFC', border: '#E2E8F0', text: '#64748B', label: 'UNKNOWN' },
    ok: { bg: '#ECFDF5', border: '#A7F3D0', text: '#059669', label: 'OPERATIONAL' },
  }
  const cfg = map[status] || { bg: '#F8FAFC', border: '#E2E8F0', text: '#64748B', label: status || 'UNKNOWN' }
  
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wider border shadow-xs"
      style={{ background: cfg.bg, borderColor: cfg.border, color: cfg.text }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.text }} />
      <span>{cfg.label}</span>
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const map = {
    LOW: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
    HIGH: 'bg-rose-50 text-rose-700 border-rose-200',
    CRITICAL: 'bg-red-100 text-red-800 border-red-300 font-extrabold',
  }
  const cls = map[severity] || 'bg-slate-100 text-slate-600 border-slate-200'
  
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full border text-[11px] font-bold tracking-wider shadow-xs ${cls}`}>
      {severity || 'UNKNOWN'}
    </span>
  )
}
