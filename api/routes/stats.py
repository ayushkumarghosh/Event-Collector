from fastapi import APIRouter

from storage.graph import get_graph
from storage.database import get_session
from storage.crud import get_raw_fetch_count
from api.schemas import StatsOut

router = APIRouter()


@router.get("/stats", response_model=StatsOut)
def get_stats():
    graph = get_graph()
    stats = graph.get_stats()

    with get_session() as session:
        raw_count = get_raw_fetch_count(session)

    return StatsOut(
        total_events=stats["total_events"],
        total_entities=stats["total_entities"],
        total_relations=stats["total_relations"],
        total_raw_fetches=raw_count,
        by_category=stats["by_category"],
        by_severity=stats["by_severity"],
    )
