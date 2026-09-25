import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid
} from 'recharts'
import { api } from '../services/api'
import { MOCK_STATIONS } from '../data/mockData'
import { LoadingSkeleton } from '../components/LoadingSkeleton'
import { ErrorState } from '../components/EmptyState'
import { healthColor } from '../utils/format'
import { BarChart3, PieChart as PieIcon, Activity } from 'lucide-react'

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true'

const CHART_COLORS = {
  NORMAL: '#10B981',
  SENSOR_FAULT: '#F43F5E',
  GENUINE_EXTREME: '#8B5CF6',
  DRIFT: '#F59E0B',
  FREEZE: '#0284C7',
  SPIKE: '#F43F5E',
  NONE: '#94A3B8',
}

export default function Analytics() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (USE_MOCK) {
        setPredictions(MOCK_STATIONS)
      } else {
        const data = await api.getStations()
        setPredictions(data?.stations ?? [])
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Derived chart data
  const predDist = ['NORMAL', 'SENSOR_FAULT', 'GENUINE_EXTREME'].map(p => ({
    name: p.replace('_', ' '),
    value: predictions.filter(r => r.prediction === p).length,
    color: CHART_COLORS[p],
  })).filter(d => d.value > 0)

  const healthData = predictions.map(p => ({
    station: p.station_id,
    health: p.sensor_health,
    score: p.anomaly_score,
  }))

  const faultDist = ['DRIFT', 'FREEZE', 'SPIKE', 'NONE'].map(f => ({
    name: f,
    value: predictions.filter(p => p.fault_type === f).length,
    color: CHART_COLORS[f],
  })).filter(d => d.value > 0)

  const severityData = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(s => ({
    name: s,
    value: predictions.filter(p => p.severity === s).length,
  }))

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-7xl mx-auto pb-12"
    >
      {/* Top Banner */}
      <div className="p-6 sm:p-8 rounded-3xl glass-panel">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-xs font-bold text-sky-700 mb-2">
          <BarChart3 size={13} />
          Statistical Aggregations
        </div>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 font-heading">
          Network Analytics & Distributions
        </h1>
        <p className="text-sm text-slate-500 font-medium mt-1">
          Visual breakdowns of anomaly classes, fault classifications, and station reliability scores.
        </p>
      </div>

      {error && <ErrorState message={error} />}

      {loading ? (
        <LoadingSkeleton rows={6} height="h-48" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartCard title="Prediction Class Distribution" icon={<PieIcon size={14} className="text-sky-600" />}>
            <ResponsiveContainer width="100%" height={230}>
              <PieChart>
                <Pie data={predDist} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={78} innerRadius={42} label>
                  {predDist.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#FFFFFF', borderRadius: 12, border: '1px solid #E2E8F0', color: '#0F172A', fontSize: 12, fontWeight: 600 }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Station Health Comparison" icon={<Activity size={14} className="text-emerald-600" />}>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={healthData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="station" tick={{ fill: '#64748B', fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748B', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#FFFFFF', borderRadius: 12, border: '1px solid #E2E8F0', color: '#0F172A', fontSize: 12 }} />
                <Bar dataKey="health" name="Health Score" radius={[6, 6, 0, 0]}>
                  {healthData.map((d, i) => <Cell key={i} fill={healthColor(d.health)} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Diagnosed Fault Categories" icon={<Activity size={14} className="text-amber-500" />}>
            {faultDist.length === 0 ? (
              <div className="flex items-center justify-center h-48 text-xs font-semibold text-slate-400">
                No active hardware faults
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={230}>
                <PieChart>
                  <Pie data={faultDist} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={78} innerRadius={42} label>
                    {faultDist.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#FFFFFF', borderRadius: 12, border: '1px solid #E2E8F0', color: '#0F172A', fontSize: 12 }} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Incident Severity Breakdown" icon={<BarChart3 size={14} className="text-rose-500" />}>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={severityData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="name" tick={{ fill: '#64748B', fontSize: 10 }} />
                <YAxis tick={{ fill: '#64748B', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#FFFFFF', borderRadius: 12, border: '1px solid #E2E8F0', color: '#0F172A', fontSize: 12 }} />
                <Bar dataKey="value" name="Flagged Observations" radius={[6, 6, 0, 0]}>
                  {severityData.map((d, i) => {
                    const c = { LOW: '#10B981', MEDIUM: '#F59E0B', HIGH: '#F43F5E', CRITICAL: '#DC2626' }
                    return <Cell key={i} fill={c[d.name] || '#94A3B8'} />
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Anomaly Score by Station" className="lg:col-span-2">
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={healthData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="station" tick={{ fill: '#64748B', fontSize: 10 }} />
                <YAxis domain={[0, 1]} tick={{ fill: '#64748B', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#FFFFFF', borderRadius: 12, border: '1px solid #E2E8F0', color: '#0F172A', fontSize: 12 }} />
                <Bar dataKey="score" name="Anomaly Score" fill="#0284C7" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}
    </motion.div>
  )
}

function ChartCard({ title, children, className = '', icon }) {
  return (
    <div className={`glass-card p-6 rounded-3xl ${className}`}>
      <div className="flex items-center gap-2 mb-4 text-xs font-bold tracking-wider text-slate-800 uppercase font-heading">
        {icon}
        <span>{title}</span>
      </div>
      {children}
    </div>
  )
}
