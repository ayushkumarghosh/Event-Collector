import json
import re
from datetime import date, timedelta

from fastapi import APIRouter, Query, HTTPException
from google import genai
from google.genai.errors import ClientError, ServerError

from config import GEMINI_API_KEY, LLM_MODEL
from storage.graph import get_graph
from api.schemas import EventOut, EventDetailOut, EntityOut, TrendingEventOut

router = APIRouter()

_gemini_client = genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 120_000})

TRENDING_PROMPT = """You are a Viral Event Manager, Growth Hacker, and Behavioral Psychologist specializing in the Indian social media audience.

Below is a list of current events happening in India (within the past 3 days and upcoming 3 days).

---

STEP 1 — TREND ANALYSIS

Analyze each event for:
- Emotional engagement (fun, pride, curiosity, nostalgia)
- Shareability — would someone repost or duet this?
- Cultural relevance to Indian audiences (regional festivals, cricket, Bollywood, student life)
- Ease of participation — can a regular person with just a phone create content?
- Meme potential — can it become a template, format, or sound trend?

---

STEP 2 — SAFETY FILTER (MANDATORY)

IMMEDIATELY REJECT any event that involves:
- Politics, political parties, politicians, elections, government policy, or legislation
- Legal or compliance risk — court cases, arrests, investigations, scams, fraud allegations
- Violence, crime, accidents, deaths, terrorism, or military conflict
- Sensitive social issues — poverty, discrimination, assault, abuse
- Anything that would make a brand or platform look bad if associated with it

ONLY ALLOW events that are:
- Fun, entertaining, or culturally engaging
- Safe for all ages and all communities
- Brand-safe — a major brand could sponsor this trend without PR risk

When in doubt, SKIP the event. It is better to return fewer results than to include a risky one.

---

STEP 3 — PARTICIPATORY FILTER

Pick ONLY events that can spark a PARTICIPATORY TREND — where regular users can create their own clips inspired by the event. The key test: "Can thousands of random people make their own version of this clip?"

GOOD examples (participatory):
- India wins T20 World Cup → everyone films their celebration reactions, street celebrations, "POV: India won" clips
- Holi festival → color throwing clips, outfit transitions, prank videos, "before vs after Holi" trends
- CBSE exam day → relatable student reaction clips, "POV: walking out of math exam", parent reaction clips
- A viral dialogue/moment → lip sync, reenactments, meme templates
- National holiday → patriotic transitions, flag hoisting clips, "proud moment" trends

BAD examples (NOT participatory — only news channels can cover these):
- Stock market crash → regular people can't make their own version
- Accident or crime news → only reportable, not recreatable
- Government policy announcement → no user participation angle
- Celebrity rumors → only gossip, users can't participate

---

STEP 4 — CHALLENGE DESIGN (Viral Formula)

For each selected event, design a trend/challenge that follows this viral loop:

HOOK → SIMPLE ACTION → SHARE → INVITE FRIENDS → REPEAT

The challenge must be:
- Simple to understand in under 3 seconds
- Easy to participate in with just a smartphone
- Fun, engaging, and highly shareable
- Suitable for short-form video (Reels, Shorts, TikTok)

---

STEP 5 — VIRAL PSYCHOLOGY TRIGGERS

For each trend, incorporate at least 2 of these behavioral triggers:
- Social proof ("everyone is doing this")
- FOMO (limited-time relevance — the event is happening NOW)
- Competition (who did it better?)
- Status & recognition (makes the creator look good, funny, or talented)
- Emotional engagement (pride, nostalgia, humor, relatability)
- Community belonging (shared identity — "only Indians will understand")
- Social currency (people share things that make them look cool or in-the-know)

---

STEP 6 — VIRAL GROWTH MECHANICS

Design each trend idea so it naturally encourages:
- "Tag a friend who..." or "Duet this" mechanics
- Team/group participation (couples, friend groups, families)
- Share-to-unlock or chain challenges ("do this and nominate 3 people")
- User-generated content that others can remix, react to, or build upon

---

STEP 7 — PLATFORM STRATEGY

Consider how the trend would perform across:
- Instagram Reels / YouTube Shorts (primary — short video)
- WhatsApp Status (high sharing in India)
- X / Twitter (quote tweets, meme threads)

The hook and trend idea should be optimized for short-form vertical video.

---

OUTPUT FORMAT

For EACH selected event, return EXACTLY this JSON structure:
{{
  "index": <integer 0-based index from the event list>,
  "trend_name": "<short catchy trend name e.g. '#IndiaCricketReaction', '#HoliTransition', '#ExamPOV'>",
  "trend_idea": "<1-2 sentence specific challenge/trend users can copy — must follow the HOOK → ACTION → SHARE formula>",
  "hook": "<short punchy caption for the clip — must grab attention in under 3 seconds>",
  "virality_score": <integer 1-10>,
  "psychology_triggers": [<list of 2-4 triggers used, e.g. "FOMO", "social_proof", "competition", "status", "emotion", "belonging", "social_currency">],
  "growth_mechanic": "<one-line description of how this trend spreads — e.g. 'Tag 3 friends to do their version', 'Duet chain challenge', 'Couples version vs solo version'>",
  "platform_fit": [<list from: "reels", "shorts", "whatsapp", "twitter">],
  "editing_suggestion": {{
    "filterPreset": "<MUST be exactly one of: none, grayscale, sepia, highContrast, coolTone, warmTone>",
    "effects": [<list of objects, each MUST be one of: {{"name":"fadeIn"}}, {{"name":"fadeOut"}}, {{"name":"zoom"}}, {{"name":"shake"}}, {{"name":"blur"}}>],
    "colorAdjustments": {{
      "brightness": <number -1 to 1>,
      "saturation": <number 0 to 3>,
      "contrast": <number -2 to 2>
    }},
    "speed": <number 0.25 to 4, only if slow/fast motion helps>,
    "vignette": <true or false>,
    "textLayers": [<optional, list of {{"text":"...","color":"#RRGGBB","x":0.5,"y":0.1,"scale":1.5,"opacity":1}}>],
    "stickerLayers": [<optional, list of {{"stickerDescription":"<describe the sticker e.g. 'Indian flag waving', 'fire emoji', 'cricket trophy'>","x":0.5,"y":0.5,"scale":1,"rotation":0,"opacity":1}}>]
  }}
}}

STRICT RULES:
- virality_score MUST be an integer (not "9/10", not 9.5 — just the number 9)
- virality_score criteria: 10 = guaranteed viral (national moment + universal participation), 7-9 = high potential, 4-6 = niche but engaged, 1-3 = low reach
- filterPreset MUST be exactly one of the 6 allowed values above — no custom values
- effects MUST only contain objects from the allowed 5 effect names
- psychology_triggers MUST only use values from the allowed list
- platform_fit MUST only use values from: "reels", "shorts", "whatsapp", "twitter"
- Return a JSON array sorted by virality_score descending
- Select at most {max_count} events, fewer if not enough qualify
- Return ONLY the JSON array, no markdown fences, no explanation
- If NO events pass both the safety filter and participatory filter, return an empty array []

Events:
{events_text}
"""


def _event_to_out(data: dict) -> EventOut:
    return EventOut(
        id=data.get("id", ""),
        name=data.get("name", ""),
        categories=data.get("categories", []),
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


@router.get("/trending", response_model=list[TrendingEventOut])
def get_trending(
    max_count: int = Query(10, ge=1, le=30, description="Max number of trending events to return"),
    days_back: int = Query(3, ge=1, le=7),
    days_ahead: int = Query(3, ge=1, le=7),
):
    """Get the most clip-worthy/engaging events from the current week, ranked by Gemini."""
    graph = get_graph()

    today = date.today()
    start = (today - timedelta(days=days_back)).isoformat()
    end = (today + timedelta(days=days_ahead)).isoformat()

    events = graph.get_timeline(start, end)
    if not events:
        return []

    # Build event list for Gemini
    parts = []
    for i, ev in enumerate(events):
        cats = ev.get("categories", [])
        cats_str = ", ".join(cats) if isinstance(cats, list) else str(cats)
        parts.append(
            f"[{i}] {ev.get('name', '?')} | {cats_str} | "
            f"{ev.get('start_date', '?')} | {ev.get('location', '?')} | "
            f"severity={ev.get('severity', '?')} | "
            f"{(ev.get('summary', '') or '')[:150]}"
        )

    prompt = TRENDING_PROMPT.format(
        max_count=max_count,
        events_text="\n".join(parts),
    )

    try:
        response = _gemini_client.models.generate_content(model=LLM_MODEL, contents=prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        picks = json.loads(raw.strip())
        if not isinstance(picks, list):
            picks = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")

    VALID_FILTERS = {"none", "grayscale", "sepia", "highContrast", "coolTone", "warmTone"}
    VALID_EFFECTS = {"fadeIn", "fadeOut", "zoom", "shake", "blur"}
    VALID_TRIGGERS = {"FOMO", "social_proof", "competition", "status", "emotion", "belonging", "social_currency"}
    VALID_PLATFORMS = {"reels", "shorts", "whatsapp", "twitter"}

    def _sanitize_triggers(raw: list | None) -> list[str]:
        if not isinstance(raw, list):
            return []
        return [t for t in raw if isinstance(t, str) and t in VALID_TRIGGERS]

    def _sanitize_platforms(raw: list | None) -> list[str]:
        if not isinstance(raw, list):
            return []
        return [p for p in raw if isinstance(p, str) and p in VALID_PLATFORMS]

    def _sanitize_editing(s: dict | None) -> dict | None:
        if not isinstance(s, dict):
            return None
        out = {}
        # Filter preset
        fp = s.get("filterPreset", "none")
        out["filterPreset"] = fp if fp in VALID_FILTERS else "none"
        # Effects
        effects = [e for e in (s.get("effects") or []) if isinstance(e, dict) and e.get("name") in VALID_EFFECTS]
        if effects:
            out["effects"] = effects
        # Color adjustments
        ca = s.get("colorAdjustments")
        if isinstance(ca, dict):
            out["colorAdjustments"] = {
                k: round(float(v), 2) for k, v in ca.items()
                if k in {"brightness", "saturation", "contrast", "gamma", "hue", "hueSaturation"} and isinstance(v, (int, float))
            }
        # Speed
        speed = s.get("speed")
        if isinstance(speed, (int, float)) and speed != 1:
            out["speed"] = max(0.25, min(4.0, float(speed)))
        # Vignette
        if isinstance(s.get("vignette"), bool):
            out["vignette"] = s["vignette"]
        # Text layers
        texts = [t for t in (s.get("textLayers") or []) if isinstance(t, dict) and t.get("text")]
        if texts:
            out["textLayers"] = texts
        # Sticker layers
        stickers = [t for t in (s.get("stickerLayers") or []) if isinstance(t, dict) and t.get("stickerDescription")]
        if stickers:
            out["stickerLayers"] = stickers
        return out

    results = []
    for pick in picks:
        idx = pick.get("index", -1)
        if not isinstance(idx, int) or not (0 <= idx < len(events)):
            continue
        ev = events[idx]
        # Parse virality_score robustly (Gemini sometimes returns "9/10" or 9.5)
        raw_score = pick.get("virality_score", 5)
        if isinstance(raw_score, str):
            raw_score = int(raw_score.split("/")[0].strip())
        results.append(TrendingEventOut(
            id=ev.get("id", ""),
            name=ev.get("name", ""),
            categories=ev.get("categories", []),
            subcategory=ev.get("subcategory") or None,
            summary=ev.get("summary") or None,
            location=ev.get("location") or None,
            start_date=ev.get("start_date") or None,
            end_date=ev.get("end_date") or None,
            severity=ev.get("severity", "normal"),
            importance=float(ev.get("importance", 5)),
            source_url=ev.get("source_url") or None,
            trend_name=pick.get("trend_name"),
            trend_idea=pick.get("trend_idea"),
            hook=pick.get("hook"),
            virality_score=int(raw_score),
            psychology_triggers=_sanitize_triggers(pick.get("psychology_triggers")),
            growth_mechanic=pick.get("growth_mechanic") or None,
            platform_fit=_sanitize_platforms(pick.get("platform_fit")),
            editing_suggestion=_sanitize_editing(pick.get("editing_suggestion")),
        ))

    return results


@router.get("/entities", response_model=list[EntityOut])
def list_entities(entity_type: str | None = Query(None)):
    graph = get_graph()
    return graph.get_entities(entity_type=entity_type)


@router.get("/entities/{entity_type}/{entity_name}/events", response_model=list[EventOut])
def get_events_by_entity(entity_type: str, entity_name: str):
    graph = get_graph()
    events = graph.get_events_by_entity(entity_type, entity_name)
    return [_event_to_out(e) for e in events]
