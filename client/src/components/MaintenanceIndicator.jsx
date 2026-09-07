import { Wrench } from 'lucide-react'

const RECOMMENDATIONS = {
  HEALTHY:          { label: 'Routine Nominal Monitoring', color: '#10B981', bg: '#ECFDF5', border: '#A7F3D0', action: 'No hardware intervention required. Normal operating conditions.' },
  NEEDS_ATTENTION:  { label: 'Inspect During Next Cycle', color: '#F59E0B', bg: '#FEF3C7', border: '#FDE68A', action: 'Schedule sensor recalibration and cleaning during the next routine site visit.' },
  DEGRADED:         { label: 'Priority Sensor Inspection', color: '#F43F5E', bg: '#FFE4E6', border: '#FECDD3', action: 'Schedule inspection within 48 hours to prevent telemetry loss or drift skew.' },
  CRITICAL:         { label: 'Immediate Field Dispatch', color: '#DC2626', bg: '#FEE2E2', border: '#FCA5A5', action: 'Immediate hardware replacement or sensor transducer check required.' },
  UNKNOWN:          { label: 'Status Indeterminate', color: '#64748B', bg: '#F8FAFC', border: '#E2E8F0', action: 'Verify telemetry data link and battery voltage levels.' },
}

export function MaintenanceIndicator({ status, score }) {
  const cfg = RECOMMENDATIONS[status] || RECOMMENDATIONS.UNKNOWN

  return (
    <div
      className="glass-card rounded-3xl p-6 border shadow-xs space-y-3"
      style={{ borderColor: cfg.border }}
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
          Hardware Maintenance Recommendation
        </div>
        <div
          className="px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5"
          style={{ background: cfg.bg, color: cfg.color }}
        >
          <Wrench size={13} />
          <span>{cfg.label}</span>
        </div>
      </div>

      <p className="text-xs sm:text-sm font-semibold text-slate-700 leading-relaxed">
        {cfg.action}
      </p>

      <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
        <span>Station Reliability: <strong className="text-slate-900">{score?.toFixed(1)} / 100</strong></span>
        <span>Diagnostic Status: <strong className="text-slate-900">{status}</strong></span>
      </div>
    </div>
  )
}
