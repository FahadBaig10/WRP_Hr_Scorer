from datetime import datetime
from dateutil.relativedelta import relativedelta

from db import init_db, SessionLocal
from models import Application

init_db()
with SessionLocal() as s:
    s.add(Application(
        candidate_id="cand-1",
        job_id="JD-042",
        status="rejected",
        decision_date=datetime.now() - relativedelta(months=2),
    ))
    s.commit()
    print("Seeded one rejection for cand-1 (2 months ago).")