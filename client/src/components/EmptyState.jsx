import { WifiOff } from 'lucide-react'

export function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="glass-panel rounded-3xl flex flex-col items-center justify-center py-16 px-6 text-center">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mb-4 text-slate-400 shadow-xs">
          <Icon size={28} />
        </div>
      )}
      <div className="text-base font-bold text-slate-800 mb-1 font-heading">{title}</div>
      {description && <div className="text-xs font-medium text-slate-500 max-w-sm">{description}</div>}
    </div>
  )
}

export function ErrorState({ message }) {
  return (
    <div className="rounded-3xl border border-rose-200 bg-rose-50/80 p-8 flex flex-col items-center justify-center text-center">
      <div className="w-12 h-12 rounded-2xl bg-rose-100 flex items-center justify-center mb-3 text-rose-600">
        <WifiOff size={24} />
      </div>
      <div className="text-sm font-bold text-rose-900 mb-1 font-heading">
        API Connection Unavailable
      </div>
      <div className="text-xs font-medium text-rose-700 max-w-sm">
        {message || 'Verify that the SkyGuard FastAPI backend is active and reachable.'}
      </div>
    </div>
  )
}
