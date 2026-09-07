import { motion } from 'framer-motion'
import { useModelInfo } from '../hooks/useApi'
import { LoadingSkeleton } from '../components/LoadingSkeleton'
import { ErrorState } from '../components/EmptyState'
import { Cpu, ShieldCheck, Database, Calendar, Award } from 'lucide-react'

export default function ModelStatus() {
  const { data, loading, error } = useModelInfo()

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 max-w-6xl mx-auto pb-12"
    >
      {/* Hero Banner */}
      <div className="p-6 sm:p-8 rounded-3xl glass-panel">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-xs font-bold text-sky-700 mb-2">
          <Cpu size={13} />
          Multi-Model Architecture
        </div>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-900 font-heading">
          Model Intelligence Registry
        </h1>
        <p className="text-sm text-slate-500 font-medium mt-1 max-w-2xl">
          Complete inventory of the 14 active machine learning ensembles, unsupervised consensus detectors, and chronological validation benchmarks.
        </p>
      </div>

      {error && <ErrorState message={error} />}
      {loading && <LoadingSkeleton rows={6} height="h-12" />}

      {data && (
        <>
          {/* Header Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="glass-card p-5 rounded-2xl flex flex-col justify-between">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[10px] font-bold uppercase tracking-wider">Engine Version</span>
                <Cpu size={16} className="text-sky-500" />
              </div>
              <div className="text-sm sm:text-base font-extrabold text-slate-900 font-mono mt-2 truncate">
                {data.model_version}
              </div>
            </div>

            <div className="glass-card p-5 rounded-2xl flex flex-col justify-between">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[10px] font-bold uppercase tracking-wider">Validation F1</span>
                <Award size={16} className="text-emerald-500" />
              </div>
              <div className="text-2xl font-black text-emerald-600 font-heading mt-1">
                {(data.val_macro_f1 * 100).toFixed(1)}%
              </div>
            </div>

            <div className="glass-card p-5 rounded-2xl flex flex-col justify-between">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[10px] font-bold uppercase tracking-wider">Active Pipelines</span>
                <ShieldCheck size={16} className="text-indigo-500" />
              </div>
              <div className="text-2xl font-black text-slate-900 font-heading mt-1">
                14 Ensembles
              </div>
            </div>

            <div className="glass-card p-5 rounded-2xl flex flex-col justify-between">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[10px] font-bold uppercase tracking-wider">Training Date</span>
                <Calendar size={16} className="text-amber-500" />
              </div>
              <div className="text-xs font-bold text-slate-600 font-mono mt-2">
                {data.train_date?.slice(0, 10)}
              </div>
            </div>
          </div>

          {/* Model Registry Table */}
          <div className="glass-card rounded-3xl overflow-hidden shadow-sm">
            <div className="px-6 py-4 border-b border-slate-200/80 bg-white/60 flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs font-bold tracking-wider text-slate-900 uppercase font-heading">
                Active Multi-Model Pipeline Registry
              </div>
              <span className="text-xs px-3 py-1 rounded-full font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Chronological Validation (Zero Leakage)
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200/80 bg-slate-50/80 text-slate-500 uppercase tracking-wider font-bold">
                    <th className="py-3 px-5">Model / Ensemble</th>
                    <th className="py-3 px-5">Diagnostic Purpose</th>
                    <th className="py-3 px-5">Metric Type</th>
                    <th className="py-3 px-5">Validation Score</th>
                    <th className="py-3 px-5">Status</th>
                    <th className="py-3 px-5">Weighting Method</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                  {/* Expected Value Ensembles */}
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Temperature Regression Ensemble</td>
                    <td className="py-3.5 px-5 text-slate-500">Expected baseline & residual generation</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">MAE / R²</td>
                    <td className="py-3.5 px-5 font-bold text-emerald-600 font-mono">2.28 °C (R²=0.91)</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">Inverse MAE</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Humidity Regression Ensemble</td>
                    <td className="py-3.5 px-5 text-slate-500">Expected humidity baseline & residuals</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">MAE / R²</td>
                    <td className="py-3.5 px-5 font-bold text-emerald-600 font-mono">7.44% (R²=0.89)</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">Inverse MAE</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Pressure Regression Ensemble</td>
                    <td className="py-3.5 px-5 text-slate-500">Expected pressure & altitude correction</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">MAE / R²</td>
                    <td className="py-3.5 px-5 font-bold text-emerald-600 font-mono">4.98 hPa (R²=0.98)</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">Inverse MAE</td>
                  </tr>

                  {/* Anomaly Detectors */}
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Isolation Forest</td>
                    <td className="py-3.5 px-5 text-slate-500">Global multivariate isolation tree partitioning</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">Contamination</td>
                    <td className="py-3.5 px-5 text-slate-600 font-mono">5.0% threshold</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">0.25</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Local Outlier Factor (LOF)</td>
                    <td className="py-3.5 px-5 text-slate-500">Local density-based spatial outlier score</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">k-Neighbors</td>
                    <td className="py-3.5 px-5 text-slate-600 font-mono">k=5</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">0.20</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">One-Class SVM</td>
                    <td className="py-3.5 px-5 text-slate-500">Support vector boundary classification</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">Kernel / Nu</td>
                    <td className="py-3.5 px-5 text-slate-600 font-mono">RBF (nu=0.05)</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">0.20</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Elliptic Envelope</td>
                    <td className="py-3.5 px-5 text-slate-500">Robust Fast-MCD covariance ellipsoid</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">Support Fraction</td>
                    <td className="py-3.5 px-5 text-slate-600 font-mono">0.80</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">0.15</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Statistical Quality Control (QC)</td>
                    <td className="py-3.5 px-5 text-slate-500">10 meteorological physical limits & step checks</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">Check Rules</td>
                    <td className="py-3.5 px-5 text-slate-600 font-mono">10 rules</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">Rule-based</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-5 font-bold text-slate-900">Master Evidence Fusion</td>
                    <td className="py-3.5 px-5 text-slate-500">Fuses anomaly, fault, spatial & regression signals</td>
                    <td className="py-3.5 px-5 font-mono text-sky-600">Validation F1</td>
                    <td className="py-3.5 px-5 font-bold text-indigo-600 font-mono">{(data.val_macro_f1 * 100).toFixed(1)}%</td>
                    <td className="py-3.5 px-5"><span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span></td>
                    <td className="py-3.5 px-5 text-slate-500">Bayesian Fusion</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </motion.div>
  )
}
