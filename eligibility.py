from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Application, RejectionResponse


REJECTION_WINDOW_MONTHS = 6


def earliest_reapplication_date(decision_dt: datetime) -> date:
    """The first day the candidate may re-apply.

    A rejection is blocked for exactly 6 calendar months (inclusive of the
    boundary day), so they become eligible the day AFTER the 6-month mark.
    """
    return (decision_dt + relativedelta(months=REJECTION_WINDOW_MONTHS)
            + relativedelta(days=1)).date()


def check_eligibility(
    session: Session,
    candidate_id: str,
    job_id: str,
    now: datetime | None = None,
) -> RejectionResponse | None:
    """Return a RejectionResponse if blocked, or None if eligible.

    `now` is injectable so tests don't depend on the real clock.
    """
    now = now or datetime.now()
    cutoff = now - relativedelta(months=REJECTION_WINDOW_MONTHS)

    stmt = (
        select(Application)
        .where(Application.candidate_id == candidate_id)
        .where(Application.status == "rejected")
        # Inclusive boundary: a rejection exactly on the cutoff is still blocked
        .where(Application.decision_date >= cutoff)
        .order_by(Application.decision_date.asc())
    )
    most_recent_block = session.execute(stmt).scalars().first()

    if most_recent_block is None:
        return None  # eligible

    return RejectionResponse(
        candidate_id=candidate_id,
        job_id=job_id,
        earliest_reapplication_date=earliest_reapplication_date(
            most_recent_block.decision_date
        ),
    )