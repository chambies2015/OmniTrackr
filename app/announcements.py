"""One-time "What's new" product update email to verified members.

The site owner previews it and presses Start on the Site stats page; nothing is
sent before that. Sending runs in the web process (a light check every hour)
and stays well inside Mailgun's free plan, which rejects anything past 100
emails a day: at most ANNOUNCEMENT_DAILY_LIMIT (default 30) a day, and never
more than SHARED_DAILY_CAP (default 80) together with the weekly email. That
always leaves room for sign-up verification and password-reset emails.

Every email has a one-click unsubscribe from product updates (account emails
such as password resets are unaffected), and each member gets a campaign once.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from html import escape

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .digest import _day, app_url, mail_configured

CAMPAIGN_KEY = "2026-10-whats-new"
PER_RUN_LIMIT = 10
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 240
UTM = "utm_source=email&utm_campaign=whats-new"


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def daily_limit() -> int:
    return _int_env("ANNOUNCEMENT_DAILY_LIMIT", 30)


def shared_cap() -> int:
    return _int_env("SHARED_DAILY_CAP", 80)


def enabled_for_process() -> bool:
    setting = os.getenv("ANNOUNCEMENT_EMAILS", "").strip().lower()
    if setting in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


# ---------------------------------------------------------------- unsubscribe tokens

def _serializer() -> URLSafeSerializer:
    from .email import SECRET_KEY
    return URLSafeSerializer(SECRET_KEY, salt="product-updates-unsubscribe")


def unsubscribe_token(user_id: int) -> str:
    return _serializer().dumps({"u": int(user_id)})


def user_id_from_token(token: str) -> int | None:
    if not token or len(token) > 200:
        return None
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    uid = data.get("u") if isinstance(data, dict) else None
    return uid if isinstance(uid, int) and not isinstance(uid, bool) else None


def opt_out(db: Session, user_id: int) -> bool:
    if db.query(models.EmailOptOut).filter_by(user_id=user_id).first():
        return False
    db.add(models.EmailOptOut(user_id=user_id))
    db.commit()
    return True


def opted_out(db: Session, user_id: int) -> bool:
    return db.query(models.EmailOptOut.id).filter_by(user_id=user_id).first() is not None


# ---------------------------------------------------------------- campaign state

def campaign(db: Session) -> models.EmailCampaign:
    row = db.query(models.EmailCampaign).filter_by(key=CAMPAIGN_KEY).first()
    if row is None:
        row = models.EmailCampaign(key=CAMPAIGN_KEY, status="draft")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _eligible_query(db: Session):
    from .editorial_collections import EDITOR_USERNAME
    sent = db.query(models.EmailCampaignSend.user_id).filter(
        models.EmailCampaignSend.campaign_key == CAMPAIGN_KEY, models.EmailCampaignSend.status != "test")
    opted = db.query(models.EmailOptOut.user_id)
    return db.query(models.User).filter(
        models.User.is_active == True, models.User.is_verified == True,
        models.User.email.isnot(None), models.User.email != "",
        models.User.username != EDITOR_USERNAME,
        ~models.User.id.in_(sent), ~models.User.id.in_(opted),
    )


def status(db: Session) -> dict:
    row = campaign(db)
    counts = dict(db.query(models.EmailCampaignSend.status, func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key == CAMPAIGN_KEY).group_by(models.EmailCampaignSend.status).all())
    remaining = _eligible_query(db).count()
    return {
        "key": CAMPAIGN_KEY,
        "status": row.status,
        "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
        "finished_at": row.finished_at.isoformat() + "Z" if row.finished_at else None,
        "sent": int(counts.get("sent", 0)),
        "failed": int(counts.get("failed", 0)),
        "remaining": remaining,
        "opted_out": int(db.query(func.count(models.EmailOptOut.id)).scalar() or 0),
        "daily_limit": daily_limit(),
        "mail_configured": mail_configured(),
        "days_to_finish": -(-remaining // daily_limit()) if daily_limit() else None,
    }


def set_status(db: Session, new_status: str) -> models.EmailCampaign:
    row = campaign(db)
    if row.status == "done" and new_status != "done":
        return row
    if new_status == "sending" and row.started_at is None:
        row.started_at = datetime.utcnow()
    row.status = new_status
    db.commit()
    return row


# ---------------------------------------------------------------- content

def _library_count(db: Session, user_id: int) -> int:
    total = 0
    for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book):
        total += int(db.query(func.count(model.id)).filter(model.user_id == user_id).scalar() or 0)
    return total


FEATURES = (
    ("Release Radar", "Every new movie, TV premiere, anime season and game coming out this month, in one place.", "/release-radar"),
    ("Title pages", "Trailers, details, critic scores and member reviews for the movies, shows, games and books you track.", "/titles"),
    ("Quick start", "Popular picks you can add in one click, so a new library takes seconds instead of typing.", "/"),
    ("Public profile (optional)", "Share your favorites and reviews at your own link. Off unless you switch it on.", "/#public-profile"),
    ("A weekly heads-up (optional)", "Turn on the weekly “Coming up for you” email from your dashboard to hear when something you track is coming out.", "/"),
    ("OmniTrackr on your phone", "Open omnitrackr.xyz on your phone and choose Add to Home Screen (or Install app) to keep it one tap away.", "/"),
)


def build_email(username: str, library_count: int, matches: list[dict], unsubscribe_url: str) -> tuple[str, str, str]:
    """(subject, html, text) for one member."""
    base = app_url()

    def link(path: str) -> str:
        joiner = "&" if "?" in path.split("#")[0] else "?"
        if "#" in path:
            head, anchor = path.split("#", 1)
            return f"{base}{head}{joiner}{UTM}#{anchor}"
        return f"{base}{path}{joiner}{UTM}"

    subject = "What's new on OmniTrackr"
    if matches:
        subject += f": {matches[0]['title']} is coming up"
    if library_count:
        library_line = f"Your library has {library_count} title{'s' if library_count != 1 else ''} waiting for you."
    else:
        library_line = "Your library is still empty. Quick start can fill the first five titles in under a minute."

    match_rows = "".join(
        '<tr><td style="padding:10px 0;border-top:1px solid #e9e5f5">'
        f'<a href="{escape(link(card["url"]), quote=True)}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">{escape(card["title"])}</a>'
        f'<div style="color:#5b5675;font-size:13px">{escape(card["label"])} · {escape(_day(card.get("date")))}</div>'
        f'<div style="color:#6d28d9;font-size:13px;margin-top:2px">{escape(card.get("reason") or "")}</div></td></tr>'
        for card in matches[:3]
    )
    matches_html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">Coming up from your library</h2>'
                    f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{match_rows}</table>') if matches else ""
    feature_rows = "".join(
        '<tr><td style="padding:10px 0;border-top:1px solid #e9e5f5">'
        f'<a href="{escape(link(path), quote=True)}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">{escape(title)}</a>'
        f'<div style="color:#5b5675;font-size:14px;line-height:1.5">{escape(text)}</div></td></tr>'
        for title, text, path in FEATURES
    )
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">OmniTrackr update</div>'
        '<div style="font-size:22px;font-weight:700;margin-top:6px">What’s new on OmniTrackr</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">Hi {escape(username)}, OmniTrackr has grown a lot since you signed up. '
        f'Here’s the short version. {escape(library_line)}</p>'
        + matches_html +
        '<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">New since you joined</h2>'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{feature_rows}</table>'
        f'<p style="margin:26px 0 8px"><a href="{escape(link("/"), quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Open my library</a></p>'
        '<p style="color:#8a86a3;font-size:12px;line-height:1.5;margin-top:24px">You’re getting this one-time update because you have an '
        'OmniTrackr account. We don’t send newsletters unless you turn one on. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a> with one click.</p>'
        '</div></div></body></html>'
    )
    text = [f"Hi {username},", "", "OmniTrackr has grown a lot since you signed up. Here's the short version.", library_line, ""]
    if matches:
        text.append("Coming up from your library:")
        text += [f"- {card['title']} ({card['label']}, {_day(card.get('date'))})" for card in matches[:3]]
        text.append("")
    text.append("New since you joined:")
    text += [f"- {title}: {body}" for title, body, _ in FEATURES]
    text += ["", f"Open your library: {link('/')}", "",
             "You're getting this one-time update because you have an OmniTrackr account.",
             f"Unsubscribe from product updates: {unsubscribe_url}"]
    return subject, html, "\n".join(text)


def email_for(db: Session, user: models.User, pool=None) -> tuple[str, str, str, str]:
    """(subject, html, text, unsubscribe_url) for a member."""
    from .for_you import coming_up
    try:
        matches = coming_up(db, user.id, pool=pool)["matches"] if pool is not None else []
    except Exception:
        matches = []
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    subject, html, text = build_email(user.username, _library_count(db, user.id), matches, unsubscribe_url)
    return subject, html, text, unsubscribe_url


# ---------------------------------------------------------------- sending

async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


def allowance(db: Session, now: datetime) -> int:
    """How many may go out right now without crowding out account emails."""
    since = now - timedelta(hours=24)
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_campaign, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


async def send_due(session_factory, client=None, now: datetime | None = None, sender=_send) -> dict:
    now = now or datetime.utcnow()
    stats = {"sent": 0, "failed": 0, "limited": False}
    if not mail_configured() and sender is _send:
        return stats
    db = session_factory()
    try:
        row = campaign(db)
        if row.status != "sending":
            return stats
        budget = allowance(db, now)
        if budget <= 0:
            stats["limited"] = True
            return stats
        users = _eligible_query(db).order_by(models.User.id).limit(budget).all()
        if not users:
            row.status, row.finished_at = "done", now
            db.commit()
            return stats
        pool = None
        try:
            from .for_you import radar_pool
            pool = radar_pool(None, client)
        except Exception:
            pool = None
        for user in users:
            # Claim first so an overlapping run can never send twice.
            claim = models.EmailCampaignSend(campaign_key=CAMPAIGN_KEY, user_id=user.id, status="sent", sent_at=now)
            db.add(claim)
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            subject, html, _text, unsubscribe_url = email_for(db, user, pool)
            try:
                await sender(user.email, subject, html, unsubscribe_url)
                stats["sent"] += 1
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Update email to user {user.id} failed: {error}")
                claim.status = "failed"
                db.commit()
                stats["failed"] += 1
        return stats
    finally:
        db.close()


async def send_test(db: Session, user: models.User, client=None, sender=_send) -> None:
    """Send the email to the owner only (doesn't count them as a recipient of the campaign)."""
    pool = None
    try:
        from .for_you import radar_pool
        pool = radar_pool(None, client)
    except Exception:
        pool = None
    subject, html, _text, unsubscribe_url = email_for(db, user, pool)
    await sender(user.email, "[Test] " + subject, html, unsubscribe_url)


async def announcement_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            stats = await send_due(SessionLocal, getattr(app.state, "external_api_client", None))
            if stats["sent"] or stats["failed"]:
                print(f"Update emails: {stats}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Update email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
