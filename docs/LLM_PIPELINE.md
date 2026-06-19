# LLM Pipeline — Multi-Provider Architecture

## Overview

The AI pipeline is split into two distinct agents with separate responsibilities and separate provider pools. Classification is cheap and high-volume so it uses free/cheap inference providers. Writing requires editorial quality so it stays on Claude Haiku.

---

## Pipeline flow

```
fetch (RSS + NewsAPI)
  │
  ▼
[Classifier]  ← Groq / Together AI / Fireworks AI (Llama 3.3 70B, round-robin)
  │  relevance_score, category, severity, tags
  │
  ├── score < 0.65 or category == NONE → reject (write CurationRecord, stop)
  │
  ▼
[Writer]  ← Claude Haiku
  │  ai_summary (2–3 sentences, editorial context)
  │  tweet (only if featured=True, i.e. score ≥ 0.90)
  │
  ▼
save Article to DB
```

---

## Agent 1 — Classifier

**File:** `backend/processors/classifier.py`
**Providers:** Groq → Together AI → Fireworks AI (Llama 3.3 70B)
**Routing:** Round-robin across healthy providers. If selected provider returns a rate-limit error or any exception, fall through to the next in rotation. Rotation state is a module-level counter.
**Output (JSON):**
```json
{
  "relevance_score": 0.0–1.0,
  "category": "REPRODUCTIVE_HEALTH | SEXUAL_HEALTH | ... | NONE",
  "severity": "low | medium | high | critical",
  "tags": ["tag1", "tag2", "tag3"]
}
```

No prose. No summary. Pure structured classification.

**Token budget:** ~500–700 input tokens, ~80 output tokens per call.
**Concurrency:** Up to 5 concurrent calls via asyncio Semaphore (same as current curator).

### Provider model IDs
| Provider | Model ID |
|---|---|
| Groq | `llama-3.3-70b-versatile` |
| Together AI | `meta-llama/Llama-3.3-70B-Instruct-Turbo` |
| Fireworks AI | `accounts/fireworks/models/llama-v3p3-70b-instruct` |

### Client setup
All three use the OpenAI-compatible API via the `openai` Python package with a custom `base_url`. No separate SDKs needed.

```python
from openai import OpenAI

groq     = OpenAI(api_key=GROQ_API_KEY,     base_url="https://api.groq.com/openai/v1")
together = OpenAI(api_key=TOGETHER_API_KEY, base_url="https://api.together.xyz/v1")
fireworks= OpenAI(api_key=FIREWORKS_API_KEY,base_url="https://api.fireworks.ai/inference/v1")
```

### Fallback behaviour
1. Pick provider at current rotation index (mod 3).
2. Increment rotation counter regardless of success/failure.
3. On `RateLimitError` or any exception: try next provider in order.
4. If all 3 fail: return `(None, False)` — article is not evaluated, not written to `CurationRecord`, will be retried next pipeline run.

---

## Agent 2 — Writer

**File:** `backend/processors/writer.py`
**Provider:** Anthropic Claude Haiku (`claude-haiku-4-5-20251001`)
**Called:** Only for articles that passed classification (score ≥ 0.65, category ≠ NONE).
**Output:**
- `ai_summary` — 2–3 sentences with real editorial context. Written for an informed adult reader. Not a classification note.
- `tweet` — single tweet under 230 chars (URL appended separately). Only produced when `featured=True` (score ≥ 0.90). `None` otherwise.

**Input:** full article text (title, description, content) + classification results (category, severity, tags).

**Token budget:** ~600–800 input tokens, ~200 output tokens per call.

### What this replaces
- The `summary` field previously written by the curator as a by-product of classification.
- `backend/processors/twitter_agent.py` — absorbed into this agent, that file is deleted.

---

## Newsletter writer

**File:** `backend/processors/newsletter_writer.py` (modified)
**Change:** Receives articles with pre-written `ai_summary` fields. No longer re-summarises articles. Its only job is to write:
- A subject line (8–60 chars)
- A 2–3 sentence intro contextualising the digest as a whole

Article summaries in the digest body come directly from `ai_summary`.

---

## Usage tracking

**File:** `backend/usage.py`
**DB table:** `api_usage_stats` — one row per `(service, date)`. Columns: `service` (str), `date` (ISO string YYYY-MM-DD UTC), `call_count` (int), `token_count` (int). Unique constraint on `(service, date)`.

**Tracked services:**
| Key | Label | Limit reference |
|---|---|---|
| `groq` | Groq | 6,000 req/day · 14,400 tok/min (free tier) |
| `together` | Together AI | varies by plan |
| `fireworks` | Fireworks AI | varies by plan |
| `anthropic` | Anthropic (Claude Haiku) | paid per token |

**Recording:** called after every successful or failed-but-evaluated API call, passing provider name, input tokens, and output tokens. Uses a simple upsert (insert or increment).

---

## Admin dashboard — API Usage page

**Route:** `GET /api-usage` in `admin/routes.py`
**Template:** `frontend/templates/admin/api_usage.html`

**Displays per provider:**
- Today's call count
- Today's token count
- All-time call count
- All-time token count
- Limit reference note

**Alert banner:** shown in the page header when today's usage for any provider exceeds a configurable threshold (default 80% of the known daily limit where applicable).

**Alert email:** sent via Resend when any provider crosses the threshold. Fires at most once per day per provider. Uses `ALERT_EMAIL` env var (falls back to `CONTACT_EMAIL`).

---

## New environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | yes (for classifier) | Groq API key |
| `TOGETHER_API_KEY` | yes (for classifier) | Together AI API key |
| `FIREWORKS_API_KEY` | yes (for classifier) | Fireworks AI API key |
| `API_USAGE_ALERT_THRESHOLD` | no (default `0.8`) | Fraction of daily limit that triggers alert |
| `ALERT_EMAIL` | no | Override recipient for usage alert emails |

---

## Files changed / created

| File | Action |
|---|---|
| `backend/processors/classifier.py` | **New** — replaces curator's classification logic |
| `backend/processors/writer.py` | **New** — summary + tweet writing, replaces twitter_agent |
| `backend/processors/curator.py` | **Deleted** — fully replaced by classifier + writer |
| `backend/processors/twitter_agent.py` | **Deleted** — absorbed into writer |
| `backend/processors/newsletter_writer.py` | **Modified** — uses pre-written summaries |
| `backend/usage.py` | **New** — usage recording module |
| `backend/database/models.py` | **Modified** — add `ApiUsageStat` model |
| `backend/scheduler.py` | **Modified** — wire classifier → writer in pipeline |
| `admin/routes.py` | **Modified** — add `/api-usage` route |
| `frontend/templates/admin/api_usage.html` | **New** — usage dashboard page |
| `requirements.txt` | **Modified** — add `openai` package |
| `.env.example` | **Modified** — add new env vars |
