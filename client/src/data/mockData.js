// Mock data — only used when VITE_USE_MOCK_DATA=true
// Default is false; real backend is used in production.

export const BASE_PRED = {
  confidence: 0.9022,
  confidence_level: 'HIGH',
  uncertainty_score: 0.12,
  class_probabilities: { GENUINE_EXTREME: 0.9022, NORMAL: 0.0978, SENSOR_FAULT: 0.0 },
  anomaly_score: 0.725,
  anomaly_consensus: {
    models_agreeing: 5,
    models_total: 6,
    score: 0.833,
    detector_scores: {
      isolation_forest: 0.78,
      lof: 0.65,
      one_class_svm: 0.72,
      elliptic_envelope: 0.85,
      mahalanobis: 0.80,
      robust_zscore: 0.70,
    },
  },
  model_agreement: 0.88,
  model_coverage: '6/6 active',
  fault_type: 'NONE',
  fault_confidence: 0.0,
  fault_evidence: [],
  genuine_event_score: 0.85,
  genuine_event_evidence: ['Multi-station temperature & humidity synchronization across Chennai cluster'],
  severity: 'HIGH',
  sensor_health: 91.8,
  sensor_health_status: 'HEALTHY',
  expected_values: { temperature_c: 31.81, relative_humidity_pct: 72.89, pressure_hpa: 1009.52 },
  observed_values: { temperature_c: 33.68, relative_humidity_pct: 59.52, pressure_hpa: 1009.4, wind_speed_kmh: 12.86, rainfall_mm: 0.0 },
  top_reasons: ['Atmospheric front pattern matching regional convective event'],
  recommended_action: 'Routine advisory. Extreme weather event flagged for meteorologist review.',
  correction: {},
  model_version: 'v2.0-multimodel',
}

export const MOCK_PREDICTION = BASE_PRED

export const MOCK_STATIONS_RESPONSE = {
  total: 3,
  stations: [
    {
      station_id: 'AWS_CHN_01', station_name: 'Guindy',
      latitude: 13.0067, longitude: 80.2021,
      latest_timestamp: '2026-09-07 23:00:00',
      temperature_c: 33.68, relative_humidity_pct: 59.52, pressure_hpa: 1009.4,
      wind_speed_kmh: 12.86, rainfall_mm: 0.0,
      prediction: 'GENUINE_EXTREME', ...BASE_PRED,
    },
    {
      station_id: 'AWS_CHN_02', station_name: 'Tambaram',
      latitude: 12.9249, longitude: 80.1000,
      latest_timestamp: '2026-09-07 23:00:00',
      temperature_c: 23.80, relative_humidity_pct: 100.0, pressure_hpa: 1012.02,
      wind_speed_kmh: 10.2, rainfall_mm: 0.0,
      prediction: 'NORMAL', confidence: 0.95, confidence_level: 'HIGH', uncertainty_score: 0.05,
      anomaly_score: 0.12, fault_type: 'NONE', severity: 'LOW', sensor_health: 93.4,
      sensor_health_status: 'HEALTHY',
      expected_values: { temperature_c: 23.5, relative_humidity_pct: 98.0, pressure_hpa: 1012.0 },
      observed_values: { temperature_c: 23.80, relative_humidity_pct: 100.0, pressure_hpa: 1012.02, wind_speed_kmh: 10.2, rainfall_mm: 0.0 },
      top_reasons: ['All sensor channels within normal historical bounds'], correction: {},
    },
    {
      station_id: 'AWS_CHN_03', station_name: 'Adyar',
      latitude: 13.0012, longitude: 80.2565,
      latest_timestamp: '2026-09-07 23:00:00',
      temperature_c: 23.83, relative_humidity_pct: 100.0, pressure_hpa: 1011.94,
      wind_speed_kmh: 9.5, rainfall_mm: 0.0,
      prediction: 'NORMAL', confidence: 0.97, confidence_level: 'HIGH', uncertainty_score: 0.03,
      anomaly_score: 0.08, fault_type: 'NONE', severity: 'LOW', sensor_health: 97.9,
      sensor_health_status: 'HEALTHY',
      expected_values: { temperature_c: 23.6, relative_humidity_pct: 99.0, pressure_hpa: 1011.9 },
      observed_values: { temperature_c: 23.83, relative_humidity_pct: 100.0, pressure_hpa: 1011.94, wind_speed_kmh: 9.5, rainfall_mm: 0.0 },
      top_reasons: ['All sensor channels within normal historical bounds'], correction: {},
    },
  ],
}

export const MOCK_STATIONS = MOCK_STATIONS_RESPONSE.stations

export const MOCK_ANOMALIES_RESPONSE = {
  total: 1,
  sensor_faults: 0,
  genuine_events: 1,
  anomalies: [
    {
      station_id: 'AWS_CHN_01', station_name: 'Guindy',
      latitude: 13.0067, longitude: 80.2021,
      timestamp: '2026-09-07 23:00:00',
      prediction: 'GENUINE_EXTREME', ...BASE_PRED,
    },
  ],
}
