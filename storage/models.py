from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class RawFetch(Base):
    """Minimal table — only used for content-hash dedup lookups."""
    __tablename__ = "raw_fetches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(200), nullable=False)
    url = Column(String(500))
    title = Column(String(500))
    content_hash = Column(String(64), nullable=False, unique=True)
    category = Column(String(50))
    processed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
