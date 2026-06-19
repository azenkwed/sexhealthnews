"""Write editorial summaries and tweets using Claude Haiku."""
import asyncio
import json
import os
import sys
from typing import Any

import anthropic
import httpx

_SYSTEM = (
    "You are the editorial voice of Sex Health News, an independent news platform covering sexual health, "
    "reproductive rights, and wellness for people who want facts they can trust.\n\n"
    "Your readers are 18-35, informed, and expect clarity without stigma or judgment. "
    "Write in a conversational, direct tone — like you're explaining something important to a friend. "
    "Be honest about complexity, don't oversimplify, and lead with what matters most.\n\n"
    "Avoid: Corporate speak, unnecessary jargon, preachy language, false urgency. "
    "Embrace: Real language, practical context, nuanced take, actual impact."
)

_PROMPT = """Write an editorial summary for this article.

Title: {title}
Source: {source}
Category: {category}
Severity: {severity}
Tags: {tags}
Description: {description}
Content: {content}

{tweet_instruction}

Respond with JSON only — no markdown fences:
{{
  "summary": "<2-3 sentences with real editorial context — what happened, why it matters, what readers should understand>",
  "tweet": {tweet_field}
}}"""

_TWEET_ON = """Also write a single tweet (under 230 characters — a URL will be appended separately).
Rules: lead with the fact that matters; write like you're telling someone why they should care; no exclamation points, no ALL CAPS, avoid emojis unless genuinely appropriate; end with 1-2 relevant hashtags; no URL."""

_TWEET_OFF = "Do not write a tweet — set tweet to null."

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(
            api_key=key,
            http_client=httpx.Client(verify=sys.platform != "win32"),
        )
    return _client


def _call_sync(article: dict, include_tweet: bool) -> tuple[dict, int]:
    prompt = _PROMPT.format(
        title=article.get("title", ""),
        source=article.get("source_name", ""),
        category=article.get("category", ""),
        severity=article.get("severity", "low"),
        tags=", ".join(article.get("tags", [])),
        description=article.get("description", "")[:800],
        content=article.get("content", "")[:800],
        tweet_instruction=_TWEET_ON if include_tweet else _TWEET_OFF,
        tweet_field='"<tweet under 230 chars>"' if include_tweet else "null",
    )
    resp = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    return json.loads(raw), tokens


async def write_article(article: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich an accepted article with ai_summary and tweet_text.
    tweet_text is only generated for featured articles (relevance_score >= 0.90).
    Returns the original article dict with empty fields on failure (never raises).
    """
    is_featured = float(article.get("relevance_score", 0)) >= 0.90
    try:
        loop = asyncio.get_running_loop()
        result, tokens = await loop.run_in_executor(None, _call_sync, article, is_featured)
        from backend.usage import record
        await record("anthropic", calls=1, tokens=tokens)
        return {
            **article,
            "ai_summary": result.get("summary", ""),
            "tweet_text": result.get("tweet") if is_featured else None,
        }
    except Exception as exc:
        print(f"[Writer] Error for '{article.get('title', '')}': {exc}")
        return {**article, "ai_summary": "", "tweet_text": None}


async def write_tweet(article: dict[str, Any]) -> str:
    """Generate a tweet for an article on demand (used by admin manual send)."""
    try:
        loop = asyncio.get_running_loop()
        result, tokens = await loop.run_in_executor(None, _call_sync, article, True)
        from backend.usage import record
        await record("anthropic", calls=1, tokens=tokens)
        return result.get("tweet") or ""
    except Exception as exc:
        print(f"[Writer] Tweet error for '{article.get('title', '')}': {exc}")
        return ""
