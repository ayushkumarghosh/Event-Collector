import httpx

from config import EVENTBRITE_API_TOKEN

EVENTBRITE_API_URL = "https://www.eventbriteapi.com/v3/destination/search/"

# Major Indian cities to search for events
INDIA_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Jaipur", "Ahmedabad", "Goa",
]


def fetch_eventbrite_events() -> list[dict]:
    """
    Fetch upcoming events from Eventbrite destination search API for Indian cities.
    Returns list of article-like dicts compatible with the extractor.
    """
    if not EVENTBRITE_API_TOKEN:
        print("  [WARN] EVENTBRITE_API_TOKEN not set, skipping Eventbrite")
        return []

    headers = {
        "Authorization": f"Bearer {EVENTBRITE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    articles = []
    seen_ids = set()

    for city in INDIA_CITIES:
        try:
            resp = httpx.post(
                EVENTBRITE_API_URL,
                json={
                    "event_search": {
                        "q": city,
                        "dates": "current_future",
                        "page_size": 10,
                    }
                },
                headers=headers,
                timeout=15,
                follow_redirects=True,
            )
            if resp.status_code == 401:
                print("  [WARN] Eventbrite auth failed (401). Check EVENTBRITE_API_TOKEN.")
                return articles
            if resp.status_code != 200:
                continue

            data = resp.json()
            events = data.get("events", {}).get("results", [])
            if not events:
                continue

            for ev in events:
                event_id = str(ev.get("id", ""))
                if not event_id or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)

                name = (ev.get("name") or "").strip()
                if not name:
                    continue

                summary = ev.get("summary", "") or ""
                url = ev.get("url", "") or f"https://www.eventbrite.com/e/{event_id}"
                start_date = ev.get("start_date", "") or ""
                end_date = ev.get("end_date", "") or ""

                # Extract city from locations array
                location = city
                for loc in ev.get("locations", []):
                    if loc.get("type") == "locality":
                        location = loc.get("name", city)
                        break

                content = f"{name}. {summary}".strip()[:3000]

                articles.append({
                    "source_name": "Eventbrite",
                    "url": url,
                    "title": name,
                    "content": content,
                    "content_hash": None,  # Computed by fetcher
                    "category": "situation",
                    "extra": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "location": location,
                    },
                })

        except Exception as e:
            print(f"  [WARN] Eventbrite fetch failed for {city}: {e}")
            continue

    print(f"  Fetched {len(articles)} events from Eventbrite ({len(INDIA_CITIES)} cities)")
    return articles
