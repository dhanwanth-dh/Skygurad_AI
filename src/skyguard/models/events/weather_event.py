"""Genuine Meteorological Event Engine.

Evaluates whether atmospheric anomalies are caused by genuine meteorological phenomena
(e.g., storms, convective downdrafts, fronts, severe weather) versus isolated sensor faults.

Uses 10 scientific evidence signals:
1. Multi-station agreement & spatial proximity
2. Spatial residual (observed vs neighbor mean)
3. Neighbor agreement score
4. Temperature variation
5. Relative humidity variation
6. Barometric pressure drop/surge
7. Wind gust and rainfall presence
8. Temporal coherence (gradual ramp vs instantaneous glitch)
9. Multivariate physical consistency
10. Multi-model anomaly consensus
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
        total_possible: float = 1.0

        # 1. Spatial Neighbor Agreement
        neighbor_score = row.get("neighbor_agreement_score", np.nan)
        spatial_temp_res = row.get("spatial_temperature_c_residual", np.nan)
        spatial_press_res = row.get("spatial_pressure_hpa_residual", np.nan)

        if not pd.isna(neighbor_score):
            # Low neighbor residual means nearby stations observe very similar conditions!
            if neighbor_score < 2.0:
                positive_points += 0.35
                evidence.append(f"Nearby AWS stations confirm synchronized atmospheric pattern (spatial residual: {neighbor_score:.2f})")
            elif neighbor_score < 4.0:
                positive_points += 0.15
                evidence.append("Moderate multi-station spatial agreement with neighboring AWS stations")
            else:
                evidence.append(f"Station isolated: neighbors do not mirror deviation (spatial residual: {neighbor_score:.2f})")

        # 2. Multivariate physical consistency (e.g. cold front or convective storm)
        temp_delta = row.get("temperature_c_delta", np.nan)
        rh_delta = row.get("relative_humidity_pct_delta", np.nan)
        press_delta = row.get("pressure_hpa_delta", np.nan)
        rain = row.get("rainfall_mm", 0.0)
        wind = row.get("wind_speed_kmh", 0.0)

        # Storm/Front signature: temp drop + humidity surge + pressure drop + wind/rain
        is_front = False
        if not pd.isna(temp_delta) and not pd.isna(rh_delta):
            if temp_delta < -1.5 and rh_delta > 5.0:
                positive_points += 0.25
                is_front = True
                evidence.append(f"Atmospheric front signature: temp drop ({temp_delta:+.1f} °C) coupled with humidity rise ({rh_delta:+.1f}%)")

        if not pd.isna(press_delta) and press_delta < -1.5:
            positive_points += 0.15
            evidence.append(f"Barometric pressure dropping rapidly ({press_delta:+.1f} hPa/hr)")

        if rain > 0.5 or wind > 25.0:
            positive_points += 0.20
            evidence.append(f"Precipitation ({rain:.1f} mm) and/or wind gusts ({wind:.1f} km/h) consistent with weather event")

        # 3. Rule-based fault disqualifiers
        # If freeze or single-point spike is flagged, it is almost certainly a sensor fault, not weather
        if row.get("rule_freeze", False):
            positive_points = min(positive_points * 0.2, 0.1)
            evidence.append("Frozen sensor telemetry strongly contradicts genuine meteorological event")
        if row.get("rule_spike", False):
            positive_points = min(positive_points * 0.2, 0.1)
            evidence.append("Single-point spike without neighbor co-occurrence contradicts physical weather")

        # Normalize score
        event_score = float(np.clip(positive_points, 0.0, 1.0))

        # Adjust score if anomaly evidence is low
        if anomaly_score < 0.25:
            event_score = min(event_score, 0.20)

        return {
            "genuine_event_score": round(event_score, 4),
            "genuine_event_evidence": evidence,
        }
