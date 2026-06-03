import json
import re
from pydantic import BaseModel, Field, ValidationError

from scoring import build_prompt, call_model


class RawScores(BaseModel):
    """The shape we demand from the model — nothing more."""
    qualifications: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    achievements: int = Field(ge=0, le=100)
    culture_fit: int = Field(ge=0, le=100)
    rationale: str


def extract_json(text: str) -> str | None:
    """Pull the first {...} block out of the model's text.

    Handles the common failure where the model wraps JSON in ```code fences```
    or adds a sentence before/after it.
    """
    # Strip code fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Grab the outermost brace-delimited block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else None


def parse_and_validate(raw_text: str) -> RawScores | None:
    """Try to turn raw model text into a validated RawScores, or None."""
    candidate = extract_json(raw_text)
    if candidate is None:
        return None
    try:
        data = json.loads(candidate)
        return RawScores(**data)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def get_scores(cv_text: str, job_description: str) -> RawScores:
    """Get validated scores, retrying once, with a safe fallback.

    Never raises — a total failure returns a zeroed RawScores so the
    pipeline can still produce a valid (Reject-tier) result.
    """
    # Attempt 1
    prompt = build_prompt(cv_text, job_description, stricter=False)
    result = parse_and_validate(call_model(prompt))
    if result is not None:
        return result

    # Attempt 2 — stricter prompt
    prompt = build_prompt(cv_text, job_description, stricter=True)
    result = parse_and_validate(call_model(prompt))
    if result is not None:
        return result

    # Fallback — model failed twice; return a safe, valid object
    return RawScores(
        qualifications=0,
        experience=0,
        achievements=0,
        culture_fit=0,
        rationale="Scoring failed: model did not return valid JSON after retry.",
    )