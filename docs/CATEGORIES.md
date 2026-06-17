# Flesh Pulse — Content Categories

These are the editorial categories used by both the AI curator and the web UI. They must stay in sync between `curator.py` and `routes.py`.

---

## Category definitions

| Key (curator.py) | Display name (routes.py + UI) | What belongs here |
|---|---|---|
| `SEXUAL_HEALTH` | Sexual Health & Education | STIs, contraception, sex ed policy, reproductive health research |
| `SEX_WORK` | Sex Work & Policy | Decriminalization, FOSTA-SESTA effects, worker rights, trafficking vs. consensual |
| `ADULT_INDUSTRY` | Adult Industry | Performer news, studio/platform business, regulation, union activity (XBIZ, AVN) |
| `LGBTQ_SEXUALITY` | LGBTQ+ & Queer Sexuality | Queer identity, same-sex rights, trans sexuality, conversion therapy bans |
| `RELATIONSHIPS` | Relationships & Intimacy | Dating culture, polyamory, consent, attachment research, hookup culture |
| `CENSORSHIP_MORALITY` | Censorship & Morality | Platform content moderation, obscenity law, age verification bills, moral panic |
| `BODY_AUTONOMY` | Body Autonomy & Rights | Abortion, reproductive coercion, bodily integrity legislation |
| `SCIENCE_RESEARCH` | Science & Research | Academic sexology, Kinsey-style studies, psychology of sexuality |
| `NONE` | Not Relevant | Does not meet relevance threshold — rejected |

---

## Severity levels

Shared with the Panoptiqa model — repurposed for this editorial context:

| Level | Meaning |
|---|---|
| `low` | Informational or soft news — research findings, trend pieces |
| `medium` | Policy debate, legal challenge, notable cultural shift |
| `high` | Legislation passed, major platform ban, significant court ruling |
| `critical` | Criminalizing legislation, large-scale rights rollback, industry-wide impact |

---

## Featured articles

Articles with `relevance_score >= 0.90` are marked `featured = True` and surfaced prominently on the homepage. These are stories Claude considers highly significant for the niche.

---

## Adding or removing categories

1. Update `CATEGORIES` dict in `backend/processors/curator.py`
2. Update `CATEGORIES` list in `backend/routes.py` (display names only, same order)
3. Add a default category image to `frontend/static/images/category-defaults/`
4. If removing a category, decide what happens to existing articles in that category (re-categorize via admin or leave as orphans)
