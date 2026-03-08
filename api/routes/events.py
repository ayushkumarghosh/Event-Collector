from fastapi import APIRouter, Query, HTTPException

from storage.graph import get_graph
from api.schemas import EventOut, EventDetailOut, EntityOut

router = APIRouter()


def _event_to_out(data: dict) -> EventOut:
    return EventOut(
        id=data.get("id", ""),
        name=data.get("name", ""),
        category=data.get("category", ""),
        subcategory=data.get("subcategory") or None,
        summary=data.get("summary") or None,
        location=data.get("location") or None,
        start_date=data.get("start_date") or None,
        end_date=data.get("end_date") or None,
        severity=data.get("severity", "normal"),
        importance=float(data.get("importance", 5)),
        source_url=data.get("source_url") or None,
        created_at=data.get("created_at") or None,
        updated_at=data.get("updated_at") or None,
    )


@router.get("/events", response_model=list[EventOut])
def list_events(
    category: str | None = Query(None),
    severity: str | None = Query(None),
    location: str | None = Query(None),
    q: str | None = Query(None),
    from_date: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    graph = get_graph()
    events = graph.get_events(
        category=category,
        severity=severity,
        location=location,
        q=q,
        from_date=from_date,
        limit=limit,
        offset=offset,
    )
    return [_event_to_out(e) for e in events]


@router.get("/events/{event_id:path}", response_model=EventDetailOut)
def get_event(event_id: str):
    graph = get_graph()
    data = graph.get_event(event_id)
    if not data:
        raise HTTPException(status_code=404, detail="Event not found")

    out = _event_to_out(data)
    return EventDetailOut(
        **out.model_dump(),
        relations=data.get("relations", []),
    )


@router.get("/events/{event_id:path}/related", response_model=list[EventOut])
def get_related_events(event_id: str, limit: int = Query(10, ge=1, le=50)):
    graph = get_graph()
    related = graph.get_related_events(event_id, limit=limit)
    return [_event_to_out(e) for e in related]


@router.get("/timeline", response_model=list[EventOut])
def get_timeline(
    start: str = Query(..., description="Start date (ISO 8601)"),
    end: str = Query(..., description="End date (ISO 8601)"),
):
    graph = get_graph()
    events = graph.get_timeline(start, end)
    return [_event_to_out(e) for e in events]


@router.get("/locations", response_model=list[str])
def list_locations():
    graph = get_graph()
    return graph.get_locations()


@router.get("/entities", response_model=list[EntityOut])
def list_entities(entity_type: str | None = Query(None)):
    graph = get_graph()
    return graph.get_entities(entity_type=entity_type)


@router.get("/entities/{entity_type}/{entity_name}/events", response_model=list[EventOut])
def get_events_by_entity(entity_type: str, entity_name: str):
    graph = get_graph()
    events = graph.get_events_by_entity(entity_type, entity_name)
    return [_event_to_out(e) for e in events]
