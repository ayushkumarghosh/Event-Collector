# India Event Collector

An automated pipeline that continuously monitors and aggregates upcoming events, festivals, government actions, disasters, sports, trends, and entertainment across India. It pulls data from curated RSS feeds, Google Trends, Eventbrite, and Calendarific, then uses Google Gemini (LLM) to extract structured event data. Events are deduplicated and stored in a local knowledge graph (NetworkX) with temporal indexing and entity relationships. A FastAPI backend serves the data through REST endpoints, while a vanilla JS dashboard lets users browse, filter, and search events.

---

## Prerequisites

- **Python 3.11+**
- **Gemini API key** — Get one free at [Google AI Studio](https://aistudio.google.com/apikey)
- **Calendarific API key** (optional) — Get one free at [calendarific.com](https://calendarific.com) (1,000 requests/day)

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd india-event-collector
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
DATABASE_URL=sqlite:///./events.db
GEMINI_API_KEY=your-gemini-api-key-here
COLLECTION_INTERVAL_MINUTES=60
DISASTER_INTERVAL_MINUTES=15
LLM_MODEL=gemini-2.0-flash
LLM_BATCH_SIZE=5
CALENDARIFIC_API_KEY=your-calendarific-api-key-here
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for event extraction |
| `CALENDARIFIC_API_KEY` | No | Calendarific API key for holidays/festivals |
| `DATABASE_URL` | No | SQLite path for dedup tracking (default: `./events.db`) |
| `LLM_MODEL` | No | Gemini model to use (default: `gemini-2.0-flash`) |
| `LLM_BATCH_SIZE` | No | Articles per Gemini API call (default: `5`) |
| `COLLECTION_INTERVAL_MINUTES` | No | Full pipeline run interval (default: `60`) |
| `DISASTER_INTERVAL_MINUTES` | No | Disaster-only pipeline interval (default: `15`) |

---

## Running

### Option A: Single collection run

```bash
python run_collector.py once
```

Filter by category:

```bash
python run_collector.py once --category disaster
python run_collector.py once --category sports
```

### Option B: Continuous scheduler

```bash
python run_collector.py schedule
```

This runs the full pipeline immediately, then:
- Full pipeline every 60 minutes (all sources)
- Disaster-only pipeline every 15 minutes

### Option C: API server + dashboard

In a separate terminal:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Dashboard**: http://localhost:8000
- **API docs**: http://localhost:8000/docs

### Full setup (two terminals)

```bash
# Terminal 1: API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Collector
python run_collector.py schedule
```

---

## Data Sources

### RSS Feeds (28 sources)

**Government** (5)
- The Hindu National — https://www.thehindu.com/news/national/feeder/default.rss
- Indian Express India — https://indianexpress.com/section/india/feed/
- News18 India — https://www.news18.com/rss/india.xml
- Tribune India — https://publish.tribuneindia.com/newscategory/nation/feed/
- India TV News India — https://www.indiatvnews.com/rssnews/topstory-india.xml

**Disaster** (4)
- NDTV India — https://feeds.feedburner.com/ndtvnews-india-news
- The Hindu — https://www.thehindu.com/feeder/default.rss
- News18 India — https://www.news18.com/rss/india.xml
- India TV News Top — https://www.indiatvnews.com/rssnews/topstory.xml

**Sports / Business** (9)
- ESPNcricinfo India — https://www.espncricinfo.com/rss/content/story/feeds/0.xml
- Economic Times — https://economictimes.indiatimes.com/rssfeedstopstories.cms
- News18 Sports — https://www.news18.com/rss/sports.xml
- Indian Express Cricket — https://indianexpress.com/section/sports/cricket/feed/
- The Hindu Sport — https://www.thehindu.com/sport/feeder/default.rss
- Hindustan Times Sports — https://www.hindustantimes.com/feeds/rss/sports/rssfeed.xml
- Livemint Sports — https://www.livemint.com/rss/sports
- Tribune Sports — https://publish.tribuneindia.com/newscategory/sports/feed/
- India TV Sports — https://www.indiatvnews.com/rssnews/topstory-sports.xml

**Trends** (4)
- India Today Trending — https://www.indiatoday.in/rss/home
- NDTV India Trends — https://feeds.feedburner.com/ndtvnews-india-news
- HT India Trends — https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml
- India TV Trending — https://www.indiatvnews.com/rssnews/topstory-trending.xml

**Entertainment** (6)
- Bollywood Hungama — https://www.bollywoodhungama.com/feed/
- News18 Entertainment — https://www.news18.com/rss/entertainment.xml
- Indian Express Entertainment — https://indianexpress.com/section/entertainment/feed/
- Hindustan Times Entertainment — https://www.hindustantimes.com/feeds/rss/entertainment/rssfeed.xml
- The Hindu Entertainment — https://www.thehindu.com/entertainment/feeder/default.rss
- India TV Entertainment — https://www.indiatvnews.com/rssnews/topstory-entertainment.xml

### APIs (3 sources)
- **Google Trends** — https://trends.google.com/trending/rss?geo=IN
- **Eventbrite** — Destination search API (10 Indian cities)
- **Calendarific** — https://calendarific.com/api/v2/holidays (national holidays and festivals)

---

## Architecture

```
RSS Feeds / APIs
      │
      ▼
 fetcher.py ──── Async fetch + feedparser + SHA-256 hash
      │
      ▼
 pipeline.py ─── Dedup by hash → Split pre-extracted vs needs-LLM
      │                │
      │ (Calendarific)  │ (RSS, Trends, Eventbrite)
      ▼                ▼
 Skip Gemini      extractor.py ── Batch 5 articles → Gemini → JSON
      │                │
      └───────┬────────┘
              ▼
       deduplicator.py ── SHA-256 dedup key + fuzzy matching
              │
              ▼
        graph.py ─── NetworkX Knowledge Graph
              │        Events, Entities, Temporal Relations
              │        Persisted as knowledge_graph.graphml
              ▼
        FastAPI ──── REST API → Dashboard
```

### Storage

- **Knowledge Graph** (`knowledge_graph.graphml`) — All events, entities, and relationships. Powered by NetworkX.
- **SQLite** (`events.db`) — Only stores content hashes for dedup tracking. Not used for event queries.

### Knowledge Graph

Events are stored as nodes in a directed graph with automatic relationship discovery:

| Edge Type | Meaning |
|-----------|---------|
| `belongs_to` | Event → Category |
| `located_in` | Event → Location entity |
| `concurrent_with` | Event → Event (overlapping dates) |
| `related_to` | Event → Event (shared location) |

Entities (locations, organizations) are auto-created from event data and linked via edges.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/events` | List events (filter by category, severity, location, search, date) |
| GET | `/api/v1/events/{id}` | Event detail with relations |
| GET | `/api/v1/events/{id}/related` | Related events via graph edges |
| GET | `/api/v1/timeline?start=...&end=...` | Events in a date range |
| GET | `/api/v1/entities` | All entities with event counts |
| GET | `/api/v1/entities/{type}/{name}/events` | Events linked to an entity |
| GET | `/api/v1/stats` | Graph-wide statistics |

### Query parameters for `/api/v1/events`

| Param | Type | Description |
|-------|------|-------------|
| `category` | string | Filter: `festivals`, `govt`, `disaster`, `sports`, `trends`, `entertainment` |
| `severity` | string | Filter: `critical`, `high`, `normal`, `low` |
| `location` | string | Partial match on location |
| `q` | string | Search in event name and summary |
| `from_date` | string | ISO 8601 date (events starting on or after) |
| `limit` | int | Max results (default: 50, max: 200) |
| `offset` | int | Pagination offset |

---

## Project Structure

```
india-event-collector/
├── collector/
│   ├── sources.py          # RSS feed registry (28 sources)
│   ├── fetcher.py          # Async httpx fetcher + feedparser
│   ├── extractor.py        # Gemini API calls, prompt, JSON extraction
│   ├── deduplicator.py     # Hash-based dedup key generation
│   ├── pipeline.py         # Orchestrates: fetch → extract → dedup → graph
│   ├── google_trends.py    # Google Trends RSS integration
│   ├── eventbrite.py       # Eventbrite destination search
│   └── calendarific.py     # Calendarific holidays API
├── storage/
│   ├── graph.py            # NetworkX knowledge graph + temporal store
│   ├── database.py         # SQLite engine (dedup hashes only)
│   ├── models.py           # SQLAlchemy RawFetch model
│   └── crud.py             # Raw fetch CRUD operations
├── api/
│   ├── main.py             # FastAPI app, CORS, static files, lifespan
│   ├── schemas.py          # Pydantic response models
│   └── routes/
│       ├── events.py       # Event, timeline, entity endpoints
│       └── stats.py        # Statistics endpoint
├── scheduler/
│   ├── jobs.py             # APScheduler job definitions
│   └── runner.py           # Scheduler entrypoint
├── frontend/
│   ├── index.html          # Dashboard shell
│   ├── app.js              # Vanilla JS: fetch, render, filter, search
│   └── style.css           # Card layout, severity colors
├── config.py               # Environment config loader
├── run_collector.py        # CLI entrypoint
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Event Categories

| Category | Description | Severity examples |
|----------|-------------|-------------------|
| `festivals` | Holi, Diwali, Eid, regional festivals, melas | High |
| `govt` | Elections, budget, policy, parliament, court rulings | High |
| `disaster` | Cyclones, floods, earthquakes, accidents | Critical |
| `sports` | Cricket, IPL, Olympics, kabaddi, market events | Normal–High |
| `trends` | Viral topics, protests, social movements | Normal |
| `entertainment` | Movies, OTT releases, concerts, celebrity events | Low–Normal |

---

## Gemini API Usage

- **Model**: `gemini-2.0-flash` (free tier: 1,500 requests/day)
- **Batch size**: 5 articles per API call
- **Rate limiting**: 4 second delay between batches, exponential backoff on 429 errors
- **Typical run**: ~200 articles → ~40 API calls → well within free tier
