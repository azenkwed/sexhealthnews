# Flesh Pulse — Content Sources

Sources are defined in `backend/collectors/rss_collector.py` as the `RSS_FEEDS` list. Each entry has `url`, `country`, and `name`.

---

## Confirmed RSS sources

### Adult industry trade
| Name | Feed URL | Country |
|---|---|---|
| XBIZ | `https://xbiz.com/feed/news` | US |
| AVN | `https://avn.com/business/articles/feed` | US |

### Sexual health & policy
| Name | Feed URL | Country |
|---|---|---|
| Rewire News Group | `https://rewirenewsgroup.com/feed/` | US |
| SIECUS | `https://siecus.org/feed/` | US |
| Planned Parenthood Newsroom | `https://www.plannedparenthood.org/about-us/newsroom/feed` | US |
| The Body (HIV/sexual health) | `https://www.thebody.com/rss` | US |

### LGBTQ+ & queer
| Name | Feed URL | Country |
|---|---|---|
| Advocate | `https://www.advocate.com/rss.xml` | US |
| GLAAD | `https://glaad.org/feed/` | US |
| PinkNews | `https://www.pinknews.co.uk/feed/` | UK |

### Research & science
| Name | Feed URL | Country |
|---|---|---|
| The Conversation – Sex | `https://theconversation.com/us/topics/sex-7/articles.atom` | INT |
| Psychology Today – Sexuality | `https://www.psychologytoday.com/us/taxonomy/term/61261/feed` | US |

### Censorship & platform policy
| Name | Feed URL | Country |
|---|---|---|
| EFF (digital rights) | `https://www.eff.org/rss/updates.xml` | US |
| Vice – Sex | `https://www.vice.com/en/section/sex/rss` | US |

### Broad news with strong sexuality signal
| Name | Feed URL | Country |
|---|---|---|
| Guardian – Sex | `https://www.theguardian.com/lifeandstyle/sex/rss` | UK |
| BBC – Health | `https://feeds.bbci.co.uk/news/health/rss.xml` | UK |

---

## Google News RSS (keyword-targeted)

Google News RSS requires no API key and covers sources not in the above list. Add these to the same `RSS_FEEDS` list using the `source_name` field to identify them.

```python
{"url": "https://news.google.com/rss/search?q=sexual+health&hl=en&gl=US&ceid=US:en", "country": "INT", "name": "Google News: Sexual Health"},
{"url": "https://news.google.com/rss/search?q=sex+work+decriminalization&hl=en&gl=US&ceid=US:en", "country": "INT", "name": "Google News: Sex Work"},
{"url": "https://news.google.com/rss/search?q=adult+industry+regulation&hl=en&gl=US&ceid=US:en", "country": "INT", "name": "Google News: Adult Industry"},
{"url": "https://news.google.com/rss/search?q=porn+censorship+legislation&hl=en&gl=US&ceid=US:en", "country": "INT", "name": "Google News: Porn Legislation"},
{"url": "https://news.google.com/rss/search?q=LGBTQ+sexuality+rights&hl=en&gl=US&ceid=US:en", "country": "INT", "name": "Google News: LGBTQ Sexuality"},
{"url": "https://news.google.com/rss/search?q=sexual+consent+law&hl=en&gl=US&ceid=US:en", "country": "INT", "name": "Google News: Consent Law"},
{"url": "https://news.google.com/rss/search?q=reproductive+rights+abortion&hl=en&gl=US&ceid=US:en", "country": "INT", "name": "Google News: Reproductive Rights"},
```

**Note on Google News articles**: The description field is minimal (just a snippet) and `content` will be empty. Claude curates on title + description alone for these — acceptable but lower-quality input than full-text feeds.

---

## NewsAPI (optional)

Set `NEWSAPI_KEY` in `.env`. Disable during development with `DISABLE_NEWSAPI=true`.

Suggested keyword queries (configured in `backend/collectors/newsapi_collector.py`):
- `"sexual health" OR "sex education"`
- `"sex work" OR "adult industry"`
- `"porn" AND ("legislation" OR "ban" OR "censorship")`
- `"LGBTQ" AND "sexuality"`
- `"reproductive rights" OR "body autonomy"`

---

## Adding a new collector

Any async function named `collect_all()` returning `list[dict]` qualifies. Required fields per article:

```python
{
    "url": str,
    "title": str,
    "description": str,
    "content": str,
    "source_name": str,
    "source_country": str,   # ISO 2-letter or "INT"
    "author": str,
    "published_at": datetime | None,
    "image_url": str | None,
}
```

Import and call it in `backend/scheduler.py`'s `run_pipeline()`.

---

## Source vetting notes

- **XBIZ/AVN feed URLs**: verify they are still active — trade publication feeds sometimes change paths.
- **Google News RSS**: returns at most 100 articles per query. Run multiple narrow queries rather than one broad one.
- **The Conversation**: uses Atom format — feedparser handles this transparently.
- **Vice**: feed URL may change; Vice has had multiple domain migrations.
- **Age-verification concern**: some sources (e.g. Pornhub blog) may themselves be behind age gates — httpx will get a redirect or a gate page, feedparser will parse nothing, and the collector will silently return zero articles.
