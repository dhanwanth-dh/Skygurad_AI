export function LoadingSkeleton({ rows = 3, height = 'h-14' }) {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={`rounded-2xl ${height} bg-slate-200/70 border border-slate-300/40`} />
      ))}
    </div>
  )
}

export function CardSkeleton() {
  return (
    <div className="glass-card rounded-2xl p-6 border border-slate-200/80 animate-pulse space-y-3">
      <div className="h-3 w-28 rounded-full bg-slate-200" />
      <div className="h-8 w-20 rounded-xl bg-slate-200" />
      <div className="h-3 w-36 rounded-full bg-slate-100" />
    </div>
  )
}
