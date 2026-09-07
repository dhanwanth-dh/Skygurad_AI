"""Central settings loader — resolves all paths relative to project root."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Project root is three levels up from this file: src/skyguard/config/settings.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r") as fh:
        return yaml.safe_load(fh) or {}


class Settings:
    """Lazy-loaded, merged view of all YAML config files."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._root = config_dir or PROJECT_ROOT / "configs"
        self._cache: dict[str, dict[str, Any]] = {}

    def _get(self, name: str) -> dict[str, Any]:
        if name not in self._cache:
            self._cache[name] = _load_yaml(self._root / f"{name}.yaml")
        return self._cache[name]

    @property
    def data(self) -> dict[str, Any]:
        return self._get("data")

    @property
    def features(self) -> dict[str, Any]:
        return self._get("features")

    @property
    def models(self) -> dict[str, Any]:
        return self._get("models")

    @property
    def thresholds(self) -> dict[str, Any]:
        return self._get("thresholds")

    def resolve(self, relative_path: str) -> Path:
        """Resolve a config-relative path against the project root."""
        return PROJECT_ROOT / relative_path

    @property
    def raw_data_path(self) -> Path:
        return self.resolve(self.data["raw_data_path"])

    @property
    def processed_dir(self) -> Path:
        return self.resolve(self.data["processed_dir"])

    @property
    def artifacts_dir(self) -> Path:
        return self.resolve(self.data["artifacts_dir"])

    @property
    def reports_dir(self) -> Path:
        return self.resolve(self.data["reports_dir"])

    @property
    def random_seed(self) -> int:
        return int(self.data.get("random_seed", 42))

    @property
    def sensor_columns(self) -> list[str]:
        return self.data["sensor_columns"]

    @property
    def physical_bounds(self) -> dict[str, list[float]]:
        return self.data["physical_bounds"]


settings = Settings()
