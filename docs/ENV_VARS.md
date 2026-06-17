# Flesh Pulse — Environment Variables

Copy `.env.example` to `.env` and fill in the required values before starting.

---

## Required

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key — used for article curation and newsletter writing |
| `JWT_SECRET_KEY` | Signs JWT cookies and session tokens. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |

---

## App settings

| Variable | Default | Purpose |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Uvicorn bind host |
| `APP_PORT` | `8000` | Uvicorn bind port |
| `ADMIN_HOST` | `127.0.0.1` | Admin app bind host — keep localhost-only |
| `ADMIN_PORT` | `8001` | Admin app bind port |
| `ADMIN_PASSWORD` | — | Basic auth password for admin dashboard |
| `DEBUG` | `false` | Enable uvicorn reload (dev only) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `APP_URL` | `http://localhost:8000` | Base URL — used in email links and OAuth redirect URIs |

---

## Pipeline

| Variable | Default | Purpose |
|---|---|---|
| `COLLECTION_INTERVAL_MINUTES` | `60` | How often the pipeline runs |
| `MIN_RELEVANCE_SCORE` | `0.65` | Articles below this score are rejected |
| `ARTICLE_RETENTION_DAYS` | `0` (disabled) | Prune articles older than N days (0 = keep forever) |
| `ALLOW_MANUAL_TRIGGER` | `true` | Enable `POST /api/trigger-collection` |
| `DISABLE_NEWSAPI` | `false` | Skip NewsAPI collector — RSS feeds still run |

---

## News sources

| Variable | Purpose |
|---|---|
| `NEWSAPI_KEY` | Optional — adds keyword search coverage on top of RSS feeds |

---

## Email (Resend)

| Variable | Default | Purpose |
|---|---|---|
| `RESEND_API_KEY` | — | Transactional email. If unset, emails are silently skipped (dev mode). |
| `FROM_EMAIL` | `Flesh Pulse <onboarding@resend.dev>` | Sender address. Use `onboarding@resend.dev` for testing; swap to verified domain for production. |
| `CONTACT_EMAIL` | `contact@fleshpulse.com` | Recipient for contact form submissions |

---

## OAuth social login

Leave empty to disable a provider — buttons only appear for configured providers.

| Variable | Provider | Where to get it |
|---|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google | console.cloud.google.com → APIs & Services → Credentials |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | LinkedIn | linkedin.com/developers → My Apps |
| `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` | Microsoft | portal.azure.com → App registrations |

OAuth redirect URIs to register with each provider:
```
http://localhost:8000/auth/google/callback
http://localhost:8000/auth/linkedin/callback
http://localhost:8000/auth/microsoft/callback
```

---

## Social media (optional)

| Variable | Default | Purpose |
|---|---|---|
| `TWITTER_HANDLE` | `fleshpulse` | X account — used as fallback URL in local dev |
| `TWITTER_MAX_PER_RUN` | `1` | Max featured articles to tweet per pipeline run |
| `TWITTER_CONSUMER_KEY` | — | OAuth 1.0a — posting tweets |
| `TWITTER_CONSUMER_SECRET` | — | OAuth 1.0a |
| `TWITTER_ACCESS_TOKEN` | — | OAuth 1.0a |
| `TWITTER_ACCESS_TOKEN_SECRET` | — | OAuth 1.0a |

Note: X/Twitter sign-in (OAuth 2.0) is disabled in code — posting tweets (OAuth 1.0a) is separate.

---

## Stripe (optional)

| Variable | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Membership payments and donations. Use `sk_test_...` for development. |
| `STRIPE_WEBHOOK_SECRET` | For verifying Stripe webhook payloads |
| `STRIPE_PRICE_ID_MEMBER` | Stripe Price ID for the Member tier |
| `STRIPE_PRICE_ID_SUPPORTER` | Stripe Price ID for the Supporter tier |
