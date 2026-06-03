import os
import argparse
import json

from db import init_db, SessionLocal
from extract import extract_text
from eligibility import check_eligibility
from parsing import get_scores
from models import ScoreResult, Application
from datetime import datetime

# Reuse the tier mapping from main so logic stays in one place
from main import score_to_tier, load_job_description, parse_bool


def candidate_id_from_filename(filename: str) -> str:
    """Derive a candidate id from the CV filename (stem without extension)."""
    return os.path.splitext(os.path.basename(filename))[0]


def score_one_cv(session, cv_path: str, job_id: str,
                 job_description: str, referred: bool) -> dict:
    """Run the full pipeline for a single CV. Never raises — failures
    are captured as a structured 'failed' entry so the batch continues."""
    candidate_id = candidate_id_from_filename(cv_path)

    try:
        # Eligibility gate first — blocked candidates aren't scored
        rejection = check_eligibility(session, candidate_id, job_id)
        if rejection is not None:
            session.add(Application(
                candidate_id=candidate_id, job_id=job_id,
                status="rejected", decision_date=datetime.now(),
                score=None, tier=None,
            ))
            session.commit()
            return {
                "candidate_id": candidate_id,
                "status": "rejected",
                "score": None,
                "tier": None,
                "rationale": "Blocked by 6-month re-application rule.",
            }

        cv_text = extract_text(cv_path)
        raw = get_scores(cv_text, job_description)

        base = (raw.qualifications + raw.experience
                + raw.achievements + raw.culture_fit) / 4
        final = min(base + (10 if referred else 0), 100)

        result = ScoreResult(
            candidate_id=candidate_id, job_id=job_id,
            qualifications=raw.qualifications, experience=raw.experience,
            achievements=raw.achievements, culture_fit=raw.culture_fit,
            score=round(final, 2), tier=score_to_tier(final),
            rationale=raw.rationale,
        )

        session.add(Application(
            candidate_id=candidate_id, job_id=job_id,
            status="scored", decision_date=datetime.now(),
            score=result.score, tier=result.tier.value,
        ))
        session.commit()

        return {
            "candidate_id": candidate_id,
            "status": "scored",
            "score": result.score,
            "tier": result.tier.value,
            "rationale": result.rationale,
        }

    except Exception as e:
        # One bad CV must not kill the whole batch
        return {
            "candidate_id": candidate_id,
            "status": "failed",
            "score": None,
            "tier": None,
            "rationale": f"Processing error: {e}",
        }


def run_batch(folder: str, job_id: str, referred: bool, urgent: bool) -> dict:
    """Score every PDF in `folder` against one job and rank the results."""
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"CV folder not found: {folder}")

    pdfs = [os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith(".pdf")]
    if not pdfs:
        raise ValueError(f"No PDF files found in folder: {folder}")

    job_description = load_job_description(job_id)

    results = []
    with SessionLocal() as session:
        for cv_path in sorted(pdfs):
            results.append(
                score_one_cv(session, cv_path, job_id, job_description, referred)
            )

    # Rank: scored candidates by score descending; rejected/failed sink to bottom
    def sort_key(r):
        # None scores rank last; negate so higher scores come first
        return (r["score"] is None, -(r["score"] or 0))

    results.sort(key=sort_key)

    return {
        "job_id": job_id,
        "urgent": urgent,
        "candidate_count": len(results),
        "leaderboard": results,
    }


def print_leaderboard(batch: dict) -> None:
    """Pretty-print a ranked table to the terminal."""
    flag = "  [URGENT]" if batch["urgent"] else ""
    print(f"\nLeaderboard for {batch['job_id']}{flag} "
          f"({batch['candidate_count']} candidates)\n")
    print(f"{'Rank':<5}{'Candidate':<16}{'Status':<10}{'Score':<8}{'Tier':<6}")
    print("-" * 45)
    for i, r in enumerate(batch["leaderboard"], start=1):
        score = "-" if r["score"] is None else f"{r['score']:.2f}"
        tier = r["tier"] or "-"
        print(f"{i:<5}{r['candidate_id']:<16}{r['status']:<10}{score:<8}{tier:<6}")
    print()


def main():
    p = argparse.ArgumentParser(description="Batch CV scorer — ranked leaderboard")
    p.add_argument("--folder", required=True, help="Folder containing CV PDFs")
    p.add_argument("--job_id", required=True)
    p.add_argument("--referred", default="false")
    p.add_argument("--urgent", default="false")
    p.add_argument("--json", action="store_true",
                   help="Print full JSON instead of the table")
    args = p.parse_args()

    init_db()
    batch = run_batch(args.folder, args.job_id,
                      parse_bool(args.referred), parse_bool(args.urgent))

    if args.json:
        print(json.dumps(batch, indent=2))
    else:
        print_leaderboard(batch)


if __name__ == "__main__":
    main()