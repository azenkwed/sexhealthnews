"""API usage recording — daily aggregates per provider."""
import os
from datetime import datetime, timezone

SERVICE_META = {
    "groq":      {"label": "Groq",        "limit_note": "6,000 req/day · 14,400 tok/min (free tier)"},
    "together":  {"label": "Together AI", "limit_note": "varies by plan"},
    "fireworks": {"label": "Fireworks AI","limit_note": "varies by plan"},
    "anthropic": {"label": "Anthropic",   "limit_note": "paid per token"},
}
SERVICE_ORDER = ["groq", "together", "fireworks", "anthropic"]

_DAILY_LIMITS: dict[str, int | None] = {
    "groq":      6000,
    "together":  None,
    "fireworks": None,
    "anthropic": None,
}


async def record(service: str, calls: int = 1, tokens: int = 0) -> None:
    """Upsert daily usage for service; send alert email if threshold is crossed."""
    from backend.database.db import SessionLocal
    from backend.database.models import ApiUsageStat
    from sqlalchemy import select

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    threshold = float(os.getenv("API_USAGE_ALERT_THRESHOLD", "0.8"))

    try:
        async with SessionLocal() as session:
            stat = (await session.execute(
                select(ApiUsageStat).where(
                    ApiUsageStat.service == service,
                    ApiUsageStat.date == today,
                )
            )).scalar_one_or_none()

            if stat:
                stat.call_count += calls
                stat.token_count += tokens
            else:
                stat = ApiUsageStat(
                    service=service, date=today,
                    call_count=calls, token_count=tokens,
                )
                session.add(stat)

            await session.flush()

            limit = _DAILY_LIMITS.get(service)
            if limit and not stat.alert_sent and stat.call_count >= int(limit * threshold):
                stat.alert_sent = True
                await session.commit()
                await _send_alert(service, stat.call_count, limit, threshold)
                return

            await session.commit()
    except Exception as exc:
        print(f"[Usage] Failed to record {service}: {exc}")


async def _send_alert(service: str, count: int, limit: int, threshold: float) -> None:
    from backend.notifications.email import _send

    label = SERVICE_META.get(service, {}).get("label", service)
    pct = int(threshold * 100)
    recipient = os.getenv("ALERT_EMAIL") or os.getenv("CONTACT_EMAIL", "")
    if not recipient:
        return

    subject = f"[Sex Health News] {label} API alert — {count}/{limit} requests today"
    body = (
        f"<p>The <strong>{label}</strong> API has reached {pct}% of its daily limit.</p>"
        f"<p><strong>Today's requests:</strong> {count} / {limit}</p>"
        f"<p>Check the admin API Usage dashboard for details.</p>"
    )
    _send(recipient, subject, body)
    print(f"[Usage] Alert sent for {service} ({count}/{limit} req today)")
