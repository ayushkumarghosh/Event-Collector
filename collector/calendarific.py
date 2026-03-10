import httpx
from datetime import datetime

from config import CALENDARIFIC_API_KEY

API_URL = "https://calendarific.com/api/v2/holidays"


def fetch_calendarific_holidays() -> list[dict]:
    """
    Fetch Indian holidays and festivals from Calendarific API.
    Returns list of article-like dicts that will be sent through Gemini for categorization.
    """
    if not CALENDARIFIC_API_KEY:
        print("  [WARN] CALENDARIFIC_API_KEY not set, skipping holidays fetch")
        return []

    year = datetime.now().year
    articles = []
    seen_names = set()

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

            # Skip duplicates across types (e.g. Holi appears in both national and religious)
            name_key = name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            description = h.get("description", "") or ""
            date_iso = h.get("date", {}).get("iso", "")
            h_types = h.get("type", [])
            types_str = ", ".join(h_types)

            url = f"https://calendarific.com/holiday/india/{name.lower().replace(' ', '-')}-{year}"

            # Build rich content for Gemini to classify properly
            content = f"{name}. {description} Type: {types_str}. Date: {date_iso[:10] if date_iso else 'unknown'}."

            articles.append({
                "source_name": "Calendarific",
                "url": url,
                "title": name,
                "content": content,
                "content_hash": None,
                "category": "holiday",  # default hint, Gemini will reclassify
            })

    print(f"  Fetched {len(articles)} holidays from Calendarific")
    return articles
