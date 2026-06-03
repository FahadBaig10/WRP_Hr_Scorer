import ollama

MODEL = "mistral"

SCORING_INSTRUCTIONS = """You are a recruitment scoring assistant.
Score the candidate's CV against the job description on four dimensions,
each an integer from 0 to 100:
- qualifications
- experience
- achievements
- culture_fit

Respond with ONLY a single valid JSON object and nothing else.
No markdown, no code fences, no commentary before or after.
The JSON must have exactly these keys:
{
  "qualifications": <int 0-100>,
  "experience": <int 0-100>,
  "achievements": <int 0-100>,
  "culture_fit": <int 0-100>,
  "rationale": "<one or two sentences explaining the scores>"
}
"""


def build_prompt(cv_text: str, job_description: str, stricter: bool = False) -> str:
    """Assemble the scoring prompt. `stricter` is used on the retry."""
    reminder = ""
    if stricter:
        reminder = (
            "\nIMPORTANT: Your previous response was not valid JSON. "
            "Return ONLY the raw JSON object. Do not include any other text.\n"
        )

    return (
        f"{SCORING_INSTRUCTIONS}{reminder}\n"
        f"--- JOB DESCRIPTION ---\n{job_description}\n\n"
        f"--- CANDIDATE CV ---\n{cv_text}\n\n"
        f"Return the JSON now:"
    )


def call_model(prompt: str) -> str:
    """Send the prompt to the local model and return its raw text output."""
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2},  # low temp = more consistent formatting
    )
    return response["message"]["content"]