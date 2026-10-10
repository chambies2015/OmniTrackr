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
# Weeks with no news from the member's own library are skipped, except for a short
# "popular this month" round-up at most this often.
ROUNDUP_EVERY = timedelta(days=28) - timedelta(hours=1)
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


# ---------------------------------------------------------------- one-click opt-in links (emails only)

SUBSCRIBE_LINK_MAX_AGE = 60 * 24 * 3600  # links in an email stay valid for 60 days


def _subscribe_serializer():
    from itsdangerous import URLSafeTimedSerializer
    from .email import SECRET_KEY
    return URLSafeTimedSerializer(SECRET_KEY, salt="weekly-email-subscribe")


def subscribe_link_token(user_id: int) -> str:
    """Signed, member-specific link token. Opening it only shows a confirm button."""
    return _subscribe_serializer().dumps({"u": int(user_id)})


def user_id_from_subscribe_token(token: str) -> int | None:
    if not token or len(token) > 300:
        return None
    try:
        data = _subscribe_serializer().loads(token, max_age=SUBSCRIBE_LINK_MAX_AGE)
    except Exception:
        return None
    uid = data.get("u") if isinstance(data, dict) else None
    return uid if isinstance(uid, int) and not isinstance(uid, bool) and uid > 0 else None


def subscribe_link(user_id: int) -> str:
    return f"{app_url()}/email/weekly/subscribe?token={subscribe_link_token(user_id)}"


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


def _spotlight_section(review: dict | None, base: str) -> tuple[str, list[str]]:
    """'Review of the week' block (html, text lines); empty when there is none."""
    if not review:
        return "", []
    text = " ".join((review.get("review") or "").split())
    excerpt = text if len(text) <= 260 else text[:260].rsplit(" ", 1)[0] + "…"
    url = f"{base}/reviews/{int(review['id'])}?category={review['category']}"
    html = (
        '<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">Review of the week</h2>'
        '<div style="border-left:3px solid #7c3aed;padding:2px 0 2px 14px">'
        f'<a href="{escape(url, quote=True)}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">{escape(review.get("title") or "")}</a>'
        f'<div style="color:#3b3557;font-size:14px;line-height:1.6;margin-top:4px">{escape(excerpt)}</div>'
        f'<div style="color:#8a86a3;font-size:13px;margin-top:6px">by {escape(review.get("username") or "a member")} · '
        f'<a href="{escape(url, quote=True)}" style="color:#6d28d9">Read the review</a></div></div>'
    )
    return html, ["Review of the week:", f"{review.get('title')} by {review.get('username')}: {excerpt}", url, ""]


def _ask_section(ask: dict | None, base: str) -> tuple[str, list[str]]:
    """'Ask a friend' block for a title the member finished recently; empty when there is none."""
    if not ask:
        return "", []
    url = f"{base}{ask['path']}#ask-friend"
    html = (
        '<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">What did your friends think?</h2>'
        f'<p style="color:#3b3557;font-size:14px;line-height:1.6;margin:0">You finished <strong>{escape(ask["title"])}</strong> recently. '
        'Send a friend a link and their review shows up on the title page, with a note to you when it does.</p>'
        f'<p style="margin:8px 0 0"><a href="{escape(url, quote=True)}" style="color:#6d28d9;font-weight:700">Ask a friend for their take</a></p>'
    )
    return html, [f"What did your friends think of {ask['title']}? Ask them for their take: {url}", ""]


def _invite_section(invite: bool, base: str) -> tuple[str, list[str]]:
    """'Bring a friend' block for members with no friends yet; empty otherwise."""
    if not invite:
        return "", []
    url = f"{base}/#invite-friends"
    html = (
        '<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">Better with a friend</h2>'
        '<p style="color:#3b3557;font-size:14px;line-height:1.6;margin:0">See what your friends are watching, playing and reading. '
        'Send them your invite link and you become friends as soon as they join.</p>'
        f'<p style="margin:8px 0 0"><a href="{escape(url, quote=True)}" style="color:#6d28d9;font-weight:700">Get my invite link</a></p>'
    )
    return html, [f"Better with a friend: send your invite link and you become friends when they join: {url}", ""]


def _goals_section(goals: list | None, year: int | None, base: str) -> tuple[str, list[str]]:
    """'Your <year> goals' progress lines; empty when the member has set none."""
    if not goals or not year:
        return "", []
    rows = "".join(
        f'<li style="margin:0 0 4px">{escape(goal["summary"])}</li>' for goal in goals)
    url = f"{base}/#goals"
    html = (
        f'<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">Your {int(year)} goals</h2>'
        f'<ul style="color:#3b3557;font-size:14px;line-height:1.6;margin:0;padding-left:18px">{rows}</ul>'
        f'<p style="margin:8px 0 0"><a href="{escape(url, quote=True)}" style="color:#6d28d9;font-weight:700">See your goals</a></p>'
    )
    return html, [f"Your {int(year)} goals:"] + [f"- {goal['summary']}" for goal in goals] + [url, ""]


def invite_nudge_due(user_id: int, now: datetime) -> bool:
    """About once a month per member (a different week for each), never every week."""
    return now.isocalendar().week % 4 == user_id % 4


def build_digest(username: str, report: dict, unsubscribe_url: str, spotlight: dict | None = None,
                 ask: dict | None = None, invite: bool = False, goals: list | None = None,
                 goals_year: int | None = None) -> tuple[str, str, str] | None:
    """(subject, html, text) or None when there is nothing to send. `spotlight`, `ask`, `invite` and `goals` never force a send."""
    matches, popular = report["matches"], report["popular"]
    if not matches and not popular:
        return None
    base = app_url()
    if matches:
        subject = f"Coming up for you: {matches[0]['title']}" + (f" and {len(matches) - 1} more" if len(matches) > 1 else "")
    else:
        subject = f"This month on Release Radar: {popular[0]['title']} and more"
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
    goals_html, goals_text = _goals_section(goals, goals_year, base)
    if goals_html:
        sections.append(goals_html)
        text += goals_text
    spotlight_html, spotlight_text = _spotlight_section(spotlight, base)
    if spotlight_html:
        sections.append(spotlight_html)
        text += spotlight_text
    ask_html, ask_text = _ask_section(ask, base)
    if ask_html:
        sections.append(ask_html)
        text += ask_text
    invite_html, invite_text = _invite_section(invite and not ask_html, base)
    if invite_html:
        sections.append(invite_html)
        text += invite_text
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


def recent_finish(db: Session, user_id: int, now: datetime) -> dict | None:
    """The member's latest finish in the last three weeks that has a public title page."""
    from . import title_pages
    moments = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.user_id == user_id,
        models.CompletionMoment.completed_at >= now - timedelta(days=21),
    ).order_by(models.CompletionMoment.completed_at.desc()).limit(5).all()
    for moment in moments:
        kind = title_pages.LIBRARY_TO_KIND.get(moment.category)
        model = title_pages.KINDS[kind][0] if kind else None
        item = db.query(model).filter(model.id == moment.item_id, model.user_id == user_id).first() if model else None
        if item is None or not (item.title or "").strip():
            continue
        path = title_pages.path_for_item(kind, item)
        if title_pages.find(db, kind, path.rsplit("/", 1)[1]) is not None:
            return {"title": item.title.strip(), "path": path}
    return None


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from fastapi_mail import FastMail
    from .email import conf, html_message
    message = html_message(subject, [to], html, headers={
        "List-Unsubscribe": f"<{unsubscribe_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    })
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
        spotlight = None
        try:
            from .review_spotlight import build as build_spotlight
            spotlight = build_spotlight(db, now)
        except Exception:
            db.rollback()
            spotlight = None  # The weekly email never depends on it.
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
            if not report["matches"] and subscription.last_sent_at and subscription.last_sent_at > now - ROUNDUP_EVERY:
                stats["skipped"] += 1  # a quiet week: no news from their library, round-up sent recently
                continue
            unsubscribe_url = f"{app_url()}/email/unsubscribe?token={subscription.token}"
            try:
                ask = recent_finish(db, user.id, now)
            except Exception:
                db.rollback()
                ask = None  # The weekly email never depends on it.
            invite = False
            if ask is None and invite_nudge_due(user.id, now):
                try:
                    from .friend_invites import has_friends
                    invite = not has_friends(db, user.id)
                except Exception:
                    db.rollback()  # Optional, like the ask above.
            try:
                from .goals import progress as goal_progress
                member_goals = goal_progress(db, user, now.year, today=now.date())
            except Exception:
                db.rollback()
                member_goals = []  # Optional, like the ask above.
            built = build_digest(user.username, report, unsubscribe_url, spotlight, ask, invite,
                                 member_goals, now.year)
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
