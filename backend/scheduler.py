"""APScheduler pipeline — collect → classify → write → store → tweet."""
import asyncio
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from backend.database.db import SessionLocal
from backend.database.models import Article, CollectionLog, CurationRecord, TweetLog


async def _tweet_featured(session, featured_pairs: list[tuple]) -> None:
    from backend.social.twitter import is_enabled, post_tweet

    if not is_enabled():
        return

    app_url = os.getenv("APP_URL", "http://localhost:8000")
    is_local = app_url.startswith("http://localhost") or app_url.startswith("http://127.")
    twitter_handle = os.getenv("TWITTER_HANDLE", "sexhealthnew")
    max_per_run = int(os.getenv("TWITTER_MAX_PER_RUN", "1"))

    featured_pairs = sorted(featured_pairs, key=lambda x: x[1].get("relevance_score", 0), reverse=True)[:max_per_run]

    for obj, art in featured_pairs:
        already_tweeted = (await session.execute(
            select(TweetLog.id).where(
                TweetLog.article_id == obj.id,
                TweetLog.success == True,
            ).limit(1)
        )).scalar_one_or_none()
        if already_tweeted:
            print(f"[Twitter] Skipping (already tweeted): {obj.title[:60]}")
            continue

        tweet_text = art.get("tweet_text") or ""
        success = False
        error = None

        if not tweet_text:
            print(f"[Twitter] No tweet text for: {obj.title[:60]}")
            error = "no tweet text generated"
        else:
            try:
                url = f"https://x.com/{twitter_handle}" if is_local else f"{app_url}/article/{obj.id}"
                _URL_CHARS = 23
                max_text = 280 - _URL_CHARS - 1
                if len(tweet_text) > max_text:
                    tweet_text = tweet_text[:max_text - 1] + "…"
                full_tweet = f"{tweet_text} {url}"
                success = post_tweet(full_tweet, image_url=art.get("image_url", ""))
                print(f"[Twitter] {'posted' if success else 'failed'}: {obj.title[:60]}")
            except Exception as exc:
                error = str(exc)
                print(f"[Twitter] Error tweeting '{art.get('title', '')}': {exc}")

        try:
            session.add(TweetLog(
                article_id=obj.id,
                article_title=obj.title,
                tweet_text=tweet_text,
                success=success,
                error=error,
                tweet_key=obj.id if success else None,
            ))
            await session.flush()
        except IntegrityError:
            await session.rollback()
            print(f"[Twitter] Duplicate prevented (race condition): {obj.title[:60]}")
            continue

    await session.commit()


async def run_pipeline():
    from backend.collectors import rss_collector, newsapi_collector
    from backend.processors.classifier import classify_batch
    from backend.processors.writer import write_article

    ran_at = datetime.now(timezone.utc)
    print(f"[Pipeline] Starting collection run at {ran_at.isoformat()}")

    fetched = 0
    accepted_count = 0
    rejected_count = 0
    error_msg = None

    try:
        # 1. Collect from all sources
        rss_articles = await rss_collector.collect_all()
        if os.getenv("DISABLE_NEWSAPI", "").lower() in ("1", "true", "yes"):
            newsapi_articles = []
            print("[Pipeline] NewsAPI disabled via DISABLE_NEWSAPI env var")
        else:
            newsapi_articles = await newsapi_collector.collect_all()
        all_raw = rss_articles + newsapi_articles
        fetched = len(all_raw)
        print(f"[Pipeline] Collected {fetched} raw articles")

        if not all_raw:
            print("[Pipeline] No articles collected — skipping curation.")
        else:
            unique_raw = []
            seen_raw_urls = set()
            for art in all_raw:
                url = art.get("url")
                if not url or url in seen_raw_urls:
                    continue
                seen_raw_urls.add(url)
                unique_raw.append(art)
            duplicate_count = len(all_raw) - len(unique_raw)
            if duplicate_count:
                print(f"[Pipeline] Removed {duplicate_count} duplicate URLs from this run")

            # 2. Filter out already-stored URLs
            async with SessionLocal() as session:
                urls = [a["url"] for a in unique_raw]
                existing = await session.execute(select(Article.url).where(Article.url.in_(urls)))
                existing_urls = {row[0] for row in existing.fetchall()}
                evaluated = await session.execute(select(CurationRecord.url).where(CurationRecord.url.in_(urls)))
                db_evaluated_urls = {row[0] for row in evaluated.fetchall()}

            already_seen_urls = existing_urls | db_evaluated_urls
            new_articles = [a for a in unique_raw if a["url"] not in already_seen_urls]
            skipped_count = len(unique_raw) - len(new_articles)
            if skipped_count:
                print(f"[Pipeline] Skipped {skipped_count} previously stored/curated articles")
            print(f"[Pipeline] {len(new_articles)} new articles to classify")

            if new_articles:
                # 3a. Classify — score, category, severity, tags
                classified, evaluated_urls = await classify_batch(new_articles)
                accepted_urls_set = {art["url"] for art in classified}
                rejected_count = len(evaluated_urls - accepted_urls_set)
                print(f"[Pipeline] Classified: {len(classified)} accepted, {rejected_count} rejected")

                # 3b. Write summaries + tweets for accepted articles
                if classified:
                    write_sem = asyncio.Semaphore(3)

                    async def _write_one(art):
                        async with write_sem:
                            return await write_article(art)

                    accepted = list(await asyncio.gather(*[_write_one(art) for art in classified]))
                else:
                    accepted = []

                accepted_count = len(accepted)

                # 4. Store accepted articles; record rejected URLs so they aren't re-evaluated
                if evaluated_urls:
                    articles_by_url = {art["url"]: art for art in new_articles}
                    accepted_by_url = {art["url"]: art for art in accepted}
                    async with SessionLocal() as session:
                        featured_pairs: list[tuple] = []
                        for art in accepted:
                            is_featured = art.get("relevance_score", 0.0) >= 0.90
                            obj = Article(
                                url=art["url"],
                                title=art["title"],
                                description=art.get("description", ""),
                                content=art.get("content", ""),
                                source_name=art.get("source_name", ""),
                                source_country=art.get("source_country", ""),
                                author=art.get("author", ""),
                                published_at=art.get("published_at"),
                                collected_at=ran_at,
                                relevance_score=art.get("relevance_score", 0.0),
                                category=art.get("category", ""),
                                tags=art.get("tags", []),
                                ai_summary=art.get("ai_summary", ""),
                                severity=art.get("severity", "low"),
                                image_url=art.get("image_url", ""),
                                featured=is_featured,
                            )
                            session.add(obj)
                            if is_featured:
                                featured_pairs.append((obj, art))
                        await session.flush()
                        for url in evaluated_urls:
                            art = accepted_by_url.get(url) or articles_by_url[url]
                            status = "accepted" if url in accepted_urls_set else "rejected"
                            session.add(CurationRecord(
                                url=url,
                                title=art.get("title", ""),
                                source_name=art.get("source_name", ""),
                                status=status,
                                relevance_score=art.get("relevance_score"),
                                category=art.get("category"),
                                evaluated_at=ran_at,
                            ))
                        await session.commit()

                        if featured_pairs:
                            async with SessionLocal() as tweet_session:
                                await _tweet_featured(tweet_session, featured_pairs)

    except Exception as exc:
        error_msg = str(exc)
        print(f"[Pipeline] ERROR: {error_msg}")

    # DB cleanup
    retention_days = int(os.getenv("ARTICLE_RETENTION_DAYS", "0"))
    if retention_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        async with SessionLocal() as session:
            result = await session.execute(
                delete(Article).where(Article.collected_at < cutoff)
            )
            pruned = result.rowcount
            await session.commit()
        if pruned:
            print(f"[Pipeline] Pruned {pruned} articles older than {retention_days} days.")

    async with SessionLocal() as session:
        session.add(CollectionLog(
            ran_at=ran_at,
            source="pipeline",
            articles_fetched=fetched,
            articles_accepted=accepted_count,
            articles_rejected=rejected_count,
            error=error_msg,
        ))
        await session.commit()

    print(f"[Pipeline] Done. Stored {accepted_count} articles.")


def create_scheduler() -> AsyncIOScheduler:
    from backend.notifications.newsletter import send_newsletters

    interval_minutes = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "60"))
    disable_startup = os.getenv("DISABLE_PIPELINE_ON_STARTUP", "false").lower() in ("true", "1", "yes")
    scheduler = AsyncIOScheduler()

    first_run = None if disable_startup else datetime.now(timezone.utc)

    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="collection_pipeline",
        name="News Collection Pipeline",
        replace_existing=True,
        next_run_time=first_run,
    )
    scheduler.add_job(
        send_newsletters,
        args=["daily"],
        trigger=CronTrigger(hour=7, minute=0, timezone="UTC"),
        id="newsletter_daily",
        name="Daily Newsletter",
        replace_existing=True,
    )
    scheduler.add_job(
        send_newsletters,
        args=["weekly"],
        trigger=CronTrigger(day_of_week="mon", hour=7, minute=0, timezone="UTC"),
        id="newsletter_weekly",
        name="Weekly Newsletter",
        replace_existing=True,
    )

    return scheduler
