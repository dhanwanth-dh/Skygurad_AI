"""Dedicated India Meteorological Department (IMD) AWS API Client.

Handles HTTP communication, authentication with API Key + OAuth JWT Bearer token,
timeout management, rate-limit resilience, and robust error handling.
Credentials, secrets, and JWT tokens are strictly protected and never logged or exposed.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from skyguard.config.settings import settings
from skyguard.services.imd_auth import IMDAuthService

logger = logging.getLogger("skyguard.services.imd_client")


class IMDClient:
    """Client for fetching live AWS weather observations from the official IMD API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        auth_service: Optional[IMDAuthService] = None,
        base_url: Optional[str] = None,
        aws_endpoint: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.imd_api_key
        self.auth_service = auth_service or IMDAuthService()
        self.base_url = (base_url or settings.imd_base_url).rstrip("/")
        self.aws_endpoint = aws_endpoint or settings.imd_aws_endpoint
        if not self.aws_endpoint.startswith("/"):
            self.aws_endpoint = "/" + self.aws_endpoint
        self.timeout = timeout if timeout is not None else settings.imd_timeout_seconds

        self._session = requests.Session()
        retries = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=10)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._last_status_code: Optional[int] = None
        self._last_error_message: Optional[str] = None

    def fetch_raw_observations(self, station_id: Optional[str] = None) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
        """Fetch raw AWS observations from IMD API using API Key + JWT Bearer token.

        Parameters
        ----------
        station_id : Optional[str]
            Optional specific station identifier to filter.

        Returns
        -------
        tuple[Optional[list[dict[str, Any]]], Optional[str]]
            Tuple of (raw_records_list, error_message). If successful, error_message is None.
        """
        # Step 1: Obtain a valid JWT token
        jwt_token, auth_err = self.auth_service.get_valid_token()
        if auth_err and not jwt_token:
            self._last_error_message = f"JWT authentication failed: {auth_err}"
            logger.warning("[IMD] %s", self._last_error_message)
            return None, self._last_error_message

        # Step 2: Build headers
        headers = {
            "Accept": "application/json",
            "User-Agent": "SkyGuard-AI-Ingestion-Engine/2.0",
        }
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"

        url = f"{self.base_url}{self.aws_endpoint}"
        params: dict[str, Any] = {}
        if station_id:
            params["id"] = station_id
            params["sid"] = station_id

        logger.info("[IMD] Requesting AWS data from endpoint: %s", self.aws_endpoint)

        try:
            response = self._session.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            self._last_status_code = response.status_code
            logger.info("[IMD] Response status: %d", response.status_code)

            # If 401 Unauthorized, try refreshing JWT once and retry request
            if response.status_code in (401, 403) and self.auth_service:
                logger.info("[IMD] Received %d from API, attempting forced JWT refresh...", response.status_code)
                new_jwt, ref_err = self.auth_service.get_valid_token(force_refresh=True)
                if new_jwt:
                    headers["Authorization"] = f"Bearer {new_jwt}"
                    response = self._session.get(url, headers=headers, params=params, timeout=self.timeout)
                    self._last_status_code = response.status_code
                    logger.info("[IMD] Retry response status: %d", response.status_code)

            if response.status_code == 200:
                try:
                    data = response.json()
                    records = self._extract_records_from_payload(data)
                    logger.info("[IMD] Raw records received: %d", len(records))
                    self._last_error_message = None
                    return records, None
                except Exception as json_err:
                    err_msg = f"Failed to parse IMD response as JSON: {json_err}"
                    logger.error("[IMD] %s", err_msg)
                    self._last_error_message = err_msg
                    return None, err_msg

            elif response.status_code in (401, 403):
                err_msg = f"Authentication failed (HTTP {response.status_code}): {response.text[:200]}"
                logger.warning("[IMD] %s", err_msg)
                self._last_error_message = err_msg
                return None, err_msg

            elif response.status_code == 429:
                err_msg = "IMD API rate limit exceeded (HTTP 429)"
                logger.warning("[IMD] %s", err_msg)
                self._last_error_message = err_msg
                return None, err_msg

            else:
                err_msg = f"IMD API request failed with HTTP {response.status_code}: {response.text[:200]}"
                logger.warning("[IMD] %s", err_msg)
                self._last_error_message = err_msg
                return None, err_msg

        except requests.exceptions.Timeout:
            err_msg = f"IMD API request timed out after {self.timeout}s"
            logger.error("[IMD] %s", err_msg)
            self._last_status_code = None
            self._last_error_message = err_msg
            return None, err_msg

        except requests.exceptions.ConnectionError as conn_err:
            err_msg = f"IMD connection failure: {conn_err}"
            logger.error("[IMD] %s", err_msg)
            self._last_status_code = None
            self._last_error_message = err_msg
            return None, err_msg

        except Exception as exc:
            err_msg = f"Unexpected error while contacting IMD API: {exc}"
            logger.exception("[IMD] %s", err_msg)
            self._last_status_code = None
            self._last_error_message = err_msg
            return None, err_msg

    def _extract_records_from_payload(self, data: Any) -> list[dict[str, Any]]:
        """Extract a flat list of station observation records from various IMD response wrappers."""
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]

        if isinstance(data, dict):
            for key in ["data", "stations", "observations", "records", "result", "aws_data", "items"]:
                if key in data and isinstance(data[key], list):
                    return [r for r in data[key] if isinstance(r, dict)]

            if any(k.lower() in [k2.lower() for k2 in data.keys()] for k in ["id", "station_id", "station_code", "station", "temp", "curr_temp", "latitude", "lat"]):
                return [data]

        return []

    def get_diagnostics(self) -> dict[str, Any]:
        """Return non-sensitive client diagnostics."""
        auth_diag = self.auth_service.get_diagnostics() if self.auth_service else {}
        return {
            "base_url": self.base_url,
            "endpoint": self.aws_endpoint,
            "has_api_key": bool(self.api_key),
            "auth": auth_diag,
            "timeout": self.timeout,
            "last_status_code": self._last_status_code,
            "last_error": self._last_error_message,
        }
