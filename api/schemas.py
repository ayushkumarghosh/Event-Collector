from pydantic import BaseModel


class EventOut(BaseModel):
    id: str
    name: str
    categories: list[str] = []
    subcategory: str | None = None
    summary: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    severity: str = "normal"
    importance: float = 5
    source_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class EventDetailOut(EventOut):
    relations: list[dict] = []


class RelationOut(BaseModel):
    relation: str
    target_id: str
    target_type: str
    target_name: str


class EntityOut(BaseModel):
    id: str
    name: str
    entity_type: str
    event_count: int


class StatsOut(BaseModel):
    total_events: int
    total_entities: int
    total_relations: int
    total_raw_fetches: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
