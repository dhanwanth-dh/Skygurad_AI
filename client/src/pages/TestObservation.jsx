import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { usePredict } from '../hooks/useApi'
import { PredictionCard } from '../components/PredictionCard'
import { ExpectedObservedCard } from '../components/ExpectedObservedCard'
import { EvidenceCard } from '../components/EvidenceCard'
import { FlaskConical, Sparkles, Send, CheckCircle2 } from 'lucide-react'

const DEMO_SCENARIOS = [
  {
    label: 'Normal Observation (Chennai)',
    color: '#10B981',
    data: {
      station_id: 'AWS_TN_01', station_name: 'Chennai Coastal AWS',
      latitude: 13.0827, longitude: 80.2707,
      temperature_c: 32.5, relative_humidity_pct: 65.0,
      pressure_hpa: 1009.5, wind_speed_kmh: 14.2, rainfall_mm: 0.0,
    },
  },
  {
    label: 'Sensor Spike (Delhi)',
    color: '#F43F5E',
    data: {
      station_id: 'AWS_DL_01', station_name: 'Delhi Urban AWS',
      latitude: 28.6139, longitude: 77.2090,
      temperature_c: 68.5, relative_humidity_pct: 25.0,
      pressure_hpa: 995.0, wind_speed_kmh: 8.0, rainfall_mm: 0.0,
    },
  },
  {
    label: 'Sensor Freeze (Mumbai)',
    color: '#0284C7',
    data: {
      station_id: 'AWS_MH_01', station_name: 'Mumbai Coastal AWS',
      latitude: 19.0760, longitude: 72.8777,
      temperature_c: 31.5, relative_humidity_pct: 78.0,
      pressure_hpa: 1010.2, wind_speed_kmh: 5.0, rainfall_mm: 0.0,
    },
  },
  {
    label: 'Sensor Drift (Bengaluru)',
    color: '#F59E0B',
    data: {
      station_id: 'AWS_KA_01', station_name: 'Bengaluru Urban AWS',
      latitude: 12.9716, longitude: 77.5946,
      temperature_c: 37.5, relative_humidity_pct: 45.0,
      pressure_hpa: 915.0, wind_speed_kmh: 12.0, rainfall_mm: 0.0,
    },
  },
  {
    label: 'Genuine Weather Event (Vizag)',
    color: '#8B5CF6',
    data: {
      station_id: 'AWS_AP_01', station_name: 'Visakhapatnam Coastal AWS',
      latitude: 17.6868, longitude: 83.2185,
      temperature_c: 24.5, relative_humidity_pct: 94.0,
      pressure_hpa: 988.0, wind_speed_kmh: 85.0, rainfall_mm: 65.0,
    },
  },
]

const FIELDS = [
  { key: 'station_id', label: 'Station ID', type: 'text', placeholder: 'AWS_TN_01' },
  { key: 'station_name', label: 'Station Name', type: 'text', placeholder: 'Chennai Coastal AWS', optional: true },
  { key: 'latitude', label: 'Latitude (°N)', type: 'number', placeholder: '13.0827', step: '0.0001' },
  { key: 'longitude', label: 'Longitude (°E)', type: 'number', placeholder: '80.2707', step: '0.0001' },
  { key: 'temperature_c', label: 'Temperature (°C)', type: 'number', placeholder: '32.5', step: '0.01', min: -25, max: 70 },
  { key: 'relative_humidity_pct', label: 'Relative Humidity (%)', type: 'number', placeholder: '65.0', step: '0.1', min: 0, max: 100 },
  { key: 'pressure_hpa', label: 'Pressure (hPa)', type: 'number', placeholder: '1009.5', step: '0.1', min: 680, max: 1084 },
  { key: 'wind_speed_kmh', label: 'Wind Speed (km/h)', type: 'number', placeholder: '14.2', step: '0.1', min: 0, max: 200 },
  { key: 'rainfall_mm', label: 'Rainfall (mm)', type: 'number', placeholder: '0.0', step: '0.1', min: 0, max: 500 },
]

const DEFAULT_FORM = {
  station_id: 'AWS_TN_01', station_name: 'Chennai Coastal AWS',
  latitude: '13.0827', longitude: '80.2707',
  temperature_c: '32.5', relative_humidity_pct: '65.0',
  pressure_hpa: '1009.5', wind_speed_kmh: '14.2', rainfall_mm: '0.0',
}

export default function TestObservation() {
  const [form, setForm] = useState(DEFAULT_FORM)
  const [validationErrors, setValidationErrors] = useState({})
  const [showTrace, setShowTrace] = useState(false)
  const { result, loading, error, steps, predict } = usePredict()

  function validate() {
    const errs = {}
    if (!form.station_id.trim()) errs.station_id = 'Required'
    const numFields = ['latitude', 'longitude', 'temperature_c', 'relative_humidity_pct',
      'pressure_hpa', 'wind_speed_kmh', 'rainfall_mm']
    numFields.forEach(k => {
      if (form[k] === '' || isNaN(Number(form[k]))) errs[k] = 'Valid number required'
    })
    return errs
  }

  function handleSubmit(e) {
    e.preventDefault()
    const errs = validate()
    setValidationErrors(errs)
    if (Object.keys(errs).length > 0) return

    predict({
      timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
      station_id: form.station_id,
      station_name: form.station_name || undefined,
      latitude: Number(form.latitude),
      longitude: Number(form.longitude),
      temperature_c: Number(form.temperature_c),
      relative_humidity_pct: Number(form.relative_humidity_pct),
      pressure_hpa: Number(form.pressure_hpa),
      wind_speed_kmh: Number(form.wind_speed_kmh),
      rainfall_mm: Number(form.rainfall_mm),
    })
  }

  function loadScenario(scenario) {
    const d = scenario.data
    setForm({
      station_id: d.station_id,
      station_name: d.station_name || '',
      latitude: String(d.latitude),
      longitude: String(d.longitude),
      temperature_c: String(d.temperature_c),
      relative_humidity_pct: String(d.relative_humidity_pct),
      pressure_hpa: String(d.pressure_hpa),
      wind_speed_kmh: String(d.wind_speed_kmh),
      rainfall_mm: String(d.rainfall_mm),
    })
    setValidationErrors({})
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-6xl mx-auto pb-12"
    >
      {/* Top Title Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-6 sm:p-8 rounded-3xl glass-panel">
        <div>
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/60 backdrop-blur-md border border-sky-300/80 text-xs font-bold text-sky-800 mb-2 shadow-xs">
            <FlaskConical size={13} />
            Diagnostic Workbench
          </div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 font-heading">
            Test AWS Observation Telemetry
          </h1>
          <p className="text-sm text-slate-600 font-medium mt-1">
            Simulate synthetic weather anomalies, sensor drift, freeze faults, or genuine fronts across the AI multi-model engine.
          </p>
        </div>

        {result && (
          <button
            onClick={() => setShowTrace(!showTrace)}
            className="flex items-center gap-2 px-4 py-2 rounded-2xl bg-gradient-to-r from-sky-500 to-indigo-600 text-white font-bold text-xs shadow-md hover:shadow-lg transition-all active:scale-95"
          >
            <Sparkles size={14} />
            <span>{showTrace ? 'Hide AI Trace' : 'View AI Decision Trace'}</span>
          </button>
        )}
      </div>

      {/* Preset Injection Scenarios */}
      <div className="glass-panel p-5 rounded-3xl space-y-3">
        <div className="text-[11px] font-bold tracking-wider text-slate-500 uppercase">
          Quick Preset Injection
        </div>
        <div className="flex flex-wrap gap-2">
          {DEMO_SCENARIOS.map(s => (
            <button
              key={s.label}
              onClick={() => loadScenario(s)}
              className="px-4 py-2 rounded-2xl border text-xs font-bold transition-all hover:scale-105 active:scale-95 shadow-xs backdrop-blur-md"
              style={{
                borderColor: `${s.color}60`,
                color: s.color,
                background: 'rgba(255, 255, 255, 0.65)',
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* AI Decision Trace Modal */}
      <AnimatePresence>
        {showTrace && result && result.trace && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass-panel rounded-3xl p-6 sm:p-8 space-y-5 overflow-hidden border border-sky-300/80 shadow-lg"
          >
            <div className="flex items-center justify-between border-b border-white/50 pb-3">
              <div className="text-sm font-bold text-slate-900 font-heading flex items-center gap-2">
                <Sparkles size={16} className="text-sky-600" />
                8-Stage AI Multi-Model Audit Trail
              </div>
              <span className="text-xs font-medium text-slate-500">Step-by-step pipeline execution</span>
            </div>

            <div className="space-y-3 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-slate-300">
              {result.trace.map((step, idx) => (
                <div key={idx} className="relative flex items-start gap-4 pl-8">
                  <div className="absolute left-2 top-2 w-3.5 h-3.5 rounded-full border-2 border-sky-500 bg-white" />
                  <div className="rounded-2xl p-4 border border-white/60 bg-white/75 backdrop-blur-md shadow-xs w-full text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-extrabold text-slate-900 tracking-wide font-heading">
                        {step.stage}
                      </span>
                      <span
                        className="px-2.5 py-0.5 rounded-full text-[10px] font-bold"
                        style={{
                          background: step.status === 'PASSED' || step.status === 'NORMAL' ? '#ECFDF5' : '#FFE4E6',
                          color: step.status === 'PASSED' || step.status === 'NORMAL' ? '#059669' : '#E11D48',
                        }}
                      >
                        {step.status}
                      </span>
                    </div>
                    <p className="text-slate-700 font-medium">{step.summary}</p>
                    {step.evidence && step.evidence.length > 0 && (
                      <ul className="list-disc list-inside text-slate-600 space-y-0.5 pt-1">
                        {step.evidence.map((ev, ei) => <li key={ei}>{ev}</li>)}
                      </ul>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Form Container */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="glass-panel p-6 sm:p-7 rounded-3xl space-y-4">
            <div className="text-xs font-bold tracking-wider text-slate-500 uppercase mb-2">
              Telemetry Parameters
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {FIELDS.map(({ key, label, type, placeholder, step, min, max, optional }) => (
                <div key={key} className={key === 'station_name' || key === 'station_id' ? 'sm:col-span-1' : ''}>
                  <label className="block text-xs font-bold text-slate-800 mb-1">
                    {label} {optional && <span className="text-slate-500 font-normal">(opt)</span>}
                  </label>
                  <input
                    type={type}
                    value={form[key]}
                    onChange={e => {
                      setForm(f => ({ ...f, [key]: e.target.value }))
                      setValidationErrors(v => ({ ...v, [key]: undefined }))
                    }}
                    placeholder={placeholder}
                    step={step}
                    min={min}
                    max={max}
                    className="glass-input w-full px-3.5 py-2.5 rounded-2xl text-sm font-semibold text-slate-900 placeholder-slate-400 outline-none focus:ring-2 focus:ring-sky-300 transition-all shadow-xs"
                    style={{
                      borderColor: validationErrors[key] ? '#F43F5E' : 'rgba(255, 255, 255, 0.7)',
                    }}
                  />
                  {validationErrors[key] && (
                    <div className="text-[11px] font-semibold text-rose-600 mt-1">
                      {validationErrors[key]}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-4 py-3.5 rounded-2xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 text-white font-extrabold text-sm tracking-wide shadow-md hover:shadow-lg transition-all active:scale-[0.99] disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Send size={16} />
              <span>{loading ? 'Executing Multi-Model Fusion...' : 'Run Multi-Model Diagnostic'}</span>
            </button>
          </div>
        </form>

        {/* Results Stream */}
        <div className="space-y-5">
          {/* Loading steps progress */}
          <AnimatePresence>
            {loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="glass-panel p-6 rounded-3xl space-y-2.5"
              >
                <div className="text-xs font-bold text-sky-700 uppercase tracking-wider mb-2">
                  Multi-Model Engine Processing
                </div>
                {steps.map((s, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="text-xs font-semibold text-slate-800 flex items-center gap-2"
                  >
                    <CheckCircle2 size={14} className="text-sky-500" />
                    <span>{s}</span>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {error && (
            <div className="rounded-3xl p-6 bg-rose-50/90 border border-rose-300 text-rose-900 text-xs font-semibold backdrop-blur-md">
              {error}
            </div>
          )}

          {result && !loading && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-5"
            >
              <PredictionCard result={result} />

              <div className="space-y-2">
                <div className="text-xs font-bold tracking-wider text-slate-500 uppercase">
                  Regression Ensemble Forecasts & Deviations
                </div>
                <ExpectedObservedCard
                  observed={result.observed_values}
                  expected={result.expected_values}
                />
              </div>

              {result.top_reasons?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-bold tracking-wider text-slate-500 uppercase">
                    Decision Evidence & Root Cause
                  </div>
                  <EvidenceCard reasons={result.top_reasons} />
                </div>
              )}
            </motion.div>
          )}

          {!result && !loading && !error && (
            <div className="glass-panel p-12 text-center rounded-3xl flex flex-col items-center justify-center gap-3">
              <FlaskConical size={36} className="text-slate-400" />
              <div className="text-sm font-bold text-slate-800 font-heading">
                Ready for Telemetry Simulation
              </div>
              <p className="text-xs text-slate-500 max-w-sm font-medium">
                Select a preset scenario above or enter custom sensor readings to evaluate the 14-model pipeline.
              </p>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}
