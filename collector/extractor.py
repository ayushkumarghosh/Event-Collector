import json
import re
import time

from google import genai
from google.genai.errors import ClientError, ServerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import GEMINI_API_KEY, LLM_MODEL, LLM_BATCH_SIZE

client = genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 1_800_000})

PROMPT_TEMPLATE = """You are an event extraction system focused on India. Analyze the following news articles and extract structured event data.

For each article, return a JSON object with these fields:
- "name": concise event name (string)
- "categories": list of applicable categories from ["religion", "state", "holiday", "festival", "situation"] — an event can belong to MULTIPLE categories
- "subcategory": more specific label (string or null)
- "summary": 1-2 sentence summary (string)
- "location": city/state/region in India, or "India" if nationwide (string or null)
- "start_date": ISO 8601 date if known, e.g. "2025-03-15" (string or null)
- "end_date": ISO 8601 date if known (string or null)
- "severity": one of ["low", "normal", "high", "critical"]
- "importance": 1-10 integer (10 = most important)
- "source_url": the article URL (string)

Category guidelines (assign ALL that apply):
- religion: anything tied to a religion — Hindu, Islamic, Christian, Sikh, Buddhist, Jain events and observances. Includes religious festivals, prayers, pilgrimages, fasting, temple/mosque/church events
- state: state/central government actions, elections, budget, policy, parliament, court rulings, political events
- holiday: government-declared holidays and days off — Republic Day, Independence Day, Gandhi Jayanti, bank holidays. Also applies to religious festivals that are gazetted holidays (e.g. Holi is both "festival" and "holiday")
- festival: major public celebrations — Holi, Diwali, Eid, Christmas, Pongal, Onam, Navratri, Durga Puja, Ganesh Chaturthi, Baisakhi, Buddha Purnima, Mahavir Jayanti, etc.
- situation: ongoing/upcoming situations — disasters, protests, sports, entertainment, business, trending topics

Examples of multi-category events:
- Holi → ["religion", "festival", "holiday"] (Hindu religious festival that is also a national holiday)
- Eid ul-Fitr → ["religion", "festival", "holiday"] (Islamic festival, gazetted holiday)
- Christmas → ["religion", "festival", "holiday"] (Christian festival, national holiday)
- Republic Day → ["holiday"] (secular national holiday, not religious or festival)
- IPL Match → ["situation"] (sports event)
- Ramadan Start → ["religion"] (religious observance, not a festival or holiday)
- Guru Nanak Jayanti → ["religion", "festival", "holiday"] (Sikh festival, gazetted holiday)
- Government Budget → ["state"]
- Durga Puja → ["religion", "festival"] (Hindu festival, not a national holiday everywhere)

Subcategory guidelines:
- For religion category, set subcategory to the religion: "Hinduism", "Islam", "Christianity", "Sikhism", "Buddhism", "Jainism", or "Multi-faith"
- For state category, set subcategory to: "Elections", "Policy", "Budget", "Judiciary", etc.
- For situation category, set subcategory to: "Sports", "Entertainment", "Disaster", "Protest", "Business", "Trending", etc.
- For holiday category, set subcategory to: "National", "Gazetted", "Restricted", etc.
- If multiple categories apply, choose the most specific subcategory (usually the religion name)

Severity guidelines:
- critical: major disasters, national emergencies, large-scale crises
- high: significant political events, large festivals, important matches, major situations
- normal: regular news events
- low: minor updates, routine announcements

DEDUPLICATION: If multiple articles in this batch are about the SAME event (same topic, same date, same location — just reported by different sources), merge them into ONE event entry and return null for the duplicate articles. Pick the best name, combine information from all sources into the summary, and use the most informative source_url.

Return a JSON array with one element per article. If an article is not about a real event, is not relevant to India, or is a DUPLICATE of another article in this batch, return null for that element.

IMPORTANT: Return ONLY the JSON array, no markdown formatting, no explanation.

Articles:
{articles_text}
"""


DEDUP_PROMPT_TEMPLATE = """You are a deduplication system. Below is a list of extracted events. Identify groups of events that are about the SAME real-world event (same topic/incident, same or overlapping dates, same or nearby location).

For each group of duplicates, keep only the BEST one (most informative name, best summary) and mark the rest for removal.

Return a JSON array of indices (0-based) to REMOVE. If there are no duplicates, return an empty array [].

Events:
{events_text}

IMPORTANT: Return ONLY the JSON array of indices to remove, no markdown formatting, no explanation."""


def _build_prompt(articles: list[dict]) -> str:
    parts = []
    for i, art in enumerate(articles, 1):
        parts.append(f"--- Article {i} ---\nTitle: {art['title']}\nURL: {art.get('url', 'N/A')}\nContent: {art.get('content', 'N/A')}\n")
    return PROMPT_TEMPLATE.format(articles_text="\n".join(parts))


def _clean_json_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _log_retry(retry_state):
    print(f"retry #{retry_state.attempt_number} after {retry_state.outcome.exception()}", flush=True)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=10, max=120),
    retry=retry_if_exception_type((ClientError, ServerError, json.JSONDecodeError)),
    before_sleep=_log_retry,
)
def _call_gemini(articles: list[dict]) -> tuple[list[dict | None], int, int]:
    """Call Gemini and return (results, input_tokens, output_tokens)."""
    prompt = _build_prompt(articles)
    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt,
    )
    raw = _clean_json_response(response.text)
    results = json.loads(raw)

    # Extract token counts from usage metadata
    input_tokens = 0
    output_tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

    return results, input_tokens, output_tokens


def extract_events_from_batch(articles: list[dict]) -> tuple[list[dict | None], int, int]:
    """Returns (events, input_tokens, output_tokens). Raises on failure."""
    results, input_tokens, output_tokens = _call_gemini(articles)
    if not isinstance(results, list):
        print("  [WARN] Gemini returned non-list, wrapping")
        results = [results]
    return results, input_tokens, output_tokens


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=10, max=120),
    retry=retry_if_exception_type((ClientError, ServerError, json.JSONDecodeError)),
    before_sleep=_log_retry,
)
def _call_gemini_dedup(events: list[dict]) -> tuple[list[int], int, int]:
    """Ask Gemini to identify duplicate events. Returns (indices_to_remove, in_tok, out_tok)."""
    parts = []
    for i, ev in enumerate(events):
        cats = ev.get("categories", [])
        cats_str = ", ".join(cats) if isinstance(cats, list) else str(cats)
        parts.append(
            f"[{i}] {ev.get('name', '?')} | {cats_str} | "
            f"{ev.get('start_date', '?')} | {ev.get('location', '?')} | "
            f"{(ev.get('summary', '') or '')[:100]}"
        )
    prompt = DEDUP_PROMPT_TEMPLATE.format(events_text="\n".join(parts))

    response = client.models.generate_content(model=LLM_MODEL, contents=prompt)
    raw = _clean_json_response(response.text)
    indices = json.loads(raw)

    input_tokens = 0
    output_tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

    if not isinstance(indices, list):
        return [], input_tokens, output_tokens
    return [i for i in indices if isinstance(i, int)], input_tokens, output_tokens


def _dedup_via_gemini(events: list[dict]) -> list[dict]:
    """Run cross-batch deduplication via Gemini. Process in chunks to stay within context limits."""
    if len(events) <= 1:
        return events

    DEDUP_CHUNK = 200  # max events per dedup call
    all_remove = set()
    total_in = 0
    total_out = 0
    chunk_count = (len(events) + DEDUP_CHUNK - 1) // DEDUP_CHUNK

    print(f"  Dedup: checking {len(events)} events in {chunk_count} chunk(s)...", end=" ", flush=True)

    for i in range(0, len(events), DEDUP_CHUNK):
        chunk = events[i : i + DEDUP_CHUNK]
        try:
            remove_indices, in_tok, out_tok = _call_gemini_dedup(chunk)
            total_in += in_tok
            total_out += out_tok
            # Map chunk-local indices back to global indices
            for idx in remove_indices:
                if 0 <= idx < len(chunk):
                    all_remove.add(i + idx)
        except Exception as e:
            print(f"\n  [WARN] Dedup chunk failed: {e}, skipping dedup for this chunk")

    deduped = [ev for i, ev in enumerate(events) if i not in all_remove]
    print(f"removed {len(all_remove)} duplicates ({total_in} in / {total_out} out tokens)")
    return deduped


def extract_all(articles: list[dict]) -> list[dict | None]:
    total_batches = (len(articles) + LLM_BATCH_SIZE - 1) // LLM_BATCH_SIZE
    all_events = []
    total_input_tokens = 0
    total_output_tokens = 0

    print(f"  Starting Gemini extraction: {len(articles)} articles in {total_batches} batches...")
    for i in range(0, len(articles), LLM_BATCH_SIZE):
        batch_num = i // LLM_BATCH_SIZE + 1
        batch = articles[i : i + LLM_BATCH_SIZE]
        print(f"  Batch {batch_num}/{total_batches}: sending {len(batch)} articles...", end=" ", flush=True)
        try:
            events, in_tok, out_tok = extract_events_from_batch(batch)
        except Exception as e:
            print(f"\n  [ERROR] Batch {batch_num} failed after retries: {e}")
            print(f"  Stopping extraction. {len(all_events)} events extracted from {batch_num - 1}/{total_batches} batches.")
            break
        total_input_tokens += in_tok
        total_output_tokens += out_tok
        print(f"  {in_tok} in / {out_tok} out tokens")
        all_events.extend(events)
        # Rate limit: wait between batches to avoid 429 errors
        if batch_num < total_batches:
            time.sleep(4)

    print(f"  Extraction token totals: {total_input_tokens} input, {total_output_tokens} output")

    # Filter out nulls before dedup
    valid_events = [e for e in all_events if e is not None]

    # Cross-batch deduplication via Gemini
    if len(valid_events) > 1:
        valid_events = _dedup_via_gemini(valid_events)

    return valid_events
