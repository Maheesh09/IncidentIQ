# tools/connectors/aws_cloudwatch.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from tools.connectors.base import BaseLogConnector

logger = logging.getLogger(__name__)


class AWSCloudWatchConnector(BaseLogConnector):
    """Connector for AWS CloudWatch Logs.

    Fetches logs from CloudWatch Log Groups using AWS credentials.
    Credentials are retrieved from Google Cloud Secret Manager
    and passed in at construction time.
    """

    def __init__(self, credentials: dict, config_metadata: dict | None = None) -> None:
        """Initialise the AWS connector with IAM credentials.

        Args:
            credentials: Dict containing access_key_id,
                        secret_access_key, and region.
            config_metadata: Optional configuration metadata.
        """
        self._access_key_id = credentials.get("access_key_id")
        self._secret_access_key = credentials.get("secret_access_key")
        self._region = credentials.get("region", "us-east-1")
        self._log_group = credentials.get("log_group")
        self._config_metadata = config_metadata or {}

    async def fetch_logs(
        self,
        service_name: str,
        window_start: str,
        window_end: str,
    ) -> str:
        """Fetch logs from AWS CloudWatch for a service and time window.

        Args:
            service_name: CloudWatch log stream prefix to filter by.
            window_start: ISO format start of investigation window.
            window_end: ISO format end of investigation window.

        Returns:
            Log entries as a plain string, one entry per line.

        Raises:
            RuntimeError: If AWS credentials are invalid or API call fails.
        """
        try:
            import boto3

            client = boto3.client(
                "logs",
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region,
            )

            # Convert ISO timestamps to milliseconds since epoch
            start_ms = int(
                datetime.fromisoformat(
                    window_start.replace("Z", "+00:00")
                ).timestamp() * 1000
            )
            end_ms = int(
                datetime.fromisoformat(
                    window_end.replace("Z", "+00:00")
                ).timestamp() * 1000
            )

            # Determine log group name
            log_group = self._log_group or f"/aws/ecs/{service_name}"

            logger.info(
                f"Fetching CloudWatch logs from '{log_group}' "
                f"for service '{service_name}'"
            )

            # Use filter_log_events for time-bounded, pattern-filtered fetch
            response = client.filter_log_events(
                logGroupName=log_group,
                startTime=start_ms,
                endTime=end_ms,
                filterPattern="ERROR",
                limit=5000,
            )

            events = response.get("events", [])

            if not events:
                logger.warning(
                    f"No CloudWatch log events found in '{log_group}'"
                )
                return ""

            # Format events as plain text lines
            log_lines = []
            for event in events:
                timestamp_ms = event.get("timestamp", 0)
                timestamp = datetime.fromtimestamp(
                    timestamp_ms / 1000, tz=timezone.utc
                ).isoformat()
                message = event.get("message", "").strip()
                log_lines.append(
                    f"{timestamp} ERROR {service_name} {message}"
                )

            raw_logs = "\n".join(log_lines)
            logger.info(
                f"Fetched {len(events)} CloudWatch events "
                f"for service '{service_name}'"
            )
            return raw_logs

        except ImportError:
            raise RuntimeError(
                "boto3 not installed. Run: pip install boto3"
            )
        except Exception as e:
            logger.error(f"CloudWatch fetch failed: {e}")
            raise RuntimeError(f"CloudWatch error: {e}") from e

    async def validate_credentials(self) -> bool:
        """Verify AWS credentials are present.

        Returns:
            True if all required credentials are present.
        """
        if not self._access_key_id:
            logger.warning("AWS connector missing access_key_id")
            return False
        if not self._secret_access_key:
            logger.warning("AWS connector missing secret_access_key")
            return False
        if not self._region:
            logger.warning("AWS connector missing region")
            return False
        return True