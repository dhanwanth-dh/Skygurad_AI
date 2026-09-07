const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  getHealth: () => request('/health'),
  getModelInfo: () => request('/model-info'),
  predict: (observation) =>
    request('/predict', { method: 'POST', body: JSON.stringify(observation) }),
  getStations: () => request('/stations'),
  getAnomalies: () => request('/anomalies'),
  getStationHistory: (stationId) => request(`/stations/${encodeURIComponent(stationId)}/history`),
}
