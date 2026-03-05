import httpx

EVENTBRITE_SEARCH_URL = "https://www.eventbrite.com/api/v3/destination/search/"

# Major Indian cities to search for events
INDIA_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Jaipur", "Ahmedabad", "Goa",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.eventbrite.com/",
}


def fetch_eventbrite_events() -> list[dict]:
    """
    Fetch upcoming events from Eventbrite's destination search for Indian cities.
    Returns list of article-like dicts compatible with the extractor.
    """
    articles = []
    seen_ids = set()

    for city in INDIA_CITIES:
        try:
            resp = httpx.get(
                EVENTBRITE_SEARCH_URL,
                params={
                    "dates": "current_future",
                    "dedup": "1",
                    "page_size": "10",
                    "place": f"{city}, India",
                },
                headers=HEADERS,
                timeout=15,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            events = data.get("events", data.get("results", []))
            if not events:
                continue

            for ev in events:
                event_id = str(ev.get("id", ""))
                if not event_id or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)

                name = ev.get("name", "").strip()
                if not name:
                    continue

                summary = ev.get("summary", "") or ev.get("description", "") or ""
                url = ev.get("url", "") or f"https://www.eventbrite.com/e/{event_id}"
                start = ev.get("start_date", "") or ""
                venue = ev.get("primary_venue", {}) or {}
                location = venue.get("address", {}).get("city", city) if venue else city

                content = f"{name}. {summary}".strip()[:3000]

                articles.append({
                    "source_name": "Eventbrite",
                    "url": url,
                    "title": name,
                    "content": content,
                    "content_hash": None,  # Computed by fetcher
                    "category": "entertainment",
                    "extra": {
                        "start_date": start,
                        "location": location,
                    },
                })

        except Exception as e:
            print(f"  [WARN] Eventbrite fetch failed for {city}: {e}")
            continue

    print(f"  Fetched {len(articles)} events from Eventbrite ({len(INDIA_CITIES)} cities)")
    return articles
