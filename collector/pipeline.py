import asyncio

from collector.sources import get_sources
from collector.fetcher import fetch_all_sources
from collector.extractor import extract_all
from collector.deduplicator import make_dedup_key
from storage.database import get_session
from storage.crud import save_raw_fetch, mark_raw_fetch_processed
from storage.graph import get_graph


def _upsert_events(graph, events: list[dict | None], raw_ids: list[int]) -> tuple[int, int]:
    """Deduplicate and upsert events into the knowledge graph. Returns (saved, skipped)."""
    saved_count = 0
    skipped_count = 0

    for i, event in enumerate(events):
        if event is None:
            continue

        name = event.get("name", "").strip()
        category = event.get("category", "").strip()
        if not name or not category:
            continue

        start_date = event.get("start_date")
        dedup_key = make_dedup_key(name, start_date, category)
        event["dedup_key"] = dedup_key

        # Fuzzy dedup: skip if a similar event already exists (same category, similar name + same date)
        if graph.fuzzy_duplicate_exists(name, category, start_date):
            skipped_count += 1
            continue

        graph.upsert_event(event)
        saved_count += 1

        # Mark raw fetch as processed
        if i < len(raw_ids):
            with get_session() as session:
                mark_raw_fetch_processed(session, raw_ids[i])

    return saved_count, skipped_count


def run_pipeline(category_filter: str | None = None):
    sources = get_sources(category_filter)
    label = category_filter or "all"
    print(f"\n=== Pipeline run: {label} ({len(sources)} sources) ===")

    graph = get_graph()

    # 1. Fetch
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

    # 3. Split: pre-extracted (Calendarific) vs needs-LLM (RSS, trends, etc.)
    pre_extracted = [a for a in raw_articles if "extracted" in a]
    needs_llm = [a for a in raw_articles if "extracted" not in a]

    # 4. Save all raw fetches to SQLite (dedup tracking only)
    raw_ids_pre = []
    raw_ids_llm = []
    with get_session() as session:
        for article in pre_extracted:
            rid = save_raw_fetch(session, article)
            raw_ids_pre.append(rid)
        for article in needs_llm:
            rid = save_raw_fetch(session, article)
            raw_ids_llm.append(rid)
    print(f"  Saved {len(raw_ids_pre) + len(raw_ids_llm)} raw fetches ({len(pre_extracted)} pre-extracted, {len(needs_llm)} for LLM)")

    # 5. Directly upsert pre-extracted events (holidays — no LLM needed)
    pre_events = [a["extracted"] for a in pre_extracted]
    saved_pre, skipped_pre = _upsert_events(graph, pre_events, raw_ids_pre)
    print(f"  Holidays: upserted {saved_pre}, skipped {skipped_pre}")

    # 6. Extract events via Gemini for the rest
    if needs_llm:
        events = extract_all(needs_llm)
        print(f"  Extracted {sum(1 for e in events if e)} events from {len(needs_llm)} articles")
        saved_llm, skipped_llm = _upsert_events(graph, events, raw_ids_llm)
        print(f"  LLM events: upserted {saved_llm}, skipped {skipped_llm}")
    else:
        saved_llm, skipped_llm = 0, 0

    # 7. Persist graph to disk
    graph.save()

    total_saved = saved_pre + saved_llm
    total_skipped = skipped_pre + skipped_llm
    stats = graph.get_stats()
    print(f"  Total: upserted {total_saved} events, skipped {total_skipped} duplicates")
    print(f"  Graph: {stats['total_events']} events, {stats['total_entities']} entities, {stats['total_relations']} relations")
    print(f"=== Pipeline complete ===\n")
