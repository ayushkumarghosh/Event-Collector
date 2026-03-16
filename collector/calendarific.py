import json
import re

import httpx
from datetime import datetime
from google import genai

from config import CALENDARIFIC_API_KEY, GEMINI_API_KEY, LLM_MODEL

API_URL = "https://calendarific.com/api/v2/holidays"

_gemini_client = genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 120_000})

SUB_EVENTS_PROMPT = """You are an Indian cultural calendar expert. Below is a list of holidays and festivals from India for {year}.

Your task: For EVERY holiday/festival that spans multiple days or has associated preparatory/concluding days, generate ALL individual sub-events with exact dates.

You MUST generate EVERY SINGLE DAY for these festivals — do NOT skip any:

1. Navratri (9 days): Generate ALL 9 days — Day 1 Shailaputri, Day 2 Brahmacharini, Day 3 Chandraghanta, Day 4 Kushmanda, Day 5 Skandamata, Day 6 Katyayani, Day 7 Kalaratri, Day 8 Mahagauri/Ashtami, Day 9 Siddhidatri/Navami
2. Durga Puja (5 days): Maha Shashti, Maha Saptami, Maha Ashtami, Maha Navami, Vijaya Dashami (Sindoor Khela + Idol Immersion)
3. Diwali (5 days): Dhanteras, Naraka Chaturdashi/Chhoti Diwali, main Diwali/Lakshmi Puja, Govardhan Puja, Bhai Dooj
4. Ganesh Chaturthi (key days): Day 1 Sthapana, Day 5 Visarjan, Day 7 Visarjan, Day 10 Anant Chaturdashi/Grand Visarjan
5. Valentine's Week (7 days): Rose Day, Propose Day, Chocolate Day, Teddy Day, Promise Day, Hug Day, Kiss Day
6. Anti-Valentine's Week (7 days): Slap Day, Kick Day, Perfume Day, Flirting Day, Confession Day, Missing Day, Breakup Day
7. Pongal (4 days): Bhogi, Thai Pongal, Mattu Pongal, Kaanum Pongal
8. Holi (2 days): Holika Dahan + Rangwali Holi/Dhulandi
9. Chhath Puja (4 days): Nahay Khay, Kharna, Sandhya Arghya, Usha Arghya
10. Onam (key days): Uthradom, First Onam, Uthradom Day, Thiruvonam
11. Ramadan milestones: Shab-e-Qadr (~21st night), Alvida Jumma (last Friday), Chand Raat (night before Eid)
12. Eid ul-Fitr: Chand Raat, Eid Day 1, Eid Day 2
13. Eid ul-Adha: Day 1 (Qurbani), Day 2, Day 3
14. Janmashtami: Midnight celebrations + Dahi Handi (next day)
15. Christmas: Christmas Eve + Christmas Day
16. Guru Nanak Jayanti: Akhand Path (2 days before), Nagar Kirtan (1 day before), main day
17. Muharram: Day 1 (Islamic New Year) + Day 10 (Ashura)
18. Karva Chauth: Sargi (pre-dawn, day before) + main Karva Chauth
19. Rath Yatra: Main procession + Bahuda Yatra (return, 9 days later)
20. Makar Sankranti: Lohri (day before) + Uttarayan/Kite Festival
21. Bihu: Goru Bihu, Manuh Bihu, Gosain Bihu
22. Any other festival you know has sub-events — generate them all

Do NOT generate sub-events for single-day observances with no sub-events (e.g. Gandhi Jayanti, Ambedkar Jayanti).
Do NOT skip any days of multi-day festivals. Generate EVERY day.

For each sub-event return:
{{
  "name": "<specific sub-event name>",
  "date": "<YYYY-MM-DD>",
  "summary": "<1-2 sentence description of what happens on this specific day>",
  "categories": [<from: "religion", "festival", "holiday", "situation">],
  "subcategory": "<religion name like Hinduism/Islam/Christianity/Sikhism or Trending for secular>",
  "parent_festival": "<name of the main festival>"
}}

Return a single JSON array of ALL sub-events for ALL festivals combined. If a festival has no sub-events, simply skip it.
Return ONLY the JSON array, no markdown fences, no explanation.

Holidays:
{holidays_text}
"""


def fetch_calendarific_holidays() -> tuple[list[dict], list[dict]]:
    """
    Fetch Indian holidays and festivals from Calendarific API.
    Uses Gemini to automatically generate sub-events for multi-day festivals.

    Returns:
        (articles, sub_events) — articles go through Gemini extraction;
        sub_events are pre-structured event dicts that bypass Gemini extraction.
    """
    if not CALENDARIFIC_API_KEY:
        print("  [WARN] CALENDARIFIC_API_KEY not set, skipping holidays fetch")
        return [], []

    year = datetime.now().year
    articles = []
    holidays_for_gemini = []
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

            name_key = name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            description = h.get("description", "") or ""
            date_iso = h.get("date", {}).get("iso", "")
            h_types = h.get("type", [])
            types_str = ", ".join(h_types)

            url = f"https://calendarific.com/holiday/india/{name.lower().replace(' ', '-')}-{year}"

            content = f"{name}. {description} Type: {types_str}. Date: {date_iso[:10] if date_iso else 'unknown'}."

            articles.append({
                "source_name": "Calendarific",
                "url": url,
                "title": name,
                "content": content,
                "content_hash": None,
                "category": "holiday",
            })

            # Collect for Gemini sub-event generation
            holidays_for_gemini.append({
                "name": name,
                "date": date_iso[:10] if date_iso else "",
                "description": description,
                "types": h_types,
            })

    # Generate sub-events via single Gemini call
    sub_events = []
    if holidays_for_gemini:
        sub_events = _generate_sub_events(holidays_for_gemini, year, seen_names)

    print(f"  Fetched {len(articles)} holidays from Calendarific ({len(sub_events)} sub-events)")
    return articles, sub_events


def _generate_sub_events(holidays: list[dict], year: int, seen_names: set) -> list[dict]:
    """Use a single Gemini call to generate all sub-events for all festivals."""
    holidays_text = "\n".join(
        f"- {h['name']} | Date: {h['date']} | {h['description'][:120]}"
        for h in holidays
    )

    prompt = SUB_EVENTS_PROMPT.format(year=year, holidays_text=holidays_text)

    try:
        response = _gemini_client.models.generate_content(model=LLM_MODEL, contents=prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        picks = json.loads(raw.strip())
        if not isinstance(picks, list):
            picks = []
    except Exception as e:
        print(f"  [WARN] Gemini sub-event generation failed: {e}")
        return []

    # Convert to event dicts, dedup against seen names
    sub_events = []
    for pick in picks:
        name = (pick.get("name") or "").strip()
        if not name:
            continue

        name_key = name.lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        date = pick.get("date", "")
        if not date or len(date) < 10:
            continue

        categories = pick.get("categories", [])
        if not isinstance(categories, list) or not categories:
            categories = ["festival"]

        parent = pick.get("parent_festival", "")
        url_slug = name.lower().replace(" ", "-").replace("'", "").replace("/", "-")
        source_url = f"https://calendarific.com/holiday/india/{url_slug}-{year}"

        sub_events.append({
            "name": name,
            "categories": categories,
            "subcategory": pick.get("subcategory") or None,
            "summary": pick.get("summary", f"Sub-event of {parent}"),
            "location": "India",
            "start_date": date[:10],
            "end_date": date[:10],
            "severity": "low",
            "importance": 4,
            "source_url": source_url,
        })

    return sub_events
