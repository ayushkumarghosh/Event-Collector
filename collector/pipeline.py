import asyncio

from collector.sources import get_sources
from collector.fetcher import fetch_all_sources
from collector.extractor import extract_all
from collector.deduplicator import make_dedup_key
from storage.database import get_session
from storage.crud import save_raw_fetch
from storage.graph import get_graph


def _normalize_categories(event: dict) -> list[str]:
    """Extract categories as a list, handling both old 'category' and new 'categories' keys."""
    cats = event.get("categories")
    if isinstance(cats, list) and cats:
        return [c.strip() for c in cats if isinstance(c, str) and c.strip()]
    # Fallback: single 'category' string
    cat = event.get("category", "").strip()
    return [cat] if cat else []


def _upsert_events(graph, events: list[dict | None], raw_ids: list[int]) -> tuple[int, int]:
    """Upsert events into the knowledge graph. Returns (saved, skipped)."""
    saved_count = 0
    skipped_count = 0

    for i, event in enumerate(events):
        if event is None:
            continue

        name = event.get("name", "").strip()
        categories = _normalize_categories(event)
        if not name or not categories:
            continue

        # Store categories as list on the event dict
        event["categories"] = categories

        start_date = event.get("start_date")
        dedup_key = make_dedup_key(name, start_date, categories)
        event["dedup_key"] = dedup_key

        # Skip if this exact dedup key already exists in graph (from a previous run)
        if graph.get_event_by_dedup_key(dedup_key):
            skipped_count += 1
            continue

        graph.upsert_event(event)
        saved_count += 1

    return saved_count, skipped_count


def run_pipeline(category_filter: str | None = None):
    sources = get_sources(category_filter)
    label = category_filter or "all"
    print(f"\n=== Pipeline run: {label} ({len(sources)} sources) ===")

    graph = get_graph()

    # 1. Fetch from all sources (RSS, Google Trends, Eventbrite, Calendarific)
    raw_articles = asyncio.run(fetch_all_sources(sources))
    if not raw_articles:
        print("  No new articles found.")
        return

    # 2. Deduplicate by content_hash (overlapping sources produce same hash)
    seen_hashes = set()
    unique_articles = []
    for article in raw_articles:
        if article["content_hash"] not in seen_hashes:
            seen_hashes.add(article["content_hash"])
            unique_articles.append(article)
    raw_articles = unique_articles

    # 3. Save all raw fetches to SQLite (dedup tracking only)
    raw_ids = []
    with get_session() as session:
        for article in raw_articles:
            rid = save_raw_fetch(session, article)
            raw_ids.append(rid)
    print(f"  Saved {len(raw_ids)} raw fetches for Gemini processing")

    # 4. Send everything through Gemini for extraction, categorization, and dedup
    events = extract_all(raw_articles)
    print(f"  Extracted {len(events)} unique events from {len(raw_articles)} articles")

    saved, skipped = _upsert_events(graph, events, [])
    print(f"  Events: upserted {saved}, skipped {skipped}")

    # 5. Persist graph to disk
    graph.save()

    stats = graph.get_stats()
    print(f"  Graph: {stats['total_events']} events, {stats['total_entities']} entities, {stats['total_relations']} relations")
    print(f"=== Pipeline complete ===\n")
