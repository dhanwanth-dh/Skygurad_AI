# SkyGuard Data Audit Report

## 1. Dataset Shape
- Rows: 504
- Columns: 12
- Columns: ['timestamp', 'station_id', 'station_name', 'latitude', 'longitude', 'temperature_c', 'relative_humidity_pct', 'pressure_hpa', 'wind_speed_kmh', 'rainfall_mm', 'ground_truth_label', 'fault_description']

## 2. Data Types
- timestamp: datetime64[ns]
- station_id: object
- station_name: object
- latitude: float64
- longitude: float64
- temperature_c: float64
- relative_humidity_pct: float64
- pressure_hpa: float64
- wind_speed_kmh: float64
- rainfall_mm: float64
- ground_truth_label: object
- fault_description: object

## 3. Missing Values
- fault_description: 467 (92.7%)

## 4. Duplicates
- Duplicate rows: 0
- Duplicate station/timestamp pairs: 0

## 5. Timestamp Range
- Start: 2026-09-01 00:00:00
- End  : 2026-09-07 23:00:00
- Span : 6 days 23:00:00

## 6. Sampling Frequency (per station)
- AWS_CHN_01: modal interval = 0 days 01:00:00
- AWS_CHN_02: modal interval = 0 days 01:00:00
- AWS_CHN_03: modal interval = 0 days 01:00:00

## 7. Stations
- AWS_CHN_01 (Guindy): 168 obs | lat=13.0067, lon=80.2021
- AWS_CHN_02 (Tambaram): 168 obs | lat=12.9249, lon=80.1
- AWS_CHN_03 (Adyar): 168 obs | lat=13.0012, lon=80.2565

## 8. Label Distribution
- NORMAL: 467 (92.7%)
- SENSOR_FAULT: 25 (5.0%)
- GENUINE_EXTREME: 12 (2.4%)

## 9. Fault Description Distribution
- Temperature Sensor Drift / Calibration Loss: 13
- Severe Thunderstorm (Multi-station consistent): 12
- Humidity Sensor Freeze (Zero variance): 11
- Barometric Sensor Single-Point Noise Spike: 1

## 10. Fault Distribution by Station
station_id ground_truth_label  count
AWS_CHN_01    GENUINE_EXTREME      4
AWS_CHN_01       SENSOR_FAULT     13
AWS_CHN_02    GENUINE_EXTREME      4
AWS_CHN_02       SENSOR_FAULT     11
AWS_CHN_03    GENUINE_EXTREME      4
AWS_CHN_03       SENSOR_FAULT      1

## 11. Numerical Distributions
       temperature_c  relative_humidity_pct  pressure_hpa  wind_speed_kmh  rainfall_mm
count        504.000                504.000       504.000         504.000      504.000
mean          28.013                 83.660      1009.533          10.659        0.566
std            4.415                 15.233         7.330           5.211        3.701
min           20.850                 57.640       850.000           4.950        0.000
25%           23.758                 67.910      1008.478           7.222        0.000
50%           27.890                 85.840      1009.850          10.130        0.000
75%           32.088                100.000      1011.382          12.965        0.000
max           38.740                100.000      1012.540          39.940       33.150

## 12. Physical Bound Violations
- temperature_c outside [-10.0, 60.0]: 0 rows
- relative_humidity_pct outside [0.0, 100.0]: 0 rows
- pressure_hpa outside [870.0, 1084.0]: 1 rows
- wind_speed_kmh outside [0.0, 200.0]: 0 rows
- rainfall_mm outside [0.0, 500.0]: 0 rows

## 13. Correlation Matrix (sensor columns)
                       temperature_c  relative_humidity_pct  pressure_hpa  wind_speed_kmh  rainfall_mm
temperature_c                  1.000                 -0.955        -0.134           0.359       -0.104
relative_humidity_pct         -0.955                  1.000         0.154          -0.375        0.073
pressure_hpa                  -0.134                  0.154         1.000          -0.132       -0.116
wind_speed_kmh                 0.359                 -0.375        -0.132           1.000        0.820
rainfall_mm                   -0.104                  0.073        -0.116           0.820        1.000

## 14. Temporal Continuity
- AWS_CHN_01: 0 gaps > 1h
- AWS_CHN_02: 0 gaps > 1h
- AWS_CHN_03: 0 gaps > 1h

## 15. Spatial Distances Between Stations (km)
- AWS_CHN_01 <-> AWS_CHN_02: 14.32 km
- AWS_CHN_01 <-> AWS_CHN_03: 5.93 km
- AWS_CHN_02 <-> AWS_CHN_03: 18.96 km

## 16. Key Findings & Implications
- Dataset is small (504 rows) and highly imbalanced (NORMAL=92.7%).
- Only 3 stations, all in Chennai, India — very close spatially.
- Hourly data over 7 days; no temporal gaps detected.
- Drift fault (13 obs) and Freeze fault (11 obs) may support limited supervised classification.
- Spike fault (1 obs) — supervised classification NOT feasible; use rule-based detection.
- Thunderstorm events affect all 3 stations simultaneously — spatial consistency is a strong signal.
- Pressure spike (850 hPa) is a clear physical violation — easily detectable by rules.
- Humidity freeze (constant 62.4%) is detectable by zero-variance rule.
- Temperature drift shows persistent positive deviation vs. neighbors — spatial residual is key.
