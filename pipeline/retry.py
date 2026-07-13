# pipeline/retry.py
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from pipeline.state import IncidentState

logger = logging.getLogger(__name__)

# How many times to retry a failed agent before accepting failure
MAX_RETRIES = 1

# How long to wait between retries in seconds
RETRY_DELAY_SECONDS = 2


def with_retry(node_fn: Callable) -> Callable:
    """Wrap a LangGraph agent node with automatic retry on failure.

    If the node returns None for its primary output field or raises
    an exception, it retries once after a short delay.

    Args:
        node_fn: The async agent node function to wrap.

    Returns:
        A wrapped version of the node function with retry behaviour.
    """
    async def wrapper(state: IncidentState) -> dict:
        """Execute the node with retry on failure.

        Args:
            state: Current incident state from LangGraph.

        Returns:
            Partial state update from the node.
        """
        last_result = {}
        last_exception = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    logger.warning(
                        f"Retrying {node_fn.__name__} for incident "
                        f"{state['incident_id']} "
                        f"(attempt {attempt + 1} of {MAX_RETRIES + 1})"
                    )
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

                result = await node_fn(state)
                last_result = result

                # Check if the agent reported an error in its result
                # If no error keys are present, consider it a success
                agent_errors = [
                    e for e in result.get("errors", [])
                    if node_fn.__name__.replace("_node", "") in e
                ]

                if not agent_errors:
                    return result

                # Agent returned errors — retry if attempts remain
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"{node_fn.__name__} returned errors on attempt "
                        f"{attempt + 1}: {agent_errors}"
                    )
                    continue

            except Exception as e:
                last_exception = e
                logger.error(
                    f"{node_fn.__name__} raised exception on attempt "
                    f"{attempt + 1}: {e}"
                )
                if attempt < MAX_RETRIES:
                    continue

        # All attempts exhausted — return last result or error state
        if last_exception and not last_result:
            return {
                "errors": state.get("errors", []) + [
                    f"{node_fn.__name__}: all {MAX_RETRIES + 1} attempts failed "
                    f"— {str(last_exception)}"
                ]
            }

        return last_result

    # Preserve the original function name for logging
    wrapper.__name__ = node_fn.__name__
    return wrapper