from datetime import datetime, date
from enum import Enum

from sqlalchemy import String, Integer, DateTime, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel, Field


# ---------- SQLAlchemy ORM ----------

class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)          # "rejected" | "scored"
    decision_date: Mapped[datetime] = mapped_column(DateTime)
    score: Mapped[float] = mapped_column(Float, nullable=True)
    tier: Mapped[str] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Application candidate={self.candidate_id} job={self.job_id} "
            f"status={self.status} date={self.decision_date.date()}>"
        )


# ---------- Pydantic schemas (validated outputs) ----------

class Tier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    REJECT = "Reject"


class RejectionResponse(BaseModel):
    """Returned when a candidate is blocked by the 6-month rule."""
    status: str = "rejected"
    candidate_id: str
    job_id: str
    reason: str = "Rejected within the last 6 months"
    earliest_reapplication_date: date


class ScoreResult(BaseModel):
    """The validated final result for an eligible candidate."""
    status: str = "scored"
    candidate_id: str
    job_id: str
    qualifications: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    achievements: int = Field(ge=0, le=100)
    culture_fit: int = Field(ge=0, le=100)
    score: float
    tier: Tier
    rationale: str