"""Genuine Meteorological Event Engine.

Evaluates whether atmospheric anomalies are caused by genuine meteorological phenomena
(e.g., severe thunderstorms, monsoons, squalls, convective downdrafts, atmospheric fronts,
heatwaves, cold waves) versus isolated sensor hardware faults.

Uses 10 scientific evidence signals:
1. Multi-station agreement & spatial proximity
2. Spatial residual (observed vs neighbor mean)
3. Direct precipitation intensity (heavy rain / downpour)
4. Wind gust intensity (storm / gale force)
5. Climatological extreme temperature (severe heatwave / cold wave)
6. Thermodynamic multi-sensor consistency (rain + high humidity + evaporative cooling)
7. Barometric pressure depression / squall line drop
8. Temporal coherence (gradual ramp vs instantaneous glitch)
9. Atmospheric front temperature-humidity inverse shifts
10. Hardware fault disqualification filtering
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class GenuineWeatherEventEngine:
    """Evaluates multi-station spatial and multivariate atmospheric consistency."""

    def __init__(
        self,
        min_spatial_agreement: float = 0.60,
        spatial_residual_tolerance: float = 3.0,
    ) -> None:
        self.min_spatial_agreement = min_spatial_agreement
        self.spatial_residual_tolerance = spatial_residual_tolerance

    def evaluate(self, row: pd.Series | dict[str, Any], anomaly_score: float = 0.0) -> dict[str, Any]:
        """Evaluate genuine weather event probability and extract concrete evidence."""
        evidence: list[str] = []
        positive_points: float = 0.0

        def _val(col: str, default: float = 0.0) -> float:
            v = row.get(col, default) if isinstance(row, dict) else row.get(col, default)
            try:
                if v is None or pd.isna(v):
                    return default
                return float(v)
            except (ValueError, TypeError):
                return default

        rain = _val("rainfall_mm", 0.0)
        wind = _val("wind_speed_kmh", 0.0)
        temp = _val("temperature_c", 25.0)
        rh = _val("relative_humidity_pct", 50.0)
        press = _val("pressure_hpa", 1013.0)

        temp_res = _val("temperature_c_residual", 0.0)
        rh_res = _val("relative_humidity_pct_residual", 0.0)

        # ── 1. Direct Heavy Precipitation / Storm Signatures ────────────────
        if rain >= 25.0:
            positive_points += 0.50
            evidence.append(f"Heavy convective downpour / storm precipitation ({rain:.1f} mm/hr)")
        elif rain >= 10.0:
            positive_points += 0.35
            evidence.append(f"Moderate-to-heavy precipitation active ({rain:.1f} mm/hr)")
        elif rain > 1.0:
            positive_points += 0.20
            evidence.append(f"Precipitation active ({rain:.1f} mm)")

        # ── 2. Severe Wind / Gale / Squall Signatures ────────────────────────
        if wind >= 45.0:
            positive_points += 0.45
            evidence.append(f"Severe storm-force gale gusts ({wind:.1f} km/h)")
        elif wind >= 30.0:
            positive_points += 0.30
            evidence.append(f"High convective wind gusts ({wind:.1f} km/h)")
        elif wind >= 22.0:
            positive_points += 0.15
            evidence.append(f"Elevated atmospheric wind speed ({wind:.1f} km/h)")

        # ── 3. Climatological Extreme Temperatures (Heatwave / Cold Wave) ───
        if temp >= 44.0 and rh <= 45.0:
            positive_points += 0.50
            evidence.append(f"Severe heatwave conditions: extreme temperature ({temp:.1f} °C) with dry air mass ({rh:.1f}%)")
        elif temp >= 40.0 and rh <= 55.0:
            positive_points += 0.35
            evidence.append(f"Heatwave threshold exceeded ({temp:.1f} °C)")
        elif temp <= 5.0 and temp >= -20.0:
            positive_points += 0.45
            evidence.append(f"Severe cold wave conditions detected ({temp:.1f} °C)")
        elif temp <= 10.0 and temp >= -20.0:
            positive_points += 0.30
            evidence.append(f"Cold wave threshold reached ({temp:.1f} °C)")

        # ── 4. Multivariate Thermodynamic Consistency ────────────────────────
        # A. Storm/Rain cooling: rain > 5mm + high humidity + temperature lower than expected
        if rain >= 5.0 and rh >= 75.0:
            positive_points += 0.30
            evidence.append(f"Atmospheric moisture saturation consistent with rainstorm (RH: {rh:.1f}%)")
            if temp_res < -2.0 or (temp < 30.0 and rh >= 80.0):
                positive_points += 0.20
                evidence.append("Convective downdraft evaporative cooling verified across sensors")

        # B. Barometric depression coupled with squall / rain
        if press < 1004.0 and (rain >= 5.0 or wind >= 25.0):
            positive_points += 0.25
            evidence.append(f"Barometric low-pressure depression ({press:.1f} hPa) aligns with storm activity")

        # ── 5. Spatial Neighbor Agreement (when available) ───────────────────
        neighbor_score = row.get("neighbor_agreement_score", np.nan)
        if not pd.isna(neighbor_score):
            if neighbor_score < 2.0:
                positive_points += 0.35
                evidence.append(f"Nearby AWS stations confirm synchronized atmospheric pattern (spatial residual: {neighbor_score:.2f})")
            elif neighbor_score < 4.0:
                positive_points += 0.15
                evidence.append("Moderate multi-station spatial agreement with neighboring AWS stations")

        # ── 6. Temporal Delta / Front Signature (when available) ─────────────
        temp_delta = row.get("temperature_c_delta", np.nan)
        rh_delta = row.get("relative_humidity_pct_delta", np.nan)
        press_delta = row.get("pressure_hpa_delta", np.nan)

        if not pd.isna(temp_delta) and not pd.isna(rh_delta):
            if temp_delta < -1.5 and rh_delta > 5.0:
                positive_points += 0.25
                evidence.append(f"Atmospheric front signature: temp drop ({temp_delta:+.1f} °C) coupled with humidity surge ({rh_delta:+.1f}%)")

        if not pd.isna(press_delta) and press_delta < -1.5:
            positive_points += 0.20
            evidence.append(f"Rapid barometric pressure drop ({press_delta:+.1f} hPa/hr)")

        # ── 7. Hardware Fault Disqualifiers ──────────────────────────────────
        is_freeze = bool(row.get("rule_freeze", False))
        is_spike = bool(row.get("rule_spike", False))
        is_comm = bool(row.get("rule_communication", False))

        if is_freeze:
            positive_points = min(positive_points * 0.15, 0.10)
            evidence.append("Frozen sensor telemetry strongly contradicts genuine meteorological event")
        if is_spike:
            positive_points = min(positive_points * 0.15, 0.10)
            evidence.append("Single-point spike without neighbor co-occurrence contradicts physical weather")
        if is_comm:
            positive_points = min(positive_points * 0.15, 0.10)
            evidence.append("Telemetry communication dropout indicates transmission failure")

        # Normalize score
        event_score = float(np.clip(positive_points, 0.0, 1.0))

        # If strong meteorological signatures are present (rain >= 15 or wind >= 35 or temp >= 42),
        # ensure event score is at least 0.50 even if baseline anomaly detector didn't fully trigger
        if not (is_freeze or is_spike or is_comm):
            if (rain >= 15.0 and rh >= 70.0) or (wind >= 38.0) or (temp >= 42.0 and rh <= 50.0):
                event_score = max(event_score, 0.65)
            elif (rain >= 8.0 and rh >= 65.0) or (wind >= 28.0) or (temp >= 40.0 and rh <= 55.0):
                event_score = max(event_score, 0.45)

        return {
            "genuine_event_score": round(event_score, 4),
            "genuine_event_evidence": evidence,
        }
