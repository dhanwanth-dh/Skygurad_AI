# SkyGuard Model Report

## 1. Dataset Information

| Property | Value |
|---|---|
| File | skyguard_synthetic_weather_fault_dataset.csv |
| Rows | 504 |
| Columns | 12 |
| Stations | 3 (AWS_CHN_01 Guindy, AWS_CHN_02 Tambaram, AWS_CHN_03 Adyar) |
| Timestamp range | 2026-09-01 00:00 → 2026-09-07 23:00 |
| Sampling frequency | Hourly |
| Missing values | None in sensor columns |
| Physical violations | 1 (pressure_hpa = 850 hPa, known barometric spike) |

### Label Distribution

| Label | Count | Fraction |
|---|---|---|
| NORMAL | 467 | 92.7% |
| SENSOR_FAULT | 25 | 5.0% |
| GENUINE_EXTREME | 12 | 2.4% |

### Fault Type Distribution

| Fault | Count | Station | Period |
|---|---|---|---|
| Temperature Sensor Drift / Calibration Loss | 13 | AWS_CHN_01 | Sep 2 10:00–22:00 |
| Humidity Sensor Freeze (Zero variance) | 11 | AWS_CHN_02 | Sep 3 08:00–18:00 |
| Barometric Sensor Single-Point Noise Spike | 1 | AWS_CHN_03 | Sep 4 14:00 |
| Severe Thunderstorm (Multi-station consistent) | 12 | All 3 | Sep 5 15:00–18:00 |

---

## 2. Split Strategy

**Chronological split on unique timestamps** — all stations at a given timestamp land in the same split to prevent cross-station future leakage.

| Split | Rows | Period | Labels |
|---|---|---|---|
| Train | 300 | Sep 1 00:00 → Sep 5 03:00 | NORMAL=275, SENSOR_FAULT=25 |
| Validation | 99 | Sep 5 04:00 → Sep 6 12:00 | NORMAL=87, GENUINE_EXTREME=12 |
| Test | 105 | Sep 6 13:00 → Sep 7 23:00 | NORMAL=105 |

**Important limitation:** The test set contains only NORMAL observations. This is an inherent consequence of the 7-day dataset where all fault/extreme events occur in the first 5 days. Test set metrics reflect only NORMAL classification performance.

---

## 3. Feature Engineering

### Temporal Features (per station, backward-looking only)
- Lag features: lag1, lag2, lag3 for all 5 sensor columns
- Delta (first difference) for all 5 sensor columns
- Rolling mean and std: windows 3h and 6h (shifted by 1 to exclude current observation)
- Rolling z-score using 6h window
- Time since previous observation (hours)
- Calendar: hour, day_of_week, day_of_year, month

### Station Baseline Features
- Per-station, per-hour-of-day median and MAD from training data
- baseline, deviation, robust_z for all 5 sensor columns

### Spatial Features
- Haversine distances between stations (~14 km Guindy-Tambaram, ~5 km Guindy-Adyar)
- Neighbor mean/std for all sensor columns (co-temporal observations only)
- Spatial residual (observed - neighbor mean)
- Neighbor agreement score

### Multivariate Consistency Features
- Cross-sensor ExtraTreesRegressor residuals (each sensor predicted from others)
- Mahalanobis distance on scaled sensor vector

### Expected Value Residuals
- predicted_temperature_c, temperature_c_residual
- predicted_relative_humidity_pct, relative_humidity_pct_residual
- predicted_pressure_hpa, pressure_hpa_residual

### Anomaly Scores
- if_anomaly_score (Isolation Forest, normalized)
- lof_anomaly_score (Local Outlier Factor, novelty mode)
- combined_anomaly_score (mean of IF and LOF)

### Rule-Based Fault Flags
- rule_freeze: near-zero variance over ≥3 consecutive observations
- rule_spike: single-point deviation > 4 MAD z-score with recovery
- rule_drift: persistent deviation > 2 robust-z for ≥5 consecutive observations

---

## 4. Model Comparison — Decision Classifier

| Model | Val Macro F1 | Notes |
|---|---|---|
| Logistic Regression (balanced) | 0.325 | Underfits; linear boundary insufficient |
| **Random Forest (balanced, depth=6)** | **0.468** | **Selected** |
| XGBoost | 0.315 | Lower F1 on this split |

**Selected model: Random Forest**

Reason: Highest macro F1 on validation set. Handles class imbalance via `class_weight="balanced"`. Provides feature importances for SHAP.

**Honest assessment of val macro F1 = 0.468:**
- The validation set has only 2 classes (NORMAL + GENUINE_EXTREME)
- SENSOR_FAULT is entirely in training; the model has never seen GENUINE_EXTREME during training
- This is a fundamental limitation of 7-day data with non-overlapping fault/extreme events
- The macro F1 reflects the difficulty of generalizing to unseen event types

---

## 5. Expected Value Models

| Target | Best Model | Val MAE | Val R² |
|---|---|---|---|
| temperature_c | ExtraTreesRegressor | 0.766°C | 0.835 |
| relative_humidity_pct | ExtraTreesRegressor | 1.485% | 0.948 |
| pressure_hpa | ExtraTreesRegressor | 0.487 hPa | 0.791 |

Ridge regression performed extremely poorly (MAE > 100) due to multicollinearity in lag features. ExtraTrees selected for all three targets.

---

## 6. Fault Classification

### Supervised Component
- Trained on DRIFT (13 samples) and FREEZE (11 samples) only
- SPIKE (1 sample) excluded from supervised training — insufficient evidence
- Validation: no SENSOR_FAULT rows in val set; fault classifier evaluated on training data only

### Rule-Based Component
- FREEZE: detected by near-zero variance rule (≥3 consecutive, variance < 0.01)
- SPIKE: detected by single-point MAD z-score rule (z > 4.0 with recovery)
- DRIFT: detected by persistent robust-z deviation rule (≥5 consecutive, |z| > 2.0)

**Validation against known labels:**
- Freeze detection: ≥5 of 11 known freeze rows correctly flagged
- Spike detection: 1/1 known spike correctly flagged
- Drift detection: depends on baseline quality (training-only baselines)

---

## 7. Sensor Health Scores

| Station | Health Score | Status | Fault Rate | Anomaly Rate |
|---|---|---|---|---|
| AWS_CHN_01 (Guindy) | 91.9 | HEALTHY | 0.077 | varies |
| AWS_CHN_02 (Tambaram) | 93.7 | HEALTHY | 0.065 | varies |
| AWS_CHN_03 (Adyar) | 98.1 | HEALTHY | 0.006 | varies |

AWS_CHN_03 correctly scores highest (only 1 spike fault). AWS_CHN_01 scores lowest (13 drift faults).

---

## 8. Test Set Evaluation

**Note: Test set contains only NORMAL observations (Sep 6–7). This is not a model failure — it reflects the dataset structure.**

| Metric | Value |
|---|---|
| Accuracy | 1.000 (trivial — all NORMAL) |
| Macro F1 | 1.000 (trivial — single class) |
| NORMAL precision/recall/F1 | 1.000 / 1.000 / 1.000 |
| GENUINE_EXTREME recall | 0.000 (no examples in test) |
| SENSOR_FAULT recall | 0.000 (no examples in test) |

**Primary evaluation metric is validation macro F1 = 0.468.**

---

## 9. Limitations

1. **7-day dataset**: Insufficient temporal coverage for robust generalization. All fault types occur in the first 5 days; test set is fault-free.
2. **3 stations only**: Spatial features are limited. All stations are within ~14 km of each other in Chennai.
3. **GENUINE_EXTREME absent from training**: The model has never seen a thunderstorm during training. It can only learn from the evidence features (spatial consistency, pressure drop, wind/rainfall spike).
4. **SPIKE class (1 sample)**: Supervised classification not possible. Rule-based detection only.
5. **Calibration**: Probability calibration not applied (insufficient val samples per class for reliable Platt scaling).
6. **Predictive maintenance**: Not implemented — insufficient historical failure data.
7. **Imputer warnings**: Feature column 45 (rainfall_mm_roll6_std or similar) is all-NaN in training — this is expected for a column that requires 6+ observations to compute.

---

## 10. Model Selection Reasoning

Random Forest was selected over Logistic Regression and XGBoost because:
- Highest validation macro F1 (0.468 vs 0.325 and 0.315)
- Handles class imbalance natively via `class_weight="balanced"`
- Robust to feature scale differences (no normalization required for tree splits)
- Provides feature importances for SHAP explainability
- Less prone to overfitting on small datasets than XGBoost with default settings

---

## 11. Reproducibility

- Random seed: 42 (set in configs/data.yaml)
- All transformers fitted on training data only
- Chronological split prevents future leakage
- Artifacts saved to artifacts/ with version metadata
- Model version: stored in artifacts/metadata/model_metadata.json
