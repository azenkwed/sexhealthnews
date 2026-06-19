"""Send personalised daily/weekly newsletter digests."""
import html
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.database.db import SessionLocal
from backend.database.models import Article, NewsletterLog, User
from backend.notifications.email import APP_URL, FROM_EMAIL, _send
from backend.processors.newsletter_writer import write_newsletter


def _period_key(frequency: str, now: datetime) -> str:
    if frequency == "daily":
        return now.strftime("%Y-%m-%d")
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

_MIN_ARTICLES = 3
_MAX_ARTICLES = 10

_WRAPPER = """
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:40px 20px;color:#111827;">
  <div style="font-size:22px;font-weight:700;margin-bottom:4px;">Sex Health News</div>
  <p style="color:#9ca3af;font-size:11px;margin-bottom:36px;text-transform:uppercase;letter-spacing:0.05em;">
    Independent reporting on surveillance, censorship, and authoritarian control
  </p>
  {body}
  <p style="margin-top:40px;font-size:11px;color:#9ca3af;border-top:1px solid #e5e7eb;padding-top:16px;">
    You're receiving this because you subscribed to the {frequency} digest on Sex Health News.
    <a href="{profile_url}" style="color:#9ca3af;">Manage preferences</a>
  </p>
</div>
"""


def _article_row(article: Article) -> str:
    title = html.escape(article.title or "")
    source = html.escape(article.source_name or "")
    category = html.escape(article.category or "")
    raw_summary = article.ai_summary or article.description or ""
    summary = html.escape(raw_summary[:200])
    ellipsis = "…" if len(raw_summary) > 200 else ""
    url = f"{APP_URL}/article/{article.id}"
    return (
        f'<div style="margin-bottom:22px;padding-bottom:22px;border-bottom:1px solid #e5e7eb;">'
        f'<div style="font-size:11px;color:#9ca3af;text-transform:uppercase;'
        f'letter-spacing:0.05em;margin-bottom:5px;">{category} · {source}</div>'
        f'<a href="{url}" style="font-size:15px;font-weight:700;color:#111827;'
        f'text-decoration:none;line-height:1.4;">{title}</a>'
        + (
            f'<p style="margin:6px 0 0;font-size:13px;color:#374151;line-height:1.55;">'
            f'{summary}{ellipsis}</p>'
            if summary else ""
        )
        + "</div>"
    )


async def send_newsletters(frequency: str) -> None:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1 if frequency == "daily" else 7)
    period = _period_key(frequency, now)
    date_str = now.strftime(f"%B {now.day}, %Y")
    period_label = "Today's" if frequency == "daily" else "This week's"

    async with SessionLocal() as db:
        art_q = await db.execute(
            select(Article)
            .where(Article.collected_at >= since)
            .order_by(Article.relevance_score.desc())
            .limit(_MAX_ARTICLES * 4)
        )
        pool = art_q.scalars().all()

        users_q = await db.execute(
            select(User).where(
                User.newsletter_frequency == frequency,
                User.email_verified == True,
            )
        )
        subscribers = users_q.scalars().all()

        # Pre-fetch already-sent user IDs for this period in one query (#18)
        sent_q = await db.execute(
            select(NewsletterLog.user_id).where(
                NewsletterLog.frequency == frequency,
                NewsletterLog.period_key == period,
            )
        )
        already_sent_ids = {row[0] for row in sent_q.fetchall()}

    if len(pool) < _MIN_ARTICLES:
        print(f"[Newsletter] Only {len(pool)} articles in window — skipping {frequency} digest.")
        return

    print(f"[Newsletter] Writing {frequency} digest to {len(subscribers)} subscriber(s) for period {period}.")
    sent = skipped = already_sent = 0
    # Cache Claude output by category set to avoid redundant API calls (#20)
    _copy_cache: dict[frozenset, dict] = {}

    for user in subscribers:
        if user.id in already_sent_ids:
            already_sent += 1
            continue

        try:
            user_cats = set(json.loads(user.categories or "[]"))
        except Exception:
            user_cats = set()

        articles = [a for a in pool if a.category in user_cats] if user_cats else list(pool)
        articles = articles[:_MAX_ARTICLES]

        if len(articles) < _MIN_ARTICLES:
            skipped += 1
            continue

        # Generate intro based on this subscriber's filtered article set (#20)
        cats_key = frozenset(user_cats)
        if cats_key in _copy_cache:
            copy = _copy_cache[cats_key]
        else:
            try:
                copy = await write_newsletter(
                    [{"title": a.title, "category": a.category, "source_name": a.source_name,
                      "ai_summary": a.ai_summary or ""}
                     for a in articles],
                    frequency,
                )
                _copy_cache[cats_key] = copy
            except Exception as exc:
                print(f"[Newsletter] Claude error for user {user.id}: {exc}")
                skipped += 1
                continue

        subject = copy.get("subject") or f"Sex Health News {frequency.title()} Digest"
        intro = html.escape(copy.get("intro") or "")

        rows_html = "".join(_article_row(a) for a in articles)
        body = (
            f'<h2 style="font-size:20px;font-weight:700;margin-bottom:4px;">'
            f'{period_label} top stories</h2>'
            f'<p style="font-size:11px;color:#9ca3af;margin-bottom:20px;">{date_str}</p>'
            f'<p style="font-size:14px;color:#374151;line-height:1.6;margin-bottom:28px;">{intro}</p>'
            f'{rows_html}'
            f'<p style="margin-top:8px;">'
            f'<a href="{APP_URL}" style="display:inline-block;padding:10px 24px;'
            f'background:#111827;color:#fff;text-decoration:none;font-weight:600;font-size:13px;">'
            f'Read more on Sex Health News</a></p>'
        )
        email_html = _WRAPPER.format(body=body, frequency=frequency, profile_url=f"{APP_URL}/profile")

        if not _send(user.email, subject, email_html):
            skipped += 1
            continue

        async with SessionLocal() as db:
            try:
                db.add(NewsletterLog(
                    user_id=user.id,
                    frequency=frequency,
                    period_key=period,
                    subject=subject,
                    article_count=len(articles),
                ))
                await db.commit()
                sent += 1
            except IntegrityError:
                await db.rollback()
                already_sent += 1

    print(f"[Newsletter] Done — sent {sent}, skipped {skipped}, already sent {already_sent}.")


async def preview_newsletter(frequency: str = "daily") -> str:
    """Return the newsletter HTML for the given frequency without sending anything."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1 if frequency == "daily" else 7)

    async with SessionLocal() as db:
        art_q = await db.execute(
            select(Article)
            .where(Article.collected_at >= since)
            .order_by(Article.relevance_score.desc())
            .limit(_MAX_ARTICLES)
        )
        articles = art_q.scalars().all()

    if not articles:
        return "<p>No articles in this window yet.</p>"

    try:
        copy = await write_newsletter(
            [{"title": a.title, "category": a.category, "source_name": a.source_name}
             for a in articles],
            frequency,
        )
    except Exception as exc:
        return f"<p>Claude error: {exc}</p>"

    intro = html.escape(copy.get("intro") or "")
    date_str = now.strftime(f"%B {now.day}, %Y")
    period_label = "Today's" if frequency == "daily" else "This week's"

    rows_html = "".join(_article_row(a) for a in articles)
    body = (
        f'<h2 style="font-size:20px;font-weight:700;margin-bottom:4px;">'
        f'{period_label} top stories</h2>'
        f'<p style="font-size:11px;color:#9ca3af;margin-bottom:20px;">{date_str}</p>'
        f'<p style="font-size:14px;color:#374151;line-height:1.6;margin-bottom:28px;">{intro}</p>'
        f'{rows_html}'
        f'<p style="margin-top:8px;">'
        f'<a href="{APP_URL}" style="display:inline-block;padding:10px 24px;'
        f'background:#111827;color:#fff;text-decoration:none;font-weight:600;font-size:13px;">'
        f'Read more on Sex Health News</a></p>'
    )
    return _WRAPPER.format(body=body, frequency=frequency, profile_url=f"{APP_URL}/profile")
