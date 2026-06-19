"""Tests for the classification pipeline: dedup logic, classifier scoring, and category mapping."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Deduplication logic (pure Python, no DB needed)
# ---------------------------------------------------------------------------

def test_dedup_removes_duplicate_urls():
    articles = [
        {"url": "https://example.com/1", "title": "A"},
        {"url": "https://example.com/2", "title": "B"},
        {"url": "https://example.com/1", "title": "A (duplicate)"},
    ]
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    assert len(unique) == 2
    assert unique[0]["url"] == "https://example.com/1"
    assert unique[1]["url"] == "https://example.com/2"


def test_dedup_filters_already_stored_urls():
    new_batch = [
        {"url": "https://example.com/1"},
        {"url": "https://example.com/2"},
        {"url": "https://example.com/3"},
    ]
    existing_urls = {"https://example.com/2"}
    to_evaluate = [a for a in new_batch if a["url"] not in existing_urls]
    assert len(to_evaluate) == 2
    urls = {a["url"] for a in to_evaluate}
    assert "https://example.com/2" not in urls


def test_dedup_empty_batch():
    articles: list = []
    seen: set = set()
    unique = [a for a in articles if a["url"] not in seen and not seen.add(a["url"])]  # type: ignore[func-returns-value]
    assert unique == []


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

def test_category_keys_map_to_display_names():
    from backend.processors.classifier import CATEGORIES
    assert CATEGORIES["SEXUAL_HEALTH"] == "Sexual Health & Wellness"
    assert CATEGORIES["SEX_WORKERS_INDUSTRY"] == "Sex Workers & Adult Industry"
    assert CATEGORIES["LGBTQ_RIGHTS"] == "LGBTQ+ Rights & Issues"
    assert CATEGORIES["NONE"] == "Not Relevant"


def test_all_categories_are_strings():
    from backend.processors.classifier import CATEGORIES
    for key, value in CATEGORIES.items():
        assert isinstance(key, str)
        assert isinstance(value, str)


def test_category_keys_are_uppercase():
    from backend.processors.classifier import CATEGORIES
    for key in CATEGORIES:
        assert key == key.upper()


# ---------------------------------------------------------------------------
# classify_article — mocked OpenAI-compatible client
# ---------------------------------------------------------------------------

_ARTICLE = {
    "url": "https://example.com/test",
    "title": "New HIV Prevention Study Shows Promising Results",
    "description": "Researchers report high efficacy in new PrEP regimen.",
    "content": "Full article content about HIV prevention research.",
    "source_name": "Test Source",
    "source_country": "US",
    "author": "Test Author",
    "published_at": None,
    "image_url": "",
}


def _mock_providers(response_json: str) -> list:
    """Build a mock (client, model, service) provider list with an OpenAI-compatible interface."""
    choice = MagicMock()
    choice.message.content = response_json
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage.total_tokens = 100
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return [(client, "llama-3.3-70b-versatile", "groq")]


async def test_classify_article_accepts_high_score():
    from backend.processors.classifier import classify_article

    providers = _mock_providers(
        '{"relevance_score": 0.87, "category": "INFECTIOUS_DISEASES", '
        '"severity": "high", "tags": ["HIV", "PrEP"]}'
    )
    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        result, evaluated = await classify_article(_ARTICLE)

    assert evaluated is True
    assert result is not None
    assert result["relevance_score"] == 0.87
    assert result["category"] == "Infectious Diseases & STIs"
    assert result["severity"] == "high"
    assert "ai_summary" not in result  # classifier does not write summaries


async def test_classify_article_rejects_low_score():
    from backend.processors.classifier import classify_article

    providers = _mock_providers(
        '{"relevance_score": 0.4, "category": "INFECTIOUS_DISEASES", '
        '"severity": "low", "tags": []}'
    )
    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        result, evaluated = await classify_article(_ARTICLE)

    assert evaluated is True
    assert result is None


async def test_classify_article_rejects_none_category():
    from backend.processors.classifier import classify_article

    providers = _mock_providers(
        '{"relevance_score": 0.92, "category": "NONE", '
        '"severity": "low", "tags": []}'
    )
    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        result, evaluated = await classify_article(_ARTICLE)

    assert evaluated is True
    assert result is None


async def test_classify_article_featured_threshold():
    """Articles at or above 0.90 should be accepted with score >= 0.90."""
    from backend.processors.classifier import classify_article

    providers = _mock_providers(
        '{"relevance_score": 0.95, "category": "REPRODUCTIVE_HEALTH", '
        '"severity": "critical", "tags": ["abortion", "policy"]}'
    )
    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        result, evaluated = await classify_article(_ARTICLE)

    assert evaluated is True
    assert result is not None
    assert result["relevance_score"] >= 0.90


async def test_classify_article_handles_json_parse_error():
    """A JSON parse error means all providers failed — article not evaluated, retried later."""
    from backend.processors.classifier import classify_article

    providers = _mock_providers("not valid json at all")
    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        result, evaluated = await classify_article(_ARTICLE)

    assert result is None
    assert evaluated is False


async def test_classify_article_falls_back_on_rate_limit():
    """Rate limit on first provider triggers fallback to the second."""
    from backend.processors.classifier import classify_article
    from openai import RateLimitError

    # Provider 1 raises rate limit; provider 2 succeeds
    choice = MagicMock()
    choice.message.content = '{"relevance_score": 0.8, "category": "SEXUAL_HEALTH", "severity": "medium", "tags": []}'
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage.total_tokens = 80

    groq_client = MagicMock()
    groq_client.chat.completions.create.side_effect = RateLimitError(
        message="rate limit", response=MagicMock(status_code=429), body={}
    )
    together_client = MagicMock()
    together_client.chat.completions.create.return_value = completion

    providers = [
        (groq_client, "llama-3.3-70b-versatile", "groq"),
        (together_client, "meta-llama/Llama-3.3-70B-Instruct-Turbo", "together"),
    ]
    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        result, evaluated = await classify_article(_ARTICLE)

    assert evaluated is True
    assert result is not None
    assert result["category"] == "Sexual Health & Wellness"


# ---------------------------------------------------------------------------
# classify_batch
# ---------------------------------------------------------------------------

async def test_classify_batch_returns_accepted_and_evaluated_urls():
    from backend.processors.classifier import classify_batch

    articles = [_ARTICLE.copy()]
    providers = _mock_providers(
        '{"relevance_score": 0.8, "category": "INFECTIOUS_DISEASES", '
        '"severity": "high", "tags": []}'
    )
    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        accepted, evaluated_urls = await classify_batch(articles)

    assert len(accepted) == 1
    assert _ARTICLE["url"] in evaluated_urls


async def test_classify_batch_empty_input():
    from backend.processors.classifier import classify_batch

    accepted, evaluated_urls = await classify_batch([])
    assert accepted == []
    assert evaluated_urls == set()


async def test_classify_batch_mixed_results():
    from backend.processors.classifier import classify_batch

    side_effects = [
        '{"relevance_score": 0.9, "category": "SEXUAL_HEALTH", "severity": "high", "tags": []}',
        '{"relevance_score": 0.3, "category": "NONE", "severity": "low", "tags": []}',
    ]
    call_count = 0

    def _make_completion():
        nonlocal call_count
        choice = MagicMock()
        choice.message.content = side_effects[call_count % len(side_effects)]
        completion = MagicMock()
        completion.choices = [choice]
        completion.usage.total_tokens = 80
        call_count += 1
        return completion

    client = MagicMock()
    client.chat.completions.create.side_effect = lambda **kwargs: _make_completion()
    providers = [(client, "llama-3.3-70b-versatile", "groq")]

    articles = [
        {**_ARTICLE, "url": "https://example.com/a"},
        {**_ARTICLE, "url": "https://example.com/b"},
    ]

    with patch("backend.processors.classifier._get_providers", return_value=providers), \
         patch("backend.usage.record", new_callable=AsyncMock):
        accepted, evaluated_urls = await classify_batch(articles)

    assert len(evaluated_urls) == 2
    assert len(accepted) == 1  # only the 0.9-score article passes
