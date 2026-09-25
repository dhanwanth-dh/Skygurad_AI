"""Central settings loader — resolves all paths relative to project root and loads environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Project root is three levels up from this file: src/skyguard/config/settings.py
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_env_file(path: Path) -> None:
    """Load key-value pairs from .env file into os.environ if not already set."""
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as exc:
        logger.debug("Could not read .env file at %s: %s", path, exc)


# Automatically load .env from project root at import time
_load_env_file(PROJECT_ROOT / ".env")


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Settings:
    """Lazy-loaded, merged view of all YAML config files and environment settings."""

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

    # ── IMD & Data Source Settings ─────────────────────────────────────────────

    @property
    def data_source(self) -> str:
        """Data source: 'imd' (default live IMD API) or 'synthetic' (local CSV)."""
        return os.environ.get("DATA_SOURCE", "imd").lower().strip()

    @property
    def imd_email(self) -> str:
        """Registered IMD portal email."""
        return os.environ.get("IMD_EMAIL", "").strip()

    @property
    def imd_password(self) -> str:
        """Registered IMD portal password."""
        return os.environ.get("IMD_PASSWORD", "").strip()

    @property
    def imd_api_key(self) -> str:
        """Official IMD API key from environment."""
        return os.environ.get("IMD_API_KEY", "").strip()

    @property
    def imd_jwt_token(self) -> str:
        """Optional static IMD JWT bearer token from environment."""
        return os.environ.get("IMD_JWT_TOKEN", "").strip()

    @property
    def imd_base_url(self) -> str:
        """IMD API base URL."""
        return os.environ.get("IMD_BASE_URL", "https://api.imd.gov.in").rstrip("/")

    @property
    def imd_token_endpoint(self) -> str:
        """IMD OAuth token endpoint path."""
        ep = os.environ.get("IMD_TOKEN_ENDPOINT", "/api/oauth/token.php").strip()
        if not ep.startswith("/"):
            ep = "/" + ep
        return ep

    @property
    def imd_aws_endpoint(self) -> str:
        """IMD AWS data endpoint path."""
        ep = os.environ.get("IMD_AWS_ENDPOINT", "/api/v1/aws_data").strip()
        if not ep.startswith("/"):
            ep = "/" + ep
        return ep

    @property
    def imd_poll_interval_seconds(self) -> int:
        """Polling interval in seconds for live IMD observations."""
        try:
            return int(os.environ.get("IMD_POLL_INTERVAL_SECONDS", "300"))
        except ValueError:
            return 300

    @property
    def imd_timeout_seconds(self) -> int:
        """HTTP request timeout in seconds for IMD API requests."""
        try:
            return int(os.environ.get("IMD_TIMEOUT_SECONDS", "30"))
        except ValueError:
            return 30

    # ── Historical Data & Training Settings ────────────────────────────────────

    @property
    def historical_db_path(self) -> Path:
        """Path to persistent historical SQLite database."""
        default_path = PROJECT_ROOT / "data" / "historical_aws.db"
        p = os.environ.get("HISTORICAL_DB_PATH", str(default_path))
        return Path(p)

    @property
    def historical_years(self) -> int:
        """Target historical depth in years (default 15 years)."""
        try:
            return int(os.environ.get("HISTORICAL_YEARS", "15"))
        except ValueError:
            return 15

    @property
    def historical_export_dir(self) -> Path:
        """Directory for partitioned historical Excel and CSV exports."""
        default_path = PROJECT_ROOT / "historical_data"
        p = os.environ.get("HISTORICAL_EXPORT_DIR", str(default_path))
        return Path(p)


settings = Settings()

