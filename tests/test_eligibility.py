from datetime import datetime
from dateutil.relativedelta import relativedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Application
from eligibility import check_eligibility


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    s = factory()
    yield s
    s.close()


NOW = datetime(2026, 6, 1, 12, 0, 0)


def add_rejection(session, months_ago):
    session.add(Application(
        candidate_id="cand-1",
        job_id="JD-042",
        status="rejected",
        decision_date=NOW - relativedelta(months=months_ago),
    ))
    session.commit()


def test_rejected_5_months_ago_is_blocked(session):
    add_rejection(session, 5)
    result = check_eligibility(session, "cand-1", "JD-042", now=NOW)
    assert result is not None
    assert result.status == "rejected"


def test_rejected_7_months_ago_is_eligible(session):
    add_rejection(session, 7)
    result = check_eligibility(session, "cand-1", "JD-042", now=NOW)
    assert result is None


def test_rejected_exactly_6_months_ago_is_blocked(session):
    # Boundary case: inclusive — still blocked on the 6-month mark.
    add_rejection(session, 6)
    result = check_eligibility(session, "cand-1", "JD-042", now=NOW)
    assert result is not None


def test_no_prior_rejection_is_eligible(session):
    result = check_eligibility(session, "cand-1", "JD-042", now=NOW)
    assert result is None


def test_reapplication_date_is_day_after_six_months(session):
    add_rejection(session, 5)
    result = check_eligibility(session, "cand-1", "JD-042", now=NOW)
    rejection_dt = NOW - relativedelta(months=5)
    expected = (rejection_dt + relativedelta(months=6) + relativedelta(days=1)).date()
    assert result.earliest_reapplication_date == expected