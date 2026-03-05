from sqlalchemy import select, func

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
