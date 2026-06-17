"""Admin routes — articles, logs, settings, pipeline trigger."""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, desc, distinct, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.database.models import Article, CollectionLog, CurationRecord, NewsletterLog, OAuthAccount, TweetLog, User
from backend.processors.curator import CATEGORIES

router = APIRouter()
templates = Jinja2Templates(directory="admin/templates")

CATEGORIES_LIST = [v for k, v in CATEGORIES.items() if k != "NONE"]
SEVERITY_LEVELS = ["low", "medium", "high", "critical"]


async def _oauth_providers_for_users(db: AsyncSession, user_ids: list[int]) -> dict[int, list[str]]:
    if not user_ids:
        return {}
    rows = (await db.execute(
        select(OAuthAccount).where(OAuthAccount.user_id.in_(user_ids))
    )).scalars().all()
    providers: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        providers[row.user_id].append(row.provider)
    return dict(providers)


async def _user_emails_by_id(db: AsyncSession, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.email).where(User.id.in_(user_ids))
    )).fetchall()
    return {row[0]: row[1] for row in rows}


# ─── Dashboard ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    msg: str = "",
    msg_type: str = "success",
    refreshing: int = 0,
):
    total = (await db.execute(select(func.count()).select_from(Article))).scalar() or 0

    since_24h = (await db.execute(
        select(func.count()).where(
            Article.collected_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        )
    )).scalar() or 0

    featured_count = (await db.execute(
        select(func.count()).where(Article.featured == True)
    )).scalar() or 0

    total_logs = (await db.execute(select(func.count()).select_from(CollectionLog))).scalar() or 0

    by_category = [
        (row[0], row[1])
        for row in (await db.execute(
            select(Article.category, func.count().label("n"))
            .group_by(Article.category)
            .order_by(desc("n"))
        )).fetchall()
        if row[0]
    ]

    by_severity = {
        row[0]: row[1]
        for row in (await db.execute(
            select(Article.severity, func.count().label("n"))
            .group_by(Article.severity)
        )).fetchall()
        if row[0]
    }

    recent_logs = (await db.execute(
        select(CollectionLog).order_by(desc(CollectionLog.ran_at)).limit(10)
    )).scalars().all()

    max_cat = max((n for _, n in by_category), default=1)

    # DB stats
    user_count  = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    oauth_count = (await db.execute(select(func.count()).select_from(OAuthAccount))).scalar() or 0
    curation_count = (await db.execute(select(func.count()).select_from(CurationRecord))).scalar() or 0
    recent_users = (await db.execute(
        select(User).order_by(desc(User.created_at)).limit(8)
    )).scalars().all()
    oauth_by_user = await _oauth_providers_for_users(db, [user.id for user in recent_users])

    # PostgreSQL version and info
    pg_version  = (await db.execute(text("SELECT version()"))).scalar() or "—"
    db_size_bytes = (await db.execute(text("SELECT pg_database_size(current_database())"))).scalar() or 0

    def _fmt_size(b: int) -> str:
        if b < 1024: return f"{b} B"
        if b < 1024 ** 2: return f"{b / 1024:.1f} KB"
        return f"{b / 1024 ** 2:.2f} MB"

    db_info = {
        "size":        _fmt_size(db_size_bytes),
        "pg_version":  pg_version,
        "rows": {
            "Articles": total,
            "Users": user_count,
            "OAuth accounts": oauth_count,
            "Curation records": curation_count,
            "Collection logs": total_logs,
        },
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active": "dashboard",
        "total": total,
        "since_24h": since_24h,
        "featured_count": featured_count,
        "total_logs": total_logs,
        "by_category": by_category,
        "by_severity": by_severity,
        "max_cat": max_cat,
        "recent_logs": recent_logs,
        "recent_users": recent_users,
        "oauth_by_user": oauth_by_user,
        "db_info": db_info,
        "msg": msg,
        "msg_type": msg_type,
        "refreshing": refreshing,
        "log_count": total_logs,
        "app_url": os.getenv("APP_URL", "http://localhost:8000"),
    })


# ─── Curation records ────────────────────────────────────────────────────────

@router.get("/curation-records", response_class=HTMLResponse)
async def curation_records_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    q: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
):
    per_page = 50
    base_q = select(CurationRecord).order_by(desc(CurationRecord.evaluated_at))
    count_q = select(func.count()).select_from(CurationRecord)

    if q:
        f = or_(
            CurationRecord.title.ilike(f"%{q}%"),
            CurationRecord.source_name.ilike(f"%{q}%"),
            CurationRecord.category.ilike(f"%{q}%"),
            CurationRecord.url.ilike(f"%{q}%"),
        )
        base_q = base_q.where(f)
        count_q = count_q.where(f)
    if status:
        base_q = base_q.where(CurationRecord.status == status)
        count_q = count_q.where(CurationRecord.status == status)

    total = (await db.execute(count_q)).scalar() or 0
    records = (await db.execute(
        base_q.offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()

    return templates.TemplateResponse("curation_records.html", {
        "request": request,
        "active": "curation",
        "records": records,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "q": q,
        "status": status,
    })


# ─── OAuth accounts ──────────────────────────────────────────────────────────

@router.get("/oauth-accounts", response_class=HTMLResponse)
async def oauth_accounts_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: str = "",
    page: int = Query(1, ge=1),
):
    per_page = 50
    base_q = select(OAuthAccount).order_by(desc(OAuthAccount.created_at))
    count_q = select(func.count()).select_from(OAuthAccount)

    if provider:
        base_q = base_q.where(OAuthAccount.provider == provider)
        count_q = count_q.where(OAuthAccount.provider == provider)

    total = (await db.execute(count_q)).scalar() or 0
    accounts = (await db.execute(
        base_q.offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    user_emails = await _user_emails_by_id(db, [account.user_id for account in accounts])
    providers = [
        row[0]
        for row in (await db.execute(
            select(distinct(OAuthAccount.provider)).order_by(OAuthAccount.provider)
        )).fetchall()
        if row[0]
    ]

    return templates.TemplateResponse("oauth_accounts.html", {
        "request": request,
        "active": "oauth",
        "accounts": accounts,
        "user_emails": user_emails,
        "providers": providers,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "provider": provider,
    })


# ─── Users ───────────────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def users_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    q: str = "",
    verified: str = "",
    page: int = Query(1, ge=1),
):
    per_page = 30
    base_q = select(User).order_by(desc(User.created_at))
    count_q = select(func.count()).select_from(User)

    if q:
        f = or_(
            User.email.ilike(f"%{q}%"),
            User.display_name.ilike(f"%{q}%"),
        )
        base_q = base_q.where(f)
        count_q = count_q.where(f)
    if verified == "1":
        base_q = base_q.where(User.email_verified == True)
        count_q = count_q.where(User.email_verified == True)
    elif verified == "0":
        base_q = base_q.where(User.email_verified == False)
        count_q = count_q.where(User.email_verified == False)

    total = (await db.execute(count_q)).scalar() or 0
    users = (await db.execute(
        base_q.offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    oauth_by_user = await _oauth_providers_for_users(db, [user.id for user in users])

    return templates.TemplateResponse("users.html", {
        "request": request,
        "active": "users",
        "users": users,
        "oauth_by_user": oauth_by_user,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "q": q,
        "verified": verified,
    })


@router.post("/trigger")
async def trigger_pipeline():
    from backend.scheduler import run_pipeline
    import asyncio
    asyncio.create_task(run_pipeline())
    return RedirectResponse("/?msg=Collection+started…&msg_type=success&refreshing=1", status_code=303)


@router.get("/api/last-run")
async def api_last_run(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count()).select_from(CollectionLog))).scalar() or 0
    last = (await db.execute(
        select(CollectionLog).order_by(desc(CollectionLog.ran_at)).limit(1)
    )).scalar_one_or_none()
    return {
        "count": total,
        "ran_at": last.ran_at.isoformat() if last else None,
        "error": last.error if last else None,
    }


# ─── Articles ────────────────────────────────────────────────────────────────

@router.get("/articles", response_class=HTMLResponse)
async def articles_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    q: str = "",
    category: str = "",
    severity: str = "",
    featured: str = "",
    page: int = Query(1, ge=1),
    msg: str = "",
    msg_type: str = "success",
):
    per_page = 30
    base_q = select(Article).order_by(desc(Article.collected_at))
    count_q = select(func.count()).select_from(Article)

    if q:
        f = or_(
            Article.title.ilike(f"%{q}%"),
            Article.source_name.ilike(f"%{q}%"),
            Article.ai_summary.ilike(f"%{q}%"),
        )
        base_q = base_q.where(f)
        count_q = count_q.where(f)
    if category:
        base_q = base_q.where(Article.category == category)
        count_q = count_q.where(Article.category == category)
    if severity:
        base_q = base_q.where(Article.severity == severity)
        count_q = count_q.where(Article.severity == severity)
    if featured == "1":
        base_q = base_q.where(Article.featured == True)
        count_q = count_q.where(Article.featured == True)

    total = (await db.execute(count_q)).scalar() or 0
    articles = (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    return templates.TemplateResponse("articles.html", {
        "request": request,
        "active": "articles",
        "articles": articles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "q": q,
        "category": category,
        "severity": severity,
        "featured": featured,
        "categories_list": CATEGORIES_LIST,
        "severity_levels": SEVERITY_LEVELS,
        "msg": msg,
        "msg_type": msg_type,
    })


@router.post("/articles/bulk-delete")
async def bulk_delete(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("ids") if str(v).isdigit()]
    if not ids:
        return RedirectResponse("/articles?msg=No+articles+selected&msg_type=error", status_code=303)
    await db.execute(delete(Article).where(Article.id.in_(ids)))
    await db.commit()
    return RedirectResponse(f"/articles?msg={len(ids)}+articles+deleted&msg_type=success", status_code=303)


@router.get("/articles/{article_id}", response_class=HTMLResponse)
async def article_detail(
    request: Request,
    article_id: int,
    db: AsyncSession = Depends(get_db),
    msg: str = "",
    msg_type: str = "success",
):
    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if not article:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "status_code": 404,
            "title": "Not Found",
            "detail": "Article not found.",
            "active": "articles",
        }, status_code=404)

    tags = article.tags if isinstance(article.tags, list) else []

    return templates.TemplateResponse("article_detail.html", {
        "request": request,
        "active": "articles",
        "article": article,
        "tags": tags,
        "categories_list": CATEGORIES_LIST,
        "severity_levels": SEVERITY_LEVELS,
        "msg": msg,
        "msg_type": msg_type,
    })


@router.post("/articles/{article_id}")
async def article_update(
    request: Request,
    article_id: int,
    db: AsyncSession = Depends(get_db),
    category: str = Form(...),
    severity: str = Form(...),
    featured: str = Form("off"),
    ai_summary: str = Form(""),
):
    if category not in CATEGORIES_LIST or severity not in SEVERITY_LEVELS:
        return HTMLResponse("Invalid category or severity value", status_code=422)

    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if not article:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "status_code": 404,
            "title": "Not Found",
            "detail": "Article not found.",
            "active": "articles",
        }, status_code=404)

    article.category = category
    article.severity = severity
    article.featured = (featured == "on")
    article.ai_summary = ai_summary
    await db.commit()

    return RedirectResponse(f"/articles/{article_id}?msg=Saved&msg_type=success", status_code=303)


@router.post("/articles/{article_id}/delete")
async def article_delete(article_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Article).where(Article.id == article_id))
    await db.commit()
    return RedirectResponse("/articles?msg=Article+deleted&msg_type=success", status_code=303)


# ─── Logs ────────────────────────────────────────────────────────────────────

@router.get("/logs", response_class=HTMLResponse)
async def logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
):
    per_page = 50
    total = (await db.execute(select(func.count()).select_from(CollectionLog))).scalar() or 0
    logs_list = (await db.execute(
        select(CollectionLog).order_by(desc(CollectionLog.ran_at))
        .offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()

    total_accepted = (await db.execute(
        select(func.sum(CollectionLog.articles_accepted))
    )).scalar() or 0

    total_fetched = (await db.execute(
        select(func.sum(CollectionLog.articles_fetched))
    )).scalar() or 0

    return templates.TemplateResponse("logs.html", {
        "request": request,
        "active": "logs",
        "logs": logs_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "total_accepted": total_accepted,
        "total_fetched": total_fetched,
    })


# ─── Settings ────────────────────────────────────────────────────────────────

_ENV_VARS = [
    # (name, required, default, description, secret)
    # ── Core ──────────────────────────────────────────────────────────────────
    ("ANTHROPIC_API_KEY",          True,  None,                          "AI curation + newsletter writing",                True),
    ("JWT_SECRET_KEY",             True,  "dev-secret-change-in-production", "JWT signing + session middleware",             True),
    # ── Pipeline ──────────────────────────────────────────────────────────────
    ("MIN_RELEVANCE_SCORE",        False, "0.65",                        "Articles below this score are discarded",         False),
    ("COLLECTION_INTERVAL_MINUTES",False, "60",                          "How often the pipeline runs (minutes)",           False),
    ("ALLOW_MANUAL_TRIGGER",       False, "true",                        "Enable POST /api/trigger-collection",             False),
    ("ARTICLE_RETENTION_DAYS",     False, "0",                           "Prune articles older than N days (0 = keep all)", False),
    ("NEWSAPI_KEY",                False, None,                          "Adds keyword search on top of RSS feeds",         True),
    ("DISABLE_NEWSAPI",            False, "false",                       "Skip NewsAPI collector (RSS still runs)",         False),
    # ── App server ────────────────────────────────────────────────────────────
    ("APP_URL",                    False, "http://localhost:8000",       "Base URL used in emails and OAuth redirects",     False),
    ("APP_HOST",                   False, "0.0.0.0",                    "Uvicorn bind host",                               False),
    ("APP_PORT",                   False, "8000",                       "Uvicorn bind port",                               False),
    ("DEBUG",                      False, "false",                      "Enable uvicorn auto-reload",                      False),
    ("LOG_LEVEL",                  False, "INFO",                       "Logging verbosity",                               False),
    # ── Email ─────────────────────────────────────────────────────────────────
    ("RESEND_API_KEY",             False, None,                         "Email delivery (verification, reset, contact)",   True),
    ("FROM_EMAIL",                 False, "Sex Health News <noreply@sexhealthnew.com>", "Sender address for transactional email",  False),
    ("CONTACT_EMAIL",              False, "contact@sexhealthnew.com",      "Recipient for contact-form submissions",          False),
    # ── OAuth ─────────────────────────────────────────────────────────────────
    ("GOOGLE_CLIENT_ID",           False, None,                         "Google OAuth (button appears only if both set)",  True),
    ("GOOGLE_CLIENT_SECRET",       False, None,                         "Google OAuth secret",                             True),
    ("LINKEDIN_CLIENT_ID",         False, None,                         "LinkedIn OAuth",                                  True),
    ("LINKEDIN_CLIENT_SECRET",     False, None,                         "LinkedIn OAuth secret",                           True),
    ("MICROSOFT_CLIENT_ID",        False, None,                         "Microsoft OAuth",                                 True),
    ("MICROSOFT_CLIENT_SECRET",    False, None,                         "Microsoft OAuth secret",                          True),
    # ── Payments ──────────────────────────────────────────────────────────────
    ("STRIPE_SECRET_KEY",          False, None,                         "Stripe payments (donation page enabled if set)",  True),
    ("STRIPE_PUBLISHABLE_KEY",     False, None,                         "Stripe publishable key (used in frontend)",       True),
    ("STRIPE_WEBHOOK_SECRET",      False, None,                         "Stripe webhook signature verification",           True),
]

_ENV_GROUPS = [
    ("Core",     ["ANTHROPIC_API_KEY", "JWT_SECRET_KEY"]),
    ("Pipeline", ["MIN_RELEVANCE_SCORE", "COLLECTION_INTERVAL_MINUTES", "ALLOW_MANUAL_TRIGGER",
                  "ARTICLE_RETENTION_DAYS", "NEWSAPI_KEY", "DISABLE_NEWSAPI"]),
    ("App Server", ["APP_URL", "APP_HOST", "APP_PORT", "DEBUG", "LOG_LEVEL"]),
    ("Email",    ["RESEND_API_KEY", "FROM_EMAIL", "CONTACT_EMAIL"]),
    ("OAuth",    ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "LINKEDIN_CLIENT_ID",
                  "LINKEDIN_CLIENT_SECRET", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"]),
    ("Payments", ["STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET"]),
]

def _build_env_status() -> dict:
    meta = {name: (required, default, desc, secret) for name, required, default, desc, secret in _ENV_VARS}
    groups = []
    for group_name, keys in _ENV_GROUPS:
        rows = []
        for key in keys:
            required, default, desc, secret = meta[key]
            raw = os.getenv(key)
            is_set = bool(raw)
            if is_set:
                display = "••••••••" if secret else raw
            else:
                display = f"(default: {default})" if default else "—"
            rows.append({
                "name": key,
                "required": required,
                "is_set": is_set,
                "display": display,
                "description": desc,
            })
        groups.append({"name": group_name, "rows": rows})
    return groups


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    msg: str = "",
    msg_type: str = "success",
):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active": "settings",
        "min_relevance_score": os.getenv("MIN_RELEVANCE_SCORE", "0.65"),
        "collection_interval": os.getenv("COLLECTION_INTERVAL_MINUTES", "60"),
        "allow_manual_trigger": os.getenv("ALLOW_MANUAL_TRIGGER", "true"),
        "article_retention_days": os.getenv("ARTICLE_RETENTION_DAYS", "0"),
        "env_groups": _build_env_status(),
        "msg": msg,
        "msg_type": msg_type,
    })


@router.post("/settings")
async def settings_update(
    min_relevance_score: str = Form("0.65"),
    collection_interval: str = Form("60"),
    allow_manual_trigger: str = Form("false"),
    article_retention_days: str = Form("0"),
):
    from dotenv import set_key
    env_path = Path(".env")
    set_key(str(env_path), "MIN_RELEVANCE_SCORE", min_relevance_score)
    set_key(str(env_path), "COLLECTION_INTERVAL_MINUTES", collection_interval)
    set_key(str(env_path), "ALLOW_MANUAL_TRIGGER", allow_manual_trigger)
    set_key(str(env_path), "ARTICLE_RETENTION_DAYS", article_retention_days)
    os.environ["MIN_RELEVANCE_SCORE"] = min_relevance_score
    os.environ["COLLECTION_INTERVAL_MINUTES"] = collection_interval
    os.environ["ALLOW_MANUAL_TRIGGER"] = allow_manual_trigger
    os.environ["ARTICLE_RETENTION_DAYS"] = article_retention_days
    return RedirectResponse(
        "/settings?msg=Settings+saved.+Restart+main+app+for+interval+changes.&msg_type=success",
        status_code=303,
    )


# ─── Newsletter logs ─────────────────────────────────────────────────────────

@router.get("/newsletter-logs", response_class=HTMLResponse)
async def newsletter_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    frequency: str = "",
    q: str = "",
    page: int = Query(1, ge=1),
):
    per_page = 50
    base_q = (
        select(NewsletterLog, User.email)
        .join(User, User.id == NewsletterLog.user_id)
        .order_by(desc(NewsletterLog.sent_at))
    )
    count_q = select(func.count()).select_from(NewsletterLog)

    if frequency:
        base_q = base_q.where(NewsletterLog.frequency == frequency)
        count_q = count_q.where(NewsletterLog.frequency == frequency)
    if q:
        base_q = base_q.where(User.email.ilike(f"%{q}%"))
        count_q = count_q.join(User, User.id == NewsletterLog.user_id).where(User.email.ilike(f"%{q}%"))

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).fetchall()

    total_daily = (await db.execute(
        select(func.count()).select_from(NewsletterLog).where(NewsletterLog.frequency == "daily")
    )).scalar() or 0
    total_weekly = (await db.execute(
        select(func.count()).select_from(NewsletterLog).where(NewsletterLog.frequency == "weekly")
    )).scalar() or 0
    unique_subscribers = (await db.execute(
        select(func.count(func.distinct(NewsletterLog.user_id))).select_from(NewsletterLog)
    )).scalar() or 0

    return templates.TemplateResponse("newsletter_logs.html", {
        "request": request,
        "active": "newsletter_logs",
        "rows": rows,
        "total": total,
        "total_daily": total_daily,
        "total_weekly": total_weekly,
        "unique_subscribers": unique_subscribers,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "frequency": frequency,
        "q": q,
    })


# ─── Tweet logs ──────────────────────────────────────────────────────────────

@router.get("/tweet-logs", response_class=HTMLResponse)
async def tweet_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str = "",
    q: str = "",
    page: int = Query(1, ge=1),
    msg: str = "",
    msg_type: str = "success",
):
    per_page = 50
    base_q = (
        select(TweetLog)
        .order_by(desc(TweetLog.tweeted_at))
    )
    count_q = select(func.count()).select_from(TweetLog)

    if status == "ok":
        base_q = base_q.where(TweetLog.success == True)
        count_q = count_q.where(TweetLog.success == True)
    elif status == "failed":
        base_q = base_q.where(TweetLog.success == False)
        count_q = count_q.where(TweetLog.success == False)
    if q:
        base_q = base_q.where(TweetLog.article_title.ilike(f"%{q}%"))
        count_q = count_q.where(TweetLog.article_title.ilike(f"%{q}%"))

    total = (await db.execute(count_q)).scalar() or 0
    logs = (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    total_ok = (await db.execute(
        select(func.count()).select_from(TweetLog).where(TweetLog.success == True)
    )).scalar() or 0
    total_failed = (await db.execute(
        select(func.count()).select_from(TweetLog).where(TweetLog.success == False)
    )).scalar() or 0

    recent_featured = (await db.execute(
        select(Article).where(Article.featured == True)
        .order_by(desc(Article.collected_at)).limit(20)
    )).scalars().all()

    return templates.TemplateResponse("tweet_logs.html", {
        "request": request,
        "active": "tweet_logs",
        "logs": logs,
        "total": total,
        "total_ok": total_ok,
        "total_failed": total_failed,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),
        "status": status,
        "q": q,
        "app_url": os.getenv("APP_URL", "http://localhost:8000"),
        "recent_featured": recent_featured,
        "msg": msg,
        "msg_type": msg_type,
    })


@router.post("/tweet-logs/bulk-delete")
async def tweet_logs_bulk_delete(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("ids") if str(v).isdigit()]
    if not ids:
        return RedirectResponse("/tweet-logs?msg=No+entries+selected&msg_type=error", status_code=303)
    await db.execute(delete(TweetLog).where(TweetLog.id.in_(ids)))
    await db.commit()
    return RedirectResponse(f"/tweet-logs?msg={len(ids)}+entries+deleted&msg_type=success", status_code=303)


@router.post("/tweet-logs/{log_id}/delete")
async def tweet_log_delete(log_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(TweetLog).where(TweetLog.id == log_id))
    await db.commit()
    return RedirectResponse("/tweet-logs?msg=Entry+deleted&msg_type=success", status_code=303)


@router.post("/tweet-logs/send")
async def tweet_send(
    db: AsyncSession = Depends(get_db),
    article_id: int = Form(...),
):
    from backend.processors.twitter_agent import write_tweet
    from backend.social.twitter import is_enabled, post_tweet

    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if not article:
        return RedirectResponse("/tweet-logs?msg=Article+not+found&msg_type=error", status_code=303)

    if not is_enabled():
        return RedirectResponse("/tweet-logs?msg=Twitter+not+configured&msg_type=error", status_code=303)

    already = (await db.execute(
        select(TweetLog.id).where(TweetLog.article_id == article_id, TweetLog.success == True).limit(1)
    )).scalar_one_or_none()
    if already:
        return RedirectResponse("/tweet-logs?msg=Already+tweeted+for+this+article&msg_type=error", status_code=303)

    app_url = os.getenv("APP_URL", "http://localhost:8000")
    is_local = app_url.startswith("http://localhost") or app_url.startswith("http://127.")
    twitter_handle = os.getenv("TWITTER_HANDLE", "sexhealthnew")
    url = f"https://x.com/{twitter_handle}" if is_local else f"{app_url}/article/{article.id}"
    tweet_text = ""
    success = False
    error = None

    try:
        art = {
            "title": article.title,
            "category": article.category,
            "severity": article.severity,
            "source_name": article.source_name,
            "ai_summary": article.ai_summary,
            "description": article.description,
        }
        tweet_text = await write_tweet(art)
        max_text = 280 - 24
        if len(tweet_text) > max_text:
            tweet_text = tweet_text[:max_text - 1] + "…"
        full_tweet = f"{tweet_text} {url}"
        success = post_tweet(full_tweet, image_url=article.image_url or "")
    except Exception as exc:
        error = str(exc)

    db.add(TweetLog(
        article_id=article.id,
        article_title=article.title,
        tweet_text=tweet_text,
        success=success,
        error=error,
        tweet_key=article.id if success else None,
    ))
    await db.commit()

    if success:
        msg = f"Tweet+posted+for%3A+{article.title[:60].replace(' ', '+')}"
        return RedirectResponse(f"/tweet-logs?msg={msg}&msg_type=success", status_code=303)
    else:
        err_enc = (error or "unknown error")[:80].replace(' ', '+')
        return RedirectResponse(f"/tweet-logs?msg=Tweet+failed%3A+{err_enc}&msg_type=error", status_code=303)


# ─── Newsletter preview ───────────────────────────────────────────────────────

@router.get("/newsletter-preview", response_class=HTMLResponse)
async def newsletter_preview(frequency: str = "daily"):
    import asyncio
    from backend.notifications.newsletter import preview_newsletter
    try:
        content = await asyncio.wait_for(preview_newsletter(frequency), timeout=30.0)
    except asyncio.TimeoutError:
        content = "<p style='font-family:sans-serif;padding:20px;color:#b91c1c;'>Preview timed out after 30s — the Claude API may be slow. Try again in a moment.</p>"
    except Exception as exc:
        content = f"<p style='font-family:sans-serif;padding:20px;color:#b91c1c;'>Preview error: {exc}</p>"
    return HTMLResponse(content=content)
