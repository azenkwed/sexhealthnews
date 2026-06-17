# Flesh Pulse — Setup Guide

## Prerequisites

- Python 3.11+
- Git
- An Anthropic API key (required)
- A `.env` file (copy from `.env.example`)

---

## Local development

```bash
# 1. Clone
git clone https://github.com/azenkwed/flesh-pulse.git
cd flesh-pulse

# 2. Create virtualenv and install dependencies
make install
# or manually:
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY and JWT_SECRET_KEY

# 4. Start the app
make run
# or:
./run.sh                           # macOS/Linux
run.bat                            # Windows

# 5. Open
open http://localhost:8000

# 6. Start admin dashboard (separate terminal)
make admin
open http://localhost:8001
```

The database (`data/flesh-pulse.db`) is created automatically on first startup. The pipeline fires immediately on startup, then every `COLLECTION_INTERVAL_MINUTES`.

---

## Useful make targets

```bash
make install   # Create .venv and install dependencies
make run       # Kill port 8000 then start main app
make admin     # Start admin dashboard on port 8001
make trigger   # Manually fire the collection pipeline
make reset     # Delete the database (stop server first)
make test      # Run pytest suite
```

---

## First pipeline run

After starting the app, watch the terminal. You'll see:

```
[Pipeline] Starting collection run at 2026-06-17T...
[Pipeline] Collected 340 raw articles
[Pipeline] 340 new articles to curate
[Pipeline] Accepted: 87, Rejected: 253
[Pipeline] Done. Stored 87 articles.
```

If accepted count is too high (lots of irrelevant articles getting through), increase `MIN_RELEVANCE_SCORE` in `.env`.

If accepted count is too low (too much is being filtered), decrease it or refine the curator prompt.

---

## Deployment (Fly.io)

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/

fly auth login

# Launch (first time)
fly launch --name flesh-pulse --region cdg   # cdg = Paris

# Create persistent volume for SQLite
fly volumes create flesh_pulse_data --region cdg --size 1

# Set secrets
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly secrets set JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
fly secrets set RESEND_API_KEY=re_...
fly secrets set APP_URL=https://fleshpulse.com

# Deploy
fly deploy

# Logs
fly logs
```

The `fly.toml` mounts the volume at `/data` where SQLite writes `flesh-pulse.db`.

---

## Adding a new RSS source

1. Open `backend/collectors/rss_collector.py`
2. Add an entry to `RSS_FEEDS`:
   ```python
   {"url": "https://example.com/feed", "country": "US", "name": "Example Source"},
   ```
3. Restart the app — the next pipeline run will pick it up

**Before adding any source**, manually browse 20+ of its recent articles to confirm:
- Content is relevant to the editorial mission
- No content involving minors in any sexual context
- Feed is publicly accessible (no paywall or age gate on the RSS endpoint)

---

## Tuning curation quality

The two main levers:

**`MIN_RELEVANCE_SCORE`** in `.env`:
- Too much noise → increase to `0.70` or `0.75`
- Too much rejected → decrease to `0.60`

**Curator prompt** in `backend/processors/curator.py`:
- Add examples of articles that should be accepted or rejected
- Tighten category definitions if articles are miscategorized
- Add explicit rejection rules (e.g. "generic health news with no sexuality angle → score below 0.50")

After prompt changes, use `make reset` to clear the database and `make trigger` to re-run the pipeline with fresh data. (Only do this in development — production data is not recoverable after reset.)

---

## Running tests

```bash
make test
# or:
pytest tests/ -v
```

Tests use an in-memory SQLite database and mock Claude API calls. See `tests/conftest.py` for fixtures.
