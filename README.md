# WRP HR & Recruitment Scoring Service

A self-hosted, offline AI service for an HR recruitment portal. It ingests a CV (PDF),
enforces a 6-month re-application rule, and produces a ranked, explainable score using a
large language model running entirely on the local machine via Ollama — with no cloud AI API.

---

## Architecture

The system is a deterministic pipeline wrapped around a single, isolated LLM call. Every
part except the model itself is plain, testable Python; the model is treated as an untrusted
component whose only job is to return four raw dimension scores.

```
CLI (main.py)
  -> PDF extraction (extract.py, pdfplumber)
  -> Eligibility gate (eligibility.py)        # early exit if rejected within 6 months
  -> LLM scoring (scoring.py + parsing.py)     # Ollama + Mistral 7B, JSON only
  -> Score adjustment (referral boost, tier)   # deterministic, in our own code
  -> Persistence + JSON output (db.py, models.py)
```

Key design principle: the LLM never sees the referral flag, never does arithmetic, and never
chooses the tier. It returns raw 0-100 scores per dimension; the boost, the 100-point cap, and
the A/B/C/Reject tier mapping all happen in deterministic code. This keeps the model's job
narrow and the business logic fully testable.

### Module overview

| File | Responsibility |
|------|----------------|
| `main.py` | CLI parsing and pipeline orchestration |
| `extract.py` | PDF text extraction (pdfplumber), guards against empty/scanned CVs |
| `eligibility.py` | 6-month re-application rule and earliest re-application date |
| `scoring.py` | Prompt construction and the local Ollama model call |
| `parsing.py` | Parse / validate / retry-once / safe-fallback for model output |
| `models.py` | SQLAlchemy ORM table and Pydantic validation schemas |
| `db.py` | Database engine, session factory, table creation |
| `batch.py` | Candidate-defined module: ranked leaderboard over a folder of CVs |

---

## Setup

Requires Python 3.11+ and [Ollama](https://ollama.com).

```bash
# 1. Clone and enter the project
git clone <YOUR_GITHUB_REPO_URL>
cd wrp-hr-scorer

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your local .env from the template
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

### Model pull (one-time, requires internet)

```bash
ollama pull mistral
ollama run mistral "say hi"   # confirm the model responds
```

After this pull, the service runs fully offline.

---

## Running the core service

Score a single CV against a job, identifying the candidate explicitly:

```bash
python main.py --cv test.pdf --job_id JD-042 --candidate_id cand-NEW --referred true --urgent false
```

### Sample output (scored candidate)

```json
{
  "status": "scored",
  "candidate_id": "cand-NEW",
  "job_id": "JD-042",
  "qualifications": 85,
  "experience": 70,
  "achievements": 80,
  "culture_fit": 60,
  "score": 83.75,
  "tier": "B",
  "rationale": "Strong educational background in AI and relevant work experience, but limited direct experience with required frameworks may impact culture fit."
}
```

### Sample output (blocked by the 6-month rule)

```json
{
  "status": "rejected",
  "candidate_id": "cand-1",
  "job_id": "JD-042",
  "reason": "Rejected within the last 6 months",
  "earliest_reapplication_date": "2026-10-04"
}
```

Tiers: A (>=85), B (70-84), C (55-69), Reject (<55).

---

## Candidate-Defined Module: Batch Mode

I chose batch mode: score an entire folder of CVs against one job and output a ranked
leaderboard. I picked it because it composes directly on the core pipeline with no new
dependencies, and because it is the natural home for the `urgent` flag that the core carries
but cannot meaningfully use for a single candidate. It demonstrates that the core was built
cleanly enough to reuse, and it enforces the same eligibility gate per candidate so blocked
applicants are surfaced rather than silently dropped.

```bash
python batch.py --folder cvs --job_id JD-042 --urgent true
```

Candidate IDs are derived from each CV's filename (e.g. `cand-101.pdf` -> `cand-101`).
Add `--json` for full machine-readable output suitable for a future recruiter UI.

---

## Design Decisions (under 200 words)

The LLM is walled off as the only non-deterministic component. It returns four raw scores
plus a rationale; the referral boost, score cap, and tier mapping live in plain Python, so
business rules are unit-testable and the model's failure surface is minimal.

The eligibility boundary is inclusive: a rejection exactly six calendar months ago is still
blocked, with eligibility resuming the following day. Month math uses `dateutil.relativedelta`
rather than a fixed day count, so it is correct across months of differing length.

Model output passes through parse -> validate (Pydantic) -> retry-once-stricter ->
safe-fallback. A persistent failure yields a zeroed Reject-tier result with an honest
rationale rather than a crash.

Every application attempt is persisted as its own row, giving an audit trail of re-applications
rather than overwriting prior records.

Known simplification: `candidate_id` is supplied via CLI / filename rather than parsed from CV
text, and `batch.py` imports three helpers from `main.py` — a `utils.py` extraction would be the
cleaner refactor.

---

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

Tests cover the eligibility edge cases: rejections at 5, 6 (boundary), and 7 months, the
no-prior-rejection case, and the earliest re-application date calculation.

---

## Time Spent

Approximately [FILL IN — e.g. "4~5 hours setup and core, ~1 hour batch module and tests, 10-20 mins README and polish"].