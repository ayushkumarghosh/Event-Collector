import hashlib


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def make_dedup_key(name: str, start_date: str | None, category: str) -> str:
    date_part = (start_date or "")[:10]
    raw = f"{_normalize(name)}|{date_part}|{category}"
    return hashlib.sha256(raw.encode()).hexdigest()
