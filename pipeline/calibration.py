# pipeline/calibration.py
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.incident import Feedback, Incident

logger = logging.getLogger(__name__)

# How many past feedback records to include in the prompt
MAX_FEEDBACK_EXAMPLES = 5


async def fetch_calibration_context(
    db: AsyncSession,
    incident_type: str | None,
    severity: str | None,
) -> str:
    """Fetch past SRE feedback to calibrate synthesis hypothesis ranking.

    Queries the feedback table for rejected hypotheses on similar incidents
    and formats them as context for the Synthesis Agent prompt.

    Args:
        db: Active database session.
        incident_type: Type of the current incident for filtering.
        severity: Severity of the current incident for filtering.

    Returns:
        Formatted string of past feedback examples, or empty string if none.
    """
    try:
        # Find past incidents of the same type that had rejected feedback
        result = await db.execute(
            select(Feedback, Incident)
            .join(Incident, Feedback.incident_id == Incident.id)
            .where(
                Feedback.verdict == "rejected",
                Feedback.actual_cause.isnot(None),
            )
            .order_by(Feedback.submitted_at.desc())
            .limit(MAX_FEEDBACK_EXAMPLES)
        )
        rows = result.all()

        if not rows:
            return ""

        # Format feedback examples for the prompt
        examples = []
        for feedback, incident in rows:
            example = (
                f"Past incident (type: {incident.incident_type or 'unknown'}, "
                f"severity: {incident.severity or 'unknown'}):\n"
                f"  Incorrect hypothesis: rank {feedback.hypothesis_rank} "
                f"was rejected\n"
                f"  Actual root cause: {feedback.actual_cause}"
            )
            examples.append(example)

        calibration_text = (
            "CALIBRATION — Learn from these past incorrect hypotheses:\n\n"
            + "\n\n".join(examples)
            + "\n\nAvoid similar reasoning patterns in your current analysis."
        )

        logger.info(
            f"Loaded {len(examples)} calibration examples for "
            f"incident type={incident_type}, severity={severity}"
        )
        return calibration_text

    except Exception as e:
        logger.warning(f"Failed to load calibration context: {e}")
        return ""