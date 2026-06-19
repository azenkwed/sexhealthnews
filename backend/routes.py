"""FastAPI routes — web UI and REST API."""
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import nh3
from markupsafe import Markup, escape
from backend.processors.content_cleaner import strip_boilerplate

from sqlalchemy import select, func, desc, distinct, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_optional_user
from backend.database.db import get_db
from backend.database.models import Article, CollectionLog, SavedArticle
from backend.notifications.email import send_contact_message
from backend.processors.classifier import CATEGORIES as _CAT_MAP

templates = Jinja2Templates(directory="frontend/templates")
templates.env.globals["now"] = lambda: datetime.now(timezone.utc)
templates.env.globals["stripe_enabled"] = bool(os.getenv("STRIPE_SECRET_KEY"))
router = APIRouter()

_VALID_MSGS = frozenset({"saved", "unsaved", "sent"})

_search_rl: dict[str, list[float]] = defaultdict(list)
_SEARCH_RL_WINDOW = 60
_SEARCH_RL_MAX = 30

def _search_rate_limited(ip: str) -> bool:
    now = time.time()
    _search_rl[ip] = [t for t in _search_rl[ip] if now - t < _SEARCH_RL_WINDOW]
    if len(_search_rl[ip]) >= _SEARCH_RL_MAX:
        return True
    _search_rl[ip].append(now)
    return False


def _last_updated() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _safe_msg(msg: str) -> str:
    return msg if msg in _VALID_MSGS else ""

CATEGORIES = [v for k, v in _CAT_MAP.items() if k != "NONE"]

SEVERITY_COLORS = {
    "low": "#4a7c59",
    "medium": "#b8860b",
    "high": "#cc4400",
    "critical": "#8b0000",
}

CATEGORY_DEFAULT_IMAGES: dict[str, str] = {
    "Sexual Health & Wellness":        "sexual-health-wellness.webp",
    "Reproductive Health & Policy":    "reproductive-health-policy.webp",
    "Maternal & Child Health":         "maternal-child-health.webp",
    "Infectious Diseases & STIs":      "infectious-diseases-stis.webp",
    "Mental Health & Sexuality":       "mental-health-sexuality.webp",
    "LGBTQ+ Rights & Issues":          "lgbtq-rights-issues.webp",
    "Sex Education & Literacy":        "sex-education-literacy.webp",
    "Sexual Violence & Consent":       "sexual-violence-consent.webp",
    "Sex Workers & Adult Industry":    "sex-workers-adult-industry.webp",
}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, page: int = Query(1, ge=1), db: AsyncSession = Depends(get_db)):
    per_page = 24

    if page == 1:
        featured_res = await db.execute(
            select(Article)
            .where(Article.featured == True)
            .order_by(desc(Article.collected_at))
            .limit(4)
        )
        featured = featured_res.scalars().all()
    else:
        featured = []

    total_res = await db.execute(select(func.count()).select_from(Article))
    recent_res = await db.execute(
        select(Article)
        .order_by(desc(Article.published_at))
        .offset(0 if page == 1 else (page - 1) * per_page)
        .limit(per_page)
    )

    total = total_res.scalar() or 0
    recent = recent_res.scalars().all()

    # Build secondary: featured[1:] padded with recent to always fill 3 slots
    hero_id = featured[0].id if featured else (recent[0].id if recent else None)
    secondary_list = list(featured[1:])
    used_ids = {a.id for a in secondary_list} | ({hero_id} if hero_id else set())
    for a in recent:
        if len(secondary_list) >= 3:
            break
        if a.id not in used_ids:
            secondary_list.append(a)
            used_ids.add(a.id)
    secondary_list = secondary_list[:3]

    stats = await _get_stats(db)
    current_user = await get_optional_user(request, db)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "featured": [_enrich(a, _is_us(request)) for a in featured],
        "secondary": [_enrich(a, _is_us(request)) for a in secondary_list],
        "recent": [_enrich(a, _is_us(request)) for a in recent if a.id not in used_ids],
        "categories": CATEGORIES,
        "stats": stats,
        "page": page,
        "total": total,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "last_updated": _last_updated(),
        "current_user": current_user,
    })


@router.get("/category/{category_name}", response_class=HTMLResponse)
async def category_page(
    request: Request,
    category_name: str,
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    per_page = 20
    offset = (page - 1) * per_page

    # Reverse the slug back to the canonical category display name
    category = next(
        (c for c in CATEGORIES if c.replace(" ", "-").replace("&", "and").lower() == category_name.lower()),
        category_name.replace("-", " ").replace("_", " "),
    )

    count_q = await db.execute(
        select(func.count()).where(Article.category == category)
    )
    total = count_q.scalar() or 0

    articles_q = await db.execute(
        select(Article)
        .where(Article.category == category)
        .order_by(desc(Article.published_at))
        .offset(offset)
        .limit(per_page)
    )
    articles = articles_q.scalars().all()

    current_user = await get_optional_user(request, db)
    return templates.TemplateResponse("category.html", {
        "request": request,
        "category": category,
        "articles": [_enrich(a, _is_us(request)) for a in articles],
        "categories": CATEGORIES,
        "page": page,
        "total": total,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "last_updated": _last_updated(),
        "current_user": current_user,
    })


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_page(request: Request, article_id: int, msg: str = "", db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        return templates.TemplateResponse("404.html", {
            "request": request,
            "categories": CATEGORIES,
            "last_updated": _last_updated(),
            "current_user": await get_optional_user(request, db),
        }, status_code=404)

    current_user = await get_optional_user(request, db)

    is_saved = False
    if current_user:
        saved_q = await db.execute(
            select(SavedArticle.id).where(
                SavedArticle.user_id == current_user.id,
                SavedArticle.article_id == article_id,
            )
        )
        is_saved = saved_q.scalar_one_or_none() is not None

    related_q = await db.execute(
        select(Article)
        .where(Article.category == article.category)
        .where(Article.id != article_id)
        .order_by(desc(Article.published_at))
        .limit(3)
    )
    related = related_q.scalars().all()

    us = _is_us(request)
    canonical_url = str(request.url.replace(query=""))
    return templates.TemplateResponse("article.html", {
        "request": request,
        "article": _enrich(article, us),
        "related": [_enrich(a, us) for a in related],
        "categories": CATEGORIES,
        "last_updated": _last_updated(),
        "current_user": current_user,
        "is_saved": is_saved,
        "msg": _safe_msg(msg),
        "share_url": canonical_url,
        "share_url_encoded": quote_plus(canonical_url),
        "share_title_encoded": quote_plus(article.title),
        "share_title": article.title,
    })


@router.post("/article/{article_id}/save")
async def toggle_saved_article(
    request: Request,
    article_id: int,
    next: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    current_user = await get_optional_user(request, db)
    if not current_user:
        return RedirectResponse(url=f"/login?next=/article/{article_id}", status_code=303)

    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        return RedirectResponse(url="/", status_code=303)

    saved_q = await db.execute(
        select(SavedArticle).where(
            SavedArticle.user_id == current_user.id,
            SavedArticle.article_id == article_id,
        )
    )
    saved = saved_q.scalar_one_or_none()
    if saved:
        await db.delete(saved)
        action = "unsaved"
    else:
        db.add(SavedArticle(user_id=current_user.id, article_id=article_id))
        action = "saved"
    await db.commit()

    safe_next = next if next.startswith("/") else ""
    redirect_to = safe_next or f"/article/{article_id}"
    return RedirectResponse(url=f"{redirect_to}?msg={action}", status_code=303)


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_optional_user(request, db)
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "categories": CATEGORIES,
        "last_updated": _last_updated(),
        "current_user": current_user,
    })


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_optional_user(request, db)
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "categories": CATEGORIES,
        "last_updated": _last_updated(),
        "current_user": current_user,
    })


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request, msg: str = "", db: AsyncSession = Depends(get_db)):
    current_user = await get_optional_user(request, db)
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "categories": CATEGORIES,
        "last_updated": _last_updated(),
        "current_user": current_user,
        "msg": _safe_msg(msg),
    })


@router.post("/contact", response_class=HTMLResponse)
async def submit_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    topic: str = Form(...),
    message: str = Form(...),
    website: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    current_user = await get_optional_user(request, db)
    form_values = {
        "name": name.strip(),
        "email": email.strip(),
        "topic": topic.strip(),
        "message": message.strip(),
    }

    if website.strip():
        return templates.TemplateResponse("contact.html", {
            "request": request,
            "categories": CATEGORIES,
            "last_updated": _last_updated(),
            "current_user": current_user,
            "msg": "sent",
        })

    if not form_values["name"] or not form_values["email"] or not form_values["message"]:
        return templates.TemplateResponse("contact.html", {
            "request": request,
            "categories": CATEGORIES,
            "last_updated": _last_updated(),
            "current_user": current_user,
            "error": "Please complete all required fields.",
            **form_values,
        })

    if len(form_values["message"]) > 4000:
        return templates.TemplateResponse("contact.html", {
            "request": request,
            "categories": CATEGORIES,
            "last_updated": _last_updated(),
            "current_user": current_user,
            "error": "Please keep your message under 4,000 characters.",
            **form_values,
        })

    sent = send_contact_message(
        form_values["name"],
        form_values["email"],
        form_values["topic"] or "General",
        form_values["message"],
    )
    if sent:
        return templates.TemplateResponse("contact.html", {
            "request": request,
            "categories": CATEGORIES,
            "last_updated": _last_updated(),
            "current_user": current_user,
            "msg": "sent",
        })

    return templates.TemplateResponse("contact.html", {
        "request": request,
        "categories": CATEGORIES,
        "last_updated": _last_updated(),
        "current_user": current_user,
        "error": "We could not send your message right now. Please email contact@sexhealthnew.com directly.",
        **form_values,
    })


@router.get("/offline", response_class=HTMLResponse)
async def offline_page(request: Request):
    return templates.TemplateResponse("offline.html", {"request": request})


@router.get("/robots.txt")
async def robots(request: Request):
    from fastapi.responses import PlainTextResponse
    base = str(request.base_url).rstrip("/")
    content = (
        "User-agent: *\n"
        "Disallow: /api/\n"
        "Disallow: /auth/\n"
        "Disallow: /donate/checkout\n"
        "Disallow: /donate/success\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return PlainTextResponse(content)


@router.get("/sitemap.xml")
async def sitemap(request: Request, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import Response as FastAPIResponse
    rows_q = await db.execute(
        select(Article.id, Article.published_at).order_by(desc(Article.published_at))
    )
    rows = rows_q.fetchall()
    base = str(request.base_url).rstrip("/")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urls = [
        f'  <url><loc>{base}/</loc><lastmod>{today}</lastmod><changefreq>hourly</changefreq><priority>1.0</priority></url>',
        f'  <url><loc>{base}/privacy</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.3</priority></url>',
        f'  <url><loc>{base}/terms</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.3</priority></url>',
        f'  <url><loc>{base}/contact</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.4</priority></url>',
    ]
    if os.getenv("STRIPE_SECRET_KEY"):
        urls.append(f'  <url><loc>{base}/donate</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.5</priority></url>')
    for cat in CATEGORIES:
        slug = cat.replace(" ", "-").replace("&", "and").lower()
        urls.append(
            f'  <url><loc>{base}/category/{slug}</loc><lastmod>{today}</lastmod><changefreq>hourly</changefreq><priority>0.8</priority></url>'
        )
    for row in rows:
        lastmod = f"<lastmod>{row.published_at.strftime('%Y-%m-%d')}</lastmod>" if row.published_at else ""
        urls.append(f'  <url><loc>{base}/article/{row.id}</loc>{lastmod}<changefreq>never</changefreq><priority>0.6</priority></url>')

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls) + "\n</urlset>"
    return FastAPIResponse(content=xml, media_type="application/xml")


@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query("", min_length=0),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"
    if _search_rate_limited(ip):
        current_user = await get_optional_user(request, db)
        return templates.TemplateResponse("search.html", {
            "request": request, "query": q, "articles": [],
            "categories": CATEGORIES, "last_updated": _last_updated(),
            "current_user": current_user, "rate_limited": True,
        }, status_code=429)

    articles = []
    if q and q.strip():
        search_q = await db.execute(
            text(
                "SELECT * FROM articles "
                "WHERE search_vector @@ plainto_tsquery('english', :q) "
                "ORDER BY ts_rank(search_vector, plainto_tsquery('english', :q)) DESC "
                "LIMIT 30"
            ),
            {"q": q.strip()},
        )
        rows = search_q.mappings().all()
        if rows:
            ids = [r["id"] for r in rows]
            art_q = await db.execute(
                select(Article).where(Article.id.in_(ids)).order_by(desc(Article.relevance_score))
            )
            articles = art_q.scalars().all()

    current_user = await get_optional_user(request, db)
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q,
        "articles": [_enrich(a, _is_us(request)) for a in articles],
        "categories": CATEGORIES,
        "last_updated": _last_updated(),
        "current_user": current_user,
    })


# ─── REST API ────────────────────────────────────────────────────────────────

@router.get("/api/articles")
async def api_articles(
    category: Optional[str] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(Article).order_by(desc(Article.published_at)).offset(offset).limit(limit)
    if category:
        q = q.where(Article.category == category)
    result = await db.execute(q)
    articles = result.scalars().all()
    return [_to_dict(a) for a in articles]


@router.get("/api/stats")
async def api_stats(db: AsyncSession = Depends(get_db)):
    return await _get_stats(db)


@router.post("/api/trigger-collection")
async def trigger_collection():
    """Manual pipeline trigger (protected in production via env flag)."""
    if os.getenv("ALLOW_MANUAL_TRIGGER", "true").lower() != "true":
        return JSONResponse({"error": "Manual trigger disabled"}, status_code=403)
    from backend.scheduler import run_pipeline
    import asyncio
    asyncio.create_task(run_pipeline())
    return {"status": "collection started"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _enrich(article: Article, us_format: bool = False) -> dict:
    d = _to_dict(article)
    try:
        d["tags_list"] = article.tags if isinstance(article.tags, list) else []
    except (TypeError, AttributeError):
        d["tags_list"] = []
    d["severity_color"] = SEVERITY_COLORS.get(article.severity or "low", "#4a7c59")
    d["category_slug"] = (article.category or "").replace(" ", "-").replace("&", "and").lower()
    d["default_image_url"] = _category_default_image(article.category)
    d["display_image_url"] = article.image_url or d["default_image_url"]

    text = " ".join(filter(None, [article.ai_summary, article.description, article.content]))
    d["reading_time"] = max(1, round(len(text.split()) / 200))
    body_text = article.content or article.description or ""
    d["body_text"] = body_text
    d["body_html"] = _paragraphize(body_text)
    d["body_has_more"] = len(body_text) > 1200

    pub = article.published_at
    if pub:
        # UTC ISO string for JS (timezone + 12/24h + separator handled client-side)
        d["display_datetime"] = pub.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Server-side fallback rendered without JS
        day = str(pub.day)
        mon = pub.strftime("%b")
        yr = pub.strftime("%Y")
        t = pub.strftime("%H:%M")
        date_str = f"{mon} {day}, {yr}" if us_format else f"{day} {mon} {yr}"
        d["display_date"] = f"{date_str} · {t} UTC"
    else:
        d["display_datetime"] = None
        d["display_date"] = None

    return d


_ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "cite", "code", "em",
    "h2", "h3", "h4", "i", "li", "ol", "p", "pre", "s",
    "small", "strong", "sub", "sup", "ul",
}
_BLOCK_TAGS = ("<p>", "<h2>", "<h3>", "<h4>", "<ul>", "<ol>", "<blockquote>", "<pre>")

def _paragraphize(text: str) -> Markup:
    raw = strip_boilerplate((text or "").strip())
    if not raw:
        return Markup("")

    # Normalise <br> tags → newlines before sanitising so the paragraph
    # splitter can see them. Two or more consecutive <br> become a paragraph
    # break; a single <br> becomes a line break within a paragraph.
    raw = re.sub(r"(<br\s*/?>\s*){2,}", "\n\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    # Collapse 3+ blank lines left by boilerplate removal into one paragraph break
    raw = re.sub(r"\n{3,}", "\n\n", raw)

    # Sanitize: keep safe formatting and links, strip scripts/iframes/etc.
    sanitized = nh3.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes={"a": {"href", "title"}},
        link_rel="nofollow noopener noreferrer",
    )

    # If sanitized output has no block-level elements, it's plain text —
    # split on double newlines and wrap each block in <p>.
    if not any(tag in sanitized for tag in _BLOCK_TAGS):
        blocks = [b.strip() for b in sanitized.split("\n\n") if b.strip()]
        if not blocks:
            blocks = [sanitized] if sanitized else []
        html_blocks = []
        for b in blocks:
            non_empty = [l.strip() for l in b.split("\n") if l.strip()]
            # Peel off a trailing attribution line only when:
            #   - at least two non-empty lines exist
            #   - last line is short (8–99 chars) and has no sentence-ending punctuation
            #   - at least one preceding line is substantial (> 50 chars)
            #     to guard against mis-splitting genuinely short two-line blocks
            if (
                len(non_empty) >= 2
                and 8 < len(non_empty[-1]) < 100
                and not non_empty[-1].endswith((".", "!", "?"))
                and any(len(l) > 50 for l in non_empty[:-1])
            ):
                body = "<br>".join(non_empty[:-1])
                html_blocks.append(f"<p>{body}</p>")
                html_blocks.append(f'<p class="article-attribution">{non_empty[-1]}</p>')
            elif len(b) < 100 and html_blocks and not b.endswith((".", "!", "?")):
                # Whole block is an attribution (its own paragraph after 2+ <br>)
                html_blocks.append(f'<p class="article-attribution">{b}</p>')
            else:
                html_blocks.append(f"<p>{b.replace(chr(10), '<br>')}</p>")
        return Markup("\n").join(Markup(b) for b in html_blocks)

    return Markup(sanitized)


def _category_default_image(category: str | None) -> str:
    filename = CATEGORY_DEFAULT_IMAGES.get(category or "")
    if not filename:
        return "/static/icons/social-800.png"
    return f"/static/images/category-defaults/{filename}"


def _is_us(request: Request) -> bool:
    lang = request.headers.get("accept-language", "").lower()
    return "en-us" in lang


def _to_dict(article: Article) -> dict:
    return {
        "id": article.id,
        "url": article.url,
        "title": article.title,
        "description": article.description,
        "content": article.content,
        "source_name": article.source_name,
        "source_country": article.source_country,
        "author": article.author,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "collected_at": article.collected_at.isoformat() if article.collected_at else None,
        "relevance_score": article.relevance_score,
        "category": article.category,
        "severity": article.severity,
        "tags": article.tags,
        "ai_summary": article.ai_summary,
        "featured": article.featured,
        "image_url": article.image_url,
    }


_stats_cache: dict = {}
_STATS_TTL = 60  # seconds

async def _get_stats(db: AsyncSession) -> dict:
    now = time.time()
    if _stats_cache.get("expires", 0) > now:
        return _stats_cache["data"]

    total_q = await db.execute(select(func.count()).select_from(Article))
    total = total_q.scalar() or 0

    by_cat_q = await db.execute(
        select(Article.category, func.count().label("n"))
        .group_by(Article.category)
        .order_by(desc("n"))
    )
    by_category = {row[0]: row[1] for row in by_cat_q.fetchall() if row[0]}

    last_log_q = await db.execute(
        select(CollectionLog).order_by(desc(CollectionLog.ran_at)).limit(1)
    )
    last_log = last_log_q.scalar_one_or_none()

    since_24h_q = await db.execute(
        select(func.count()).where(
            Article.collected_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        )
    )
    since_24h = since_24h_q.scalar() or 0

    result = {
        "total_articles": total,
        "articles_last_24h": since_24h,
        "by_category": by_category,
        "last_collection": last_log.ran_at.isoformat() if last_log else None,
    }
    _stats_cache["data"] = result
    _stats_cache["expires"] = now + _STATS_TTL
    return result
