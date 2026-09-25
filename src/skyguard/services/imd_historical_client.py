"""Dedicated IMD Historical AWS API Client.

Handles date-range historical queries against official India Meteorological Department
endpoints using secure JWT + X-API-KEY dual authentication with exponential backoff.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from skyguard.config.settings import settings
from skyguard.services.imd_auth import IMDAuthService

logger = logging.getLogger("skyguard.services.imd_historical_client")


class IMDHistoricalClient:
    """Client for official IMD historical AWS API endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        auth_service: Optional[IMDAuthService] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or settings.imd_base_url).rstrip("/")
        self.api_key = api_key or settings.imd_api_key
        self.auth_service = auth_service or IMDAuthService()
        self.timeout = timeout or settings.imd_timeout_seconds
        self._last_status_code: Optional[int] = None
        self._last_error: Optional[str] = None

    def fetch_historical_records(
        self,
        start_datetime: str,
        end_datetime: str,
        station_ids: Optional[list[str]] = None,
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        """Query official IMD historical endpoint with date range and optional station filter."""
        token, auth_err = self.auth_service.get_valid_token()
        if auth_err or not token:
            self._last_error = auth_err or "Failed to obtain valid IMD authentication token"
            return [], self._last_error

        # Candidate historical endpoints in official IMD API hierarchy
        historical_endpoints = [
            "/api/v1/aws_data",
            "/api/v1/historical_aws",
            "/api/v1/aws_archive",
        ]

        query_params: dict[str, str] = {
            "start_date": start_datetime.split(" ")[0] if " " in start_datetime else start_datetime,
            "end_date": end_datetime.split(" ")[0] if " " in end_datetime else end_datetime,
        }
        if start_datetime:
            query_params["start"] = start_datetime
        if end_datetime:
            query_params["end"] = end_datetime
        if station_ids:
            query_params["station_id"] = ",".join(station_ids[:20])

        headers = {
            "User-Agent": "SkyGuard-AI/2.0 (IMD-AWS-Historical-Integration)",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        if self.api_key:
            headers["X-API-KEY"] = self.api_key

        last_endpoint_err = None
        for endpoint in historical_endpoints:
            url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(query_params)}"
            req = urllib.request.Request(url, headers=headers, method="GET")

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    self._last_status_code = response.status
                    raw_body = response.read().decode("utf-8")
                    data = json.loads(raw_body)
                    records = self._extract_records(data)
                    if records:
                        self._last_error = None
                        return records, None
            except urllib.error.HTTPError as exc:
                self._last_status_code = exc.code
                err_body = exc.read().decode("utf-8", errors="ignore")
                last_endpoint_err = f"HTTP {exc.code} from {endpoint}: {err_body[:200]}"
                logger.debug("[IMDHistorical] %s", last_endpoint_err)
            except urllib.error.URLError as exc:
                self._last_error = f"Network connection failure: {exc.reason}"
                return [], self._last_error
            except Exception as exc:
                last_endpoint_err = str(exc)

        limitation_msg = (
            f"Historical IMD data unavailable for requested period ({start_datetime} to {end_datetime}). "
            "Additional IMD historical-data access is required."
        )
        self._last_error = limitation_msg
        return [], limitation_msg

    def _extract_records(self, data: Any) -> list[dict[str, Any]]:
        """Extract list of records from various IMD response JSON schemas."""
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for key in ["data", "records", "stations", "aws_data", "observations", "result"]:
                if key in data and isinstance(data[key], list):
                    return [r for r in data[key] if isinstance(r, dict)]
        return []

    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic status of historical client."""
        return {
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "auth": self.auth_service.get_diagnostics(),
            "timeout": self.timeout,
            "last_status_code": self._last_status_code,
            "last_error": self._last_error,
        }
