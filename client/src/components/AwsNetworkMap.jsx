import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { useNavigate } from 'react-router-dom'
import { fmt } from '../utils/format'
import { MapPin, ArrowRight } from 'lucide-react'

// Fix Leaflet default icon path broken by bundlers
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const STATUS_CONFIG = {
  NORMAL:          { color: '#10B981', label: 'Normal',                symbol: 'â—' },
  SENSOR_FAULT:    { color: '#F43F5E', label: 'Sensor Fault',          symbol: 'âš ' },
  GENUINE_EXTREME: { color: '#8B5CF6', label: 'Genuine Weather Event', symbol: 'â—†' },
  UNKNOWN:         { color: '#94A3B8', label: 'Unknown',               symbol: '?' },
}

function makeIcon(prediction, isSelected) {
  const cfg = STATUS_CONFIG[prediction] || STATUS_CONFIG.UNKNOWN
  const size = isSelected ? 36 : 28
  const pulse = prediction !== 'NORMAL' && prediction !== 'UNKNOWN'

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 36 36">
      ${pulse ? `<circle cx="18" cy="18" r="17" fill="${cfg.color}" opacity="0.3"/>` : ''}
      <circle cx="18" cy="18" r="${isSelected ? 13 : 11}" fill="${cfg.color}" opacity="0.95"/>
      <circle cx="18" cy="18" r="${isSelected ? 13 : 11}" fill="none" stroke="#FFFFFF" stroke-width="2.5" opacity="0.95"/>
      <text x="18" y="22.5" text-anchor="middle" font-size="11" fill="white" font-weight="bold" font-family="system-ui">${cfg.symbol}</text>
    </svg>`

  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -(size / 2)],
  })
}

// Auto-fit map to all station bounds
function FitBounds({ stations }) {
  const map = useMap()
  useEffect(() => {
    if (!stations || stations.length === 0) return
    const bounds = L.latLngBounds(stations.map(s => [s.latitude, s.longitude]))
    map.fitBounds(bounds, { padding: [50, 50] })
  }, [map, stations])
  return null
}

const FILTERS = ['ALL', 'NORMAL', 'ANOMALOUS', 'SENSOR_FAULT', 'GENUINE_EXTREME']

export function AwsNetworkMap({ stations = [], loading = false }) {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('ALL')
  const [selected, setSelected] = useState(null)

  const filtered = stations.filter(s => {
    if (filter === 'ALL') return true
    if (filter === 'NORMAL') return s.prediction === 'NORMAL'
    if (filter === 'ANOMALOUS') return s.prediction !== 'NORMAL'
    return s.prediction === filter
  })

  const anomalyCount = stations.filter(s => s.prediction !== 'NORMAL').length

  return (
    <div className="glass-card rounded-3xl overflow-hidden shadow-md">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-white/40 bg-white/45 backdrop-blur-xl">
        <div>
          <div className="text-sm font-bold tracking-tight text-slate-900 font-heading flex items-center gap-2">
            <MapPin className="w-4 h-4 text-sky-600" />
            Pan-India AWS Telemetry Map
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {stations.length} stations active Â· {anomalyCount} flagged anomal{anomalyCount !== 1 ? 'ies' : 'y'}
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap gap-1.5 p-1 rounded-2xl bg-white/50 backdrop-blur-md border border-white/60">
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={'px-3 py-1 rounded-xl text-xs font-bold transition-all duration-200 ' +
                (filter === f
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60')}
            >
              {f.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      <div style={{ height: 420, position: 'relative' }}>
        {loading ? (
          <div className="flex items-center justify-center h-full bg-white/30 backdrop-blur-md">
            <span className="text-xs font-semibold text-slate-500">Loading geospatial telemetry...</span>
          </div>
        ) : (
          <MapContainer center={[22.5, 78.9]} zoom={5} style={{ height: '100%', width: '100%', background: '#E2E8F0' }} zoomControl>
            <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}" attribution="&copy; Esri" maxZoom={19} />
            <FitBounds stations={filtered} />
            {filtered.map(s => (
              <Marker key={s.station_id} position={[s.latitude, s.longitude]} icon={makeIcon(s.prediction, selected === s.station_id)} eventHandlers={{ click: () => setSelected(s.station_id) }}>
                <Popup className="skyguard-popup" maxWidth={260}><StationPopup station={s} onView={() => navigate('/stations/' + s.station_id)} /></Popup>
              </Marker>
            ))}
          </MapContainer>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-3 border-t border-white/40 bg-white/45 backdrop-blur-xl text-xs">
        <span className="font-bold text-slate-500 uppercase tracking-wider text-[10px]">Status Legend</span>
        <div className="flex flex-wrap items-center gap-4">
          {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
            <span key={key} className="flex items-center gap-1.5 font-semibold text-slate-700">
              <span className="w-2 h-2 rounded-full" style={{ background: cfg.color }} />
              {cfg.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function StationPopup({ station, onView }) {
  const cfg = STATUS_CONFIG[station.prediction] || STATUS_CONFIG.UNKNOWN
  return (
    <div className="p-1 font-sans space-y-3">
      <div>
        <div className="font-bold text-sm text-slate-900 font-heading">{station.station_id}</div>
        {station.station_name && <div className="text-xs text-slate-500 font-medium">{station.station_name}</div>}
      </div>

      <div className="flex items-center gap-1.5">
        <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: cfg.color + '18', color: cfg.color }}>
          {station.prediction?.replace('_', ' ')}
        </span>
        <span className="text-[11px] font-semibold text-slate-400">Â· {station.severity}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs py-1 border-t border-b border-slate-100">
        <div><span className="text-slate-400 text-[10px] block uppercase">Temp</span><span className="font-bold text-slate-800">{fmt(station.temperature_c)} Â°C</span></div>
        <div><span className="text-slate-400 text-[10px] block uppercase">Humidity</span><span className="font-bold text-slate-800">{fmt(station.relative_humidity_pct)} %</span></div>
        <div><span className="text-slate-400 text-[10px] block uppercase">Pressure</span><span className="font-bold text-slate-800">{fmt(station.pressure_hpa)} hPa</span></div>
        <div><span className="text-slate-400 text-[10px] block uppercase">Health</span><span className="font-bold text-emerald-600">{station.sensor_health?.toFixed(0)}/100</span></div>
      </div>

      <button onClick={onView} className="w-full py-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 text-white font-bold text-xs tracking-wider flex items-center justify-center gap-1.5 transition-all shadow-xs">
        <span>View Details</span><ArrowRight size={13} />
      </button>
    </div>
  )
}



