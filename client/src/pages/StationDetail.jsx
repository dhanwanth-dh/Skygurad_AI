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
        <div className="text-xs font-bold tracking-wider text-slate-400 uppercase">
          Historical Telemetry & Anomaly Sequence
        </div>
        {histLoading ? (
          <LoadingSkeleton rows={3} height="h-48" />
        ) : histError ? (
          <ErrorState message={histError} />
        ) : histData?.records?.length > 0 ? (
          <HistoricalCharts records={histData.records} />
        ) : (
          <div className="glass-panel p-8 text-center rounded-3xl text-xs font-semibold text-slate-400">
            No historical telemetry records found.
          </div>
        )}
      </section>
    </motion.div>
  )
}

function HistoricalCharts({ records }) {
  const step = Math.max(1, Math.floor(records.length / 80))
  const data = records
    .filter((_, i) => i % step === 0)
    .map(r => ({
      ts: r.timestamp.slice(5, 16),
      temp: r.temperature_c,
      humidity: r.relative_humidity_pct,
      pressure: r.pressure_hpa,
      label: r.ground_truth_label,
      fault: r.fault_description,
    }))

  const anomalyPoints = data.filter(d => d.label && d.label !== 'NORMAL')

  return (
    <div className="space-y-4">
      {[
        { key: 'temp', label: 'Temperature (°C)', color: '#0284C7', unit: '°C' },
        { key: 'humidity', label: 'Relative Humidity (%)', color: '#10B981', unit: '%' },
        { key: 'pressure', label: 'Pressure (hPa)', color: '#8B5CF6', unit: 'hPa' },
      ].map(({ key, label, color, unit }) => (
        <div key={key} className="glass-card p-5 rounded-3xl">
          <div className="text-xs font-bold tracking-wider text-slate-700 uppercase mb-3 font-heading">
            {label}
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data} margin={{ top: 4, right: 8, left: -10, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="ts" tick={{ fill: '#94A3B8', fontSize: 10 }} interval={Math.floor(data.length / 6)} />
              <YAxis tick={{ fill: '#94A3B8', fontSize: 10 }} unit={unit} />
              <Tooltip contentStyle={{ background: '#FFFFFF', borderRadius: 12, border: '1px solid #E2E8F0', color: '#0F172A', fontSize: 11 }} />
              <Line type="monotone" dataKey={key} stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              {anomalyPoints.map((p, i) => (
                <ReferenceDot key={i} x={p.ts} y={p[key]} r={4} fill={p.label === 'SENSOR_FAULT' ? '#F43F5E' : '#8B5CF6'} stroke="none" />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  )
}
