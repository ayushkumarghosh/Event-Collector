import json
import re
import time

from google import genai
from google.genai.errors import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import GEMINI_API_KEY, LLM_MODEL, LLM_BATCH_SIZE

client = genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 600_000})

PROMPT_TEMPLATE = """You are an event extraction system focused on India. Analyze the following news articles and extract structured event data.

For each article, return a JSON object with these fields:
- "name": concise event name (string)
- "category": one of ["religion", "state", "holiday", "festival", "situation"]
- "subcategory": more specific label (string or null)
- "summary": 1-2 sentence summary (string)
- "location": city/state/region in India, or "India" if nationwide (string or null)
- "start_date": ISO 8601 date if known, e.g. "2025-03-15" (string or null)
- "end_date": ISO 8601 date if known (string or null)
- "severity": one of ["low", "normal", "high", "critical"]
- "importance": 1-10 integer (10 = most important)
- "source_url": the article URL (string)

Category guidelines:
- religion: religious events, prayers, pilgrimages, temple/mosque/church events, spiritual gatherings, religious rulings
- state: state/central government actions, elections, budget, policy, parliament, court rulings, political events by location
- holiday: national holidays (Republic Day, Independence Day, Gandhi Jayanti), bank holidays, government-declared holidays
- festival: Holi, Diwali, Eid, Navratri, Pongal, Onam, Christmas, regional festivals, melas, cultural celebrations
- situation: upcoming or ongoing situations — disasters, protests, sports events, entertainment, business/market events, trending topics, anything currently happening or about to happen

Severity guidelines:
- critical: major disasters, national emergencies, large-scale crises
- high: significant political events, large festivals, important matches, major situations
- normal: regular news events
- low: minor updates, routine announcements

Return a JSON array with one element per article. If an article is not about a real event or is not relevant to India, return null for that element.

IMPORTANT: Return ONLY the JSON array, no markdown formatting, no explanation.

Articles:
{articles_text}
"""


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
    wait=wait_exponential(min=5, max=60),
    retry=retry_if_exception_type((ClientError, json.JSONDecodeError)),
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
    """Returns (events, input_tokens, output_tokens)."""
    try:
        results, input_tokens, output_tokens = _call_gemini(articles)
        if not isinstance(results, list):
            print("  [WARN] Gemini returned non-list, wrapping")
            results = [results]
        return results, input_tokens, output_tokens
    except Exception as e:
        print(f"  [ERROR] Gemini extraction failed: {e}")
        return [None] * len(articles), 0, 0


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
        events, in_tok, out_tok = extract_events_from_batch(batch)
        total_input_tokens += in_tok
        total_output_tokens += out_tok
        print(f"→ {in_tok} in / {out_tok} out tokens")
        all_events.extend(events)
        # Rate limit: wait between batches to avoid 429 errors
        if batch_num < total_batches:
            time.sleep(4)

    print(f"  Token totals: {total_input_tokens} input, {total_output_tokens} output")
    return all_events
