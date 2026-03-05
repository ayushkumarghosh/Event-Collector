import json
import re
import time

from google import genai
from google.genai.errors import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import GEMINI_API_KEY, LLM_MODEL, LLM_BATCH_SIZE

client = genai.Client(api_key=GEMINI_API_KEY)

PROMPT_TEMPLATE = """You are an event extraction system focused on India. Analyze the following news articles and extract structured event data.

For each article, return a JSON object with these fields:
- "name": concise event name (string)
- "category": one of ["festivals", "govt", "disaster", "sports", "trends", "entertainment"]
- "subcategory": more specific label (string or null)
- "summary": 1-2 sentence summary (string)
- "location": city/state/region in India, or "India" if nationwide (string or null)
- "start_date": ISO 8601 date if known, e.g. "2025-03-15" (string or null)
- "end_date": ISO 8601 date if known (string or null)
- "severity": one of ["low", "normal", "high", "critical"]
- "importance": 1-10 integer (10 = most important)
- "source_url": the article URL (string)

Category guidelines:
- festivals: Holi, Diwali, Eid, regional festivals, melas, cultural gatherings
- govt: elections, budget, policy, state visits, parliament, court rulings
- disaster: cyclones, floods, earthquakes, droughts, public health alerts, accidents
- sports: cricket, IPL, Olympics, major tournaments, kabaddi, business/market events
- trends: viral topics, social movements, public protests, trending memes/hashtags
- entertainment: upcoming movies, OTT releases, concerts, stand-up shows, music albums

Severity guidelines:
- critical: major disasters, national emergencies
- high: significant political events, large festivals, important matches
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


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=5, max=60),
    retry=retry_if_exception_type((ClientError, json.JSONDecodeError)),
)
def _call_gemini(articles: list[dict]) -> list[dict | None]:
    prompt = _build_prompt(articles)
    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt,
    )
    raw = _clean_json_response(response.text)
    return json.loads(raw)


def extract_events_from_batch(articles: list[dict]) -> list[dict | None]:
    try:
        results = _call_gemini(articles)
        if not isinstance(results, list):
            print("  [WARN] Gemini returned non-list, wrapping")
            results = [results]
        return results
    except Exception as e:
        print(f"  [ERROR] Gemini extraction failed: {e}")
        return [None] * len(articles)


def extract_all(articles: list[dict]) -> list[dict | None]:
    total_batches = (len(articles) + LLM_BATCH_SIZE - 1) // LLM_BATCH_SIZE
    all_events = []
    for i in range(0, len(articles), LLM_BATCH_SIZE):
        batch_num = i // LLM_BATCH_SIZE + 1
        batch = articles[i : i + LLM_BATCH_SIZE]
        print(f"  Extracting batch {batch_num}/{total_batches} ({len(batch)} articles)...")
        events = extract_events_from_batch(batch)
        all_events.extend(events)
        # Rate limit: wait between batches to avoid 429 errors
        if batch_num < total_batches:
            time.sleep(4)
    return all_events
