import asyncio
import hashlib

import feedparser
import httpx

from collector.sources import FeedSource
from collector.google_trends import fetch_google_trends
from collector.eventbrite import fetch_eventbrite_events
from collector.calendarific import fetch_calendarific_holidays
from storage.database import get_session
from storage.crud import raw_fetch_exists

MAX_ENTRIES_PER_FEED = 20
MAX_CONTENT_LENGTH = 3000
FETCH_TIMEOUT = 30


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def compute_content_hash(url: str, title: str) -> str:
    raw = f"{_normalize(url or '')}::{_normalize(title or '')}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _fetch_feed(client: httpx.AsyncClient, source: FeedSource) -> list[dict]:
    try:
        resp = await client.get(source.url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [WARN] Failed to fetch {source.name}: {e}")
        return []

    feed = feedparser.parse(resp.text)
    articles = []

    for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "") or entry.get("description", "") or ""
        content_text = summary.strip()[:MAX_CONTENT_LENGTH]

        if not title:
            continue

        content_hash = compute_content_hash(link, title)

        articles.append({
            "source_name": source.name,
            "url": link,
            "title": title,
            "content": content_text,
            "content_hash": content_hash,
            "category": source.category,
        })

    return articles


def _filter_unseen(articles: list[dict]) -> list[dict]:
    with get_session() as session:
        return [a for a in articles if not raw_fetch_exists(session, a["content_hash"])]


async def fetch_all_sources(sources: list[FeedSource]) -> list[dict]:
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, headers={
        "User-Agent": "IndiaEventCollector/1.0"
    }) as client:
        tasks = [_fetch_feed(client, s) for s in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles = []
    for result in results:
        if isinstance(result, Exception):
            print(f"  [WARN] Feed fetch error: {result}")
            continue
        all_articles.extend(result)

    # Fetch Google Trends
    trends_articles = fetch_google_trends()
    for article in trends_articles:
        article["content_hash"] = compute_content_hash(article["url"], article["title"])
    all_articles.extend(trends_articles)

    # Fetch Eventbrite events
    eb_articles = fetch_eventbrite_events()
    for article in eb_articles:
        article["content_hash"] = compute_content_hash(article["url"], article["title"])
    all_articles.extend(eb_articles)

    # Fetch Calendarific holidays + pre-structured sub-events
    cal_articles, cal_sub_events = fetch_calendarific_holidays()
    for article in cal_articles:
        article["content_hash"] = compute_content_hash(article["url"], article["title"])
    all_articles.extend(cal_articles)

    unseen = _filter_unseen(all_articles)
    print(f"  Fetched {len(all_articles)} articles, {len(unseen)} new (unseen)")
    return unseen, cal_sub_events
