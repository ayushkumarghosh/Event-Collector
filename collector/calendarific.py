import httpx
from datetime import datetime

from config import CALENDARIFIC_API_KEY

API_URL = "https://calendarific.com/api/v2/holidays"

# Map Calendarific holiday types to our categories
TYPE_TO_CATEGORY = {
    "national": "festivals",
    "religious": "festivals",
    "observance": "festivals",
    "local": "festivals",
}

# Map Calendarific types to severity
TYPE_TO_SEVERITY = {
    "national": "high",
    "religious": "normal",
    "observance": "low",
    "local": "low",
}


def fetch_calendarific_holidays() -> list[dict]:
    """
    Fetch Indian holidays and festivals from Calendarific API.
    Returns list of article-like dicts compatible with the extractor pipeline,
    but with pre-extracted event fields in 'extracted' key so they can bypass LLM.
    """
    if not CALENDARIFIC_API_KEY:
        print("  [WARN] CALENDARIFIC_API_KEY not set, skipping holidays fetch")
        return []

    year = datetime.now().year
    articles = []

    for holiday_type in ("national", "religious", "observance"):
        try:
            resp = httpx.get(
                API_URL,
                params={
                    "api_key": CALENDARIFIC_API_KEY,
                    "country": "IN",
                    "year": year,
                    "type": holiday_type,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [WARN] Calendarific fetch failed for type={holiday_type}: {e}")
            continue

        holidays = data.get("response", {}).get("holidays", [])

        for h in holidays:
            name = h.get("name", "").strip()
            if not name:
                continue

            description = h.get("description", "") or ""
            date_iso = h.get("date", {}).get("iso", "")
            h_types = h.get("type", [])

            # Pick most important type for severity mapping
            severity = "normal"
            for t in h_types:
                if t in TYPE_TO_SEVERITY:
                    s = TYPE_TO_SEVERITY[t]
                    if s == "high":
                        severity = "high"
                        break
                    elif s == "normal" and severity != "high":
                        severity = "normal"

            articles.append({
                "source_name": "Calendarific",
                "url": f"https://calendarific.com/holiday/india/{name.lower().replace(' ', '-')}-{year}",
                "title": name,
                "content": f"{name}: {description}" if description else name,
                "content_hash": None,  # Computed by fetcher
                "category": "festivals",
                # Pre-extracted fields — these skip LLM processing
                "extracted": {
                    "name": name,
                    "category": "festivals",
                    "subcategory": ", ".join(h_types),
                    "summary": description or f"{name} — Indian holiday/festival.",
                    "location": "India",
                    "start_date": date_iso[:10] if date_iso else None,
                    "end_date": None,
                    "severity": severity,
                    "importance": 8 if severity == "high" else 5,
                    "source_url": f"https://calendarific.com/holiday/india/{name.lower().replace(' ', '-')}-{year}",
                },
            })

    print(f"  Fetched {len(articles)} holidays from Calendarific")
    return articles
