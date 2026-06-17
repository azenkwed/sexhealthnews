# Flesh Pulse — Project Overview

## What it is

Flesh Pulse is an AI-powered news aggregator for sexuality, sexual health, and the adult industry. It collects articles from curated RSS feeds and keyword sources, sends each one to Claude for relevance scoring and categorization, and presents the filtered result as a clean, browsable feed.

It is a direct fork of the [Panoptiqa](https://panoptiqa.com) architecture — same pipeline, same tech stack, different editorial lens.

## What it covers

- Sexual health policy and research
- Sex work legislation and decriminalization
- Adult industry news (XBIZ, AVN)
- LGBTQ+ and queer sexuality
- Relationships, dating, and intimacy culture
- Censorship of sexual content (platforms, obscenity law)
- Body autonomy and reproductive rights

## What it does not cover

- Explicit pornographic content — this is a news aggregator, not a content host
- Non-consensual content of any kind
- Content involving minors in any sexual context

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async) |
| Database | SQLite (file-based, zero-config) |
| AI curation | Anthropic Claude Haiku |
| Scheduler | APScheduler (async) |
| Templates | Jinja2 |
| Email | Resend |
| Auth | JWT cookies + OAuth (Google, LinkedIn, Microsoft) |
| Deployment | Fly.io (recommended) |

## Repository structure

```
flesh-pulse/
├── main.py                        # App entrypoint
├── backend/
│   ├── collectors/
│   │   ├── rss_collector.py       # RSS feed collector
│   │   └── newsapi_collector.py   # NewsAPI collector (optional)
│   ├── processors/
│   │   ├── curator.py             # Claude curation logic
│   │   ├── content_cleaner.py     # Strip boilerplate from article text
│   │   └── newsletter_writer.py   # Claude newsletter intro writer
│   ├── database/
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   └── db.py                  # Async engine + session factory
│   ├── auth/
│   │   ├── routes.py              # Login, register, OAuth callbacks
│   │   ├── dependencies.py        # get_optional_user() FastAPI dep
│   │   ├── utils.py               # Password hashing, JWT
│   │   └── oauth.py               # OAuth provider config
│   ├── notifications/
│   │   ├── email.py               # Resend transactional email
│   │   └── newsletter.py          # Digest send logic
│   ├── scheduler.py               # Pipeline + newsletter cron
│   └── routes.py                  # Web routes + REST API
├── admin/
│   ├── app.py                     # Admin FastAPI app (port 8001)
│   └── routes.py                  # Admin dashboard routes
├── frontend/
│   ├── templates/                 # Jinja2 HTML templates
│   └── static/                    # CSS, JS, images
├── docs/                          # This folder
├── tests/                         # pytest suite
├── .env.example                   # Environment variable template
├── requirements.txt
└── Makefile
```

## Key design decisions inherited from Panoptiqa

- **Two FastAPI processes**: main app on port 8000 (public), admin on port 8001 (localhost only)
- **SQLite**: no external DB dependency, works on Fly.io with a persistent volume
- **Synchronous Anthropic SDK** called via `run_in_executor` — avoids async compatibility issues
- **CurationRecord** table: rejected articles are never re-evaluated; deduplication is permanent
- **`verify=False` on Windows**: all outbound `httpx` calls skip SSL verification on Windows only
