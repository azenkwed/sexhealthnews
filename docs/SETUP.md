# Sex Health News — Setup Guide

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for local database)
- An Anthropic API key (required)
- A `.env` file (copy from `.env.example`)

---

## Local development

### 1. Start the database

```bash
docker compose up -d db
```

This starts a PostgreSQL 17 container on port 5432 (Alpine image, lightweight). Data is persisted in a named Docker volume (`postgres_data`). Optionally start pgAdmin too for a visual DB browser:

```bash
docker compose up -d        # starts both db + pgAdmin
open http://localhost:5050  # pgAdmin — login: admin@localhost / admin
```

In pgAdmin, add a server connection:
- Host: `db` (if connecting from another container) or `localhost` (from host machine)
- Port: `5432`
- Database: `sexhealthnews`
- Username: `postgres`
- Password: `postgres`

### 2. Install Python dependencies

```bash
make install
# or manually:
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Minimum required values:

```env
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sexhealthnews
```

### 4. Start the app

```bash
make run       # main app on port 8000
make admin     # admin dashboard on port 8001 (separate terminal)
```

The database schema is created automatically on first startup (`init_db()` runs `CREATE TABLE IF NOT EXISTS` for all models and sets up the full-text search index).

---

## Useful make targets

```bash
make install      # Create .venv and install dependencies
make run          # Start main app on port 8000
make admin        # Start admin dashboard on port 8001
make trigger      # Manually fire the collection pipeline
make db-reset     # Drop and recreate the sexhealthnews database (dev only)
make test         # Run pytest suite
```

---

## First pipeline run

After starting the app, watch the terminal:

```
[Pipeline] Starting collection run at 2026-06-17T...
[Pipeline] Collected 340 raw articles
[Pipeline] 340 new articles to curate
[Pipeline] Accepted: 87, Rejected: 253
[Pipeline] Done. Stored 87 articles.
```

If the accepted count is too high (irrelevant articles slipping through), increase `MIN_RELEVANCE_SCORE` in `.env` (e.g. `0.75`).
If too many legitimate articles are being rejected, decrease it (e.g. `0.60`).

---

## Supabase — production setup

Supabase is a managed Postgres service. The app connects to it exactly like a local Postgres — only the `DATABASE_URL` changes.

### 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) → New project
2. Choose a region close to your users (e.g. `eu-west-1` for Europe)
3. Set a strong database password — save it, you'll need it

### 2. Get the connection string

In the Supabase dashboard:
- **Project Settings → Database → Connection string → URI**
- Use the **Session mode** URI (port 5432) for SQLAlchemy:

```
postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

For high-traffic deployments, use the **Transaction mode** (pgBouncer, port 6543) pooler instead:

```
postgresql+asyncpg://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-eu-west-1.pooler.supabase.com:6543/postgres
```

### 3. Run migrations

On first deploy, the app's `init_db()` will create all tables automatically. Nothing to do manually unless you need to run custom SQL (e.g., seed data or custom indexes).

You can also run migrations directly in the Supabase SQL Editor.

### 4. Environment variables for production

```env
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET_KEY=<production secret>
RESEND_API_KEY=re_...
APP_URL=https://sexhealthnew.com
```

---

## Deployment (Fly.io)

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/

fly auth login
fly launch --name sexhealthnews --region cdg

# Set secrets — no volume needed, DB is on Supabase
fly secrets set DATABASE_URL="postgresql+asyncpg://postgres:..."
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly secrets set JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
fly secrets set RESEND_API_KEY=re_...
fly secrets set APP_URL=https://sexhealthnew.com

fly deploy
fly logs
```

No persistent volume needed — the database lives on Supabase, not on the Fly machine.

---

## Resetting the local database

```bash
# Hard reset — drops and recreates the sexhealthnews database
docker compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS sexhealthnews;"
docker compose exec db psql -U postgres -c "CREATE DATABASE sexhealthnews;"
# Then restart the app — init_db() recreates all tables
make run
```

---

## Adding a new RSS source

1. Open `backend/collectors/rss_collector.py`
2. Add an entry to `RSS_FEEDS`:
   ```python
   {"url": "https://example.com/feed", "country": "US", "name": "Example Source"},
   ```
3. Restart the app — the next pipeline run picks it up

**Before adding any source**, manually browse 20+ recent articles to confirm:
- Content is relevant to the editorial mission
- No content involving minors in any sexual context
- Feed is publicly accessible (no paywall or age gate on the RSS endpoint)

---

## Tuning curation quality

**`MIN_RELEVANCE_SCORE`** in `.env`:
- Too much noise → `0.70` or `0.75`
- Too much rejected → `0.60`

**Curator prompt** in `backend/processors/curator.py`:
- Tighten category definitions if articles are miscategorized
- Add explicit rejection rules for recurring false positives

---

## Running tests

```bash
make test
# or:
pytest tests/ -v
```

Tests use a separate `sexhealthnews_test` database. Set `TEST_DATABASE_URL` in `.env` or the test suite will create it automatically.
