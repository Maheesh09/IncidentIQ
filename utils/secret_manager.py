# utils/secret_manager.py
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


async def store_secret(secret_name: str, secret_value: dict) -> str:
    """Store credentials in Google Cloud Secret Manager.

    Args:
        secret_name: Unique name for the secret in Secret Manager.
        secret_value: Dict of credentials to store as JSON.

    Returns:
        The secret name confirming successful storage.

    Raises:
        RuntimeError: If Secret Manager is unavailable or storage fails.
    """
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        project_id = _get_project_id()
        parent = f"projects/{project_id}"

        # Create the secret container
        try:
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {
                        "replication": {"automatic": {}}
                    },
                }
            )
        except Exception:
            # Secret already exists — that's fine, we'll add a new version
            pass

        # Store the secret value as a new version
        payload = json.dumps(secret_value).encode("utf-8")
        resource_name = f"{parent}/secrets/{secret_name}"
        client.add_secret_version(
            request={
                "parent": resource_name,
                "payload": {"data": payload},
            }
        )

        logger.info(f"Secret stored successfully: {secret_name}")
        return secret_name

    except ImportError:
        # google-cloud-secret-manager not installed — use local fallback
        logger.warning(
            "google-cloud-secret-manager not installed — "
            "storing credentials in memory (development mode only)"
        )
        _local_secret_store[secret_name] = secret_value
        return secret_name

    except Exception as e:
        logger.error(f"Failed to store secret {secret_name}: {e}")
        raise RuntimeError(f"Secret storage failed: {e}") from e


async def retrieve_secret(secret_name: str) -> dict:
    """Retrieve credentials from Google Cloud Secret Manager.

    Args:
        secret_name: Name of the secret to retrieve.

    Returns:
        Dict of credentials parsed from JSON.

    Raises:
        RuntimeError: If the secret cannot be retrieved.
    """
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        project_id = _get_project_id()
        name = (
            f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        )
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("utf-8")
        return json.loads(payload)

    except ImportError:
        # Fall back to local store in development
        if secret_name in _local_secret_store:
            return _local_secret_store[secret_name]
        raise RuntimeError(
            f"Secret '{secret_name}' not found in local store"
        )

    except Exception as e:
        logger.error(f"Failed to retrieve secret {secret_name}: {e}")
        raise RuntimeError(f"Secret retrieval failed: {e}") from e


def _get_project_id() -> str:
    """Get the GCP project ID from environment or metadata server.

    Returns:
        GCP project ID string.

    Raises:
        RuntimeError: If project ID cannot be determined.
    """
    from config import settings
    if hasattr(settings, "gcp_project_id") and settings.gcp_project_id:
        return settings.gcp_project_id

    # Try the GCP metadata server (works on Cloud Run)
    try:
        import httpx
        response = httpx.get(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=2.0,
        )
        return response.text
    except Exception:
        raise RuntimeError(
            "Cannot determine GCP project ID — set GCP_PROJECT_ID in .env"
        )


# Local fallback store for development without Secret Manager
_local_secret_store: dict[str, dict] = {}