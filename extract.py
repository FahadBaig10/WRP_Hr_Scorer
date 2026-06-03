import pdfplumber

def extract_text(path: str) -> str:
    text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    joined = "\n".join(text).strip()
    if not joined:
        raise ValueError("No extractable text found in CV")
    return joined