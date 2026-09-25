"""Historical Data Provider abstraction for SkyGuard AI.

Defines the interface for official meteorological data providers and the concrete
implementation for India Meteorological Department (IMD) historical telemetry.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from skyguard.services.imd_historical_client import IMDHistoricalClient
from skyguard.services.imd_normalizer import IMDNormalizer

logger = logging.getLogger("skyguard.services.historical_data_provider")


class HistoricalDataProvider(ABC):
    """Abstract base class for historical AWS data providers."""

    @abstractmethod
    def fetch(
        self,
        start_datetime: str,
        end_datetime: str,
        station_ids: Optional[list[str]] = None,
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        """Fetch historical observations for a date range and optional station list.

        Returns (normalized_records, error_or_limitation_message).
        """
        pass

    @abstractmethod
    def get_provider_status(self) -> dict[str, Any]:
        """Return provider status, authorized capabilities, and diagnostic info."""
        pass


class IMDHistoricalDataProvider(HistoricalDataProvider):
    """Concrete provider querying official IMD AWS endpoints with date-range parameters."""

    def __init__(self, client: Optional[IMDHistoricalClient] = None) -> None:
        self.client = client or IMDHistoricalClient()

    def fetch(
        self,
        start_datetime: str,
        end_datetime: str,
        station_ids: Optional[list[str]] = None,
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        """Fetch and normalize official IMD historical records for the specified window."""
        logger.info(
            "[IMDHistorical] Querying official IMD historical stream (%s to %s)...",
            start_datetime,
            end_datetime,
        )

        raw_records, err = self.client.fetch_historical_records(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            station_ids=station_ids,
        )

        if err:
            logger.warning("[IMDHistorical] %s", err)
            return [], err

        if not raw_records:
            msg = (
                f"Historical IMD data unavailable for requested period ({start_datetime} to {end_datetime}). "
                "Additional IMD historical-data access is required."
            )
            logger.info("[IMDHistorical] %s", msg)
            return [], msg

        normalized = IMDNormalizer.normalize_batch(raw_records)
        logger.info(
            "[IMDHistorical] Normalized %d historical observations from official IMD response",
            len(normalized),
        )
        return normalized, None

    def get_provider_status(self) -> dict[str, Any]:
        """Return IMD historical capability diagnostics."""
        return {
            "provider": "IMD Historical Data Provider",
            "source": "official_imd",
            "client_diagnostics": self.client.get_diagnostics(),
        }
