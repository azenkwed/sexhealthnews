# Sex Health News — Operator Guide

A practical reference for running, extending, and deploying the system.

Live site: [sexhealthnew.com](https://sexhealthnew.com)

---

## Table of contents

1. [First-time setup](#1-first-time-setup)
2. [How the pipeline works](#2-how-the-pipeline-works)
3. [Adding news sources](#3-adding-news-sources)
4. [Tuning the AI curation](#4-tuning-the-ai-curation)
5. [Display settings & themes](#5-display-settings--themes)
6. [Managing the database](#6-managing-the-database)
7. [Deploying to a server](#7-deploying-to-a-server)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. First-time setup

### Requirements

- Python 3.10 or later
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Optionally a NewsAPI key ([newsapi.org](https://newsapi.org) — free tier: 100 req/day)

### Steps

**1. Create and activate virtual environment:**

```bash
python3 -m venv .venv

# macOS / Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

**2. Install dependencies:**

```bash
pip install -r requirements.txt
```

**3. Configure environment:**

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

**4. Start PostgreSQL:**

PostgreSQL is required and runs in Docker. Start it with:

```bash
./start-postgres.sh    # Linux / macOS
start-postgres.bat     # Windows
```

This script will:
- Check that Docker is installed and running
- Start PostgreSQL and pgAdmin containers
- Wait for PostgreSQL to be ready
- Show you the connection details

**5. Run the application:**

```bash
make run      # recommended — auto-kills any existing process on the port first
./run.sh      # Linux / macOS alternative
run.bat       # Windows alternative
```

These scripts will:
- Check that PostgreSQL is running and ready
- Automatically activate the venv
- Install/upgrade dependencies
- Start the app with auto-reload

The pipeline fires immediately on startup. Within a few minutes (depending on how many articles need curating) the feed will populate.

---

## 2. How the pipeline works

The pipeline runs on an interval (default: every 60 minutes). Each run does the following:

```
[RSS feeds]  ──┐
               ├──► collect  ──► deduplicate  ──► curate (Claude AI)  ──► store
[NewsAPI]    ──┘
```

**Step 1 — Collect.** All RSS feeds are fetched in parallel. NewsAPI is queried for 15 dystopian keywords. Results are merged and de-duplicated by URL.

**Step 2 — Deduplicate against DB.** URLs already in the database are discarded before curation — no duplicate API calls.

**Step 3 — Curate.** Each new article is sent to Claude Haiku with a prompt that asks for:
- `relevance_score` (0.0–1.0) — how strongly dystopian
- `category` — one of 9 predefined categories
- `severity` — low / medium / high / critical
- `tags` — up to 5 short descriptive tags
- `summary` — one sentence on what makes it dystopian

Articles scoring below `MIN_RELEVANCE_SCORE` (default `0.65`) are rejected. Articles scoring `0.90+` are marked featured and shown at the top of the homepage.

**Step 4 — Store.** Accepted articles are written to PostgreSQL. A `CollectionLog` entry is created with counts.

### Manually trigger a run

```bash
curl -X POST http://localhost:8000/api/trigger-collection
# or via make:
make trigger
```

Or set `COLLECTION_INTERVAL_MINUTES=1` in `.env` temporarily.

---

## 3. Adding news sources

### Adding an RSS feed

Open `backend/collectors/rss_collector.py` and add an entry to `RSS_FEEDS`:

```python
{"url": "https://example.com/feed.rss", "country": "US", "name": "Example Source"},
```

`country` is a free-form label used for display. Use standard country codes or `INT` for international organizations.

Good sources to add:
- Bellingcat: `https://www.bellingcat.com/feed/`
- ProPublica: `https://feeds.propublica.org/propublica/main`
- The Guardian (world): `https://www.theguardian.com/world/rss`
- OCCRP: `https://occrp.org/en/rss`
- Freedom of the Press Foundation: `https://freedom.press/news/feed/`

### Adding a NewsAPI keyword query

Open `backend/collectors/newsapi_collector.py` and add to `SEARCH_QUERIES`:

```python
"your keyword phrase here",
```

Keep queries specific enough to avoid noise. The free NewsAPI tier allows 100 requests/day — with 15 queries per run and hourly runs, keep the total under ~20 queries or the free tier will hit its daily cap mid-run.

---

## 4. Tuning the AI curation

### Changing the relevance threshold

In `.env`:

```env
MIN_RELEVANCE_SCORE=0.70   # stricter — fewer but higher-quality articles
MIN_RELEVANCE_SCORE=0.55   # looser — more articles, some borderline
```

### Changing the AI model

In `backend/processors/curator.py`, change the model:

```python
model="claude-haiku-4-5-20251001",   # fast, cheap — default
model="claude-sonnet-4-6",            # better accuracy, higher cost
```

### Modifying the curation prompt

The system prompt and evaluation template are at the top of `backend/processors/curator.py`:

- `SYSTEM_PROMPT` — sets the editorial persona and definition of dystopian
- `EVAL_PROMPT` — the per-article instruction with the JSON schema

If you add a new category, update **both**:
1. `CATEGORIES` dict in `curator.py` — maps uppercase key to display name
2. `CATEGORIES` list in `backend/routes.py` — used by the web UI and slug resolution

### Concurrency

Curation sends up to 5 concurrent API calls (controlled by the semaphore in `curate_batch`). Lower it if you hit rate limits:

```python
semaphore = asyncio.Semaphore(2)
```

---

## 5. Display settings & themes

The **⚙ Settings** drawer (top-right of the header) lets visitors change theme, font face, and font size. All choices persist in `localStorage` — they are entirely client-side and do not affect the server.

### Themes

| Theme | Background | Accent | Feel |
|---|---|---|---|
| Amber | Near-black warm | `#ffcc00` | Analog decay, oxidized tape |
| Cyan | Near-black cold | `#00c8ff` | Digital surveillance |
| Green | Near-black green | `#00ff41` | Terminal / Matrix |
| Red | Near-black red | `#ff3030` | Authoritarian state |
| Broadcast | Light grey `#f4f4f4` | `#cc0000` | CNN / BBC mainstream news |
| White | Pure white | `#1a4a7a` | Clinical / institutional |

All theme colours are CSS custom properties in `frontend/static/css/main.css` under `[data-theme="..."]` blocks. Adding a theme requires a new CSS block, a swatch dot colour, a `<div class="theme-swatch">` in `base.html`, and no JS changes.

### Font faces

| Option | Body | Headlines | Character |
|---|---|---|---|
| Military | Rajdhani | Oswald | Default — tactical sans |
| Terminal | Share Tech Mono | Share Tech Mono | Full CRT |
| Dispatch | Georgia | Courier New | Redacted document |
| Broadcast | Inter | Barlow Condensed | BBC / CNN editorial |

The Broadcast font auto-activates when the Broadcast theme is selected, and restores the previous font when switching away. This is handled in `frontend/static/js/main.js`.

### Font sizes

Small (14px) / Medium (16px, default) / Large (18px) — applied to the `html` element, scaling all `rem`-based sizes proportionally.

---

## 6. Managing the database

PostgreSQL is managed via Docker. The database is created automatically when you run `docker-compose up -d`.

### Inspect with PostgreSQL CLI

```bash
# Connect to the database
psql -h localhost -U postgres -d sexhealthnews

# List tables
\dt

# Query articles
SELECT count(*) FROM articles;
SELECT category, count(*) FROM articles GROUP BY category;
SELECT title, relevance_score, severity FROM articles ORDER BY collected_at DESC LIMIT 10;
```

### Access pgAdmin UI

Open http://localhost:5050 and login with:
- Email: `admin@sexhealthnews.local`
- Password: `admin`

Browse, query, and manage your database graphically.

### Reset the database

Stop the app and PostgreSQL, then:

```bash
docker-compose down -v    # Remove containers and volumes
docker-compose up -d      # Recreate with fresh database
```

The tables are created automatically on the next app startup.

### Export articles to JSON

```bash
curl http://localhost:8000/api/articles?limit=100 > export.json
```

---

## 7. Deploying to a server

### With systemd (Linux)

Create `/etc/systemd/system/sexhealthnews.service`:

```ini
[Unit]
Description=Sex Health News
After=network.target

[Service]
WorkingDirectory=/opt/sexhealthnews
ExecStart=python -m uvicorn main:app --host 0.0.0.0 --port 8000
EnvironmentFile=/opt/sexhealthnews/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now sexhealthnews
sudo journalctl -fu sexhealthnews
```

### With Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t sexhealthnews .
docker run -d -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data sexhealthnews
```

### Behind nginx

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 8. Troubleshooting

### Feed is empty after startup

- Confirm `ANTHROPIC_API_KEY` is set in `.env`
- Check the terminal output — the pipeline logs how many articles were collected and accepted
- If `0 raw articles` — your network may be blocking outbound requests, or all feeds returned errors
- If `0 accepted` — the relevance threshold may be too high, or the AI key is invalid

### SSL errors on Windows (collectors or Anthropic API)

All three HTTP clients use `verify=False` to bypass Windows certificate chain issues:
- `backend/collectors/rss_collector.py` — async httpx client
- `backend/collectors/newsapi_collector.py` — async httpx client
- `backend/processors/curator.py` — sync httpx client passed to `anthropic.Anthropic(http_client=...)`

On Linux/macOS this is not needed. To restore strict SSL on Windows, set `verify=True` in all three and install `pip install certifi`.

### Category pages show 0 articles despite the ALL feed being populated

Category URLs encode `&` as `and` in the slug (e.g. `"AI & Technology Control"` → `/category/ai-and-technology-control`). The route in `backend/routes.py` resolves this back to the canonical name by matching against the `CATEGORIES` list — a naive `.replace("-", " ")` will not restore the `&` and the DB query will return nothing. If this breaks after editing categories, verify the slug round-trip with:

```bash
python -c "
cats = ['AI & Technology Control', 'Censorship & Information Control']
for c in cats:
    slug = c.replace(' ', '-').replace('&', 'and').lower()
    resolved = next((x for x in cats if x.replace(' ','-').replace('&','and').lower() == slug), None)
    print(slug, '->', resolved)
"
```

### NewsAPI 429 Too Many Requests

The free tier allows 100 requests/day. With 15 queries per pipeline run, triggering the pipeline more than ~6 times a day will exhaust the quota. The RSS feeds continue to work — NewsAPI failing silently does not stop the pipeline.

### Pipeline runs but articles stop appearing

The database deduplicates by URL, so after the first run most articles will already be known. New articles only appear when sources publish new content. Verify with:

```bash
make trigger
curl http://localhost:8000/api/stats
```

The `articles_last_24h` field shows how many passed curation in the last 24 hours.
