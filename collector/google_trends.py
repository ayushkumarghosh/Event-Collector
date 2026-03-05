import feedparser
import httpx

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo=IN"


def fetch_google_trends() -> list[dict]:
    """
    Fetch daily trending searches from Google Trends RSS for India.
    Returns list of article-like dicts compatible with the extractor.
    """
    try:
        resp = httpx.get(
            GOOGLE_TRENDS_RSS,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  [WARN] Failed to fetch Google Trends: {e}")
        return []

    feed = feedparser.parse(resp.text)
    articles = []

    for entry in feed.entries[:20]:
        title = entry.get("title", "").strip()
        if not title:
            continue

        link = entry.get("link", "")
        traffic = entry.get("ht_approx_traffic", "")
        summary = f"'{title}' is trending on Google Search in India."
        if traffic:
            summary += f" Approximate search volume: {traffic}."

        articles.append({
            "source_name": "Google Trends India",
            "url": link or f"https://trends.google.com/trends/explore?q={title.replace(' ', '%20')}&geo=IN",
            "title": f"Trending: {title}",
            "content": summary,
            "content_hash": None,  # Computed by fetcher
            "category": "trends",
        })

    print(f"  Fetched {len(articles)} trends from Google Trends")
    return articles
