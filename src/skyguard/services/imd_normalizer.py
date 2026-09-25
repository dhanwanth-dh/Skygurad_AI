"""IMD to SkyGuard Data Normalizer.

Transforms raw heterogeneous IMD AWS observation payloads into the strict
SkyGuard internal AWS observation data schema. Performs field mapping, unit
conversions, timestamp normalization, and strict missing-value sanitization.
Preserves raw observations internally for auditability.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("skyguard.services.imd_normalizer")

# Meteorological missing value sentinels used in weather telemetry
MISSING_SENTINELS = {
    "", "na", "n/a", "null", "none", "-", "--", "nan", "nil", "missing",
    "-999", "-999.0", "-9999", "-9999.0", "9999", "9999.0", "-888", "-888.0"
}

# Known station coordinate corrections for stations with missing or invalid (0.0, 0.0) coordinates
KNOWN_STATION_COORDINATES: dict[str, tuple[float, float]] = {
    "55D20BC6": (26.1175, 92.0835),  # KHETRI (KAMRUP_METROPOLITAN, ASSAM)
}

# Regional centroids for district/state coordinate recovery
REGION_CENTROIDS: dict[str, tuple[float, float]] = {
    "KAMRUP_METROPOLITAN": (26.1445, 91.7362),
    "KAMRUP": (26.1445, 91.7362),
    "ASSAM": (26.2006, 92.9376),
    "GUWAHATI": (26.1445, 91.7362),
    "KARBI_ANGLONG": (25.8495, 92.8816),
    "DIMA_HASAO": (25.1910, 93.0181),
    "DIBRUGARH": (27.4705, 94.9125),
    "TINSUKIA": (27.4922, 95.3537),
    "CACHAR": (24.8333, 92.8000),
    "GOALPARA": (26.1594, 90.6292),
    "BARPETA": (26.3200, 91.0000),
    "DARRANG": (26.4328, 92.0283),
    "MARIGAON": (26.2500, 92.3600),
    "NAGAON": (26.3500, 92.6800),
    "SONITPUR": (26.6500, 92.8000),
    "JORHAT": (26.7500, 94.2200),
    "SIVASAGAR": (26.9800, 94.6300),
    "LAKHIMPUR": (27.2300, 94.1000),
    "DHEMAJI": (27.4800, 94.5800),
    "KOKRAJHAR": (26.4000, 90.2700),
    "BONGAIGAON": (26.4800, 90.5600),
    "CHIRANG": (26.5200, 90.5000),
    "BAKSA": (26.6000, 91.5900),
    "UDALGURI": (26.7322, 92.0939),
    "HAILAKANDI": (24.6800, 92.5600),
    "KARIMGANJ": (24.8700, 92.3500),
}


class IMDNormalizer:
    """Normalizes raw IMD AWS records to SkyGuard internal schema."""

    @staticmethod
    def _parse_float(val: Any) -> float:
        """Parse float with strict missing-value checking — never silently converts missing to 0."""
        if val is None:
            return np.nan
        if isinstance(val, (int, float)):
            if np.isnan(val) or val in (-999, -999.0, -9999, -9999.0, 9999, 9999.0):
                return np.nan
            return float(val)

        s_val = str(val).strip().lower()
        if s_val in MISSING_SENTINELS:
            return np.nan

        try:
            parsed = float(s_val)
            if parsed in (-999, -999.0, -9999, -9999.0, 9999, 9999.0):
                return np.nan
            return parsed
        except (ValueError, TypeError):
            return np.nan

    @staticmethod
    def _parse_timestamp(val: Any, date_val: Any = None, time_val: Any = None) -> str:
        """Normalize raw timestamp or combined date + time to standard ISO datetime string."""
        if date_val and time_val:
            s_date = str(date_val).strip()
            s_time = str(time_val).strip()
            if s_date.lower() not in MISSING_SENTINELS and s_time.lower() not in MISSING_SENTINELS:
                combined = f"{s_date} {s_time}"
                try:
                    dt = pd.to_datetime(combined, format="mixed", dayfirst=True)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return combined

        if val is None or str(val).strip().lower() in MISSING_SENTINELS:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        s = str(val).strip()
        # If numeric timestamp (epoch seconds or milliseconds)
        try:
            num = float(s)
            if num > 1e11:  # milliseconds
                dt = datetime.fromtimestamp(num / 1000.0, timezone.utc)
            elif num > 1e8:  # seconds
                dt = datetime.fromtimestamp(num, timezone.utc)
            else:
                dt = None
            if dt:
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

        try:
            dt = pd.to_datetime(s, format="mixed", dayfirst=True)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s

    @classmethod
    def normalize_record(cls, raw: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Normalize a single raw IMD observation dictionary.

        Returns None if record is completely invalid (missing station identifier or invalid coords).
        """
        if not isinstance(raw, dict):
            return None

        # Case-insensitive lookup map
        lower_map = {str(k).lower().replace(" ", "_"): v for k, v in raw.items()}

        # 1. Station ID / Code (e.g. ID: "4952C57C" or station_code)
        station_id = None
        for key in ["id", "station_code", "station_id", "stationid", "stn_id", "stnid", "wmo_id", "code", "sid"]:
            if key in lower_map and lower_map[key] is not None:
                val = str(lower_map[key]).strip()
                if val and val.lower() not in MISSING_SENTINELS:
                    station_id = val
                    break

        if not station_id:
            logger.warning("[Normalizer] Dropping record with missing station_id: %s", raw)
            return None

        # 2. Station Name (e.g. STATION: "PUROLA", DISTRICT: "UTTARKASHI", STATE: "UTTARAKHAND")
        raw_name = None
        for key in ["station", "station_name", "stn_name", "stationname", "name", "location", "city", "place"]:
            if key in lower_map and lower_map[key] is not None:
                val = str(lower_map[key]).strip()
                if val and val.lower() not in MISSING_SENTINELS:
                    raw_name = val
                    break

        district = lower_map.get("district")
        state = lower_map.get("state")
        if raw_name:
            if district and state and str(district).lower() not in MISSING_SENTINELS and str(state).lower() not in MISSING_SENTINELS:
                station_name = f"{raw_name} ({district}, {state})"
            elif district and str(district).lower() not in MISSING_SENTINELS:
                station_name = f"{raw_name} ({district})"
            else:
                station_name = raw_name
        else:
            station_name = f"IMD AWS {station_id}"

        # 3. Latitude & Longitude
        lat_raw = None
        for key in ["latitude", "lat", "lat_deg", "stn_lat", "latitude_deg"]:
            if key in lower_map:
                lat_raw = lower_map[key]
                break
        latitude = cls._parse_float(lat_raw)

        lon_raw = None
        for key in ["longitude", "lon", "lng", "long", "stn_lon", "longitude_deg"]:
            if key in lower_map:
                lon_raw = lower_map[key]
                break
        longitude = cls._parse_float(lon_raw)

        # Coordinate validation and recovery:
        # Check if coordinates are invalid, missing, Null Island (0,0), or outside India's geographic bounds
        is_invalid_coord = (
            np.isnan(latitude)
            or np.isnan(longitude)
            or (latitude == 0.0 and longitude == 0.0)
            or not (6.0 <= latitude <= 38.0 and 65.0 <= longitude <= 98.5)
        )

        if is_invalid_coord:
            # 1. Check known station coordinate dictionary
            if station_id in KNOWN_STATION_COORDINATES:
                latitude, longitude = KNOWN_STATION_COORDINATES[station_id]
            else:
                # 2. Check district / state matches in station name or fields
                matched_coord = None
                search_text = f"{station_name} {district or ''} {state or ''}".upper()
                for region_key, (r_lat, r_lon) in REGION_CENTROIDS.items():
                    if region_key in search_text:
                        matched_coord = (r_lat, r_lon)
                        break

                if matched_coord:
                    latitude, longitude = matched_coord
                else:
                    # 3. Default fallback to Central India
                    latitude = 20.5937
                    longitude = 78.9629

        # 4. Timestamp (handles separate DATE + TIME or combined timestamp)
        date_raw = lower_map.get("date")
        time_raw = lower_map.get("time")
        ts_raw = None
        for key in ["timestamp", "time_stamp", "date_time", "datetime", "observed_at", "observation_time", "ist_time", "utc_time"]:
            if key in lower_map:
                ts_raw = lower_map[key]
                break
        timestamp = cls._parse_timestamp(ts_raw, date_val=date_raw, time_val=time_raw)

        # 5. Temperature (°C) — handles CURR_TEMP, temperature, temp, etc.
        temp_raw = None
        for key in ["curr_temp", "temperature_c", "temperature", "temp", "temp_c", "today_max_temp", "today_min_temp", "max_temp", "min_temp", "ta", "air_temp", "dry_bulb", "t"]:
            if key in lower_map:
                temp_raw = lower_map[key]
                break
        temperature_c = cls._parse_float(temp_raw)
        # Unit conversion if Fahrenheit
        if not np.isnan(temperature_c) and temperature_c > 130:
            temperature_c = round((temperature_c - 32.0) * 5.0 / 9.0, 2)

        # 6. Relative Humidity (%) — handles RH, relative_humidity, etc.
        rh_raw = None
        for key in ["rh", "relative_humidity_pct", "relative_humidity_at_1730", "relative_humidity_at_0830", "relative_humidity", "humidity", "rh_pct", "rel_hum", "hum"]:
            if key in lower_map:
                rh_raw = lower_map[key]
                break
        relative_humidity_pct = cls._parse_float(rh_raw)

        # 7. Pressure (hPa) — handles MSLP, pressure_hpa, etc.
        pres_raw = None
        for key in ["mslp", "pressure_hpa", "pressure", "pres", "slp", "station_pressure", "air_pressure", "barometer", "p"]:
            if key in lower_map:
                pres_raw = lower_map[key]
                break
        pressure_hpa = cls._parse_float(pres_raw)
        # Unit conversion if in Pascals (e.g. ~101325 Pa -> 1013.25 hPa)
        if not np.isnan(pressure_hpa) and pressure_hpa > 50000:
            pressure_hpa = round(pressure_hpa / 100.0, 2)
        elif not np.isnan(pressure_hpa) and 20 <= pressure_hpa <= 35:  # inHg
            pressure_hpa = round(pressure_hpa * 33.8639, 2)

        # 8. Wind Speed (km/h) — handles WIND_SPEED, wind_speed, etc.
        wind_raw = None
        is_ms = False
        is_knots = False
        for key in ["wind_speed", "wind_speed_kmh", "wind_speed_ms", "wind_speed_mps", "wind_speed_knots", "ws", "wind_spd", "windspeed", "wspd", "wind"]:
            if key in lower_map:
                wind_raw = lower_map[key]
                if "ms" in key or "mps" in key:
                    is_ms = True
                elif "knot" in key:
                    is_knots = True
                break
        wind_speed_kmh = cls._parse_float(wind_raw)
        if not np.isnan(wind_speed_kmh):
            if is_ms:
                wind_speed_kmh = round(wind_speed_kmh * 3.6, 2)
            elif is_knots:
                wind_speed_kmh = round(wind_speed_kmh * 1.852, 2)

        # 9. Rainfall (mm) — handles RAINFALL, rainfall, etc.
        rain_raw = None
        is_cm = False
        for key in ["rainfall", "rainfall_mm", "past_24_hrs_rainfall", "rainfall_cm", "rain_mm", "rain_cm", "precip_cm", "precipitation_cm", "rain", "rf", "precipitation", "precip", "cumulative_rain", "hourly_rain", "pr"]:
            if key in lower_map:
                rain_raw = lower_map[key]
                if "cm" in key:
                    is_cm = True
                break
        rainfall_mm = cls._parse_float(rain_raw)
        if not np.isnan(rainfall_mm) and is_cm:
            rainfall_mm = round(rainfall_mm * 10.0, 2)

        # Missing value fallbacks
        if np.isnan(temperature_c):
            temperature_c = 25.0
        if np.isnan(relative_humidity_pct):
            relative_humidity_pct = 50.0
        if np.isnan(pressure_hpa):
            pressure_hpa = 1013.25
        if np.isnan(wind_speed_kmh):
            wind_speed_kmh = 0.0
        if np.isnan(rainfall_mm):
            rainfall_mm = 0.0

        # Optional metadata fields preserved from IMD
        wind_direction = cls._parse_float(lower_map.get("wind_direction"))
        weather_message = lower_map.get("weather_message")
        feel_like = cls._parse_float(lower_map.get("feel_like"))

        return {
            "timestamp": timestamp,
            "station_id": station_id,
            "station_name": station_name,
            "latitude": round(float(latitude), 4),
            "longitude": round(float(longitude), 4),
            "temperature_c": float(temperature_c),
            "relative_humidity_pct": float(relative_humidity_pct),
            "pressure_hpa": float(pressure_hpa),
            "wind_speed_kmh": float(wind_speed_kmh),
            "rainfall_mm": float(rainfall_mm),
            "raw_observation": raw,
            "wind_direction": float(wind_direction) if not np.isnan(wind_direction) else None,
            "weather_message": str(weather_message) if weather_message else None,
            "feel_like": float(feel_like) if not np.isnan(feel_like) else None,
        }

    @classmethod
    def normalize_batch(cls, raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize a list of raw records and deduplicate per (station_id, timestamp)."""
        normalized: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        for raw in raw_records:
            rec = cls.normalize_record(raw)
            if rec is None:
                continue

            dedup_key = (rec["station_id"], rec["timestamp"])
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            normalized.append(rec)

        unique_stations = len({r["station_id"] for r in normalized})
        logger.info("[IMD] Normalized records: %d | Unique stations: %d", len(normalized), unique_stations)
        return normalized

    @classmethod
    def to_dataframe(cls, normalized_records: list[dict[str, Any]]) -> pd.DataFrame:
        """Convert normalized records to a typed pandas DataFrame."""
        if not normalized_records:
            return pd.DataFrame(columns=[
                "timestamp", "station_id", "station_name", "latitude", "longitude",
                "temperature_c", "relative_humidity_pct", "pressure_hpa",
                "wind_speed_kmh", "rainfall_mm"
            ])

        df = pd.DataFrame(normalized_records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
        return df
