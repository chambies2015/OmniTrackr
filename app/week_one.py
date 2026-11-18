"""A new member's first week on the home screen (Nov 2026).

Site stats showed where new members fall away: of 100 who started a library, 31 reached five
titles and only 6 of those ever came back for a second day. Everything that brings a member back
(What's new, the stay-posted card, the weekly email, notifications) either waits for a second
visit or needs a switch the member never found. On day one the home screen said nothing about
what happens next.

This card fills the first seven days of an account:

* The member's week, day by day: new episodes of the shows and anime they haven't finished
  (from the episode schedule cache) and release days of titles in their library (Release Radar
  cache). Nothing here calls an outside service during a request.
* When their week is thin (the start page saves everything as finished, so most new libraries
  have nothing airing), shows other members follow that have an episode this week, with one
  button to save one as "watching". Its episodes then join their week.
* One reminder, asked for by the member: "Email me on Sunday" sends a single email that day
  (around 5 pm their time) naming what's out. Nothing repeats and nothing else is signed up for.
  Or "Notify me on this device", which is the existing notifications switch.

Counters go into ``site_traffic_daily`` under kind "weekone" and name no member. "returned" is
the number Dan cares about: members who saw the card and opened the home screen again on a later
day of their first week.
"""
from __future__ import annotations

import asyncio
import json
import os
import time as clock
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

WEEK_DAYS = 7                      # the card shows on days 1 to 7 of an account
MIN_TITLES = 1                     # an empty library has the launchpad instead
SUGGEST_BELOW = 3                  # fewer things than this in their week: offer shows airing now
SUGGEST_LIMIT = 6
POOL_LIMIT = 40
POOL_SECONDS = 1800
PER_DAY_LIMIT = 4
REMIND_HOUR = 17                   # local time on the chosen day: after work and school
LATE = timedelta(hours=10)         # a reminder that can't go out within this long is dropped, never sent late
SEND_PREFIX = "week-one-"
CHECK_EVERY_SECONDS = 900
FIRST_CHECK_DELAY_SECONDS = 420
PER_RUN_LIMIT = 20
UTM = "utm_source=email&utm_campaign=week-one"
CATEGORIES = {"tv": "tv-shows", "anime": "anime"}
LABELS = {"tv-shows": "TV show", "anime": "Anime"}
VISIBLE_FLAG = {"tv-shows": "tv_shows_visible", "anime": "anime_visible"}

COUNTERS = {
    "seen": "Saw the first-week card",
    "returned": "Came back on a later day of their first week",
    "saved": "Saved a show airing this week",
    "email_set": "Asked for a reminder email",
    "email_cancel": "Cancelled the reminder",
    "sent": "Reminder emails sent",
    "dropped": "Reminders dropped (late, or nothing out that day any more)",
    "back_after_email": "Came back after their reminder email",
    "push_on": "Turned on notifications from the card",
    "hidden": "Hid the card",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str) -> bool:
    """Add 1 to a "weekone" counter for today. Never raises."""
    if key not in COUNTERS:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "weekone", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("WEEK_ONE_DAILY_LIMIT", "30")))
    except ValueError:
        return 30


def emails_enabled() -> bool:
    if os.getenv("WEEK_ONE_EMAILS", "").strip().lower() in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


# ---------------------------------------------------------------- whose week is it

def local_today(now: datetime, value: Optional[str]) -> date:
    """The member's date from the browser, trusted only within a day of UTC's."""
    utc_today = now.date()
    try:
        given = date.fromisoformat(value or "")
    except ValueError:
        return utc_today
    return given if abs((given - utc_today).days) <= 1 else utc_today


def day_number(user: models.User, today: date) -> Optional[int]:
    """1 on the day the account was made, up to 7; None outside the first week."""
    if user.created_at is None:
        return None
    number = (today - user.created_at.date()).days + 1
    return number if 1 <= number <= WEEK_DAYS else None


def get_row(db: Session, user_id: int) -> Optional[models.WeekOnePlan]:
    return db.query(models.WeekOnePlan).filter(models.WeekOnePlan.user_id == user_id).first()


def _row(db: Session, user_id: int) -> models.WeekOnePlan:
    row = get_row(db, user_id)
    if row is None:
        row = models.WeekOnePlan(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def active(db: Session, user: models.User, now: Optional[datetime] = None) -> bool:
    """The card is (or could be) on this member's home screen, so other asks stay out of its way."""
    now = now or _now()
    if user.created_at is None or now - user.created_at >= timedelta(days=WEEK_DAYS):
        return False
    row = get_row(db, user.id)
    return row is None or row.hidden_at is None


def _library_size(db: Session, user_id: int) -> int:
    from .stay_posted import _library_size as size
    return size(db, user_id)


# ---------------------------------------------------------------- the member's week

def _poster(item) -> Optional[str]:
    from .for_you import _safe_image
    return _safe_image(getattr(item, "poster_url", None))


def week_items(db: Session, user: models.User, today: date) -> list[dict]:
    """Episodes and release days from the member's own library, today and the six days after it."""
    from . import episode_calendar, title_pages
    from .user_columns import ensure_loaded
    end = today + timedelta(days=WEEK_DAYS - 1)
    items: list[dict] = []
    ensure_loaded(user, tuple(VISIBLE_FLAG.values()) + tuple(episode_calendar.PRIVATE_FLAG.values()))
    try:
        for category, item, schedule, episode, _link in episode_calendar._member_episodes(db, user, today):
            if not getattr(user, VISIBLE_FLAG[category], True):
                continue
            day = date.fromisoformat(episode["date"])
            if not today <= day <= end:
                continue
            season = episode.get("season") if category == "tv-shows" else None
            what = f"S{season} E{episode['number']}" if season else f"Episode {episode['number']}"
            path = None
            if not getattr(user, episode_calendar.PRIVATE_FLAG[category], False):
                path = title_pages.title_path(episode_calendar.PAGE_KIND[category], item.title, item.year)
            items.append({
                "kind": "episode", "date": day.isoformat(), "category": category, "label": LABELS[category],
                "title": (schedule.get("show") or item.title or "").strip()[:200], "what": what,
                "image": _poster(item), "url": path, "item_id": item.id,
            })
    except Exception:
        db.rollback()
    try:
        from .for_you import coming_up
        for card in coming_up(db, user.id, today).get("matches", []):
            when = card.get("date") or ""
            if not (today.isoformat() <= when <= end.isoformat()):
                continue
            if not str(card.get("reason") or "").startswith("In your library"):
                continue  # a sequel is a guess; the week only names titles they saved
            items.append({
                "kind": "release", "date": when, "category": card.get("library_category") or "",
                "label": card.get("label") or "", "title": str(card["title"])[:200], "what": "Out",
                "image": card.get("image"), "url": card.get("url"), "item_id": None,
            })
    except Exception:
        db.rollback()
    seen, found = set(), []
    for item in sorted(items, key=lambda entry: (entry["date"], entry["title"].lower(), entry["what"])):
        key = (item["date"], item["title"].lower())
        if key in seen:
            continue  # two episodes of one show on one day read as one line
        seen.add(key)
        found.append(item)
    return found


def _days(items: list[dict], today: date) -> list[dict]:
    days = []
    for offset in range(WEEK_DAYS):
        day = today + timedelta(days=offset)
        mine = [item for item in items if item["date"] == day.isoformat()]
        days.append({"date": day.isoformat(), "items": mine[:PER_DAY_LIMIT], "more": max(0, len(mine) - PER_DAY_LIMIT)})
    return days


# ---------------------------------------------------------------- shows airing this week

_POOL: dict = {}


def _key_parts(key: str) -> Optional[tuple[str, str, Optional[int]]]:
    """("tv-shows", normalized title, year) from an "airing:tv:<title>:<year>" cache key."""
    try:
        _prefix, kind, rest = key.split(":", 2)
        name, _sep, year = rest.rpartition(":")
    except ValueError:
        return None
    if kind not in CATEGORIES or not name:
        return None
    return CATEGORIES[kind], name, int(year) if year.isdigit() else None


def airing_pool(db: Session, today: date) -> list[dict]:
    """Shows members follow (on shelves they share) that have an episode in the next seven days.

    Read from the episode schedule cache and the libraries; kept for half an hour per process.
    """
    cached = _POOL.get("pool")
    if cached and _POOL.get("day") == today and clock.monotonic() - _POOL.get("at", 0) < POOL_SECONDS:
        return cached
    from . import episode_calendar
    from .editorial_collections import EDITOR_USERNAME
    from .for_you import LIBRARY, _safe_image, _shareable_ids
    end = (today + timedelta(days=WEEK_DAYS - 1)).isoformat()
    airing: dict[str, dict] = {}
    rows = db.query(models.TitleMetadata.key, models.TitleMetadata.data).filter(
        models.TitleMetadata.key.like("airing:%"), models.TitleMetadata.status == "ok").all()
    for key, data in rows:
        if _key_parts(key) is None:
            continue
        try:
            schedule = json.loads(data) if data else None
        except ValueError:
            continue
        if not isinstance(schedule, dict) or schedule.get("source_id") is None:
            continue
        upcoming = [episode for episode in schedule.get("episodes") or []
                    if isinstance(episode, dict) and type(episode.get("number")) is int
                    and today.isoformat() <= str(episode.get("date") or "") <= end]
        if upcoming:
            upcoming.sort(key=lambda episode: (episode["date"], episode.get("season") or 0, episode["number"]))
            airing[key] = {"schedule": schedule, "next": upcoming[0]}
    pool: list[dict] = []
    if airing:
        editors = db.query(models.User.id).filter(models.User.username == EDITOR_USERNAME)
        for category in ("tv-shows", "anime"):
            model, fields = LIBRARY[category]
            shareable = _shareable_ids(db, category)
            entries = db.query(model).filter(model.user_id.in_(shareable), ~model.user_id.in_(editors)).all()
            grouped: dict[str, list] = {}
            for entry in entries:
                if not (entry.title or "").strip():
                    continue
                key = episode_calendar.airing_key(category, entry.title, entry.year)
                if key in airing:
                    grouped.setdefault(key, []).append(entry)
            for key, members in grouped.items():
                best = max(members, key=lambda entry: (bool(_safe_image(entry.poster_url)),
                                                       sum(bool(getattr(entry, field, None)) for field in fields)))
                found = airing[key]
                episode = found["next"]
                season = episode.get("season") if category == "tv-shows" else None
                pool.append({
                    "key": key, "category": category, "label": LABELS[category],
                    "title": (found["schedule"].get("show") or best.title).strip()[:200],
                    "library_title": best.title.strip()[:200], "year": best.year,
                    "image": _safe_image(best.poster_url),
                    "network": str(found["schedule"].get("network") or "")[:60] or None,
                    "next": {"date": episode["date"],
                             "what": f"S{season} E{episode['number']}" if season else f"Episode {episode['number']}"},
                    "members": len({entry.user_id for entry in members}),
                })
    pool.sort(key=lambda show: (-show["members"], show["next"]["date"], show["title"].lower()))
    pool = pool[:POOL_LIMIT]
    _POOL.update({"pool": pool, "day": today, "at": clock.monotonic()})
    return pool


def suggestions(db: Session, user: models.User, today: date) -> list[dict]:
    from .for_you import normalize_title, owned_titles
    owned = owned_titles(db, user.id, ("tv-shows", "anime"))
    mine = {normalize_title(title) for titles in owned.values() for title in titles}
    picks = []
    for show in airing_pool(db, today):
        if normalize_title(show["title"]) in mine or normalize_title(show["library_title"]) in mine:
            continue
        # Counts under two members could point at one person's shelf, so they aren't shown.
        picks.append({**{k: v for k, v in show.items() if k != "library_title"},
                      "members": show["members"] if show["members"] >= 2 else None})
        if len(picks) >= SUGGEST_LIMIT:
            break
    return picks


def save_suggestion(db: Session, user: models.User, key: str, today: date) -> dict:
    """Copy a show airing this week into the member's library as not finished yet ("watching")."""
    from .for_you import LIBRARY, _safe_image, _shareable_ids, normalize_title
    found = next((show for show in airing_pool(db, today) if show["key"] == key), None)
    if found is None:
        raise LookupError("That show isn't on this week's list any more. Reload and try another.")
    category = found["category"]
    model, fields = LIBRARY[category]
    for entry in db.query(model).filter(model.user_id == user.id).all():
        if normalize_title(entry.title) in (normalize_title(found["title"]), normalize_title(found["library_title"])):
            return {"state": "existing", "category": category, "item_id": entry.id, "title": entry.title}
    from . import episode_calendar
    entries = [entry for entry in db.query(model).filter(model.user_id.in_(_shareable_ids(db, category))).all()
               if (entry.title or "").strip() and episode_calendar.airing_key(category, entry.title, entry.year) == key]
    if not entries:
        raise LookupError("That show isn't on this week's list any more. Reload and try another.")
    source = max(entries, key=lambda entry: (bool(_safe_image(entry.poster_url)),
                                             sum(bool(getattr(entry, field, None)) for field in fields)))
    # Only public details are copied (title, year, seasons, poster); ratings and notes stay with their owner.
    payload = {field: getattr(source, field, None) for field in fields}
    payload["poster_url"] = _safe_image(payload.get("poster_url"))
    record = model(user_id=user.id, watched=False, **payload)
    db.add(record)
    row = _row(db, user.id)
    row.saved_count = (row.saved_count or 0) + 1
    db.commit()
    db.refresh(record)
    count("saved")
    return {"state": "created", "category": category, "item_id": record.id, "title": record.title}


# ---------------------------------------------------------------- the card

def _reminder(row: Optional[models.WeekOnePlan]) -> Optional[dict]:
    if row is None or row.remind_on is None:
        return None
    return {"date": row.remind_on.isoformat(), "status": row.reminder_status or "set"}


def _has_push(db: Session, user_id: int) -> bool:
    return db.query(models.PushSubscription.id).filter(models.PushSubscription.user_id == user_id).first() is not None


def email_offer(user: models.User) -> bool:
    from . import digest
    return bool(user.is_verified and digest.mail_configured())


def build(db: Session, user: models.User, today: date, now: Optional[datetime] = None) -> Optional[dict]:
    """The card for today, or None. Looking doesn't count as seen."""
    now = now or _now()
    number = day_number(user, today)
    if number is None:
        return None
    row = get_row(db, user.id)
    if row is not None and row.hidden_at is not None:
        return None
    if _library_size(db, user.id) < MIN_TITLES:
        return None
    items = week_items(db, user, today)
    picks = suggestions(db, user, today) if len(items) < SUGGEST_BELOW else []
    future_days = sorted({item["date"] for item in items if item["date"] > today.isoformat()})
    reminder = _reminder(row)
    if reminder and reminder["status"] == "sent" and row.back_at is None and row.reminder_sent_at and now > row.reminder_sent_at:
        row.back_at = now  # the email brought them back (or they came back anyway; either way it was on time)
        db.commit()
        count("back_after_email")
    return {
        "day": number,
        "today": today.isoformat(),
        "days": _days(items, today),
        "count": len(items),
        "suggestions": picks,
        "reminder": reminder,
        "remind_day": future_days[0] if future_days else None,
        "offer": {"email": email_offer(user), "push": not _has_push(db, user.id)},
    }


def mark_seen(db: Session, user: models.User, today: date, now: Optional[datetime] = None) -> bool:
    """The card reached the screen. The first time counts as seen; a later day of the week counts as a return."""
    now = now or _now()
    if day_number(user, today) is None:
        return False
    row = _row(db, user.id)
    changed = False
    if row.first_seen_on is None:
        row.first_seen_on = today
        count("seen")
        changed = True
    elif today > row.first_seen_on and row.returned_at is None:
        row.returned_at = now
        count("returned")
        changed = True
    if row.last_seen_on != today:
        row.last_seen_on = today
        changed = True
    if changed:
        db.commit()
    return True


def set_reminder(db: Session, user: models.User, day: date, today: date, tz_minutes: int,
                 now: Optional[datetime] = None) -> dict:
    """One email on ``day`` at about 5 pm the member's time, naming what's out that day."""
    now = now or _now()
    if day_number(user, today) is None:
        raise ValueError("The first-week reminder is only for new accounts.")
    if not email_offer(user):
        raise ValueError("Confirm your email address first, then try again.")
    if not today < day <= today + timedelta(days=WEEK_DAYS - 1):
        raise ValueError("Pick a day later this week.")
    if not any(item["date"] == day.isoformat() for item in week_items(db, user, today)):
        raise ValueError("Nothing from your library is out that day.")
    tz_minutes = max(-14 * 60, min(14 * 60, int(tz_minutes)))
    row = _row(db, user.id)
    if row.reminder_status == "sent" and row.remind_on == day:
        return _reminder(row)
    row.remind_on = day
    row.remind_at = datetime.combine(day, time(REMIND_HOUR)) - timedelta(minutes=tz_minutes)
    row.reminder_status = "set"
    row.reminder_set_at = now
    row.reminder_sent_at = None
    db.commit()
    count("email_set")
    return _reminder(row)


def cancel_reminder(db: Session, user: models.User) -> bool:
    row = get_row(db, user.id)
    if row is None or row.reminder_status != "set":
        return False
    row.remind_on = row.remind_at = None
    row.reminder_status = None
    db.commit()
    count("email_cancel")
    return True


def hide(db: Session, user: models.User, now: Optional[datetime] = None) -> bool:
    row = _row(db, user.id)
    if row.hidden_at is None:
        row.hidden_at = now or _now()
        db.commit()
        count("hidden")
    return True


def note_push(db: Session, user: models.User, now: Optional[datetime] = None) -> bool:
    """Notifications were turned on from the card. Counted once, and only when a device is really on."""
    if not _has_push(db, user.id):
        return False
    row = _row(db, user.id)
    if row.push_at is None:
        row.push_at = now or _now()
        db.commit()
        count("push_on")
    return True


# ---------------------------------------------------------------- the reminder email

def _link(path: str) -> str:
    from .digest import app_url
    joiner = "&" if "?" in path else "?"
    return f"{app_url()}{path}{joiner}{UTM}"


def build_email(username: str, day: date, items: list[dict], unsubscribe_url: str) -> tuple[str, str, str]:
    first = items[0]
    if len(items) == 1:
        subject = (f"{first['title']} {first['what']} is out today" if first["kind"] == "episode"
                   else f"{first['title']} is out today")
    else:
        subject = f"{first['title']} and {len(items) - 1} more from your list are out today"
    subject = " ".join(subject.split())[:150]  # library titles are member-typed: one line, bounded
    home = _link("/")
    rows = []
    for item in items[:8]:
        image = item.get("image")
        cover = (f'<img src="{escape(image, quote=True)}" width="44" height="66" alt="" '
                 'style="display:block;width:44px;height:66px;object-fit:cover;border-radius:6px;background:#e9e5f5">'
                 if image else '<div style="width:44px;height:66px;border-radius:6px;background:#e9e5f5"></div>')
        detail = " · ".join(part for part in (item.get("label"), item["what"] if item["kind"] == "episode" else "Release day") if part)
        name = escape(item["title"])
        if item.get("url"):
            name = (f'<a href="{escape(_link(item["url"]), quote=True)}" style="color:#1f1640;text-decoration:none">{name}</a>')
        rows.append(
            '<tr><td style="padding:10px 12px 10px 0;border-top:1px solid #e9e5f5;vertical-align:top;width:44px">'
            f'{cover}</td><td style="padding:10px 0;border-top:1px solid #e9e5f5;vertical-align:top">'
            f'<div style="color:#1f1640;font-weight:700;font-size:15px">{name}</div>'
            f'<div style="color:#5b5675;font-size:13px;line-height:1.5">{escape(detail)}</div></td></tr>')
    weekday = day.strftime("%A")
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">Your reminder</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">It’s {escape(weekday)}, {escape(username)}</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        '<p style="color:#1f1640;font-size:15px;line-height:1.6">You asked us to remind you today. '
        f'{"This is" if len(items) == 1 else "These are"} out:</p>'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>'
        f'<p style="margin:24px 0 8px"><a href="{escape(home, quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Mark what you watched</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">This is the one reminder you asked for '
        'on your OmniTrackr home screen. We won’t send another unless you ask. Air dates come from TVmaze and AniList and can move. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a>.</p>'
        '</div></div></body></html>'
    )
    text = "\n".join(
        [f"Hi {username},", "", "You asked us to remind you today. Out today:", ""]
        + [f"- {item['title']} ({item['what'] if item['kind'] == 'episode' else 'release day'})" for item in items[:8]]
        + ["", f"Mark what you watched: {home}", "",
           "This is the one reminder you asked for on your OmniTrackr home screen. We won't send another unless you ask.",
           f"Unsubscribe from product updates: {unsubscribe_url}"])
    return subject, html, text


def email_for(db: Session, user: models.User, day: date) -> Optional[tuple[str, str, str, str]]:
    """(subject, html, text, unsubscribe_url), or None when nothing of theirs is out that day any more."""
    from .announcements import unsubscribe_token
    from .digest import app_url
    items = [item for item in week_items(db, user, day) if item["date"] == day.isoformat()]
    if not items:
        return None
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    subject, html, text = build_email(user.username, day, items, unsubscribe_url)
    return subject, html, text, unsubscribe_url


def allowance(db: Session, now: datetime) -> int:
    """How many may go out now: inside this email's own daily limit and the shared daily cap."""
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_mine = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_mine, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


def due(db: Session, now: datetime) -> list[models.WeekOnePlan]:
    return db.query(models.WeekOnePlan).filter(
        models.WeekOnePlan.reminder_status == "set", models.WeekOnePlan.remind_at <= now,
    ).order_by(models.WeekOnePlan.remind_at).limit(200).all()


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


async def send_due(session_factory, now: Optional[datetime] = None, sender=_send) -> dict:
    from .digest import mail_configured
    now = now or _now()
    result = {"sent": 0, "failed": 0, "dropped": 0, "limited": False}
    if not mail_configured() and sender is _send:
        return result
    db = session_factory()
    try:
        from .email_quota import lock_email_budget
        for row in due(db, now):
            user = db.get(models.User, row.user_id)
            if (user is None or not user.is_active or not user.is_verified or row.remind_on is None
                    or now - row.remind_at > LATE):
                row.reminder_status = "dropped"
                db.commit()
                count("dropped")
                result["dropped"] += 1
                continue
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                result["limited"] = True
                break  # still inside its window; the next run tries again
            try:
                built = email_for(db, user, row.remind_on)
            except Exception as error:
                print(f"Week-one reminder for user {user.id} couldn't be built: {error}")
                db.rollback()
                continue
            if built is None:
                row.reminder_status = "dropped"
                db.commit()
                count("dropped")
                result["dropped"] += 1
                continue
            # Claim first so an overlapping run can never send twice.
            db.add(models.EmailCampaignSend(campaign_key=f"{SEND_PREFIX}{row.remind_on.isoformat()}",
                                            user_id=user.id, status="sent", sent_at=now))
            row.reminder_status = "sent"
            row.reminder_sent_at = now
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            subject, html, _text, unsubscribe_url = built
            try:
                await sender(user.email, subject, html, unsubscribe_url)
                result["sent"] += 1
                count("sent")
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Week-one reminder to user {user.id} failed: {error}")
                row.reminder_status = "failed"
                db.commit()
                result["failed"] += 1
        return result
    finally:
        db.close()


async def week_one_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await send_due(SessionLocal)
            if result["sent"] or result["failed"]:
                print(f"Week-one reminders: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Week-one reminder check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "weekone", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    pending = int(db.query(func.count(models.WeekOnePlan.id)).filter(
        models.WeekOnePlan.reminder_status == "set").scalar() or 0)
    return {"counts": {key: int(counts.get(key) or 0) for key in COUNTERS},
            "labels": COUNTERS, "pending_reminders": pending}
