# Flesh Pulse — Roadmap

---

## Phase 1 — Fork & adapt (week 1)

- [ ] Fork Panoptiqa codebase into this repo
- [ ] Replace `CATEGORIES` in `curator.py` and `routes.py` with Flesh Pulse categories (see `CATEGORIES.md`)
- [ ] Rewrite curator system prompt for sexuality/health editorial lens
- [ ] Replace `RSS_FEEDS` list with sources from `SOURCES.md`
- [ ] Add Google News RSS keyword feeds
- [ ] Update all brand strings: "Panoptiqa" → "Flesh Pulse", colors, fonts
- [ ] Replace category default images
- [ ] Update `.env.example` with Flesh Pulse defaults
- [ ] Update privacy policy and terms of service templates

---

## Phase 2 — Legal & safety baseline (week 1–2)

- [ ] Add 18+ acknowledgment to registration flow
- [ ] Publish privacy policy and terms of service
- [ ] Register DMCA agent (copyright.gov, ~$6)
- [ ] Add hard rejection rule to curator prompt: minors in sexual context → score 0.0
- [ ] Manually vet all RSS sources before enabling them
- [ ] Contact form doubles as DMCA/abuse reporting channel

---

## Phase 3 — Launch (week 2–3)

- [ ] Deploy to Fly.io (`fly launch` + persistent volume for SQLite)
- [ ] Configure custom domain (fleshpulse.com or aphrodiqa.com)
- [ ] Set up Resend with verified domain for transactional email
- [ ] First pipeline run — review accepted articles manually
- [ ] Tune `MIN_RELEVANCE_SCORE` based on initial results
- [ ] Set up admin dashboard access (ADMIN_PASSWORD)

---

## Phase 4 — Growth features

- [ ] **Newsletter** — daily/weekly digest, personalized by category preference (already built in Panoptiqa — just carry over)
- [ ] **Search** — FTS5 full-text search (already built — carry over)
- [ ] **Saved articles** — bookmarks (already built — carry over)
- [ ] **Dark mode** (already built — carry over)
- [ ] **Twitter/X auto-posting** — tweet featured articles (already built — configure credentials)
- [ ] **Category default images** — design 8 images, one per category

---

## Phase 5 — Monetization

- [ ] **Donations** — Stripe one-time or Ko-fi (1 day of work, high ROI)
- [ ] **Membership tiers** — Free / Member ($7/mo) / Supporter ($15/mo) via Stripe
  - Member: full articles, daily newsletter, keyword alerts
  - Supporter: everything + weekly deep-dive digest
- [ ] **Keyword alerts** — user subscribes to a keyword; pipeline emails on match
- [ ] **API access** — tiered pricing for researchers and industry (see `MONETIZATION.md`)

---

## Backlog

- [ ] **Related articles** panel on article page
- [ ] **Industry people search** — by performer/executive name (requires tagging people in the curator prompt)
- [ ] **Country filter** — filter feed by source country
- [ ] **Source reputation scores** — weight curation by source credibility
- [ ] **Weekly "state of the industry" digest** — curated by Claude, sent to all subscribers
