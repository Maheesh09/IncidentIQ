# tools/connectors/gcp_logging.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from tools.connectors.base import BaseLogConnector

logger = logging.getLogger(__name__)


class GCPLoggingConnector(BaseLogConnector):
    """Connector for Google Cloud Logging.

    Fetches logs from GCP Cloud Logging using a service account.
    Credentials are retrieved from Google Cloud Secret Manager
    and passed in at construction time.
    """

    def __init__(self, credentials: dict) -> None:
        """Initialise the GCP connector with service account credentials.

        Args:
            credentials: Dict containing project_id and
                        service_account_key (JSON string or dict).
        """
        self._project_id = credentials.get("project_id")
        self._service_account_key = credentials.get("service_account_key")

    async def fetch_logs(
        self,
        service_name: str,
        window_start: str,
        window_end: str,
    ) -> str:
        """Fetch logs from GCP Cloud Logging for a service and time window.

        Args:
            service_name: GCP service name (e.g. 'auth-service').
            window_start: ISO format start of investigation window.
            window_end: ISO format end of investigation window.

        Returns:
            Log entries as a plain string, one entry per line.

        Raises:
            RuntimeError: If GCP credentials are invalid or API call fails.
        """
        try:
            import json
            from google.cloud import logging as gcp_logging
            from google.oauth2 import service_account

            # Build credentials from service account key
            if isinstance(self._service_account_key, str):
                key_dict = json.loads(self._service_account_key)
            else:
                key_dict = self._service_account_key

            credentials = service_account.Credentials.from_service_account_info(
                key_dict,
                scopes=["https://www.googleapis.com/auth/logging.read"],
            )

            client = gcp_logging.Client(
                project=self._project_id,
                credentials=credentials,
            )

            # Build the log filter
            log_filter = (
                f'resource.labels.service_name="{service_name}" '
                f'timestamp>="{window_start}" '
                f'timestamp<="{window_end}" '
                f'severity>=ERROR'
            )

            logger.info(
                f"Fetching GCP logs for service '{service_name}' "
                f"between {window_start} and {window_end}"
            )

            # Fetch log entries
            entries = list(client.list_entries(
                filter_=log_filter,
                order_by=gcp_logging.ASCENDING,
                max_results=5000,
            ))

            if not entries:
                logger.warning(
                    f"No log entries found for service '{service_name}' "
                    f"in GCP Logging"
                )
                return ""

            # Format entries as plain text lines
            log_lines = []
            for entry in entries:
                timestamp = entry.timestamp.isoformat() if entry.timestamp else "unknown"
                severity = entry.severity or "INFO"
                payload = entry.payload

                if isinstance(payload, dict):
                    message = payload.get("message", str(payload))
                else:
                    message = str(payload)

                log_lines.append(
                    f"{timestamp} {severity} {service_name} {message}"
                )

            raw_logs = "\n".join(log_lines)
            logger.info(
                f"Fetched {len(entries)} log entries from GCP "
                f"for service '{service_name}'"
            )
            return raw_logs

        except ImportError:
            raise RuntimeError(
                "google-cloud-logging not installed. "
                "Run: pip install google-cloud-logging"
            )
        except Exception as e:
            logger.error(f"GCP Logging fetch failed: {e}")
            raise RuntimeError(f"GCP Logging error: {e}") from e

    async def validate_credentials(self) -> bool:
        """Verify GCP credentials are present and correctly structured.

        Returns:
            True if credentials look valid, False otherwise.
        """
        if not self._project_id:
            logger.warning("GCP connector missing project_id")
            return False
        if not self._service_account_key:
            logger.warning("GCP connector missing service_account_key")
            return False
        return True