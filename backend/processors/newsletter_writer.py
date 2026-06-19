"""Write newsletter subject line and intro paragraph using Claude Haiku."""
import asyncio
import json
import os
import sys

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

_PROMPT = """Write a newsletter digest intro for Sex Health News readers covering {period}'s top stories.

Articles:
{articles}

Create a subject line that makes people actually want to open this email (not spammy, just honest).
Then write 2-3 sentences that contextualize these stories and explain why they matter right now.

Respond with JSON only — no markdown fences:
{{
  "subject": "<subject line: 8-60 chars, no clickbait>",
  "intro": "<2-3 sentences: plain language, real context, why this matters to readers>"
}}"""

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


def _call_sync(articles: list[dict], frequency: str) -> tuple[dict, int]:
    period = "today" if frequency == "daily" else "this week"
    lines = []
    for i, a in enumerate(articles, 1):
        summary = a.get("ai_summary", "")
        summary_snippet = f" — {summary[:120]}" if summary else ""
        lines.append(f"{i}. [{a['category']}] {a['title']} ({a['source_name']}){summary_snippet}")

    prompt = _PROMPT.format(period=period, articles="\n".join(lines))
    resp = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip().rstrip("```").strip()
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    return json.loads(text), tokens


async def write_newsletter(articles: list[dict], frequency: str) -> dict:
    loop = asyncio.get_running_loop()
    result, tokens = await loop.run_in_executor(None, _call_sync, articles, frequency)
    from backend.usage import record
    await record("anthropic", calls=1, tokens=tokens)
    return result
