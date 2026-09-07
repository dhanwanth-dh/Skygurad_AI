#!/usr/bin/env python
"""Entry point: python scripts/predict.py -- accepts JSON from stdin or --input flag."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skyguard.config.settings import settings
from skyguard.inference.predictor import SkyGuardPredictor


SAMPLE_INPUT = {
    "timestamp": "2025-02-15 14:00:00",
    "station_id": "AWS_TN_01",
    "station_name": "Chennai Coastal AWS",
    "latitude": 13.0827,
    "longitude": 80.2707,
    "temperature_c": 32.5,
    "relative_humidity_pct": 65.0,
    "pressure_hpa": 1009.5,
    "wind_speed_kmh": 14.2,
    "rainfall_mm": 0.0,
}


def main() -> None:
    predictor = SkyGuardPredictor(settings.artifacts_dir)
    predictor.load()

    if len(sys.argv) > 1 and sys.argv[1] == "--input":
        with open(sys.argv[2]) as f:
            observation = json.load(f)
    else:
        observation = SAMPLE_INPUT

    result = predictor.predict_single(observation)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
