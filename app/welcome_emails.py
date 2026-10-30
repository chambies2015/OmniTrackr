"""Welcome emails: three short notes in a new member's first week.

Most new members save a few titles on day one and never open OmniTrackr again.
The in-app first-week steps only help the ones who come back, so this sends
three emails while the account is new:

- day 1: the quickest ways to fill the library (or what to do with it),
- day 3: invite a friend and write a first review (skipped when both are done),
- day 6: the weekly email, Release Radar and a few things to play.

Rules (all of them, every time):
- Nothing is sent until the site owner presses Start on the Site stats page,
  and only members who sign up after that get the series. Nobody who already
  had an account when it started ever gets one.
- Verified, active members only; anyone who switched off "Occasional news"
  (the product updates opt-out) is skipped, and every email can switch it off
  in one click.
- Each email has a two-day window. One that can't go out in time (paused,
  over the daily budget, unverified until later) is dropped, never sent late.
- No two product emails within 40 hours of each other, and none within 20
  hours of the member's weekly email.
- Inside the shared daily email budget, so sign-up and password-reset emails
  always have room on the free Mailgun plan.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .digest import app_url, mail_configured

STATE_KEY = "welcome-series"  # the EmailCampaign row holding the owner's on/off switch
SEND_PREFIX = "welcome-"  # each email is an EmailCampaignSend row keyed by step
WINDOW = timedelta(days=2)
GAP = timedelta(hours=40)
WEEKLY_GAP = timedelta(hours=20)
CAME_BACK_WITHIN_DAYS = 3
PER_RUN_LIMIT = 10
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 360
UTM = "utm_source=email&utm_campaign=welcome"


@dataclass(frozen=True)
class Step:
    number: int
    slug: str
    day: int
    label: str

    @property
    def key(self) -> str:
        return f"{SEND_PREFIX}{self.number}-{self.slug}"


STEPS = (
    Step(1, "start", 1, "Day 1: fill your library"),
    Step(2, "friends", 3, "Day 3: friends and a first review"),
    Step(3, "never-miss", 6, "Day 6: the weekly email and things to play"),
)
STEP_KEYS = tuple(step.key for step in STEPS)
LAST_DAY = STEPS[-1].day


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("WELCOME_DAILY_LIMIT", "20")))
    except ValueError:
        return 20


def enabled_for_process() -> bool:
    setting = os.getenv("WELCOME_EMAILS", "").strip().lower()
    if setting in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


def step_for(number: int) -> Step | None:
    return next((step for step in STEPS if step.number == number), None)


def current_step(user: models.User, now: datetime) -> Step | None:
    """The step whose window contains now (the windows never overlap)."""
    if not user.created_at:
        return None
    for step in STEPS:
        opens = user.created_at + timedelta(days=step.day)
        if opens <= now < opens + WINDOW:
            return step
    return None


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
        # Members who signed up before this moment never get the series.
        row.started_at = datetime.utcnow()
    row.status = new_status
    db.commit()
    return row


# ---------------------------------------------------------------- who is due

def _progress(db: Session, user: models.User) -> dict:
    """The member's first-week steps, read by the same function as the library launchpad."""
    from .for_you import first_week
    # first_week only answers for new accounts; the owner's preview and test use an old one.
    report = first_week(db, user, now=user.created_at or datetime.utcnow())
    return report if report.get("show") else {}


def _wanted(step: Step, progress: dict) -> bool:
    if step.slug == "friends":
        return not (progress.get("friend") and progress.get("public_review"))
    return True


def due_members(db: Session, now: datetime, limit: int | None = None) -> list[tuple[models.User, Step]]:
    from .editorial_collections import EDITOR_USERNAME
    started = state(db).started_at
    if started is None:
        return []
    earliest = max(started, now - timedelta(days=LAST_DAY) - WINDOW)
    opted = db.query(models.EmailOptOut.user_id)
    candidates = db.query(models.User).filter(
        models.User.is_active == True, models.User.is_verified == True,
        models.User.email.isnot(None), models.User.email != "",
        models.User.username != EDITOR_USERNAME,
        models.User.created_at.isnot(None),
        models.User.created_at >= earliest,
        models.User.created_at <= now - timedelta(days=STEPS[0].day),
        ~models.User.id.in_(opted),
    ).order_by(models.User.created_at, models.User.id).all()
    if not candidates:
        return []
    ids = [user.id for user in candidates]
    # Read every send for these members once: what they've had, and their last product email.
    had: set[tuple[int, str]] = set()
    last_email: dict[int, datetime] = {}
    for user_id, key, send_status, sent_at in db.query(
            models.EmailCampaignSend.user_id, models.EmailCampaignSend.campaign_key,
            models.EmailCampaignSend.status, models.EmailCampaignSend.sent_at).filter(
            models.EmailCampaignSend.user_id.in_(ids)):
        had.add((user_id, key))
        if send_status == "sent" and sent_at and sent_at > last_email.get(user_id, datetime.min):
            last_email[user_id] = sent_at
    weekly = dict(db.query(models.EmailDigestSubscription.user_id, models.EmailDigestSubscription.last_sent_at)
                  .filter(models.EmailDigestSubscription.user_id.in_(ids)).all())
    due = []
    for user in candidates:
        step = current_step(user, now)
        if step is None or (user.id, step.key) in had:
            continue
        if user.id in last_email and last_email[user.id] > now - GAP:
            continue
        if weekly.get(user.id) and weekly[user.id] > now - WEEKLY_GAP:
            continue
        if not _wanted(step, _progress(db, user)):
            continue
        due.append((user, step))
        if limit is not None and len(due) >= limit:
            break
    return due


def status(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    row = state(db)
    since = now - timedelta(days=30)
    sends = db.query(models.EmailCampaignSend).filter(
        models.EmailCampaignSend.campaign_key.in_(STEP_KEYS),
        models.EmailCampaignSend.status == "sent",
        models.EmailCampaignSend.sent_at >= since,
    ).all()
    users = {user.id: user for user in db.query(models.User).filter(
        models.User.id.in_({send.user_id for send in sends}))} if sends else {}
    came_back = 0
    for send in sends:
        user = users.get(send.user_id)
        if user and user.last_seen_on and send.sent_at.date() <= user.last_seen_on <= (
                send.sent_at + timedelta(days=CAME_BACK_WITHIN_DAYS)).date():
            came_back += 1
    joined = 0
    if row.started_at:
        joined = int(db.query(func.count(models.User.id)).filter(models.User.created_at >= row.started_at).scalar() or 0)
    return {
        "status": row.status,
        "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
        "joined_since_start": joined,
        "steps": [{"number": step.number, "label": step.label,
                   "sent_30d": sum(1 for send in sends if send.campaign_key == step.key)} for step in STEPS],
        "sent_30d": len(sends),
        "came_back": came_back,
        "came_back_window_days": CAME_BACK_WITHIN_DAYS,
        "due_now": len(due_members(db, now)) if row.status == "sending" else 0,
        "daily_limit": daily_limit(),
        "mail_configured": mail_configured(),
    }


# ---------------------------------------------------------------- content

def _link(path: str) -> str:
    joiner = "&" if "?" in path.split("#")[0] else "?"
    if "#" in path:
        head, anchor = path.split("#", 1)
        return f"{app_url()}{head}{joiner}{UTM}#{anchor}"
    return f"{app_url()}{path}{joiner}{UTM}"


def _rows(items: list[tuple[str, str, str]]) -> str:
    return "".join(
        '<tr><td style="padding:10px 0;border-top:1px solid #e9e5f5">'
        f'<a href="{escape(_link(path), quote=True)}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">{escape(title)}</a>'
        f'<div style="color:#5b5675;font-size:13px;line-height:1.5">{escape(detail)}</div></td></tr>'
        for title, detail, path in items)


def _section(heading: str, items: list[tuple[str, str, str]]) -> str:
    return (f'<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">{escape(heading)}</h2>'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{_rows(items)}</table>')


def _text_items(heading: str, items: list[tuple[str, str, str]]) -> list[str]:
    return [f"{heading}:"] + [f"- {title}: {detail} {_link(path)}" for title, detail, path in items] + [""]


def _day_one(library_total: int) -> tuple[str, str, str, list[tuple[str, str, list]]]:
    """(subject, heading, intro, sections)."""
    if library_total:
        plural = "s" if library_total != 1 else ""
        return (
            "A few things to try with your OmniTrackr library",
            "Your library is off to a start",
            f"You've saved {library_total} title{plural} so far. Here's what else the library can do, "
            "and how to bring over anything you track somewhere else.",
            [("Make it yours", [
                ("Line up what's next", "Put a few titles in your Next Up queue and your home page shows "
                 "what to start next.", "/#next-up"),
                ("Let OmniTrackr pick", "Can't decide what to watch tonight? Pick for me suggests one title "
                 "at a time, with the reason it picked it.", "/pick"),
            ]), ("Moving from another site", [
                ("Bring your lists over", "Import from Letterboxd, IMDb, Goodreads, MyAnimeList, AniList, Trakt "
                 "or Steam. You see a preview before anything is saved.", "/switch"),
            ])],
        )
    return (
        "Fill your OmniTrackr library in a couple of minutes",
        "Let's fill your library",
        "Your library is empty so far, which is normal on day one. Either of these gets it going in a couple of minutes.",
        [("Two quick ways in", [
            ("Take the taste quiz", "Tap through well-known movies, shows, anime and games, mark what you've seen "
             "and liked, and they go straight into your library.", "/taste-quiz"),
            ("Bring your lists over", "Import from Letterboxd, IMDb, Goodreads, MyAnimeList, AniList, Trakt or Steam. "
             "You see a preview before anything is saved.", "/switch"),
        ])],
    )


def _day_three(progress: dict) -> tuple[str, str, str, list[tuple[str, str, list]]]:
    items = []
    if not progress.get("friend"):
        items.append(("Send a friend your invite link", "When they join from your link you're friends straight away, "
                      "and you can see what each other is watching, playing and reading.", "/#invite-friends"))
    target = progress.get("review_target")
    if not progress.get("public_review") and target:
        items.append((f"Review {target['title']}", "A few lines is plenty. Your review shows on the title's public "
                      "page, and other members can read it there.", target["path"]))
    items.append(("Start a watch club", "Pick one title with friends, everyone gets to it by a date, then you "
                  "talk it over.", "/clubs"))
    if not progress.get("friend"):
        subject = "OmniTrackr is better with a friend"
        heading = "Bring someone along"
        intro = ("Lists are more fun when someone else can see them. Here are the easiest ways to get other people "
                 "into your OmniTrackr.")
    else:
        subject = (f"What did you think of {target['title']}?" if target else "Write your first OmniTrackr review")
        heading = "Say what you thought"
        intro = "You've already got a friend on OmniTrackr. The next step is a review, even a short one."
        if not target:
            items.insert(0, ("Write your first review", "Open any title in your library and add a few lines. "
                             "See what other members wrote first if you like.", "/reviews"))
    return subject, heading, intro, [("Where to start", items)]


def _day_six(weekly: bool, today: date) -> tuple[str, str, str, list[tuple[str, str, list]]]:
    from .comeback import _things_to_try
    play = _things_to_try(today)
    if weekly:
        return (
            "Three small things to try on OmniTrackr",
            "One last tip from us",
            "You've had OmniTrackr for almost a week, and you're already on the weekly email, so this is the "
            "last welcome note. Here are a few things to play with between releases.",
            [("Worth a look", play)],
        )
    return (
        "Want to hear when something on your list comes out?",
        "Never miss a release",
        "OmniTrackr keeps an eye on new seasons, episodes, games and releases connected to what you track. "
        "The weekly email is how you hear about them without checking.",
        [("Coming up", [("Open Release Radar", "Upcoming movies, shows, anime and games in one list. Save one "
                         "and you hear about it the day it comes out.", "/release-radar")]),
         ("Worth a look", play)],
    )


def build_email(step: Step, username: str, library_total: int, progress: dict, unsubscribe_url: str,
                weekly_url: str | None, today: date) -> tuple[str, str, str]:
    """(subject, html, text) for one member."""
    if step.slug == "start":
        subject, heading, intro, sections = _day_one(library_total)
    elif step.slug == "friends":
        subject, heading, intro, sections = _day_three(progress)
    else:
        subject, heading, intro, sections = _day_six(weekly_url is None, today)
    subject = " ".join(subject.split())[:150]  # titles in it are member-typed: one line, bounded
    weekly_html = ""
    if step.slug == "never-miss" and weekly_url:
        weekly_html = (
            '<div style="background:#f4f0ff;border:1px solid #e1d8fb;border-radius:12px;padding:16px 18px;margin:22px 0 4px">'
            '<div style="color:#1f1640;font-weight:700;font-size:16px">Turn on the weekly email</div>'
            '<div style="color:#5b5675;font-size:14px;line-height:1.5;margin:6px 0 12px">One short email a week with '
            'new episodes of your shows, releases you track and what your friends added. Weeks with no news are skipped.</div>'
            f'<a href="{escape(weekly_url, quote=True)}" style="display:inline-block;background:#1a1433;color:#fff;padding:10px 18px;'
            'border-radius:999px;text-decoration:none;font-weight:700;font-size:14px">Email me weekly</a></div>')
    text = [f"Hi {username},", "", intro, ""]
    if weekly_html:
        text += ["Turn on the weekly email (one short email a week, quiet weeks skipped):", weekly_url, ""]
    html_sections = ""
    for section_heading, items in sections:
        html_sections += _section(section_heading, items)
        text += _text_items(section_heading, items)
    support_html = ""
    if step.slug == "never-miss":
        support_html = (
            '<p style="color:#5b5675;font-size:14px;line-height:1.6;margin:22px 0 0">OmniTrackr is a small independent '
            'site, paid for by ads and supporters. If it earns a spot in your week, the '
            f'<a href="{escape(_link("/supporters"), quote=True)}" style="color:#6d28d9">Supporters page</a> has the details.</p>')
        text += ["OmniTrackr is a small independent site, paid for by ads and supporters. "
                 f"If it earns a spot in your week, the Supporters page has the details: {_link('/supporters')}", ""]
    count_line = f"This is {step.number} of 3 short emails in your first week, and then they stop."
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">OmniTrackr</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">{escape(heading)}</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">Hi {escape(username)},</p>'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">{escape(intro)}</p>'
        + weekly_html + html_sections + support_html +
        f'<p style="margin:26px 0 8px"><a href="{escape(_link("/"), quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Open my library</a></p>'
        '<p style="color:#8a86a3;font-size:12px;line-height:1.5;margin-top:24px">You’re getting this because you joined '
        f'OmniTrackr this week. {escape(count_line)} '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a> '
        'with one click, or switch off “Occasional news” under Email in Account Settings.</p>'
        '</div></div></body></html>'
    )
    text += [f"Open your library: {_link('/')}", "",
             f"You're getting this because you joined OmniTrackr this week. {count_line}",
             f"Unsubscribe from product updates: {unsubscribe_url}"]
    return subject, html, "\n".join(text)


def email_for(db: Session, user: models.User, step: Step, today: date | None = None) -> tuple[str, str, str, str]:
    """(subject, html, text, unsubscribe_url) for a member."""
    from .announcements import unsubscribe_token
    from .comeback import library_snapshot
    from . import digest
    today = today or datetime.utcnow().date()
    total, _waiting = library_snapshot(db, user.id)
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    weekly_url = None if digest.subscription_for(db, user.id) else digest.subscribe_link(user.id)
    subject, html, text = build_email(step, user.username, total, _progress(db, user), unsubscribe_url, weekly_url, today)
    return subject, html, text, unsubscribe_url


# ---------------------------------------------------------------- sending

async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


def allowance(db: Session, now: datetime) -> int:
    """How many may go out now: inside this email's own limit and the shared daily cap."""
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_welcome = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.in_(STEP_KEYS),
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_welcome, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


async def send_due(session_factory, now: datetime | None = None, sender=_send) -> dict:
    now = now or datetime.utcnow()
    stats = {"sent": 0, "failed": 0, "limited": False}
    if not mail_configured() and sender is _send:
        return stats
    db = session_factory()
    try:
        if state(db).status != "sending":
            return stats
        budget = allowance(db, now)
        if budget <= 0:
            stats["limited"] = True
            return stats
        from .email_quota import lock_email_budget
        for user, step in due_members(db, now, limit=budget):
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                stats["limited"] = True
                break
            # Claim first so an overlapping run can never send twice.
            claim = models.EmailCampaignSend(campaign_key=step.key, user_id=user.id, status="sent", sent_at=now)
            db.add(claim)
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            try:
                subject, html, _text, unsubscribe_url = email_for(db, user, step, now.date())
                await sender(user.email, subject, html, unsubscribe_url)
                stats["sent"] += 1
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Welcome email {step.number} to user {user.id} failed: {error}")
                db.rollback()
                claim.status = "failed"
                db.commit()
                stats["failed"] += 1
        return stats
    finally:
        db.close()


async def send_test(db: Session, user: models.User, sender=_send) -> None:
    """Send all three to the owner only (none of them counts as a welcome email for them)."""
    for step in STEPS:
        subject, html, _text, unsubscribe_url = email_for(db, user, step)
        await sender(user.email, f"[Test {step.number}/3] " + subject, html, unsubscribe_url)


async def welcome_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            stats = await send_due(SessionLocal)
            if stats["sent"] or stats["failed"]:
                print(f"Welcome emails: {stats}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Welcome email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
