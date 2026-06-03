import argparse
import json
import sys

import os
from scoring import build_prompt  # not strictly needed in main, but fine
from parsing import get_scores
from models import ScoreResult

from db import init_db, SessionLocal
from extract import extract_text
from eligibility import check_eligibility
from models import ScoreResult, Tier


def parse_bool(value: str) -> bool:
    """Turn a CLI string like 'true'/'false' into a real bool."""
    return str(value).strip().lower() in ("true", "1", "yes")

def load_job_description(job_id: str) -> str:
    path = os.path.join("job_descriptions", f"{job_id}.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Job description not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def score_to_tier(score: float) -> Tier:
    """Map a final score to its tier band."""
    if score >= 85:
        return Tier.A
    if score >= 70:
        return Tier.B
    if score >= 55:
        return Tier.C
    return Tier.REJECT


def run(args) -> dict:
    """The pipeline. Returns a JSON-serializable dict."""
    referred = parse_bool(args.referred)

    # 1. Extract CV text (raises on empty / unreadable PDF)
    cv_text = extract_text(args.cv)

    # 2. Eligibility gate — early exit if blocked within 6 months
    with SessionLocal() as session:
        rejection = check_eligibility(session, args.candidate_id, args.job_id)
        if rejection is not None:
            # mode="json" turns the date into an ISO string automatically
            return rejection.model_dump(mode="json")

        # 3. Score (stub for now)
        rejection = check_eligibility(session, args.candidate_id, args.job_id)
        if rejection is not None:
            return rejection.model_dump(mode="json")

        # 3. Score with the local LLM
        job_description = load_job_description(args.job_id)
        raw = get_scores(cv_text, job_description)

        base = (raw.qualifications + raw.experience
                + raw.achievements + raw.culture_fit) / 4
        final = min(base + (10 if referred else 0), 100)

        result = ScoreResult(
            candidate_id=args.candidate_id,
            job_id=args.job_id,
            qualifications=raw.qualifications,
            experience=raw.experience,
            achievements=raw.achievements,
            culture_fit=raw.culture_fit,
            score=round(final, 2),
            tier=score_to_tier(final),
            rationale=raw.rationale,
        )
        return result.model_dump(mode="json")


def main():
    p = argparse.ArgumentParser(description="WRP HR CV scorer")
    p.add_argument("--cv", required=True, help="Path to the CV PDF")
    p.add_argument("--job_id", required=True, help="Job description ID")
    p.add_argument("--candidate_id", required=True,
                   help="Unique candidate identifier")
    p.add_argument("--referred", default="false")
    p.add_argument("--urgent", default="false")
    args = p.parse_args()

    # Make sure tables exist before we query
    init_db()

    try:
        output = run(args)
    except FileNotFoundError:
        output = {"status": "error", "reason": f"CV file not found: {args.cv}"}
    except ValueError as e:
        output = {"status": "error", "reason": str(e)}

    print(json.dumps(output, indent=2))

    # Non-zero exit code on error so scripts/CI can detect failure
    if output.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()