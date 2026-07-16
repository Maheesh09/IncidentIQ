# utils/webhook.py
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# How many times to retry a failed webhook delivery
MAX_DELIVERY_ATTEMPTS = 3

# Seconds to wait between delivery attempts
DELIVERY_RETRY_DELAYS = [2, 5, 10]


def _sign_payload(payload: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature of the webhook payload.

    Args:
        payload: JSON string of the webhook body.
        secret: The organisation's webhook signing secret.

    Returns:
        Hex-encoded HMAC-SHA256 signature string.
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def deliver_webhook(
    url: str,
    secret: str,
    incident_id: str,
    report: dict,
) -> bool:
    """Deliver an RCA report to a customer's webhook endpoint.

    Signs the payload with HMAC-SHA256 and includes the signature
    in the X-IncidentIQ-Signature header. Retries up to 3 times
    with increasing delays on failure.

    Args:
        url: The customer's webhook endpoint URL.
        secret: The signing secret for HMAC verification.
        incident_id: The incident ID for logging and payload.
        report: The complete RCA report dict to deliver.

    Returns:
        True if delivery succeeded, False if all attempts failed.
    """
    payload = json.dumps({
        "event": "rca.completed",
        "incident_id": incident_id,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "report": report,
    })

    signature = _sign_payload(payload, secret)

    headers = {
        "Content-Type": "application/json",
        "X-IncidentIQ-Signature": f"sha256={signature}",
        "X-IncidentIQ-Event": "rca.completed",
        "User-Agent": "IncidentIQ-Webhook/1.0",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(MAX_DELIVERY_ATTEMPTS):
            try:
                response = await client.post(
                    url,
                    content=payload,
                    headers=headers,
                )

                if response.status_code in (200, 201, 202, 204):
                    logger.info(
                        f"Webhook delivered successfully for incident "
                        f"{incident_id} — status {response.status_code}"
                    )
                    return True

                logger.warning(
                    f"Webhook delivery attempt {attempt + 1} failed for "
                    f"incident {incident_id} — "
                    f"status {response.status_code}"
                )

            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook delivery attempt {attempt + 1} timed out "
                    f"for incident {incident_id}"
                )
            except Exception as e:
                logger.error(
                    f"Webhook delivery attempt {attempt + 1} error "
                    f"for incident {incident_id}: {e}"
                )

            # Wait before retrying
            if attempt < MAX_DELIVERY_ATTEMPTS - 1:
                import asyncio
                await asyncio.sleep(DELIVERY_RETRY_DELAYS[attempt])

    logger.error(
        f"Webhook delivery failed after {MAX_DELIVERY_ATTEMPTS} attempts "
        f"for incident {incident_id}"
    )
    return False