from sqlalchemy import select, func, distinct

from storage.models import RawFetch


def raw_fetch_exists(session, content_hash: str) -> bool:
    stmt = select(RawFetch.id).where(RawFetch.content_hash == content_hash).limit(1)
    return session.execute(stmt).first() is not None


def save_raw_fetch(session, article: dict) -> int:
    row = RawFetch(
        source_name=article["source_name"],
        url=article.get("url"),
        title=article.get("title"),
        content_hash=article["content_hash"],
        category=article.get("category"),
    )
    session.add(row)
    session.flush()
    return row.id


def mark_raw_fetch_processed(session, raw_fetch_id: int):
    row = session.get(RawFetch, raw_fetch_id)
    if row:
        row.processed = True


def get_raw_fetch_count(session) -> int:
    return session.execute(select(func.count(RawFetch.id))).scalar() or 0


def get_total_source_count(session) -> int:
    """Get the total number of distinct news sources in raw_fetches."""
    return session.execute(
        select(func.count(distinct(RawFetch.source_name)))
    ).scalar() or 1  # avoid division by zero


def get_source_coverage(session, keywords: list[str]) -> tuple[int, int]:
    """
    Count how many distinct sources have articles matching ANY of the keywords.
    Returns (matching_source_count, total_source_count).
    """
    total = get_total_source_count(session)

    if not keywords:
        return 0, total

    # Build a LIKE filter for each keyword
    conditions = []
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if kw_clean and len(kw_clean) >= 3:
            conditions.append(func.lower(RawFetch.title).contains(kw_clean))

    if not conditions:
        return 0, total

    from sqlalchemy import or_
    stmt = select(func.count(distinct(RawFetch.source_name))).where(or_(*conditions))
    matching = session.execute(stmt).scalar() or 0

    return matching, total
