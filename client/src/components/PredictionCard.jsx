import { motion } from 'framer-motion'
import { StatusBadge, SeverityBadge } from './StatusBadge'
import { AnomalyScoreMeter } from './AnomalyScoreMeter'
import { HealthGauge } from './HealthGauge'
import { fmt, fmtPct } from '../utils/format'
import { Sparkles, AlertTriangle, ShieldCheck, Zap } from 'lucide-react'

export function PredictionCard({ result }) {
  const consensus = result.anomaly_consensus || { models_agreeing: 0, models_total: 6, score: 0.0, detector_scores: {} }
  const agreementPct = Math.round((result.model_agreement ?? 1.0) * 100)
  const uncertaintyPct = Math.round((result.uncertainty_score ?? 0.0) * 100)
  const coverage = result.model_coverage || '6/6 active'

  const isFault = result.prediction === 'SENSOR_FAULT'
  const isExtreme = result.prediction === 'GENUINE_EXTREME'
  const isNormal = result.prediction === 'NORMAL'

  const detectors = [
    { key: 'isolation_forest', label: 'Isolation Forest' },
    { key: 'lof', label: 'Local Outlier Factor' },
    { key: 'one_class_svm', label: 'One-Class SVM' },
    { key: 'elliptic_envelope', label: 'Elliptic Envelope' },
    { key: 'mahalanobis', label: 'Mahalanobis Distance' },
    { key: 'robust_zscore', label: 'Robust Z-Score' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="glass-card rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm border border-slate-200/90"
    >
      {/* Header Banner */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-bold tracking-widest text-slate-400 uppercase mb-1">
            Station Telemetry Assessment
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-heading">
            {result.station_id}
          </div>
          <div className="mt-3 flex flex-wrap gap-2 items-center">
            <StatusBadge status={result.prediction} />
            <SeverityBadge severity={result.severity} />
            <span className="px-3 py-0.5 rounded-full text-xs font-bold bg-sky-50 text-sky-700 border border-sky-200">
              {result.confidence_level || 'MEDIUM'} Confidence
            </span>
            <span className="px-3 py-0.5 rounded-full text-xs font-mono bg-slate-100 text-slate-600 border border-slate-200">
              Coverage: {coverage}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-center">
          <HealthGauge score={result.sensor_health} size={88} />
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1.5">Sensor Health</span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <AnomalyScoreMeter score={result.anomaly_score} />

        {/* Confidence & Uncertainty */}
        <div className="rounded-2xl p-5 border border-slate-200/80 bg-white/80 shadow-xs flex flex-col justify-between">
          <div>
            <div className="text-xs font-bold tracking-wider text-slate-500 uppercase mb-1">
              Decision Confidence
            </div>
            <div className="text-3xl font-extrabold font-heading text-sky-600">
              {fmtPct(result.confidence)}
            </div>
            <div className="text-xs text-slate-400 font-medium mt-0.5">
              Bayesian multi-model evidence
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100">
            <div className="flex justify-between text-xs font-bold text-slate-600 mb-1.5">
              <span>Uncertainty Level</span>
              <span className="font-mono">{uncertaintyPct}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/60">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${uncertaintyPct}%`,
                  background: uncertaintyPct > 40 ? '#F59E0B' : '#10B981',
                }}
              />
            </div>
          </div>
        </div>

        {/* Model Agreement */}
        <div className="rounded-2xl p-5 border border-slate-200/80 bg-white/80 shadow-xs flex flex-col justify-between">
          <div>
            <div className="text-xs font-bold tracking-wider text-slate-500 uppercase mb-1">
              Model Agreement
            </div>
            <div className="text-3xl font-extrabold font-heading text-slate-900">
              {agreementPct}%
            </div>
            <div className="text-xs font-bold mt-1 text-emerald-600 flex items-center gap-1">
              <ShieldCheck size={14} />
              {agreementPct >= 70 ? 'High Ensemble Consistency' : 'Moderate Agreement'}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex justify-between items-center text-xs">
            <span className="text-slate-500 font-medium">Diagnosed Fault</span>
            <span className="font-extrabold text-slate-900">
              {result.fault_type === 'NONE' ? 'None' : result.fault_type}
            </span>
          </div>
        </div>
      </div>

      {/* 6 AI Detectors Consensus Grid */}
      <div className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-bold tracking-wider text-slate-700 uppercase">
            6-Detector Anomaly Consensus ({consensus.models_agreeing} / {consensus.models_total} Flagging)
          </div>
          <span
            className="text-[11px] font-bold px-2.5 py-0.5 rounded-full border"
            style={{
              background: consensus.models_agreeing >= 3 ? '#FFE4E6' : '#ECFDF5',
              borderColor: consensus.models_agreeing >= 3 ? '#FECDD3' : '#A7F3D0',
              color: consensus.models_agreeing >= 3 ? '#E11D48' : '#059669',
            }}
          >
            {consensus.models_agreeing >= 3 ? 'High Outlier Evidence' : 'Within Normal Climatology'}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
          {detectors.map(d => {
            const rawScore = consensus.detector_scores?.[d.key] ?? 0.0
            const isAnom = rawScore >= 0.50
            return (
              <div
                key={d.key}
                className="rounded-xl p-3 border bg-white/90 shadow-xs flex items-center justify-between transition-all"
                style={{ borderColor: isAnom ? '#FECDD3' : '#E2E8F0' }}
              >
                <div className="truncate pr-2">
                  <div className="text-xs font-bold text-slate-800 truncate">{d.label}</div>
                  <div className="text-[10px] font-mono text-slate-400">Score: {rawScore.toFixed(2)}</div>
                </div>
                <span
                  className="text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0"
                  style={{
                    background: isAnom ? '#FFE4E6' : '#ECFDF5',
                    color: isAnom ? '#E11D48' : '#059669',
                  }}
                >
                  {isAnom ? 'ANOMALY' : 'NORMAL'}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Genuine Weather Event Callout */}
      {isExtreme && (
        <div className="rounded-2xl p-5 border border-purple-200 bg-purple-50/70 space-y-2">
          <div className="text-sm font-bold text-purple-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-600" />
            GENUINE EXTREME METEOROLOGICAL EVENT
          </div>
          <p className="text-xs text-purple-700 leading-relaxed font-medium">
            Multi-station spatial consensus and atmospheric front dynamics confirm this observation is a real storm or front, not a hardware fault.
          </p>
          {result.genuine_event_evidence?.length > 0 && (
            <ul className="text-xs space-y-1 list-disc list-inside text-purple-800 font-semibold pt-1">
              {result.genuine_event_evidence.map((ev, i) => <li key={i}>{ev}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Sensor Fault Callout */}
      {isFault && (
        <div className="rounded-2xl p-5 border border-rose-200 bg-rose-50/70 space-y-2">
          <div className="text-sm font-bold text-rose-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            SENSOR FAULT DIAGNOSED — {result.fault_type} ({fmtPct(result.fault_confidence || result.confidence)})
          </div>
          <p className="text-xs text-rose-700 leading-relaxed font-medium">
            {result.fault_type === 'DRIFT' && 'Persistent directional drift detected. Sensor calibration offset has deviated from historical baseline.'}
            {result.fault_type === 'FREEZE' && 'Sensor output frozen with zero variance. Transducer is stuck or mechanically blocked.'}
            {result.fault_type === 'SPIKE' && 'Single-point transient spike detected. Telemetry isolated excursion with immediate recovery.'}
            {result.fault_type === 'COMMUNICATION_FAILURE' && 'Temporal telemetry gap detected. Modem or battery voltage drop.'}
            {result.fault_type === 'NONE' && 'Sensor anomaly detected. Physical audit recommended.'}
          </p>
          {result.fault_evidence?.length > 0 && (
            <ul className="text-xs space-y-1 list-disc list-inside text-rose-800 font-semibold pt-1">
              {result.fault_evidence.map((ev, i) => <li key={i}>{ev}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Recommended Action */}
      {result.recommended_action && (
        <div className="rounded-2xl p-4 border border-sky-200 bg-sky-50/80 flex items-center gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-sky-500 text-white flex items-center justify-center shrink-0 shadow-xs">
            <Zap size={18} />
          </div>
          <div>
            <div className="text-[10px] font-bold text-sky-600 uppercase tracking-widest">Recommended Corrective Action</div>
            <div className="text-xs sm:text-sm font-bold text-slate-900 mt-0.5">{result.recommended_action}</div>
          </div>
        </div>
      )}
    </motion.div>
  )
}
