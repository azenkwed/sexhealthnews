"""Classify articles via Llama 3.3 70B — Groq primary, round-robin with Together / Fireworks fallback."""
import asyncio
import itertools
import json
import os
from typing import Any

from openai import OpenAI, RateLimitError

CATEGORIES = {
    "SEXUAL_HEALTH":           "Sexual Health & Wellness",
    "REPRODUCTIVE_HEALTH":     "Reproductive Health & Policy",
    "MATERNAL_CHILD_HEALTH":   "Maternal & Child Health",
    "INFECTIOUS_DISEASES":     "Infectious Diseases & STIs",
    "MENTAL_HEALTH":           "Mental Health & Sexuality",
    "LGBTQ_RIGHTS":            "LGBTQ+ Rights & Issues",
    "SEX_EDUCATION":           "Sex Education & Literacy",
    "SEXUAL_VIOLENCE":         "Sexual Violence & Consent",
    "SEX_WORKERS_INDUSTRY":    "Sex Workers & Adult Industry",
    "NONE":                    "Not Relevant",
}

SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

_SYSTEM = """You are the editorial classifier for Sex Health News, an independent news aggregator covering sexual health, reproductive rights, and wellness. Your role is to evaluate whether an article belongs on the site and assign metadata.

A relevant article covers real events or findings involving:
- Sexual health & wellness: sexual function, satisfaction, menstrual health, fertility, PCOS, endometriosis, sexual health research
- Reproductive health & policy: abortion access, contraception regulation, family planning laws, reproductive medicine
- Maternal & child health: pregnancy care, childbirth, postpartum care, maternal mortality, child sexual health education
- Infectious diseases & STIs: HIV/AIDS, STI testing and treatment, viral infections, prevention strategies
- Mental health & sexuality: body image, anxiety, depression, sexual dysfunction, relationships, sexual psychology
- LGBTQ+ rights & issues: legal rights, discrimination, same-sex marriage, trans healthcare, gender identity
- Sex education & literacy: school curriculum, public awareness campaigns, misinformation debunking
- Sexual violence & consent: assault, harassment, survivor support, consent education
- Sex workers & adult industry: sex work legalization, labor protections, content creators, industry safety

HARD REJECT — score 0.0 regardless of other factors:
- Any content involving minors in a sexual context
- Generic politics, crime, or business news with no sexual health, rights, or wellness angle
- Celebrity gossip with no substantive health, rights, or educational dimension

Respond with JSON only — no explanation, no markdown."""

_PROMPT = """Classify this news article for Sex Health News.

Title: {title}
Source: {source}
Description: {description}
Content: {content}

Respond with this exact JSON:
{{
  "relevance_score": <float 0.0-1.0>,
  "category": <one of: SEXUAL_HEALTH, REPRODUCTIVE_HEALTH, MATERNAL_CHILD_HEALTH, INFECTIOUS_DISEASES, MENTAL_HEALTH, LGBTQ_RIGHTS, SEX_EDUCATION, SEXUAL_VIOLENCE, SEX_WORKERS_INDUSTRY, NONE>,
  "severity": <one of: low, medium, high, critical>,
  "tags": [<up to 5 short descriptive tags>]
}}"""

_PROVIDERS: list | None = None
_counter = itertools.count()


def _get_providers() -> list:
    global _PROVIDERS
    if _PROVIDERS is None:
        clients = []
        if key := os.getenv("GROQ_API_KEY"):
            clients.append((
                OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1"),
                "llama-3.3-70b-versatile",
                "groq",
            ))
        if key := os.getenv("TOGETHER_API_KEY"):
            clients.append((
                OpenAI(api_key=key, base_url="https://api.together.xyz/v1"),
                "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "together",
            ))
        if key := os.getenv("FIREWORKS_API_KEY"):
            clients.append((
                OpenAI(api_key=key, base_url="https://api.fireworks.ai/inference/v1"),
                "accounts/fireworks/models/llama-v3p3-70b-instruct",
                "fireworks",
            ))
        if not clients:
            raise RuntimeError(
                "No classifier API keys set — add GROQ_API_KEY, TOGETHER_API_KEY, or FIREWORKS_API_KEY"
            )
        _PROVIDERS = clients
    return _PROVIDERS


async def classify_article(article: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    """
    Returns (enriched article, True) if accepted, (None, True) if rejected,
    (None, False) if all providers failed (will be retried next run).
    """
    min_score = float(os.getenv("MIN_RELEVANCE_SCORE", "0.65"))
    providers = _get_providers()
    start = next(_counter) % len(providers)

    prompt = _PROMPT.format(
        title=article.get("title", ""),
        source=article.get("source_name", ""),
        description=article.get("description", "")[:800],
        content=article.get("content", "")[:800],
    )

    for offset in range(len(providers)):
        client, model, service = providers[(start + offset) % len(providers)]
        try:
            loop = asyncio.get_running_loop()

            def _call():
                return client.chat.completions.create(
                    model=model,
                    max_tokens=200,
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )

            resp = await loop.run_in_executor(None, _call)
            raw = resp.choices[0].message.content.strip()
            tokens = resp.usage.total_tokens if resp.usage else 0

            from backend.usage import record
            await record(service, calls=1, tokens=tokens)

            result = json.loads(raw)
        except RateLimitError:
            print(f"[Classifier] Rate limit on {service}, trying next provider…")
            continue
        except json.JSONDecodeError as exc:
            print(f"[Classifier] JSON error from {service} for '{article.get('title', '')}': {exc}")
            continue
        except Exception as exc:
            print(f"[Classifier] Error on {service} for '{article.get('title', '')}': {exc}")
            continue

        score = float(result.get("relevance_score", 0.0))
        category_key = result.get("category", "NONE")

        if score < min_score or category_key == "NONE":
            return None, True

        tags = result.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        return {
            **article,
            "relevance_score": score,
            "category": CATEGORIES.get(category_key, category_key),
            "severity": result.get("severity", "low"),
            "tags": tags,
        }, True

    print(f"[Classifier] All providers failed for '{article.get('title', '')}'")
    return None, False


async def classify_batch(articles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str]]:
    """Classify a batch of articles; returns (accepted, evaluated_urls)."""
    semaphore = asyncio.Semaphore(5)
    error_count = 0

    async def _limited(art):
        nonlocal error_count
        async with semaphore:
            try:
                return await classify_article(art)
            except Exception as exc:
                error_count += 1
                print(f"[Classifier] Unexpected error for '{art.get('title', '')}': {exc}")
                return None, False

    results = await asyncio.gather(*[_limited(art) for art in articles])
    accepted = [result for result, evaluated in results if result is not None]
    evaluated_urls = {
        art["url"]
        for art, (result, evaluated) in zip(articles, results)
        if evaluated
    }
    if error_count:
        print(f"[Classifier] {error_count} article(s) failed (not counted as rejections)")
    return accepted, evaluated_urls
