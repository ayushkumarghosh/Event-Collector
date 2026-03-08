"""
Knowledge Graph + Temporal Event Store built on NetworkX.

Node types:
  - event:    {node_type, name, category, subcategory, summary, severity, importance,
               start_date, end_date, source_url, dedup_key, created_at, updated_at}
  - entity:   {node_type, entity_type, name}          (location, person, org, topic)
  - category: {node_type, name}

Edge types (stored as edge attr "relation"):
  - located_in:      event → location entity
  - belongs_to:      event → category node
  - involves:        event → person/org/topic entity
  - related_to:      event → event (same entity overlap)
  - concurrent_with: event → event (overlapping dates)
  - preceded_by:     event → event (sequential)

Persistence: saved as GraphML to disk after every mutation batch.
"""

import os
import threading
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import networkx as nx

_lock = threading.Lock()

GRAPH_PATH = os.getenv("GRAPH_PATH", "knowledge_graph.graphml")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _make_entity_id(entity_type: str, name: str) -> str:
    return f"{entity_type}::{_normalize(name)}"


def _make_category_id(category: str) -> str:
    return f"category::{category}"


def _safe(value, default=""):
    """Ensure a value is GraphML-safe (no None — GraphML cannot serialize NoneType)."""
    if value is None:
        return default
    return value


class KnowledgeGraph:
    def __init__(self, path: str | None = None):
        self.path = Path(path or GRAPH_PATH)
        self.G = nx.DiGraph()
        self._load()

    # --- Persistence ---

    def _load(self):
        if self.path.exists() and self.path.stat().st_size > 0:
            try:
                self.G = nx.read_graphml(self.path)
                print(f"  [Graph] Loaded {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
            except Exception as e:
                print(f"  [Graph] Failed to load, starting fresh: {e}")
                self.G = nx.DiGraph()
        else:
            self.G = nx.DiGraph()
            # Seed category nodes
            for cat in ["religion", "state", "holiday", "festival", "situation"]:
                cid = _make_category_id(cat)
                self.G.add_node(cid, node_type="category", name=cat)

    def save(self):
        with _lock:
            nx.write_graphml(self.G, str(self.path))

    # --- Entity management ---

    def _ensure_entity(self, entity_type: str, name: str) -> str:
        eid = _make_entity_id(entity_type, name)
        if eid not in self.G:
            self.G.add_node(eid, node_type="entity", entity_type=entity_type, name=name)
        return eid

    def _ensure_category(self, category: str) -> str:
        cid = _make_category_id(category)
        if cid not in self.G:
            self.G.add_node(cid, node_type="category", name=category)
        return cid

    # --- Event CRUD ---

    def get_event_by_dedup_key(self, dedup_key: str) -> str | None:
        for nid, data in self.G.nodes(data=True):
            if data.get("node_type") == "event" and data.get("dedup_key") == dedup_key:
                return nid
        return None

    def upsert_event(self, event_dict: dict) -> str:
        """Insert or update an event node. Returns the node ID."""
        dedup_key = event_dict["dedup_key"]
        existing_id = self.get_event_by_dedup_key(dedup_key)

        if existing_id:
            # Update mutable fields
            self.G.nodes[existing_id]["summary"] = _safe(event_dict.get("summary"), self.G.nodes[existing_id].get("summary", ""))
            self.G.nodes[existing_id]["severity"] = _safe(event_dict.get("severity"), self.G.nodes[existing_id].get("severity", "normal"))
            self.G.nodes[existing_id]["importance"] = float(_safe(event_dict.get("importance"), self.G.nodes[existing_id].get("importance", 5)))
            self.G.nodes[existing_id]["updated_at"] = _now_iso()
            return existing_id

        # Create new event node
        node_id = f"event::{uuid.uuid4().hex[:12]}"
        self.G.add_node(
            node_id,
            node_type="event",
            name=_safe(event_dict.get("name")),
            category=_safe(event_dict.get("category")),
            subcategory=_safe(event_dict.get("subcategory")),
            summary=_safe(event_dict.get("summary")),
            location=_safe(event_dict.get("location")),
            start_date=_safe(event_dict.get("start_date")),
            end_date=_safe(event_dict.get("end_date")),
            severity=_safe(event_dict.get("severity"), "normal"),
            importance=float(_safe(event_dict.get("importance"), 5)),
            source_url=_safe(event_dict.get("source_url")),
            dedup_key=dedup_key,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )

        # Link to category
        category = _safe(event_dict.get("category"))
        if category:
            cid = self._ensure_category(category)
            self.G.add_edge(node_id, cid, relation="belongs_to")

        # Link to location entity
        location = _safe(event_dict.get("location"))
        if location:
            lid = self._ensure_entity("location", location)
            self.G.add_edge(node_id, lid, relation="located_in")

        # Auto-discover temporal relations with existing events
        self._link_temporal(node_id, event_dict)

        # Auto-discover entity relations (shared location/category)
        self._link_related(node_id)

        return node_id

    def _link_temporal(self, node_id: str, event_dict: dict):
        """Link concurrent/sequential events based on date overlap."""
        start = _safe(event_dict.get("start_date"))
        end = _safe(event_dict.get("end_date")) or start
        if not start:
            return

        for nid, data in self.G.nodes(data=True):
            if data.get("node_type") != "event" or nid == node_id:
                continue
            other_start = _safe(data.get("start_date"))
            other_end = _safe(data.get("end_date")) or other_start
            if not other_start:
                continue

            # Check overlap: events are concurrent if date ranges intersect
            if start <= other_end and end >= other_start:
                if not self.G.has_edge(node_id, nid):
                    self.G.add_edge(node_id, nid, relation="concurrent_with")

    def _link_related(self, node_id: str):
        """Link events that share the same location entity."""
        location_neighbors = [
            target for _, target, data in self.G.out_edges(node_id, data=True)
            if data.get("relation") == "located_in"
        ]

        for loc_id in location_neighbors:
            # Find other events also located_in this location
            for source, _, data in self.G.in_edges(loc_id, data=True):
                if data.get("relation") == "located_in" and source != node_id:
                    if self.G.nodes[source].get("node_type") == "event":
                        if not self.G.has_edge(node_id, source) and not self.G.has_edge(source, node_id):
                            self.G.add_edge(node_id, source, relation="related_to")

    # --- Queries ---

    def get_events(
        self,
        category: str | None = None,
        severity: str | None = None,
        location: str | None = None,
        q: str | None = None,
        from_date: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        events = []
        for nid, data in self.G.nodes(data=True):
            if data.get("node_type") != "event":
                continue
            if category and data.get("category") != category:
                continue
            if severity and data.get("severity") != severity:
                continue
            if location and location.lower() not in _safe(data.get("location")).lower():
                continue
            if q:
                q_lower = q.lower()
                if q_lower not in _safe(data.get("name")).lower() and q_lower not in _safe(data.get("summary")).lower():
                    continue
            if from_date and _safe(data.get("start_date")) and _safe(data.get("start_date")) < from_date:
                continue

            events.append({"id": nid, **data})

        # Sort by importance desc, then created_at desc
        events.sort(key=lambda e: (-float(_safe(e.get("importance"), 5)), e.get("created_at", "")))

        return events[offset : offset + limit]

    def get_event(self, event_id: str) -> dict | None:
        if event_id not in self.G or self.G.nodes[event_id].get("node_type") != "event":
            return None
        data = dict(self.G.nodes[event_id])
        data["id"] = event_id

        # Gather relations
        relations = []
        for _, target, edata in self.G.out_edges(event_id, data=True):
            rel = edata.get("relation", "unknown")
            target_data = dict(self.G.nodes[target])
            relations.append({
                "relation": rel,
                "target_id": target,
                "target_type": target_data.get("node_type", ""),
                "target_name": target_data.get("name", ""),
            })
        for source, _, edata in self.G.in_edges(event_id, data=True):
            rel = edata.get("relation", "unknown")
            source_data = dict(self.G.nodes[source])
            if source_data.get("node_type") == "event":
                relations.append({
                    "relation": rel,
                    "target_id": source,
                    "target_type": "event",
                    "target_name": source_data.get("name", ""),
                })

        data["relations"] = relations
        return data

    def get_stats(self) -> dict:
        total_events = 0
        by_category = {}
        by_severity = {}
        total_entities = 0

        for _, data in self.G.nodes(data=True):
            nt = data.get("node_type")
            if nt == "event":
                total_events += 1
                cat = data.get("category", "unknown")
                by_category[cat] = by_category.get(cat, 0) + 1
                sev = data.get("severity", "normal")
                by_severity[sev] = by_severity.get(sev, 0) + 1
            elif nt == "entity":
                total_entities += 1

        return {
            "total_events": total_events,
            "total_entities": total_entities,
            "total_relations": self.G.number_of_edges(),
            "by_category": by_category,
            "by_severity": by_severity,
        }

    def get_related_events(self, event_id: str, limit: int = 10) -> list[dict]:
        """Get events related to a given event via any edge."""
        if event_id not in self.G:
            return []

        related_ids = set()
        # Outgoing edges to other events
        for _, target, data in self.G.out_edges(event_id, data=True):
            if self.G.nodes[target].get("node_type") == "event":
                related_ids.add(target)
        # Incoming edges from other events
        for source, _, data in self.G.in_edges(event_id, data=True):
            if self.G.nodes[source].get("node_type") == "event":
                related_ids.add(source)

        results = []
        for rid in list(related_ids)[:limit]:
            d = dict(self.G.nodes[rid])
            d["id"] = rid
            results.append(d)
        return results

    def get_events_by_entity(self, entity_type: str, entity_name: str) -> list[dict]:
        """Get all events linked to a specific entity (e.g., location 'Mumbai')."""
        eid = _make_entity_id(entity_type, entity_name)
        if eid not in self.G:
            return []

        events = []
        for source, _, data in self.G.in_edges(eid, data=True):
            if self.G.nodes[source].get("node_type") == "event":
                d = dict(self.G.nodes[source])
                d["id"] = source
                events.append(d)
        return events

    def get_timeline(self, start: str, end: str) -> list[dict]:
        """Get all events within a date range."""
        events = []
        for nid, data in self.G.nodes(data=True):
            if data.get("node_type") != "event":
                continue
            ev_start = _safe(data.get("start_date"))
            ev_end = _safe(data.get("end_date")) or ev_start
            if not ev_start:
                continue
            if ev_start <= end and ev_end >= start:
                d = dict(data)
                d["id"] = nid
                events.append(d)

        events.sort(key=lambda e: e.get("start_date", ""))
        return events

    def fuzzy_duplicate_exists(self, name: str, category: str, start_date: str | None = None, threshold: float = 0.85) -> bool:
        """Check if a similar event already exists in the graph.
        For dated events, also requires the same date to match.
        For undated events, matches on name similarity + category only."""
        norm_name = _normalize(name)
        date_key = (start_date or "")[:10]
        count = 0
        for _, data in self.G.nodes(data=True):
            if data.get("node_type") != "event":
                continue
            # Category must match
            if data.get("category") != category:
                continue
            # If the new event has a date, existing event must share the same date
            if date_key:
                existing_date = (_safe(data.get("start_date")) or "")[:10]
                if existing_date != date_key:
                    continue
            existing = _normalize(_safe(data.get("name")))
            if SequenceMatcher(None, norm_name, existing).ratio() >= threshold:
                return True
            count += 1
            if count >= 500:
                break
        return False

    def get_locations(self) -> list[str]:
        """Get all unique non-empty location values from events, sorted by frequency."""
        loc_counts: dict[str, int] = {}
        for _, data in self.G.nodes(data=True):
            if data.get("node_type") != "event":
                continue
            loc = _safe(data.get("location")).strip()
            if loc and loc.lower() != "india":
                loc_counts[loc] = loc_counts.get(loc, 0) + 1
        # Sort by count descending
        return [loc for loc, _ in sorted(loc_counts.items(), key=lambda x: -x[1])]

    def get_entities(self, entity_type: str | None = None) -> list[dict]:
        """List all entities, optionally filtered by type."""
        entities = []
        for nid, data in self.G.nodes(data=True):
            if data.get("node_type") != "entity":
                continue
            if entity_type and data.get("entity_type") != entity_type:
                continue
            # Count connected events
            event_count = sum(
                1 for source, _, _ in self.G.in_edges(nid, data=True)
                if self.G.nodes[source].get("node_type") == "event"
            )
            entities.append({
                "id": nid,
                "name": data.get("name", ""),
                "entity_type": data.get("entity_type", ""),
                "event_count": event_count,
            })
        entities.sort(key=lambda e: -e["event_count"])
        return entities


# --- Singleton ---
_graph_instance: KnowledgeGraph | None = None


def get_graph() -> KnowledgeGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = KnowledgeGraph()
    return _graph_instance


def init_graph():
    """Initialize the graph (called at startup)."""
    get_graph()
    print("  [Graph] Initialized")
