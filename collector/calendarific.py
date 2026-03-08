import httpx
from datetime import datetime

from config import CALENDARIFIC_API_KEY

API_URL = "https://calendarific.com/api/v2/holidays"

# Religious tradition type strings returned by Calendarific
RELIGIOUS_TYPES = {
    "hinduism", "islam", "sikhism", "christianity", "buddhism",
    "jainism", "jewish", "zoroastrianism", "christian",
}

# Major public celebrations — classified as "festival" regardless of religion
# These are widely celebrated across India, not just private observances
FESTIVAL_NAMES = {
    # Hindu festivals
    "holi", "diwali", "deepavali", "diwali/deepavali", "dussehra", "navratri",
    "pongal", "onam", "makar sankranti", "ganesh chaturthi", "raksha bandhan",
    "janmashtami", "rama navami", "ugadi", "gudi padwa", "vishu", "baisakhi",
    "lohri", "bihu", "chhath puja", "maha shivaratri", "vasant panchami",
    "rath yatra", "karaka chaturthi", "bhai duj",
    # Islamic festivals
    "eid", "eid ul-fitr", "eid ul-adha", "eid al-fitr", "eid al-adha",
    "ramzan id", "bakrid", "muharram", "milad un-nabi", "eid-e-milad",
    # Christian festivals
    "christmas", "easter", "good friday",
    # Sikh festivals
    "guru nanak jayanti", "guru gobind singh jayanti",
    # Buddhist/Jain festivals
    "buddha purnima", "mahavir jayanti",
}

# Purely religious observances — prayer days, fasting starts, not public celebrations
RELIGION_NAMES = {
    "maundy thursday", "ramadan start", "first day of passover",
    "first day of hanukkah", "last day of hanukkah",
    "first day of sharad navratri", "first day of durga puja festivities",
    "chhat puja (pratihar sashthi/surya sashthi)",
}


def _classify_holiday(name: str, h_types: list[str]) -> tuple[str, str]:
    """Determine (category, severity) from Calendarific type list and name."""
    types_lower = [t.lower() for t in h_types]
    name_lower = name.lower().strip()

    # Explicit religion observances (prayer/fasting start days, not celebrations)
    if name_lower in RELIGION_NAMES:
        return "religion", "normal"

    # Known festival names — public celebrations regardless of religion of origin
    is_festival = name_lower in FESTIVAL_NAMES or any(
        name_lower.startswith(f) for f in FESTIVAL_NAMES
    )
    if is_festival:
        return "festival", "high"

    # Has a religious tradition type → religion observance
    if any(t in RELIGIOUS_TYPES for t in types_lower):
        return "religion", "normal"

    # National holiday (non-religious, e.g. Republic Day, Independence Day, Gandhi Jayanti)
    if any("national" in t for t in types_lower):
        return "holiday", "high"

    # Observance / Season
    if any("observance" in t or "season" in t for t in types_lower):
        return "holiday", "low"

    return "holiday", "normal"


def fetch_calendarific_holidays() -> list[dict]:
    """
    Fetch Indian holidays and festivals from Calendarific API.
    Returns list of article-like dicts with pre-extracted event fields.
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

            category, severity = _classify_holiday(name, h_types)

            url = f"https://calendarific.com/holiday/india/{name.lower().replace(' ', '-')}-{year}"

            articles.append({
                "source_name": "Calendarific",
                "url": url,
                "title": name,
                "content": f"{name}: {description}" if description else name,
                "content_hash": None,
                "category": category,
                "extracted": {
                    "name": name,
                    "category": category,
                    "subcategory": ", ".join(h_types),
                    "summary": description or f"{name} — Indian {category}.",
                    "location": "India",
                    "start_date": date_iso[:10] if date_iso else None,
                    "end_date": None,
                    "severity": severity,
                    "importance": 8 if severity == "high" else 5,
                    "source_url": url,
                },
            })

    print(f"  Fetched {len(articles)} holidays from Calendarific")
    return articles
