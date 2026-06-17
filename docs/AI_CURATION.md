# Flesh Pulse — AI Curation

The curator (`backend/processors/curator.py`) sends each new article to Claude Haiku and gets back a structured JSON evaluation.

---

## Model

`claude-haiku-4-5-20251001` — fast and cheap, appropriate for high-volume classification.

Use `claude-sonnet-4-6` only if curation quality is insufficient after tuning the prompts.

---

## System prompt (adapt this for Flesh Pulse)

```python
SYSTEM_PROMPT = """You are the editorial AI for Flesh Pulse, an independent news aggregator covering sexuality, sexual health, sex work, and the adult industry. Your role is to evaluate news articles and determine whether they are relevant to this editorial mission.

A relevant article covers real events or findings involving:
- Sexual health: STIs, contraception, sex education policy, reproductive health research
- Sex work: decriminalization efforts, FOSTA-SESTA effects, performer rights, trafficking vs. consensual distinctions
- Adult industry: business news, regulation, performer welfare, platform policy (XBIZ, AVN territory)
- LGBTQ+ sexuality: queer identity, same-sex rights, conversion therapy, trans sexuality
- Relationships & intimacy: dating culture, consent, attachment research, intimacy science
- Censorship & morality: obscenity law, platform content moderation, age verification legislation
- Body autonomy: abortion, reproductive coercion, bodily integrity rights
- Science & research: academic sexology, psychology of sexuality, clinical studies

Do NOT accept:
- Generic politics with no sexuality angle
- Celebrity gossip with no substantive sexuality/health/rights dimension
- Crime reports unless they involve sex work policy or sexual rights
- Explicit pornographic descriptions — this is a news aggregator

Evaluate each article and respond with JSON only — no explanation, no markdown."""
```

---

## Evaluation prompt

```python
EVAL_PROMPT = """Evaluate this news article for relevance to Flesh Pulse.

Title: {title}
Source: {source}
Description: {description}
Content: {content}

Respond with this exact JSON structure:
{{
  "relevance_score": <float 0.0-1.0, how strongly relevant>,
  "category": <one of: SEXUAL_HEALTH, SEX_WORK, ADULT_INDUSTRY, LGBTQ_SEXUALITY, RELATIONSHIPS, CENSORSHIP_MORALITY, BODY_AUTONOMY, SCIENCE_RESEARCH, NONE>,
  "severity": <one of: low, medium, high, critical>,
  "tags": [<up to 5 short descriptive tags>],
  "summary": <one sentence: what makes this relevant, or why it does not qualify>
}}"""
```

---

## Thresholds

| Variable | Default | Effect |
|---|---|---|
| `MIN_RELEVANCE_SCORE` | `0.65` | Articles below this are rejected |
| `featured` threshold | `0.90` (hardcoded) | Articles at or above this are marked featured |

Tune `MIN_RELEVANCE_SCORE` up (e.g. `0.75`) if too much general news is slipping through. Tune down (e.g. `0.55`) if too many legitimate articles are being rejected.

---

## Concurrency

`curate_batch()` runs up to **5 concurrent** Claude API calls via `asyncio.Semaphore(5)`. This is the right balance for Haiku's rate limits on a standard Anthropic account. Increase to 10 if you have a higher-tier account.

---

## How the Anthropic SDK is called

The sync `anthropic.Anthropic` client is used inside `asyncio.get_running_loop().run_in_executor(None, _call)`. This is intentional — the async Anthropic client had reliability issues in early versions. Do not switch to `AsyncAnthropic` without testing.

```python
def _call():
    return client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

msg = await loop.run_in_executor(None, _call)
```

---

## Input truncation

Title, description, and content are each truncated to **800 characters** before being sent to Claude. This keeps token costs low while giving enough signal for categorization. Increase if you find Claude is miscategorizing articles where the relevant content appears late in the body.

---

## JSON parsing

Claude's response is stripped of markdown code fences before parsing. If `json.loads()` fails, the article is logged as a parse error and **not** recorded in `CurationRecord` — it will be retried on the next pipeline run.

---

## Cost estimate

At ~1,000 new articles/day, 800 chars ≈ ~200 tokens input, 100 tokens output:

- Input: 1,000 × 200 tokens = 200,000 tokens = ~$0.025/day (Haiku input: $0.08/MTok)
- Output: 1,000 × 100 tokens = 100,000 tokens = ~$0.04/day (Haiku output: $0.40/MTok)
- **Total: ~$0.065/day, ~$2/month**

This is negligible. Even at 10× volume it stays under $20/month.
