"""PII guard. First layer: prompts are built from non-personal fields only (trip labels, never names).
Second layer: this scrubber runs on every stored prompt preview. Prune's PII shield is a third layer."""
import re

PHONE = re.compile(r"(?<![\w])\+?\d[\d \-]{8,}\d(?![\w])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
AADHAAR_LIKE = re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")


def scrub(text: str) -> str:
    text = EMAIL.sub("[EMAIL]", text)
    text = AADHAAR_LIKE.sub("[ID]", text)
    return PHONE.sub("[PHONE]", text)


def find_pii(text: str, terms: list[str] = ()) -> list[str]:
    hits = [m.group(0) for m in PHONE.finditer(text)] + [m.group(0) for m in EMAIL.finditer(text)]
    low = text.lower()
    hits += [t for t in terms if t and t.lower() in low]
    return hits
