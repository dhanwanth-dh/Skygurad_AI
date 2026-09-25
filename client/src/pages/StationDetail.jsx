import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, MapPin, Radio, Activity } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceDot, Legend
} from 'recharts'
import { api } from '../services/api'
import { useStationHistory } from '../hooks/useApi'
import { PredictionCard } from '../components/PredictionCard'
import { ExpectedObservedCard } from '../components/ExpectedObservedCard'
import { EvidenceCard } from '../components/EvidenceCard'
import { HealthGauge } from '../components/HealthGauge'
import { StatusBadge, SeverityBadge } from '../components/StatusBadge'
import { MaintenanceIndicator } from '../components/MaintenanceIndicator'
import { LoadingSkeleton } from '../components/LoadingSkeleton'
import { ErrorState } from '../components/EmptyState'
import { fmt, formatTimestamp } from '../utils/format'

export default function StationDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [prediction, setPrediction] = useState(null)
  const [predLoading, setPredLoading] = useState(true)
  const [predError, setPredError] = useState(null)

  const [stationMeta, setStationMeta] = useState(null)
  useEffect(() => {
    api.getStations()
      .then(res => {
        const s = res.stations?.find(s => s.station_id === id)
        setStationMeta(s || null)
        if (s) {
          setPredLoading(true)
          api.predict({
            timestamp: s.latest_timestamp,
            station_id: s.station_id,
            station_name: s.station_name,
            latitude: s.latitude,
            longitude: s.longitude,
            temperature_c: s.temperature_c,
            relative_humidity_pct: s.relative_humidity_pct,
            pressure_hpa: s.pressure_hpa,
            wind_speed_kmh: s.wind_speed_kmh,
            rainfall_mm: s.rainfall_mm,
          })
            .then(setPrediction)
            .catch(e => setPredError(e.message))
            .finally(() => setPredLoading(false))
        } else {
          setPredLoading(false)
        }
      })
      .catch(e => { setPredError(e.message); setPredLoading(false) })
  }, [id])

  const { data: histData, loading: histLoading, error: histError } = useStationHistory(id)
  const station = stationMeta

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-6xl mx-auto pb-12"
    >
      {/* Back button & Station Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/stations')}
          className="p-2.5 rounded-2xl bg-white hover:bg-slate-100 border border-slate-200 text-slate-600 shadow-xs transition-colors"
          aria-label="Back to Stations"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 font-heading">{id}</h1>
            {station?.station_name && (
              <span className="text-sm font-semibold text-slate-500">({station.station_name})</span>
            )}
          </div>
          {station && (
            <p className="text-xs text-slate-400 font-medium flex items-center gap-1 mt-0.5">
              <MapPin size={12} />
              {station.latitude?.toFixed(4)}°N, {station.longitude?.toFixed(4)}°E
            </p>
          )}
        </div>
      </div>

      {/* Station Health & Status Grid */}
      {station && (
        <div className="glass-panel p-6 sm:p-8 rounded-3xl grid grid-cols-1 sm:grid-cols-2 gap-8">
          <div>
            <div className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-3">
              Station Reliability Score
            </div>
            <div className="flex items-center gap-5">
              <HealthGauge score={station.sensor_health} size={88} />
              <div>
                <div className="text-2xl font-black text-slate-900 font-heading">
                  {station.sensor_health?.toFixed(1)} / 100
                </div>
                <div className="mt-1">
                  <StatusBadge status={station.sensor_health_status} />
                </div>
                <div className="text-[11px] text-slate-500 font-medium mt-1">
                  Rolling 30-day sensor drift and failure rate index.
                </div>
              </div>
            </div>
          </div>

          <div>
            <div className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-3">
              Latest Observation Assessment
            </div>
            <div className="space-y-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={station.prediction} />
                <SeverityBadge severity={station.severity} />
              </div>
              <div className="text-xs font-semibold text-slate-600">
                Anomaly Score: <span className="font-bold text-sky-600">{station.anomaly_score?.toFixed(3)}</span>
              </div>
              <div className="text-[11px] text-slate-400 font-medium">
                Station health is an aggregated reliability index, whereas observation status evaluates current telemetry.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Telemetry Grid */}
      {station && (
        <div className="glass-card p-6 rounded-3xl space-y-3">
          <div className="text-xs font-bold tracking-wider text-slate-400 uppercase">
            Current Telemetry Snapshot · {formatTimestamp(station.latest_timestamp)}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              { label: 'Temperature', val: fmt(station.temperature_c), unit: '°C' },
              { label: 'Humidity', val: fmt(station.relative_humidity_pct), unit: '%' },
              { label: 'Barometer', val: fmt(station.pressure_hpa), unit: 'hPa' },
              { label: 'Wind Speed', val: fmt(station.wind_speed_kmh), unit: 'km/h' },
              { label: 'Rainfall', val: fmt(station.rainfall_mm), unit: 'mm' },
            ].map(({ label, val, unit }) => (
              <div key={label} className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-100 text-center">
                <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">{label}</div>
                <div className="text-base font-extrabold text-slate-900 font-heading">
                  {val} <span className="text-xs font-normal text-slate-400">{unit}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {predError && <ErrorState message={predError} />}

      {predLoading ? (
        <LoadingSkeleton rows={4} height="h-20" />
      ) : prediction ? (
        <>
          <PredictionCard result={prediction} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-2">
              <div className="text-xs font-bold tracking-wider text-slate-400 uppercase">
                Observed vs Expected Regression Ensembles
              </div>
              <ExpectedObservedCard
                observed={prediction.observed_values}
                expected={prediction.expected_values}
              />
            </div>
            <div className="space-y-2">
              <div className="text-xs font-bold tracking-wider text-slate-400 uppercase">
                Diagnostic Evidence & Drivers
              </div>
              <EvidenceCard reasons={prediction.top_reasons} />
            </div>
          </div>

          <MaintenanceIndicator
            status={prediction.sensor_health_status}
            score={prediction.sensor_health}
          />
        </>
      ) : null}

      {/* Historical Sensor Charts */}
      <section className="space-y-4">
        <HistoricalTelemetrySection stationId={id} stationMeta={station} />
      </section>
    </motion.div>
  )
}

function HistoricalTelemetrySection({ stationId, stationMeta }) {
  const [range, setRange] = useState('ALL')
  const [histData, setHistData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const RANGES = [
    { id: '24H', label: 'Last 24 Hours', days: 1 },
    { id: '7D', label: 'Last 7 Days', days: 7 },
    { id: '30D', label: 'Last 30 Days', days: 30 },
    { id: '3M', label: 'Last 3 Months', days: 90 },
    { id: '1Y', label: 'Last 1 Year', days: 365 },
    { id: '5Y', label: 'Last 5 Years', days: 365 * 5 },
    { id: '10Y', label: 'Last 10 Years', days: 365 * 10 },
    { id: 'ALL', label: 'All Available', days: null },
  ]

  useEffect(() => {
    setLoading(true)
    setError(null)

    const params = { max_points: 250 }
    if (range !== 'ALL') {
      const selected = RANGES.find(r => r.id === range)
      if (selected && selected.days) {
        const now = new Date()
        const startDt = new Date(now.getTime() - selected.days * 24 * 60 * 60 * 1000)
        params.start = startDt.toISOString().slice(0, 19).replace('T', ' ')
      }
    }

    api.getHistoricalStationData(stationId, params)
      .then(res => {
        setHistData(res)
        setLoading(false)
      })
      .catch(e => {
        // Fallback to legacy history endpoint if needed
        api.getStationHistory(stationId)
          .then(legacy => {
            setHistData({
              station_id: stationId,
              total_records: legacy.records?.length || 0,
              displayed_points: legacy.records?.length || 0,
              points: legacy.records || [],
              anomalies: legacy.records?.filter(r => r.ground_truth_label && r.ground_truth_label !== 'NORMAL') || [],
              latest_observation: legacy.records?.[legacy.records.length - 1] || null,
            })
            setLoading(false)
          })
          .catch(err => {
            setError(err.message)
            setLoading(false)
          })
      })
  }, [stationId, range])

  const points = histData?.points || []
  const latestObs = histData?.latest_observation || stationMeta

  const exportUrlXlsx = api.getHistoricalExportUrl({ station_id: stationId, format: 'xlsx' })
  const exportUrlCsv = api.getHistoricalExportUrl({ station_id: stationId, format: 'csv' })

  return (
    <div className="space-y-4">
      {/* Header & Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 glass-panel p-4 rounded-3xl">
        <div>
          <div className="text-xs font-bold tracking-wider text-slate-700 uppercase font-heading flex items-center gap-2">
            <span>Historical Telemetry & Anomaly Sequence</span>
            {latestObs && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200/80">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live: {latestObs.timestamp?.slice(0, 16)}
              </span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 font-medium mt-0.5">
            {histData ? `${histData.total_records.toLocaleString()} total historical observations recorded (${histData.displayed_points} points plotted)` : 'Loading historical telemetry timeline...'}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Time Range Pills */}
          <div className="flex items-center bg-slate-100/90 p-1 rounded-2xl border border-slate-200/80">
            {RANGES.map(r => (
              <button
                key={r.id}
                onClick={() => setRange(r.id)}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-xl transition-all ${
                  range === r.id
                    ? 'bg-white text-sky-700 shadow-xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {r.id}
              </button>
            ))}
          </div>

          {/* Export Dropdown */}
          <div className="flex items-center gap-1">
            <a
              href={exportUrlXlsx}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-[11px] font-bold text-slate-700 shadow-xs transition-colors flex items-center gap-1"
            >
              <span>Excel (.xlsx)</span>
            </a>
            <a
              href={exportUrlCsv}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-[11px] font-bold text-slate-700 shadow-xs transition-colors flex items-center gap-1"
            >
              <span>CSV</span>
            </a>
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSkeleton rows={4} height="h-48" />
      ) : error ? (
        <ErrorState message={error} />
      ) : points.length > 0 ? (
        <HistoricalCharts points={points} anomalies={histData.anomalies || []} latestObs={latestObs} />
      ) : (
        <div className="glass-panel p-8 text-center rounded-3xl text-xs font-semibold text-slate-400">
          No historical telemetry records found for the selected time window.
        </div>
      )}
    </div>
  )
}

function HistoricalCharts({ points, anomalies, latestObs }) {
  const chartData = points.map(r => ({
    ts: r.timestamp.length > 10 ? r.timestamp.slice(5, 16) : r.timestamp,
    fullTs: r.timestamp,
    temp: r.temperature_c,
    humidity: r.relative_humidity_pct,
    pressure: r.pressure_hpa,
    wind: r.wind_speed_kmh,
    rain: r.rainfall_mm,
    label: r.ground_truth_label,
    fault: r.fault_description,
  }))

  const metrics = [
    { key: 'temp', label: 'Temperature (°C)', color: '#0284C7', unit: '°C', gradient: 'from-sky-500/10' },
    { key: 'humidity', label: 'Relative Humidity (%)', color: '#10B981', unit: '%', gradient: 'from-emerald-500/10' },
    { key: 'pressure', label: 'Atmospheric Pressure (hPa)', color: '#8B5CF6', unit: 'hPa', gradient: 'from-purple-500/10' },
    { key: 'wind', label: 'Wind Speed (km/h)', color: '#F59E0B', unit: 'km/h', gradient: 'from-amber-500/10' },
    { key: 'rain', label: 'Rainfall (mm)', color: '#06B6D4', unit: 'mm', gradient: 'from-cyan-500/10' },
  ]

  return (
    <div className="space-y-4">
      {metrics.map(({ key, label, color, unit }) => {
        const hasValues = chartData.some(d => d[key] !== null && d[key] !== undefined && !isNaN(d[key]))
        if (!hasValues) return null

        return (
          <div key={key} className="glass-card p-5 rounded-3xl">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold tracking-wider text-slate-800 uppercase font-heading">
                {label}
              </div>
              <div className="flex items-center gap-3 text-[10px] font-semibold text-slate-400">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} /> Telemetry
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-rose-500" /> Sensor Fault
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-purple-500" /> Weather Event
                </span>
              </div>
            </div>

            <ResponsiveContainer width="100%" height={190}>
              <LineChart data={chartData} margin={{ top: 6, right: 12, left: -10, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="ts" tick={{ fill: '#94A3B8', fontSize: 10 }} interval={Math.max(1, Math.floor(chartData.length / 7))} />
                <YAxis tick={{ fill: '#94A3B8', fontSize: 10 }} unit={unit} domain={['auto', 'auto']} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const d = payload[0].payload
                      return (
                        <div className="bg-white/95 backdrop-blur-md p-3 rounded-2xl shadow-lg border border-slate-200 text-xs space-y-1">
                          <div className="font-bold text-slate-800">{d.fullTs}</div>
                          <div className="text-slate-600 font-semibold">
                            {label}: <span className="font-bold text-slate-900">{d[key]} {unit}</span>
                          </div>
                          {d.label && d.label !== 'NORMAL' && (
                            <div className="pt-1 text-[11px] font-bold text-rose-600">
                              Status: {d.label} {d.fault ? `(${d.fault})` : ''}
                            </div>
                          )}
                        </div>
                      )
                    }
                    return null
                  }}
                />
                <Line type="monotone" dataKey={key} stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                {chartData
                  .filter(d => d.label && d.label !== 'NORMAL' && d[key] !== null)
                  .map((p, i) => (
                    <ReferenceDot
                      key={i}
                      x={p.ts}
                      y={p[key]}
                      r={4.5}
                      fill={p.label === 'SENSOR_FAULT' ? '#F43F5E' : '#8B5CF6'}
                      stroke="#FFFFFF"
                      strokeWidth={1.5}
                    />
                  ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )
      })}
    </div>
  )
}

