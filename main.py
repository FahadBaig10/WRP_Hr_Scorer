import argparse
import json
import sys

from db import init_db, SessionLocal
from extract import extract_text
from eligibility import check_eligibility
from models import ScoreResult, Tier


def parse_bool(value: str) -> bool:
    """Turn a CLI string like 'true'/'false' into a real bool."""
    return str(value).strip().lower() in ("true", "1", "yes")


def stub_score(cv_text: str, candidate_id: str, job_id: str,
               referred: bool) -> ScoreResult:
    """Placeholder scorer. Replaced by the real Ollama call in Step 7.

    Returns raw per-dimension scores, applies the referral boost and tier
    mapping deterministically — exactly where the real logic will live.
    """
    qualifications = 70
    experience = 72
    achievements = 68
    culture_fit = 74

    raw = (qualifications + experience + achievements + culture_fit) / 4
    final = raw + (10 if referred else 0)
    final = min(final, 100)  # don't let the boost exceed 100

    return ScoreResult(
        candidate_id=candidate_id,
        job_id=job_id,
        qualifications=qualifications,
        experience=experience,
        achievements=achievements,
        culture_fit=culture_fit,
        score=round(final, 2),
        tier=score_to_tier(final),
        rationale="Stub scorer — replace with Ollama in Step 7.",
    )


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
        result = stub_score(cv_text, args.candidate_id, args.job_id, referred)
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