import re
import spacy

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError(
        "spaCy model 'en_core_web_sm' not found. "
        "Run: python -m spacy download en_core_web_sm"
    )


EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

PHONE_PATTERN = re.compile(
    r"(\+?\d{1,3}[\s\-.]?)?"       
    r"(\(?\d{3}\)?[\s\-.]?)"      
    r"\d{3}[\s\-.]?\d{4}"        
)

LINKEDIN_PATTERN = re.compile(
    r"linkedin\.com/in/[A-Za-z0-9\-_%]+"
)

GITHUB_PATTERN = re.compile(
    r"github\.com/[A-Za-z0-9\-_%]+"
)


def extract_email(text: str) -> str | None:
    match = EMAIL_PATTERN.search(text)
    return match.group(0).lower() if match else None


def extract_phone(text: str) -> str | None:
    match = PHONE_PATTERN.search(text)
    if not match:
        return None
    phone = re.sub(r"[\s\-.]", "", match.group(0))
    digits = re.sub(r"\D", "", phone)
    return phone if len(digits) >= 10 else None


def extract_linkedin(text: str) -> str | None:
    match = LINKEDIN_PATTERN.search(text)
    return match.group(0) if match else None


def extract_github(text: str) -> str | None:
    match = GITHUB_PATTERN.search(text)
    return match.group(0) if match else None


def extract_name(text: str, filename_hint: str = "") -> str:
    
    snippet = text[:500]
    doc = nlp(snippet)
    for ent in doc.ents:
        if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
            return ent.text.strip()

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:10]:
        words = line.split()
       
        if (
            2 <= len(words) <= 4
            and all(w[0].isupper() for w in words if w)
            and not re.search(r"[\d@|•\-]", line)
            and not any(kw in line.upper() for kw in [
                "RESUME", "CURRICULUM", "VITAE", "CV", "PROFILE",
                "SUMMARY", "OBJECTIVE", "SKILLS", "EXPERIENCE"
            ])
        ):
            return line

    # Strategy 3: Filename fallback
    if filename_hint:
        raw = filename_hint.rsplit(".", 1)[0]          # remove extension
        raw = re.sub(r"[_\-]+", " ", raw)              # underscores → spaces
        raw = re.sub(r"\d{8}_\d{6}$", "", raw).strip() # remove timestamp
        raw = re.sub(r"(resume|cv|final|v\d)", "", raw, flags=re.IGNORECASE).strip()
        if raw:
            return raw.title()

    return "Unknown Candidate"


def extract_pii(text: str, filename_hint: str = "") -> dict:

    return {
        "name":     extract_name(text, filename_hint),
        "email":    extract_email(text),
        "phone":    extract_phone(text),
        "linkedin": extract_linkedin(text),
        "github":   extract_github(text),
    }