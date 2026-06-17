# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

### First-time setup

```bash
# 1. Copy environment config
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 2. Start PostgreSQL (required)
./start-postgres.sh    # or start-postgres.bat on Windows

# 3. Start the app (in another terminal)
make run               # recommended — checks PostgreSQL, creates venv, installs deps
# or
./run.sh               # Linux / macOS
run.bat                # Windows
```

### Daily development

```bash
make run               # auto-reloads main app on file changes (port 8000)
make admin             # auto-reloads admin dashboard (port 8001, localhost only)
make trigger           # manually fire the collection pipeline
```

### Configuration

Requires a `.env` file (copy from `.env.example`):

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sexhealthnews

# Optional
NEWSAPI_KEY=...        # Adds keyword search
RESEND_API_KEY=...     # Email verification and password reset
```

For testing without NewsAPI:
```bash
DISABLE_NEWSAPI=true   # Skip NewsAPI collector, RSS feeds still run
```

### Admin dashboard URLs

```
http://127.0.0.1:8001/                     # main dashboard
http://127.0.0.1:8001/articles             # article list & editor
http://127.0.0.1:8001/newsletter-preview   # daily digest preview
http://127.0.0.1:8001/newsletter-preview?frequency=weekly
http://localhost:5050                      # pgAdmin database browser
```

## Architecture

The app is two FastAPI processes:

**Main app (`main.py`, port 8000)** — public-facing, three concerns:
- Pipeline (automated, runs on startup then hourly)
- Web layer (HTML pages + REST API)
- Auth (registration, login, OAuth, profile)

**Admin app (`admin/app.py`, port 8001)** — internal only, bound to 127.0.0.1.

---

### Pipeline (automated, runs on startup then hourly)

`backend/scheduler.py` drives the full loop: `rss_collector` + `newsapi_collector` fetch raw articles in parallel → deduplicate against the DB by URL and `CurationRecord` (so rejected articles are not re-evaluated) → `curator.curate_batch` sends each new article to Claude Haiku → accepted articles are written to PostgreSQL. Both `Article` rows and `CurationRecord` rows (accepted + rejected) are written after each run. `CollectionLog` records each run's counts.

The scheduler also fires newsletter jobs: daily digest at 07:00 UTC, weekly digest at 07:00 UTC on Mondays.

### Web layer

`backend/routes.py` serves HTML pages (Jinja2 via `frontend/templates/`) and a small REST API. Key routes:

| Route | Purpose |
|---|---|
| `GET /` | Home feed (paginated, 24/page) |
| `GET /category/{slug}` | Category feed |
| `GET /article/{id}` | Article detail |
| `POST /article/{id}/save` | Toggle bookmark (auth required) |
| `GET /search` | Full-text search |
| `GET /saved` | Saved articles (auth required) |
| `GET /contact` | Contact form |
| `GET /privacy`, `/terms` | Static pages |
| `GET /sitemap.xml`, `/robots.txt` | SEO |
| `GET /api/articles` | REST — list articles |
| `GET /api/stats` | REST — counts + last run |
| `POST /api/trigger-collection` | REST — manual pipeline trigger |

The `_enrich()` helper converts `Article` ORM objects to template-ready dicts, adding: `tags_list` (parsed JSON), `severity_color`, `category_slug`, `default_image_url`, `display_image_url`, `reading_time`, `body_text`, `body_html`, `body_has_more`, `display_datetime` (ISO string for JS), `display_date` (server-side fallback with US/intl format detection via `Accept-Language`).

### AI curation

`backend/processors/curator.py` sends article title + description + content (truncated to 800 chars each) to Claude Haiku with a structured JSON prompt. The response is parsed for `relevance_score`, `category`, `severity`, `tags`, and `summary`. Articles below `MIN_RELEVANCE_SCORE` (default `0.65`) or categorized as `NONE` are discarded. Articles scoring `≥ 0.90` are marked `featured=True`. The Anthropic SDK is called synchronously via `run_in_executor` because the sync client is used, and receives a custom `httpx.Client(verify=False)` to bypass Windows SSL issues. `curate_batch` runs up to 5 concurrent API calls via a semaphore.

### Auth system

`backend/auth/` handles all user authentication:

- **Email/password** — PBKDF2-SHA256 (480k iterations) via `auth/utils.py`. Registration sends a verification email; unverified accounts cannot log in.
- **JWT cookies** — 30-day `access_token` httponly cookie, HS256-signed with `JWT_SECRET_KEY`. `auth/dependencies.py::get_optional_user()` resolves the cookie to a `User` row.
- **Password reset** — signed timed token (itsdangerous), 1-hour expiry.
- **OAuth social login** — Google, LinkedIn, Microsoft (X/Twitter code exists but is deliberately disabled). Providers are enabled only if both `CLIENT_ID` and `CLIENT_SECRET` are set. LinkedIn is handled manually (authlib rejects LinkedIn's id_token because LinkedIn omits the nonce claim). All OAuth flows use `SESSION_MIDDLEWARE` (starlette sessions) for state/nonce storage.
- **Profile page** — users can set display name, newsletter frequency (daily/weekly/never), and category preferences (used to filter newsletter content).
- **Saved articles** — toggled via `POST /article/{id}/save`, listed at `/saved`.

`auth/routes.py` imports `CATEGORIES` from `routes.py` (not the other way around) to avoid circular dependencies.

### Email / notifications

`backend/notifications/email.py` — Resend-based email delivery. Falls back silently (prints a warning) if `RESEND_API_KEY` is not set. Sends:
- Email verification link (24-hour expiry)
- Password reset link (1-hour expiry)
- Contact form messages to `CONTACT_EMAIL`

### Newsletter

`backend/notifications/newsletter.py` + `backend/processors/newsletter_writer.py` — Claude Haiku writes a subject line and intro paragraph for each digest. The scheduler fires `send_newsletters("daily")` and `send_newsletters("weekly")` on their respective cron triggers. Articles are filtered by each user's category preferences. Users with no selected categories receive all top articles. Minimum 3 articles required to send; maximum 10 per digest. Only `email_verified=True` users with a matching `newsletter_frequency` receive each digest.

### Admin app

`admin/app.py` — separate FastAPI process, `make admin` starts it on port 8001. Routes in `admin/routes.py`:

| Route | Purpose |
|---|---|
| `GET /` | Dashboard — stats, recent logs, recent users, DB info |
| `GET /articles` | Article list with search/filter |
| `GET /articles/{id}` | Article detail + edit |
| `POST /articles/{id}` | Update category/severity/featured/summary |
| `POST /articles/{id}/delete` | Delete one article |
| `POST /articles/bulk-delete` | Bulk delete |
| `GET /logs` | Collection log history |
| `GET /curation-records` | Evaluated (accepted+rejected) URL history |
| `GET /users` | User list |
| `GET /oauth-accounts` | OAuth linked accounts |
| `GET /settings` | Pipeline settings (reads/writes `.env`) |
| `POST /trigger` | Fire pipeline immediately |
| `GET /newsletter-preview` | Preview digest HTML |

## Critical coupling: category naming

Categories are defined in two places and must stay in sync:
- `backend/processors/curator.py` — `CATEGORIES` dict maps uppercase keys (e.g. `"SURVEILLANCE"`) to display names (e.g. `"Surveillance & Privacy"`)
- `backend/routes.py` — `CATEGORIES` list holds the display names used by the web UI

URL slugs replace spaces with `-` and `&` with `and` (lowercased). The category page route **reverses this by matching the slug against the `CATEGORIES` list** — do not use a naive `.replace("-", " ")` which fails to restore `&`. The current implementation in `routes.py` uses `next((c for c in CATEGORIES if c.replace(" ", "-").replace("&", "and").lower() == slug), ...)`.

## SSL on Windows

All outbound HTTP uses `verify=False` across four places:
- `backend/collectors/rss_collector.py` — `httpx.AsyncClient(verify=False)`
- `backend/collectors/newsapi_collector.py` — `httpx.AsyncClient(verify=False)`
- `backend/processors/curator.py` — `anthropic.Anthropic(http_client=httpx.Client(verify=False))`
- `backend/auth/routes.py` — LinkedIn OAuth token + userinfo calls use `httpx.AsyncClient(verify=False)`

On Linux/macOS `verify=False` is not needed. Do not remove it on Windows without testing all RSS feeds, a live curation call, and a LinkedIn OAuth login.

## Data model

Six tables in `backend/database/models.py`:

| Table | Purpose |
|---|---|
| `Article` | Curated articles with AI-enriched fields |
| `SavedArticle` | User bookmarks (user_id + article_id, unique) |
| `CurationRecord` | Every evaluated URL (accepted or rejected) — prevents re-evaluation |
| `User` | Registered users (email, password_hash, display_name, newsletter_frequency, categories JSON) |
| `OAuthAccount` | Social login links per user (provider + provider_user_id) |
| `CollectionLog` | Append-only pipeline run log |

`dystopian_tags` on `Article` is a JSON array stored as TEXT — always parse with `json.loads` before use. `categories` on `User` is also a JSON array of display-name strings.

`CurationRecord` is the deduplication mechanism for rejected articles — the pipeline checks both `Article.url` and `CurationRecord.url` before curating, so articles rejected in a previous run are not sent to Claude again.

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | — | AI curation and newsletter writing |
| `JWT_SECRET_KEY` | yes | `dev-secret-change-in-production` | JWT signing + session middleware |
| `RESEND_API_KEY` | no | — | Email delivery (verification, reset, contact) |
| `FROM_EMAIL` | no | `Sex Health News <noreply@sexhealthnew.com>` | Sender address for transactional emails |
| `CONTACT_EMAIL` | no | `contact@sexhealthnew.com` | Recipient for contact form submissions |
| `APP_URL` | no | `http://localhost:8000` | Base URL in email links and OAuth redirect URIs |
| `NEWSAPI_KEY` | no | — | Adds keyword search on top of RSS feeds |
| `DISABLE_NEWSAPI` | no | `false` | Skip NewsAPI collector (RSS still runs) |
| `COLLECTION_INTERVAL_MINUTES` | no | `60` | Pipeline run interval |
| `MIN_RELEVANCE_SCORE` | no | `0.65` | Articles below this score are rejected |
| `ARTICLE_RETENTION_DAYS` | no | `0` (disabled) | Prune articles older than N days |
| `ALLOW_MANUAL_TRIGGER` | no | `true` | Enable `POST /api/trigger-collection` |
| `APP_HOST` | no | `0.0.0.0` | Uvicorn bind host |
| `APP_PORT` | no | `8000` | Uvicorn bind port |
| `DEBUG` | no | `false` | Enable uvicorn reload |
| `LOG_LEVEL` | no | `INFO` | Logging level |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | no | — | Google OAuth (button appears only if both set) |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | no | — | LinkedIn OAuth (manual flow, no authlib) |
| `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` | no | — | Microsoft OAuth |
| `TWITTER_CLIENT_ID` / `TWITTER_CLIENT_SECRET` | no | — | X/Twitter OAuth (disabled in code, credentials ignored) |

## Frontend

`frontend/static/js/main.js` is minimal — it shows a refresh toast after 5 minutes suggesting the user reload. All templates receive `current_user` (a `User` ORM object or `None`) and `categories` (the display-name list).

## Adding a new collector

Collectors must be async functions named `collect_all()` returning `list[dict]` where each dict has at minimum: `url`, `title`, `description`, `content`, `source_name`, `source_country`, `author`, `published_at` (datetime or None), `image_url`. Add the import and call in `backend/scheduler.py`'s `run_pipeline`.
