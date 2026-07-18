# tools/connectors/datadog_logs.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from tools.connectors.base import BaseLogConnector

logger = logging.getLogger(__name__)

# Datadog Logs API endpoint
DATADOG_LOGS_URL = "https://api.datadoghq.com/api/v2/logs/events/search"


class DatadogLogsConnector(BaseLogConnector):
    """Connector for Datadog Logs.

    Fetches logs from Datadog using API and Application keys.
    Credentials are retrieved from Google Cloud Secret Manager
    and passed in at construction time.
    """

    def __init__(self, credentials: dict, config_metadata: dict | None = None) -> None:
        """Initialise the Datadog connector with API credentials.

        Args:
            credentials: Dict containing api_key and app_key.
            config_metadata: Optional configuration metadata.
        """
        self._api_key = credentials.get("api_key")
        self._app_key = credentials.get("app_key")
        self._site = credentials.get("site", "datadoghq.com")
        self._config_metadata = config_metadata or {}

    async def fetch_logs(
        self,
        service_name: str,
        window_start: str,
        window_end: str,
    ) -> str:
        """Fetch logs from Datadog for a service and time window.

        Args:
            service_name: Datadog service tag value to filter by.
            window_start: ISO format start of investigation window.
            window_end: ISO format end of investigation window.

        Returns:
            Log entries as a plain string, one entry per line.

        Raises:
            RuntimeError: If Datadog credentials are invalid or
                         API call fails.
        """
        try:
            headers = {
                "DD-API-KEY": self._api_key,
                "DD-APPLICATION-KEY": self._app_key,
                "Content-Type": "application/json",
            }

            # Datadog query — filter by service and error status
            query_body = {
                "filter": {
                    "query": (
                        f"service:{service_name} "
                        f"(status:error OR status:critical)"
                    ),
                    "from": window_start,
                    "to": window_end,
                },
                "sort": "timestamp",
                "page": {
                    "limit": 5000,
                },
            }

            logger.info(
                f"Fetching Datadog logs for service '{service_name}' "
                f"between {window_start} and {window_end}"
            )

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://api.{self._site}/api/v2/logs/events/search",
                    headers=headers,
                    json=query_body,
                )

            if response.status_code == 403:
                raise RuntimeError(
                    "Datadog authentication failed — check api_key and app_key"
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Datadog API error {response.status_code}: "
                    f"{response.text}"
                )

            data = response.json()
            events = data.get("data", [])

            if not events:
                logger.warning(
                    f"No Datadog log events found for service "
                    f"'{service_name}'"
                )
                return ""

            # Format events as plain text lines
            log_lines = []
            for event in events:
                attributes = event.get("attributes", {})
                timestamp = attributes.get("timestamp", "unknown")
                status = attributes.get("status", "ERROR").upper()
                message = attributes.get("message", "").strip()
                log_lines.append(
                    f"{timestamp} {status} {service_name} {message}"
                )

            raw_logs = "\n".join(log_lines)
            logger.info(
                f"Fetched {len(events)} Datadog log events "
                f"for service '{service_name}'"
            )
            return raw_logs

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Datadog logs fetch failed: {e}")
            raise RuntimeError(f"Datadog error: {e}") from e

    async def validate_credentials(self) -> bool:
        """Verify Datadog credentials are present.

        Returns:
            True if both api_key and app_key are present.
        """
        if not self._api_key:
            logger.warning("Datadog connector missing api_key")
            return False
        if not self._app_key:
            logger.warning("Datadog connector missing app_key")
            return False
        return True