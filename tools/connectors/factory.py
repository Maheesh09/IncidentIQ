# tools/connectors/factory.py
from __future__ import annotations

import logging

from tools.connectors.base import BaseLogConnector
from tools.connectors.manual import ManualLogConnector
from tools.connectors.gcp_logging import GCPLoggingConnector
from tools.connectors.aws_cloudwatch import AWSCloudWatchConnector
from tools.connectors.datadog_logs import DatadogLogsConnector

logger = logging.getLogger(__name__)

# Maps source_type strings to connector classes
CONNECTOR_REGISTRY: dict[str, type[BaseLogConnector]] = {
    "gcp": GCPLoggingConnector,
    "aws": AWSCloudWatchConnector,
    "datadog": DatadogLogsConnector,
    "manual": ManualLogConnector,
}


async def get_connector(
    source_type: str,
    credentials: dict | None = None,
    raw_logs: str | None = None,
) -> BaseLogConnector:
    """Build and return the appropriate log connector.

    Selects the connector based on source_type and initialises
    it with the provided credentials or raw logs.

    Args:
        source_type: One of 'gcp', 'aws', 'datadog', 'manual'.
        credentials: Credentials dict retrieved from Secret Manager.
                    Required for gcp, aws, datadog.
        raw_logs: Pre-loaded log content for manual uploads.
                 Required for manual.

    Returns:
        An initialised connector ready to call fetch_logs on.

    Raises:
        ValueError: If source_type is unknown or required params missing.
    """
    if source_type not in CONNECTOR_REGISTRY:
        raise ValueError(
            f"Unknown log source type '{source_type}'. "
            f"Valid types: {list(CONNECTOR_REGISTRY.keys())}"
        )

    if source_type == "manual":
        if not raw_logs:
            raise ValueError(
                "raw_logs is required for manual connector"
            )
        connector = ManualLogConnector(raw_logs=raw_logs)

    else:
        if not credentials:
            raise ValueError(
                f"credentials are required for {source_type} connector"
            )
        connector_class = CONNECTOR_REGISTRY[source_type]
        connector = connector_class(credentials=credentials)

    # Validate credentials before returning
    is_valid = await connector.validate_credentials()
    if not is_valid:
        raise ValueError(
            f"Invalid credentials for {source_type} connector — "
            f"check your log source configuration"
        )

    logger.info(f"Connector ready: {source_type}")
    return connector