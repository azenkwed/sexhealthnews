# Flesh Pulse — Data Model

Seven SQLite tables via SQLAlchemy ORM (`backend/database/models.py`).

---

## Article

The core table. One row per accepted article.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `url` | String(2048) | Unique — deduplication key |
| `title` | String(512) | |
| `description` | Text | Feed summary |
| `content` | Text | Full body if available |
| `source_name` | String(256) | e.g. `"XBIZ"`, `"Rewire News"` |
| `source_country` | String(64) | ISO 2-letter or `"INT"` |
| `author` | String(256) | |
| `published_at` | DateTime | UTC, from feed |
| `collected_at` | DateTime | UTC, pipeline run time |
| `relevance_score` | Float | 0.0–1.0 from Claude |
| `category` | String(128) | Display name, e.g. `"Sexual Health & Education"` |
| `dystopian_tags` | Text | JSON array stored as text — always `json.loads()` before use |
| `ai_summary` | Text | One sentence from Claude |
| `severity` | String(32) | `low` / `medium` / `high` / `critical` |
| `featured` | Boolean | True if `relevance_score >= 0.90` |
| `image_url` | String(2048) | From feed or scraped from article page |

Indexes: `category`, `published_at`, `relevance_score`, `collected_at`.

---

## CurationRecord

Every evaluated URL (accepted **and** rejected). This is the deduplication mechanism — articles rejected once are never sent to Claude again.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `url` | String(2048) | Unique |
| `title` | String(512) | |
| `source_name` | String(256) | |
| `status` | String(32) | `accepted` or `rejected` |
| `relevance_score` | Float | Claude's score |
| `category` | String(128) | Claude's category |
| `evaluated_at` | DateTime | UTC |

Indexes: `url`, `status`, `evaluated_at`.

---

## User

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `email` | String(256) | Unique |
| `password_hash` | String(256) | PBKDF2-SHA256, 480k iterations |
| `display_name` | String(128) | |
| `email_verified` | Boolean | Must be True to log in |
| `newsletter_frequency` | String(16) | `daily` / `weekly` / `never` |
| `categories` | Text | JSON array of selected category display names |
| `password_reset_token_version` | Integer | Increment to invalidate outstanding reset tokens |
| `created_at` | DateTime | |
| `last_login` | DateTime | |

---

## SavedArticle

User bookmarks. Unique on `(user_id, article_id)`.

| Column | Type |
|---|---|
| `id` | Integer PK |
| `user_id` | FK → users.id |
| `article_id` | FK → articles.id |
| `created_at` | DateTime |

---

## OAuthAccount

One row per social login link per user.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → users.id | |
| `provider` | String(32) | `google` / `linkedin` / `microsoft` |
| `provider_user_id` | String(256) | External ID from the provider |
| `provider_email` | String(256) | Email as returned by provider |
| `created_at` | DateTime | |

Unique index on `(provider, provider_user_id)`.

---

## CollectionLog

Append-only pipeline run log.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `ran_at` | DateTime | UTC |
| `source` | String(256) | Always `"pipeline"` |
| `articles_fetched` | Integer | Raw count before dedup |
| `articles_accepted` | Integer | After curation |
| `articles_rejected` | Integer | Evaluated but below threshold |
| `error` | Text | Exception message if run failed |

---

## NewsletterLog

Deduplication table for newsletter sends — prevents double-sending.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → users.id | |
| `frequency` | String(16) | `daily` / `weekly` |
| `period_key` | String(16) | `"2026-06-17"` (daily) or `"2026-W24"` (weekly) |
| `subject` | String(256) | |
| `article_count` | Integer | |
| `sent_at` | DateTime | |

Unique on `(user_id, frequency, period_key)`.

---

## FTS virtual table

`articles_fts` — SQLite FTS5, not an ORM model. Created manually in `db.py` on startup.

Indexed columns: `title`, `description`, `ai_summary`, `dystopian_tags` (repurposed as `tags` for this project).

Populated in the pipeline immediately after each `Article` row is flushed.
