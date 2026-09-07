export function fmt(val, decimals = 2) {
  if (val == null || isNaN(val)) return '—'
  return Number(val).toFixed(decimals)
}

export function fmtPct(val) {
  if (val == null) return '—'
  return `${(val * 100).toFixed(1)}%`
}

export function deviation(observed, expected) {
  if (observed == null || expected == null) return null
  return observed - expected
}

export function fmtDeviation(val, unit = '') {
  if (val == null) return '—'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}${unit}`
}

export function severityColor(severity) {
  const map = {
    LOW: '#22C55E',
    MEDIUM: '#F59E0B',
    HIGH: '#EF4444',
    CRITICAL: '#DC2626',
  }
  return map[severity] || '#9AAAC0'
}

export function predictionColor(prediction) {
  const map = {
    NORMAL: '#22C55E',
    SENSOR_FAULT: '#EF4444',
    GENUINE_EXTREME: '#A855F7',
  }
  return map[prediction] || '#9AAAC0'
}

export function healthColor(score) {
  if (score >= 90) return '#22C55E'
  if (score >= 70) return '#F59E0B'
  if (score >= 50) return '#EF4444'
  return '#DC2626'
}

export function healthStatus(score) {
  if (score >= 90) return 'HEALTHY'
  if (score >= 70) return 'NEEDS ATTENTION'
  if (score >= 50) return 'DEGRADED'
  return 'CRITICAL'
}

export function formatTimestamp(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString('en-IN', {
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch {
    return ts
  }
}
