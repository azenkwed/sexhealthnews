# Flesh Pulse — Monetization

## Core principle

Flesh Pulse's audience — sex workers, researchers, health professionals, activists, and informed adults — chose an independent platform. Every monetization decision must preserve editorial independence. **No display ads. No sponsored content.**

---

## Revenue streams

### 1. Memberships (primary)

| Tier | Price | What they get |
|---|---|---|
| **Free** | $0 | Homepage, article summaries, basic search |
| **Member** | $7/month or $60/year | Full articles, daily newsletter, keyword alerts, advanced search |
| **Supporter** | $15/month or $120/year | Everything above + weekly deep-dive digest, early access, name in credits |

**Why this works:** Sex workers, researchers, and health professionals pay for tools they trust and use. The AI-curated signal saves hours of searching across fragmented sources — that's the product.

---

### 2. API access

The Flesh Pulse database is a structured, AI-curated dataset of sexuality news across categories. Commercial value exists for:

- Academic researchers and universities studying sexuality
- NGOs working on sex work policy or reproductive rights
- Journalists building databases or tracking legislation
- Compliance and policy monitoring companies
- Sexual health platforms doing content marketing research

| Tier | Price | Limits |
|---|---|---|
| **Research** | $49/month | 1,000 requests/day, full article data |
| **Professional** | $149/month | 10,000 requests/day, webhook support |
| **Enterprise** | Custom | Unlimited, SLA, dedicated support |

---

### 3. Donations

Simple, frictionless, no strings attached.

- One-time: $10 / $25 / $50 / custom
- Monthly recurring: $5 / $10 / $25 / custom
- Processed via Stripe or Ko-fi

**No editorial obligation attached to donations.**

---

### 4. Grants and partnerships

Organizations that fund independent sexuality and health journalism:

| Organization | Focus |
|---|---|
| Planned Parenthood Federation | Reproductive/sexual health advocacy |
| SIECUS (Sexuality Information & Education Council) | Sex education policy |
| Open Society Foundations | Rights-based organizations |
| Ford Foundation | Sexuality and reproductive rights programs |
| Robert Wood Johnson Foundation | Health journalism |
| Adult Performer Advocacy Committee (APAC) | Industry welfare |

Strategy: Wait until 3–6 months of published content and a demonstrated audience before applying.

---

### 5. Industry advertising (considered, rejected)

Adult industry companies (platforms, toy manufacturers, health brands) might pay for advertising. This is **rejected** for the same reason Panoptiqa rejects display ads — it creates editorial conflict. If XBIZ is an advertiser, we cannot critically cover XBIZ. The signal quality is the product.

**Exception**: Sponsorship of specific content verticals (e.g., "Sexual Health section sponsored by [health brand]") could work if clearly labeled and the editorial team retains full independence. Only consider after establishing the brand.

---

## Build order

1. **Stripe donations** — 1 day, immediately deployable, no gating required
2. **Newsletter system** — already built in Panoptiqa, carry over
3. **Membership tiers** — Stripe subscriptions + feature gating
4. **Keyword alerts** — member perk, builds stickiness
5. **API key management** — rate limiting + billing

---

## Key metric

**Member conversion rate**: industry average for independent news is 2–5%. At 10,000 monthly readers and 3% conversion, that's 300 members. At $7/month average, that's $2,100/month — covers infrastructure and begins building toward sustainability.

---

*Last updated: June 2026*
