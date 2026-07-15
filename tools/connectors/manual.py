# tools/connectors/manual.py
from __future__ import annotations

import logging

from tools.connectors.base import BaseLogConnector

logger = logging.getLogger(__name__)


class ManualLogConnector(BaseLogConnector):
    """Connector for manually uploaded log files.

    Used when the organisation's log source is configured as 'manual'
    or when logs were uploaded via POST /incidents/{id}/logs.
    The raw logs are passed directly from the incident state.
    """

    def __init__(self, raw_logs: str) -> None:
        """Initialise the manual connector with pre-loaded log content.

        Args:
            raw_logs: Log content already loaded from the file upload.
        """
        self._raw_logs = raw_logs

    async def fetch_logs(
        self,
        service_name: str,
        window_start: str,
        window_end: str,
    ) -> str:
        """Return the pre-loaded log content.

        No fetching needed — logs were already uploaded by the SRE.

        Args:
            service_name: Ignored for manual uploads.
            window_start: Ignored for manual uploads.
            window_end: Ignored for manual uploads.

        Returns:
            The raw log string from the file upload.
        """
        logger.info(
            f"Manual connector returning {len(self._raw_logs)} "
            f"characters of pre-loaded logs"
        )
        return self._raw_logs

    async def validate_credentials(self) -> bool:
        """Manual connector needs no credentials — always valid.

        Returns:
            Always True.
        """
        return bool(self._raw_logs)