"""Shared fixtures for the Sex Health News test suite."""
import os

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/sexhealthnews_test",
)

# Set required env vars before any app import
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key-not-real")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-testing-only")
os.environ["DATABASE_URL"] = TEST_DB_URL

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.models import Article, Base, SavedArticle, User
from backend.auth.utils import hash_password


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # FTS setup — mirrors init_db()
        await conn.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS search_vector tsvector"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_articles_search ON articles USING GIN(search_vector)"
        ))
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_articles_search_vector()
            RETURNS TRIGGER AS $$
            BEGIN
              NEW.search_vector := to_tsvector('english',
                coalesce(NEW.title, '') || ' ' ||
                coalesce(NEW.description, '') || ' ' ||
                coalesce(NEW.ai_summary, '') || ' ' ||
                coalesce(NEW.tags::text, '')
              );
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        await conn.execute(text("""
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_trigger WHERE tgname = 'articles_search_vector_update'
              ) THEN
                CREATE TRIGGER articles_search_vector_update
                  BEFORE INSERT OR UPDATE ON articles
                  FOR EACH ROW EXECUTE FUNCTION update_articles_search_vector();
              END IF;
            END $$;
        """))
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        # Roll back after each test to keep tests isolated
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    mock_scheduler = MagicMock()
    mock_scheduler.start = MagicMock()
    mock_scheduler.shutdown = MagicMock()

    with patch("backend.database.db.init_db", new_callable=AsyncMock), \
         patch("backend.scheduler.create_scheduler", return_value=mock_scheduler):
        from main import app
        from backend.database.db import get_db
        app.dependency_overrides[get_db] = _override_get_db
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as ac:
            yield ac
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_article(db):
    article = Article(
        url="https://example.com/article/sexual-health-test",
        title="New Sexual Health Policy Expands Access",
        description="Federal policy expands access to contraception and STI testing.",
        content="Full content about the new policy.",
        source_name="Rewire News Group",
        source_country="US",
        author="Test Author",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        relevance_score=0.85,
        category="Sexual Health & Education",
        severity="high",
        tags=["sexual health", "policy", "contraception"],
        ai_summary="Federal policy expands sexual health access.",
        featured=False,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


@pytest_asyncio.fixture
async def featured_article(db):
    article = Article(
        url="https://example.com/article/featured",
        title="Critical: Age Verification Law Passed",
        description="Major age verification legislation signed into law.",
        content="Content about the new law.",
        source_name="EFF",
        source_country="US",
        author="Journalist",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        relevance_score=0.95,
        category="Censorship & Morality",
        severity="critical",
        tags=["age verification", "censorship", "legislation"],
        ai_summary="Age verification law signed, affecting adult content sites.",
        featured=True,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


@pytest_asyncio.fixture
async def verified_user(db):
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword123"),
        display_name="Test User",
        email_verified=True,
        newsletter_frequency="weekly",
        categories=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_client(client, verified_user):
    """Authenticated client with a valid session cookie."""
    resp = await client.post("/login", data={
        "email": "test@example.com",
        "password": "testpassword123",
    })
    assert resp.status_code in (302, 303), f"Login failed: {resp.status_code}"
    return client


@pytest.fixture(autouse=True)
def clear_module_state():
    """Reset in-process rate limiters and caches between tests."""
    yield
    import backend.auth.routes as auth_r
    import backend.routes as routes_r
    auth_r._rl_store.clear()
    routes_r._search_rl.clear()
    routes_r._stats_cache.clear()
    import backend.processors.classifier as classifier_m
    classifier_m._PROVIDERS = None
