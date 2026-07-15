# tools/connectors/base.py
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLogConnector(ABC):
    """Abstract base class for all log source connectors.

    Every connector implements one method: fetch_logs.
    The pipeline calls fetch_logs and receives a plain string
    regardless of which log source the organisation uses.
    """

    @abstractmethod
    async def fetch_logs(
        self,
        service_name: str,
        window_start: str,
        window_end: str,
    ) -> str:
        """Fetch logs for a service within the investigation window.

        Args:
            service_name: Name of the service to fetch logs for.
            window_start: ISO format start of investigation window.
            window_end: ISO format end of investigation window.

        Returns:
            Raw log content as a plain string, ready for the
            Log Analysis Agent to process.

        Raises:
            RuntimeError: If log fetching fails.
        """
        ...

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Verify the connector credentials are valid.

        Returns:
            True if credentials are valid, False otherwise.
        """
        ...