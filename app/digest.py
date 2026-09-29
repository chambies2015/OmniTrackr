"""Opt-in weekly "Coming up for you" email.

Sized for Mailgun's free plan (100 emails a day, shared with verification and
password-reset mail): at most DIGEST_DAILY_LIMIT digests (default 50) go out
in any 24 hours, each subscriber gets at most one a week, and nothing is sent
when there is nothing worth sending. Runs inside the web process: a light
check every hour while the app is awake, so no paid cron job is needed.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from datetime import date, datetime, timedelta
from html import escape

from sqlalchemy.orm import Session

from . import models
from . import release_radar as radar
from .for_you import coming_up

SEND_EVERY = timedelta(days=7) - timedelta(hours=1)
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 180


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("DIGEST_DAILY_LIMIT", "50")))
    except ValueError:
        return 50


def app_url() -> str:
    return (os.getenv("APP_URL") or os.getenv("SITE_URL") or "https://omnitrackr.xyz").rstrip("/")


def mail_configured() -> bool:
    from .email import conf
    return bool(conf.MAIL_USERNAME and conf.MAIL_PASSWORD)


def enabled_for_process() -> bool:
    setting = os.getenv("DIGEST_EMAILS", "").strip().lower()
    if setting in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


# ---------------------------------------------------------------- subscriptions

def subscription_for(db: Session, user_id: int):
    return db.query(models.EmailDigestSubscription).filter_by(user_id=user_id).first()


def subscribe(db: Session, user_id: int):
    existing = subscription_for(db, user_id)
    if existing:
        return existing
    row = models.EmailDigestSubscription(user_id=user_id, token=secrets.token_urlsafe(32))
    db.add(row)
    db.commit()
    return row


def unsubscribe_user(db: Session, user_id: int) -> bool:
    removed = db.query(models.EmailDigestSubscription).filter_by(user_id=user_id).delete()
    db.commit()
    return bool(removed)


def unsubscribe_token(db: Session, token: str) -> bool:
    if not token or len(token) > 64:
        return False
    removed = db.query(models.EmailDigestSubscription).filter_by(token=token).delete()
    db.commit()
    return bool(removed)


# ---------------------------------------------------------------- email content

def _day(iso: str | None) -> str:
    if not iso:
        return "Date to be announced"
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return "Date to be announced"
    return day.strftime("%a %b ") + str(day.day)


def _rows(cards: list[dict], base: str) -> str:
    rows = []
    for card in cards:
        link = escape(base + card["url"], quote=True)
        reason = f'<div style="color:#6d28d9;font-size:13px;margin-top:2px">{escape(card["reason"])}</div>' if card.get("reason") else ""
        rows.append(
            '<tr><td style="padding:10px 0;border-top:1px solid #e9e5f5">'
            f'<a href="{link}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">{escape(card["title"])}</a>'
            f'<div style="color:#5b5675;font-size:13px">{escape(card["label"])} · {escape(_day(card.get("date")))}</div>{reason}'
            '</td></tr>'
        )
    return "".join(rows)


def build_digest(username: str, report: dict, unsubscribe_url: str) -> tuple[str, str, str] | None:
    """(subject, html, text) or None when there is nothing to send."""
    matches, popular = report["matches"], report["popular"]
    if not matches and not popular:
        return None
    base = app_url()
    if matches:
        subject = f"Coming up for you: {matches[0]['title']}" + (f" and {len(matches) - 1} more" if len(matches) > 1 else "")
    else:
        subject = f"This week on Release Radar: {popular[0]['title']} and more"
    sections = []
    text = [f"Hi {username},", ""]
    if matches:
        sections.append('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">From your library</h2>'
                        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{_rows(matches, base)}</table>')
        text.append("From your library:")
        text += [f"- {c['title']} ({c['label']}, {_day(c.get('date'))}) - {c['reason']}" for c in matches]
        text.append("")
    if popular:
        sections.append('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">Popular this month</h2>'
                        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{_rows(popular[:5], base)}</table>')
        text.append("Popular this month:")
        text += [f"- {c['title']} ({c['label']}, {_day(c.get('date'))})" for c in popular[:5]]
        text.append("")
    text += [f"See everything: {base}/release-radar", "",
             "You get this because you turned on the weekly email in OmniTrackr.",
             f"Unsubscribe with one click: {unsubscribe_url}"]
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">OmniTrackr weekly</div>'
        '<div style="font-size:22px;font-weight:700;margin-top:6px">Coming up for you</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        f'<p style="color:#1f1640;font-size:15px">Hi {escape(username)}, here is what is on the way.</p>'
        + "".join(sections) +
        f'<p style="margin:26px 0 8px"><a href="{escape(base, quote=True)}/release-radar" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Open Release Radar</a></p>'
        '<p style="color:#8a86a3;font-size:12px;margin-top:24px">You get this because you turned on the weekly email in OmniTrackr. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe</a> any time with one click.</p>'
        '</div></div></body></html>'
    )
    return subject, html, "\n".join(text)


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from fastapi_mail import FastMail, MessageSchema, MessageType
    from .email import conf
    message = MessageSchema(
        subject=subject, recipients=[to], body=html, subtype=MessageType.html,
        headers={
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )
    await asyncio.wait_for(FastMail(conf).send_message(message), timeout=30.0)


# ---------------------------------------------------------------- scheduler

async def send_due_digests(session_factory, client=None, now: datetime | None = None, sender=_send,
                           today: date | None = None) -> dict:
    """Send every digest that is due, within the daily limit. Returns counters."""
    now = now or datetime.utcnow()
    stats = {"sent": 0, "skipped": 0, "failed": 0, "limited": 0}
    if not mail_configured() and sender is _send:
        return stats
    db = session_factory()
    try:
        sent_today = db.query(models.EmailDigestSubscription).filter(
            models.EmailDigestSubscription.last_sent_at >= now - timedelta(hours=24)
        ).count()
        allowance = daily_limit() - sent_today
        due = db.query(models.EmailDigestSubscription).filter(
            (models.EmailDigestSubscription.last_checked_at.is_(None))
            | (models.EmailDigestSubscription.last_checked_at <= now - SEND_EVERY)
        ).order_by(models.EmailDigestSubscription.last_checked_at.asc().nullsfirst(),
                   models.EmailDigestSubscription.id).all()
        pool = None
        for subscription in due:
            if allowance <= 0:
                stats["limited"] += 1
                continue
            user = db.query(models.User).filter_by(id=subscription.user_id).first()
            subscription.last_checked_at = now
            db.commit()  # Mark first so an overlapping run can never send twice.
            if user is None or not user.is_active or not user.is_verified or not user.email:
                stats["skipped"] += 1
                continue
            if pool is None:
                from .for_you import radar_pool
                pool = radar_pool(today, client)
            report = coming_up(db, user.id, today=today, pool=pool)
            unsubscribe_url = f"{app_url()}/email/unsubscribe?token={subscription.token}"
            built = build_digest(user.username, report, unsubscribe_url)
            if built is None:
                stats["skipped"] += 1
                continue
            subject, html, _text = built
            try:
                await sender(user.email, subject, html, unsubscribe_url)
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Weekly email to user {user.id} failed: {error}")
                stats["failed"] += 1
                continue
            subscription.last_sent_at = now
            db.commit()
            allowance -= 1
            stats["sent"] += 1
        return stats
    finally:
        db.close()


async def digest_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            client = getattr(app.state, "external_api_client", None)
            if client is not None:
                today = radar.today_utc()
                for category in radar.CATEGORY_ORDER:
                    for window in radar.allowed_windows(category, today)[1:3]:
                        try:
                            await radar.CACHE.get(client, window, wait=20)
                        except Exception:
                            pass
            stats = await send_due_digests(SessionLocal, client)
            if stats["sent"] or stats["failed"]:
                print(f"Weekly emails: {stats}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Weekly email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
