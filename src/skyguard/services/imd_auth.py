"""IMD Authentication Service.

Handles secure OAuth JWT authentication against the official IMD API.
Caches and auto-refreshes JWT tokens in backend memory without logging or leaking credentials.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional
import requests

from skyguard.config.settings import settings

logger = logging.getLogger("skyguard.services.imd_auth")


class IMDAuthService:
    """Manages JWT generation, caching, and auto-refresh for official IMD API communication."""

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        base_url: Optional[str] = None,
        token_endpoint: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.email = email if email is not None else settings.imd_email
        self.password = password if password is not None else settings.imd_password
        self.base_url = (base_url or settings.imd_base_url).rstrip("/")
        self.token_endpoint = token_endpoint or settings.imd_token_endpoint
        if not self.token_endpoint.startswith("/"):
            self.token_endpoint = "/" + self.token_endpoint
        self.timeout = timeout if timeout is not None else settings.imd_timeout_seconds

        self._cached_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None

    def get_valid_token(self, force_refresh: bool = False) -> tuple[Optional[str], Optional[str]]:
        """Retrieve a valid JWT token, fetching a new one only when expired or forced.

        Returns
        -------
        tuple[Optional[str], Optional[str]]
            Tuple of (jwt_token, error_message).
        """
        # If static token is provided in environment, use it directly
        if settings.imd_jwt_token and not (self.email and self.password):
            return settings.imd_jwt_token, None

        with self._lock:
            now = time.time()
            # If cached token is still valid for at least 60 more seconds, reuse it
            if not force_refresh and self._cached_token and now < (self._expires_at - 60):
                return self._cached_token, None

            if not self.email or not self.password:
                err_msg = "IMD credentials (email/password) not configured in environment."
                self._last_error = err_msg
                return None, err_msg

            url = f"{self.base_url}{self.token_endpoint}"
            logger.info("[IMD] Requesting JWT token from authentication endpoint: %s", self.token_endpoint)

            try:
                payload = {
                    "email": self.email,
                    "password": self.password,
                }
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "SkyGuard-AI-Ingestion-Engine/2.0",
                }

                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)

                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("access_token") or data.get("token")
                    expires_in = int(data.get("expires_in", 3600))

                    if token:
                        self._cached_token = token
                        self._expires_at = time.time() + expires_in
                        self._last_error = None
                        logger.info("[IMD] JWT generated successfully (valid for %d seconds).", expires_in)
                        return self._cached_token, None
                    else:
                        err_msg = "No access_token field found in IMD authentication response."
                        logger.error("[IMD] %s", err_msg)
                        self._last_error = err_msg
                        return None, err_msg
                else:
                    err_msg = f"IMD JWT generation failed with HTTP {resp.status_code}: {resp.text[:200]}"
                    logger.warning("[IMD] %s", err_msg)
                    self._last_error = err_msg
                    return None, err_msg

            except requests.exceptions.Timeout:
                err_msg = f"IMD OAuth token request timed out after {self.timeout}s"
                logger.error("[IMD] %s", err_msg)
                self._last_error = err_msg
                return None, err_msg
            except requests.exceptions.ConnectionError as conn_err:
                err_msg = f"IMD OAuth connection failure: {conn_err}"
                logger.error("[IMD] %s", err_msg)
                self._last_error = err_msg
                return None, err_msg
            except Exception as exc:
                err_msg = f"Unexpected error during IMD JWT authentication: {exc}"
                logger.exception("[IMD] %s", err_msg)
                self._last_error = err_msg
                return None, err_msg

    def is_authenticated(self) -> bool:
        """Check if a valid unexpired JWT token is currently cached."""
        return bool(self._cached_token and time.time() < (self._expires_at - 60))

    def get_diagnostics(self) -> dict:
        """Return safe authentication diagnostics."""
        return {
            "has_email": bool(self.email),
            "has_password": bool(self.password),
            "is_authenticated": self.is_authenticated(),
            "expires_in_seconds": max(0, int(self._expires_at - time.time())) if self._cached_token else 0,
            "last_error": self._last_error,
        }
