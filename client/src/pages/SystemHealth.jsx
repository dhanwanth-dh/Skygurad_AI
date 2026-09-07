import { motion } from 'framer-motion'
import { useHealth } from '../hooks/useApi'
import { LoadingSkeleton } from '../components/LoadingSkeleton'
import { RefreshCw, Activity, CheckCircle2, AlertOctagon, Cpu, Server } from 'lucide-react'

export default function SystemHealth() {
  const { data, loading, error, refetch } = useHealth()

  const isOk = data?.status === 'ok' && data?.model_loaded

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-3xl mx-auto pb-12"
    >
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-6 sm:p-8 rounded-3xl glass-panel">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-xs font-bold text-emerald-700 mb-2">
            <Activity size={13} />
            Diagnostics & Runtime Health
          </div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 font-heading">
            System Operational Health
          </h1>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Real-time inference server readiness and multi-model memory status.
          </p>
        </div>

        <button
          onClick={refetch}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-xs font-bold text-slate-700 shadow-xs transition-all disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          <span>Ping API</span>
        </button>
      </div>

      {loading && <LoadingSkeleton rows={4} height="h-20" />}

      {error && (
        <div className="glass-panel p-8 rounded-3xl border border-rose-200 bg-rose-50/70 text-center space-y-2">
          <div className="text-base font-bold text-rose-900 font-heading flex items-center justify-center gap-2">
            <AlertOctagon size={20} className="text-rose-600" />
            System API Unavailable
          </div>
          <p className="text-xs text-rose-700 font-medium max-w-md mx-auto">
            Unable to establish WebSocket / HTTP connection with the SkyGuard backend daemon.
          </p>
        </div>
      )}

      {data && (
        <div className="space-y-6">
          {/* Status Hero Card */}
          <div
            className={`p-8 rounded-3xl border text-center shadow-xs ${
              isOk
                ? 'bg-emerald-50/80 border-emerald-200'
                : 'bg-rose-50/80 border-rose-200'
            }`}
          >
            <div className="inline-flex p-3 rounded-2xl bg-white shadow-xs mb-3">
              {isOk ? (
                <CheckCircle2 size={32} className="text-emerald-500" />
              ) : (
                <AlertOctagon size={32} className="text-rose-500" />
              )}
            </div>
            <div className="text-xl font-black tracking-tight font-heading text-slate-900">
              {isOk ? 'All Systems Operational' : 'Degraded System State'}
            </div>
            <p className="text-xs font-medium text-slate-500 mt-1 max-w-md mx-auto">
              {isOk
                ? 'FastAPI microservices, model registry caches, and spatial geospatial trees are online.'
                : 'One or more subsystem dependencies are offline.'}
            </p>
          </div>

          {/* Component Status */}
          <div className="glass-card p-6 sm:p-8 rounded-3xl space-y-4">
            <div className="text-xs font-bold tracking-wider text-slate-400 uppercase">
              Microservices & Subsystem Components
            </div>

            <div className="space-y-3">
              {[
                { label: 'FastAPI Telemetry Gateway', status: data.status === 'ok', icon: Server, desc: 'Serving REST endpoints & CORS policies' },
                { label: 'Multi-Model Inference Pipeline', status: data.model_loaded, icon: Cpu, desc: '14 multi-models in memory' },
              ].map(({ label, status, icon: Icon, desc }) => (
                <div
                  key={label}
                  className="p-4 rounded-2xl bg-slate-50/80 border border-slate-100 flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center text-slate-700 shadow-xs">
                      <Icon size={18} />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-900">{label}</div>
                      <div className="text-[11px] text-slate-400 font-medium">{desc}</div>
                    </div>
                  </div>

                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold ${
                      status
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {status ? 'ONLINE' : 'OFFLINE'}
                  </span>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-slate-100 text-xs">
              <span className="font-semibold text-slate-500">Pipeline Release Version</span>
              <span className="font-mono font-bold text-sky-600">{data.version}</span>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  )
}
