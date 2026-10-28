"""Come-back email: a short, personal check-in for members who have been away.

Most members signed up, saved a few titles and never came back, and nothing
reaches them unless they opened the weekly email (almost nobody has). This
sends one email to a member who hasn't opened OmniTrackr for 30 days, with
what's coming up from their own library, what's still waiting in it, and a
few things to try.

Rules (all of them, every time):
- Nothing is sent until the site owner presses Start on the Site stats page.
- Verified, active members only; anyone who unsubscribed from product updates
  is skipped, and so are weekly-email subscribers (they already hear from us).
- At most one every 60 days, and none within 30 days of the "What's new"
  update. After two with no visit in between, the member gets no more until
  they come back by themselves.
- Paused automatically while the "What's new" update is sending, and kept
  inside the shared daily email budget, so sign-up and password-reset emails
  always have room on the free Mailgun plan.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timedelta
from html import escape

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import models
from .digest import _day, app_url, mail_configured

STATE_KEY = "comeback"  # the EmailCampaign row holding the owner's on/off switch
SEND_PREFIX = "comeback-"  # each send is an EmailCampaignSend row keyed by month
AWAY_DAYS = 30
EVERY_DAYS = 60
QUIET_AFTER_WHATS_NEW_DAYS = 30
MAX_UNANSWERED = 2
CAME_BACK_WITHIN_DAYS = 14
PER_RUN_LIMIT = 10
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 300
UTM = "utm_source=email&utm_campaign=come-back"


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("COMEBACK_DAILY_LIMIT", "20")))
    except ValueError:
        return 20


def enabled_for_process() -> bool:
    setting = os.getenv("COMEBACK_EMAILS", "").strip().lower()
    if setting in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


def send_key(now: datetime) -> str:
    return f"{SEND_PREFIX}{now:%Y-%m}"


# ---------------------------------------------------------------- owner switch

def state(db: Session) -> models.EmailCampaign:
    row = db.query(models.EmailCampaign).filter_by(key=STATE_KEY).first()
    if row is None:
        row = models.EmailCampaign(key=STATE_KEY, status="draft")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def set_status(db: Session, new_status: str) -> models.EmailCampaign:
    row = state(db)
    if new_status == "sending" and row.started_at is None:
        row.started_at = datetime.utcnow()
    row.status = new_status
    db.commit()
    return row


def _whats_new_sending(db: Session) -> bool:
    from .announcements import CAMPAIGN_KEY
    row = db.query(models.EmailCampaign).filter_by(key=CAMPAIGN_KEY).first()
    return row is not None and row.status == "sending"


# ---------------------------------------------------------------- who is due

def _away_since(user: models.User) -> datetime:
    """The member's last sign of life: a visit day, a log-in, or signing up."""
    moments = [user.created_at or datetime(2000, 1, 1)]
    if user.last_login_at:
        moments.append(user.last_login_at)
    if user.last_seen_on:
        moments.append(datetime.combine(user.last_seen_on, datetime.min.time()))
    return max(moments)


def due_members(db: Session, now: datetime, limit: int | None = None) -> list[models.User]:
    from .editorial_collections import EDITOR_USERNAME
    from .announcements import CAMPAIGN_KEY
    cutoff = now - timedelta(days=AWAY_DAYS)
    opted = db.query(models.EmailOptOut.user_id)
    weekly = db.query(models.EmailDigestSubscription.user_id)
    recent_comeback = db.query(models.EmailCampaignSend.user_id).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status != "test",
        models.EmailCampaignSend.sent_at >= now - timedelta(days=EVERY_DAYS))
    recent_whats_new = db.query(models.EmailCampaignSend.user_id).filter(
        models.EmailCampaignSend.campaign_key == CAMPAIGN_KEY,
        models.EmailCampaignSend.status != "test",
        models.EmailCampaignSend.sent_at >= now - timedelta(days=QUIET_AFTER_WHATS_NEW_DAYS))
    candidates = db.query(models.User).filter(
        models.User.is_active == True, models.User.is_verified == True,
        models.User.email.isnot(None), models.User.email != "",
        models.User.username != EDITOR_USERNAME,
        or_(models.User.created_at.is_(None), models.User.created_at < cutoff),
        or_(models.User.last_login_at.is_(None), models.User.last_login_at < cutoff),
        or_(models.User.last_seen_on.is_(None), models.User.last_seen_on < cutoff.date()),
        ~models.User.id.in_(opted), ~models.User.id.in_(weekly),
        ~models.User.id.in_(recent_comeback), ~models.User.id.in_(recent_whats_new),
    ).order_by(models.User.id).all()
    # Every come-back email ever sent, read once (a few rows per member at most) instead of
    # one count query per candidate, which made Site stats slow with many quiet members.
    sent_at_by_user: dict[int, list[datetime]] = {}
    for user_id, sent_at in db.query(models.EmailCampaignSend.user_id, models.EmailCampaignSend.sent_at).filter(
            models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
            models.EmailCampaignSend.status == "sent"):
        if sent_at is not None:
            sent_at_by_user.setdefault(user_id, []).append(sent_at)
    due = []
    for user in candidates:
        away_since = _away_since(user)
        if away_since >= cutoff:
            continue
        unanswered = sum(1 for sent_at in sent_at_by_user.get(user.id, ()) if sent_at > away_since)
        if unanswered >= MAX_UNANSWERED:
            continue
        due.append(user)
        if limit is not None and len(due) >= limit:
            break
    return due


def status(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    row = state(db)
    since = now - timedelta(days=30)
    sends = db.query(models.EmailCampaignSend).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status == "sent",
        models.EmailCampaignSend.sent_at >= since - timedelta(days=CAME_BACK_WITHIN_DAYS),
    ).all()
    sent_30d = [send for send in sends if send.sent_at >= since]
    came_back = 0
    for send in sends:
        user = db.get(models.User, send.user_id)
        if user is None:
            continue
        back = user.last_seen_on and send.sent_at.date() <= user.last_seen_on <= (
            send.sent_at + timedelta(days=CAME_BACK_WITHIN_DAYS)).date()
        logged = user.last_login_at and send.sent_at <= user.last_login_at <= send.sent_at + timedelta(days=CAME_BACK_WITHIN_DAYS)
        if back or logged:
            came_back += 1
    return {
        "status": row.status,
        "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
        "sent_30d": len(sent_30d),
        "sent_all_time": int(db.query(func.count(models.EmailCampaignSend.id)).filter(
            models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
            models.EmailCampaignSend.status == "sent").scalar() or 0),
        "came_back": came_back,
        "came_back_window_days": CAME_BACK_WITHIN_DAYS,
        "due_now": len(due_members(db, now)),
        "waiting_on_whats_new": _whats_new_sending(db),
        "daily_limit": daily_limit(),
        "away_days": AWAY_DAYS,
        "every_days": EVERY_DAYS,
        "mail_configured": mail_configured(),
    }


# ---------------------------------------------------------------- content

FINISHED = (
    (models.Movie, "watched", "Movie"),
    (models.TVShow, "watched", "TV show"),
    (models.Anime, "watched", "Anime"),
    (models.VideoGame, "played", "Video game"),
    (models.Book, "read", "Book"),
    (models.Manga, "read", "Manga"),
)


def library_snapshot(db: Session, user_id: int) -> tuple[int, list[dict]]:
    """(total titles, up to three unfinished ones, newest first)."""
    total = 0
    waiting: list[tuple[datetime, dict]] = []
    for model, done_field, label in FINISHED + ((models.Music, None, "Album"),):
        total += int(db.query(func.count(model.id)).filter(model.user_id == user_id).scalar() or 0)
        if done_field is None:
            continue
        rows = db.query(model).filter(model.user_id == user_id, getattr(model, done_field) != True) \
            .order_by(model.added_at.desc().nullslast(), model.id.desc()).limit(3).all()
        for row in rows:
            title = (row.title or "").strip()
            if title:
                waiting.append((row.added_at or datetime(2000, 1, 1), {"title": title, "label": label}))
    waiting.sort(key=lambda pair: pair[0], reverse=True)
    return total, [item for _, item in waiting[:3]]


def _link(path: str) -> str:
    joiner = "&" if "?" in path.split("#")[0] else "?"
    if "#" in path:
        head, anchor = path.split("#", 1)
        return f"{app_url()}{head}{joiner}{UTM}#{anchor}"
    return f"{app_url()}{path}{joiner}{UTM}"


def _things_to_try(today: date) -> list[tuple[str, str, str]]:
    from . import challenges
    month = challenges.month_key(today)
    challenge = challenges.challenge_for(month)
    return [
        ("OmniTrackr Daily", "Guess the movie, show, anime or game from six clues. A new puzzle every day.", "/daily"),
        (f"{challenges.month_label(month)} challenge: {challenge['name']}",
         challenge.get("tagline") or "Three small steps for the month.", f"/challenges/{challenges.slug_for(month)}"),
        ("Tier list maker", "Rank titles from S to D and save the board as an image to share.", "/tier-list"),
    ]


def build_email(username: str, library_total: int, waiting: list[dict], matches: list[dict],
                unsubscribe_url: str, weekly_url: str | None, today: date) -> tuple[str, str, str]:
    """(subject, html, text) for one member."""
    if matches:
        subject = f"{matches[0]['title']} is coming up, and it's on your list"
    elif waiting:
        subject = f"{waiting[0]['title']} is still waiting for you on OmniTrackr"
    elif library_total:
        subject = "Your OmniTrackr library is right where you left it"
    else:
        subject = "Your OmniTrackr library is ready when you are"
    subject = " ".join(subject.split())[:150]  # library titles are member-typed: one line, bounded
    if library_total:
        intro = (f"It's been a while, so here's what's new for you. Your library still has your "
                 f"{library_total} title{'s' if library_total != 1 else ''}, exactly as you left {'them' if library_total != 1 else 'it'}.")
    else:
        intro = ("It's been a while, so here's what's new. Your library is still empty: pick a few favourites from "
                 "Quick start and it fills in under a minute.")

    def rows(items: list[tuple[str, str, str | None]]) -> str:
        return "".join(
            '<tr><td style="padding:10px 0;border-top:1px solid #e9e5f5">'
            + (f'<a href="{escape(url, quote=True)}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">{escape(title)}</a>'
               if url else f'<div style="color:#1f1640;font-weight:700;font-size:15px">{escape(title)}</div>')
            + f'<div style="color:#5b5675;font-size:13px;line-height:1.5">{escape(detail)}</div></td></tr>'
            for title, detail, url in items)

    def section(heading: str, body: str) -> str:
        return (f'<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">{escape(heading)}</h2>'
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{body}</table>')

    html_sections = ""
    text = [f"Hi {username},", "", intro, ""]
    if matches:
        html_sections += section("Coming up from your library", rows([
            (card["title"], f"{card['label']} · {_day(card.get('date'))} · {card.get('reason') or ''}".rstrip(" ·"),
             _link(card["url"]) if card.get("url") else None) for card in matches[:3]]))
        text += ["Coming up from your library:"] + [
            f"- {card['title']} ({card['label']}, {_day(card.get('date'))})" for card in matches[:3]] + [""]
    if waiting:
        html_sections += section("Still on your list", rows([
            (item["title"], f"{item['label']} you saved but haven't finished", None) for item in waiting]))
        text += ["Still on your list:"] + [f"- {item['title']} ({item['label']})" for item in waiting] + [""]
    tries = _things_to_try(today)
    html_sections += section("New since your last visit", rows([(title, detail, _link(path)) for title, detail, path in tries]))
    text += ["New since your last visit:"] + [f"- {title}: {detail} {_link(path)}" for title, detail, path in tries] + [""]
    weekly_html = ""
    if weekly_url:
        weekly_html = (
            '<div style="background:#f4f0ff;border:1px solid #e1d8fb;border-radius:12px;padding:16px 18px;margin:22px 0 4px">'
            '<div style="color:#1f1640;font-weight:700;font-size:16px">Rather hear only when something you track comes out?</div>'
            '<div style="color:#5b5675;font-size:14px;line-height:1.5;margin:6px 0 12px">Turn on the weekly email instead: '
            'new episodes, seasons, games and releases from your library, quiet weeks skipped.</div>'
            f'<a href="{escape(weekly_url, quote=True)}" style="background:#1a1433;color:#fff;padding:10px 18px;border-radius:999px;'
            'text-decoration:none;font-weight:700;font-size:14px">Email me weekly</a></div>')
        text += ["Rather hear only when something you track comes out? Turn on the weekly email:", weekly_url, ""]
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">OmniTrackr</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">We saved your spot, {escape(username)}</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">Hi {escape(username)}, {escape(intro[0].lower() + intro[1:])}</p>'
        + html_sections + weekly_html +
        f'<p style="margin:26px 0 8px"><a href="{escape(_link("/"), quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Open my library</a></p>'
        '<p style="color:#8a86a3;font-size:12px;line-height:1.5;margin-top:24px">You’re getting this because you have an '
        'OmniTrackr account and haven’t visited in a while. We send one of these at most every two months, and stop after two '
        'if you don’t come back. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a> with one click.</p>'
        '</div></div></body></html>'
    )
    text += [f"Open your library: {_link('/')}", "",
             "You're getting this because you have an OmniTrackr account and haven't visited in a while. "
             "We send one of these at most every two months, and stop after two if you don't come back.",
             f"Unsubscribe from product updates: {unsubscribe_url}"]
    return subject, html, "\n".join(text)


def email_for(db: Session, user: models.User, pool=None, today: date | None = None) -> tuple[str, str, str, str]:
    """(subject, html, text, unsubscribe_url) for a member."""
    from .announcements import unsubscribe_token
    from .for_you import coming_up
    from . import digest
    today = today or datetime.utcnow().date()
    try:
        matches = coming_up(db, user.id, today=today, pool=pool)["matches"] if pool is not None else []
    except Exception:
        db.rollback()
        matches = []
    total, waiting = library_snapshot(db, user.id)
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    weekly_url = None if digest.subscription_for(db, user.id) else digest.subscribe_link(user.id)
    subject, html, text = build_email(user.username, total, waiting, matches, unsubscribe_url, weekly_url, today)
    return subject, html, text, unsubscribe_url


# ---------------------------------------------------------------- sending

async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


def allowance(db: Session, now: datetime) -> int:
    """How many may go out now: inside this email's own limit and the shared daily cap."""
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_comeback = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status != "test",
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_comeback, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


async def send_due(session_factory, client=None, now: datetime | None = None, sender=_send) -> dict:
    now = now or datetime.utcnow()
    stats = {"sent": 0, "failed": 0, "limited": False}
    if not mail_configured() and sender is _send:
        return stats
    db = session_factory()
    try:
        if state(db).status != "sending" or _whats_new_sending(db):
            return stats
        budget = allowance(db, now)
        if budget <= 0:
            stats["limited"] = True
            return stats
        users = due_members(db, now, limit=budget)
        if not users:
            return stats
        pool = None
        try:
            from .for_you import radar_pool
            pool = radar_pool(None, client)
        except Exception:
            pool = None
        from .email_quota import lock_email_budget
        for user in users:
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                stats["limited"] = True
                break
            # Claim first so an overlapping run can never send twice.
            claim = models.EmailCampaignSend(campaign_key=send_key(now), user_id=user.id, status="sent", sent_at=now)
            db.add(claim)
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            try:
                subject, html, _text, unsubscribe_url = email_for(db, user, pool, now.date())
                await sender(user.email, subject, html, unsubscribe_url)
                stats["sent"] += 1
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Come-back email to user {user.id} failed: {error}")
                db.rollback()  # building the email may have left the session mid-transaction
                claim.status = "failed"
                db.commit()
                stats["failed"] += 1
        return stats
    finally:
        db.close()


async def send_test(db: Session, user: models.User, client=None, sender=_send) -> None:
    """Send the email to the owner only (doesn't count as a come-back email for them)."""
    pool = None
    try:
        from .for_you import radar_pool
        pool = radar_pool(None, client)
    except Exception:
        pool = None
    subject, html, _text, unsubscribe_url = email_for(db, user, pool)
    await sender(user.email, "[Test] " + subject, html, unsubscribe_url)


async def comeback_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            stats = await send_due(SessionLocal, getattr(app.state, "external_api_client", None))
            if stats["sent"] or stats["failed"]:
                print(f"Come-back emails: {stats}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Come-back email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
