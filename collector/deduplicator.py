import hashlib


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def make_dedup_key(name: str, start_date: str | None, categories: list[str]) -> str:
    date_part = (start_date or "")[:10]
    cats_part = ",".join(sorted(categories))
    raw = f"{_normalize(name)}|{date_part}|{cats_part}"
    return hashlib.sha256(raw.encode()).hexdigest()
