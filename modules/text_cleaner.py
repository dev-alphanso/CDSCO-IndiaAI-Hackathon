import re


_NOISE_PATTERNS = [
    r"[|\\]{2,}",          # repeated pipes/backslashes (table borders)
    r"_{4,}",              # long underscores
    r"\s{3,}",             # excessive whitespace (collapse to 2)
    r"[^\x00-\x7F]{3,}",  # long runs of non-ASCII garbage
]

_ENTITY_PATTERNS = {
    # Phone: must have 7+ consecutive digits (with optional separators).
    # Uses \d{3,} segments so short date-like groups (2 digits) don't qualify alone.
    "phone":   r"(\+?(?:\d{1,3}[-.\s])?(?:\(?\d{2,5}\)?[-.\s])?\d{3,5}[-.\s]?\d{4,8})(?!\d)",
    "email":   r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "date": (
        r"\b("
        r"\d{4}[-/]\d{2}[-/]\d{2}"   # YYYY-MM-DD  YYYY/MM/DD
        r"|\d{2}[-/]\d{2}[-/]\d{4}"  # DD-MM-YYYY  DD/MM/YYYY
        r"|\d{4}[-/]\d{1,2}[-/]\d{1,2}"  # YYYY-M-D  (single-digit month/day)
        r"|\d{1,2}[-/]\d{1,2}[-/]\d{4}"  # D-M-YYYY
        r")\b"
    ),
    "aadhar":  r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    "pan":     r"\b[A-Z]{5}\d{4}[A-Z]\b",
    "pin":     r"\bPin(?:code)?[:\s]*(\d{6})\b",
}

# All date shapes — used to reject false phone matches
_DATE_RE = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}$"        # YYYY-MM-DD  YYYY/MM/DD
    r"|^\d{2}[-/]\d{2}[-/]\d{4}$"       # DD-MM-YYYY  DD/MM/YYYY
    r"|^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"   # YYYY-M-D
    r"|^\d{1,2}[-/]\d{1,2}[-/]\d{4}$"   # D-M-YYYY
)


def clean_text(raw: str) -> str:
    text = raw
    for pat in _NOISE_PATTERNS:
        text = re.sub(pat, " ", text)
    # Normalize line breaks
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_entities(text: str) -> dict:
    found = {}
    for label, pat in _ENTITY_PATTERNS.items():
        matches = re.findall(pat, text, re.IGNORECASE)
        if label == "phone":
            # Drop anything that is purely a date (e.g. 2025-06-22, 1975-04-30)
            matches = [m for m in matches if not _DATE_RE.match(m.strip())]
        if matches:
            found[label] = list(set(matches))
    return found


def mask_pii(text: str) -> str:
    """Replace PII patterns with placeholder tokens."""
    masked = text
    replacements = {
        "phone":  ("[PHONE]",  _ENTITY_PATTERNS["phone"]),
        "email":  ("[EMAIL]",  _ENTITY_PATTERNS["email"]),
        "aadhar": ("[AADHAR]", _ENTITY_PATTERNS["aadhar"]),
        "pan":    ("[PAN]",    _ENTITY_PATTERNS["pan"]),
    }
    for _label, (token, pat) in replacements.items():
        masked = re.sub(pat, token, masked, flags=re.IGNORECASE)
    return masked
