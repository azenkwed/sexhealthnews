from datetime import datetime, timezone
from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), unique=True, nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text)
    content = Column(Text)
    source_name = Column(String(256))
    source_country = Column(String(64))
    author = Column(String(256))
    published_at = Column(DateTime(timezone=True))
    collected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # AI curation fields
    relevance_score = Column(Float, default=0.0)
    category = Column(String(128))
    tags = Column(JSONB, default=list)      # array of tag strings
    ai_summary = Column(Text)
    severity = Column(String(32))           # low / medium / high / critical

    # Display
    featured = Column(Boolean, default=False)
    image_url = Column(String(2048))

    # Full-text search — populated by DB trigger in init_db(), not written by app code
    search_vector = Column(TSVECTOR)

    __table_args__ = (
        Index("idx_category", "category"),
        Index("idx_published_at", "published_at"),
        Index("idx_relevance_score", "relevance_score"),
        Index("idx_collected_at", "collected_at"),
        Index("idx_tags_gin", "tags", postgresql_using="gin"),
    )


class SavedArticle(Base):
    __tablename__ = "saved_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_saved_user_article", "user_id", "article_id", unique=True),
        Index("idx_saved_created_at", "created_at"),
    )


class CurationRecord(Base):
    __tablename__ = "curation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), unique=True, nullable=False)
    title = Column(String(512))
    source_name = Column(String(256))
    status = Column(String(32), nullable=False)  # accepted / rejected
    relevance_score = Column(Float)
    category = Column(String(128))
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_curation_url", "url"),
        Index("idx_curation_status", "status"),
        Index("idx_curation_evaluated_at", "evaluated_at"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(256), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(128))
    email_verified = Column(Boolean, default=False)
    newsletter_frequency = Column(String(16), default="weekly")  # daily / weekly / never
    categories = Column(JSONB, default=list)                     # array of selected category display names
    password_reset_token_version = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_user_email", "email"),
    )


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(32), nullable=False)           # google / linkedin / microsoft
    provider_user_id = Column(String(256), nullable=False)
    provider_email = Column(String(256))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_oauth_provider_uid", "provider", "provider_user_id", unique=True),
    )


class CollectionLog(Base):
    __tablename__ = "collection_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ran_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source = Column(String(256))
    articles_fetched = Column(Integer, default=0)
    articles_accepted = Column(Integer, default=0)
    articles_rejected = Column(Integer, default=0)
    error = Column(Text)


class NewsletterLog(Base):
    __tablename__ = "newsletter_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    frequency = Column(String(16), nullable=False)   # daily / weekly
    period_key = Column(String(16), nullable=False)  # "2026-06-17" or "2026-W24"
    subject = Column(String(256))
    article_count = Column(Integer, default=0)
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_newsletter_log_dedup", "user_id", "frequency", "period_key", unique=True),
    )


class ApiUsageStat(Base):
    __tablename__ = "api_usage_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String(64), nullable=False)
    date = Column(String(16), nullable=False)      # YYYY-MM-DD UTC
    call_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    alert_sent = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_api_usage_service_date", "service", "date", unique=True),
    )


class TweetLog(Base):
    __tablename__ = "tweet_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    article_title = Column(String(512))
    tweet_text = Column(Text)
    success = Column(Boolean, default=False)
    error = Column(Text)
    tweeted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    tweet_key = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_tweet_log_article", "article_id"),
        Index("idx_tweet_log_tweeted_at", "tweeted_at"),
        Index("idx_tweet_log_dedup", "tweet_key", unique=True),
    )
