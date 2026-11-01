"""Release calendars: Release Radar dates as feeds people subscribe to in their own calendar app.

Two kinds of feed, both plain iCalendar (RFC 5545) that Google Calendar, Apple
Calendar and Outlook refresh on their own:

* Public feeds, one per Release Radar section plus a highlights feed. Anyone can
  subscribe, no account needed. Every event links back to its Release Radar card.
* A member's private feed: only releases connected to their library (the same
  matching as "Coming up for you" and release day alerts). The address holds a
  random token stored in ``calendar_feeds``; turning it off deletes the row and a
  reset swaps the token, so an old address stops working at once.

Feeds are built from Release Radar's cache only, so a calendar app polling them
never makes OmniTrackr call an outside service.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from typing import Iterable, Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from . import models
from . import release_radar as radar
from .digest import app_url
from .for_you import RADAR_LABELS, LibraryMatcher, normalize_title, owned_titles, radar_pool
from .release_alerts import item_link

PAST_DAYS = 14
AHEAD_DAYS = 120
HIGHLIGHTS_PER_SECTION = 15
MEMBER_LIMIT = 200
REFRESH_HOURS = 12
FETCH_RECORD_EVERY = timedelta(hours=6)
FEED_NAMES = {
    "all": "OmniTrackr Release Radar highlights",
    "movies": "OmniTrackr new movies",
    "tv": "OmniTrackr TV premieres",
    "anime": "OmniTrackr anime season",
    "games": "OmniTrackr game releases",
}
FEED_DESCRIPTIONS = {
    "all": "The most followed new movies, TV premieres, anime and games from OmniTrackr's Release Radar.",
    "movies": "New movie releases from OmniTrackr's Release Radar.",
    "tv": "Series premieres and new seasons from OmniTrackr's Release Radar.",
    "anime": "Every show in the current and next anime season, from OmniTrackr's Release Radar.",
    "games": "Video games with a firm release date, from OmniTrackr's Release Radar.",
}
SUMMARY_SUFFIX = {"movies": "premieres", "tv": "premieres", "anime": "premieres", "games": "out"}


# ---------------------------------------------------------------- iCalendar text

def _escape(value: str) -> str:
    return (str(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _fold(line: str) -> str:
    """Split a content line into 75-octet pieces without breaking a UTF-8 character."""
    out, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        limit = 75 if not out else 74  # continuation lines start with a space
        if size + width > limit:
            out.append(current)
            current, size = "", 0
        current += char
        size += width
    out.append(current)
    return "\r\n ".join(out)


def _event_lines(event: dict, stamp: str) -> list[str]:
    if event.get("start"):
        # A timed event in UTC; calendar apps show it in the reader's own time zone.
        start = datetime.strptime(event["start"], "%Y-%m-%dT%H:%M:%SZ")
        end = start + timedelta(minutes=event.get("minutes") or 30)
        when = [f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}", f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}"]
    else:
        day = date.fromisoformat(event["date"])
        when = [f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}"]
    lines = [
        "BEGIN:VEVENT",
        f"UID:{event['uid']}",
        f"DTSTAMP:{stamp}",
        *when,
        f"SUMMARY:{_escape(event['summary'])}",
        f"DESCRIPTION:{_escape(event['description'])}",
        "TRANSP:TRANSPARENT",
    ]
    url = event.get("url") or ""
    # Links come partly from TVmaze and AniList. One with a line break or space in it
    # could start a new property in the feed, so it is left out.
    if url.startswith(("https://", "http://")) and url.isprintable() and not any(ch.isspace() for ch in url):
        lines.append(f"URL:{url}")
    lines.append("END:VEVENT")
    return lines


def build_ics(name: str, description: str, events: Iterable[dict], now: Optional[datetime] = None) -> str:
    stamp = (now or datetime.utcnow()).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OmniTrackr//Release Radar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        f"X-WR-CALDESC:{_escape(description)}",
        f"REFRESH-INTERVAL;VALUE=DURATION:PT{REFRESH_HOURS}H",
        f"X-PUBLISHED-TTL:PT{REFRESH_HOURS}H",
    ]
    for event in events:
        lines += _event_lines(event, stamp)
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------- events from Release Radar

def _in_range(item: dict, today: date) -> bool:
    try:
        day = date.fromisoformat(item.get("date") or "")
    except ValueError:
        return False
    return today - timedelta(days=PAST_DAYS) <= day <= today + timedelta(days=AHEAD_DAYS)


def event_for(item: dict, reason: str = "") -> dict:
    """One all-day event for a Release Radar item. The UID is stable, so moved dates update in place."""
    category = item["category"]
    base = app_url()
    label = RADAR_LABELS.get(category, "Release")
    summary = f"{item['title']} {SUMMARY_SUFFIX.get(category, 'out')}"
    details = [part for part in [reason, *(item.get("details") or [])[:2], *(item.get("platforms") or [])[:3]] if part]
    note = f" ({item['date_note']})" if item.get("date_note") else ""
    url = f"{base}{item_link(item)}"
    description = "\n".join([
        f"{label} on OmniTrackr's Release Radar{note}.",
        *details,
        "",
        f"Track it, or see what else is coming: {url}",
        "Dates can move. Your calendar picks up changes on its next refresh.",
    ])
    key = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in item.get("key") or item["title"])[:80]
    return {
        "uid": f"{category}-{key}@omnitrackr.xyz",
        "date": item["date"],
        "summary": summary,
        "description": description,
        "url": url,
    }


def _sorted_events(items: Iterable[tuple[dict, str]]) -> list[dict]:
    seen, events = set(), []
    for item, reason in sorted(items, key=lambda pair: (pair[0].get("date") or "", pair[0]["title"].lower())):
        event = event_for(item, reason)
        if event["uid"] in seen:
            continue
        seen.add(event["uid"])
        events.append(event)
    return events


def public_events(pool: list[dict], feed: str, today: date) -> list[dict]:
    """Events for a public feed: one section in full, or the most followed titles of each for "all"."""
    dated = [item for item in pool if _in_range(item, today) and (item.get("title") or "").strip()]
    if feed != "all":
        return _sorted_events((item, "") for item in dated if item["category"] == feed)
    chosen = []
    for category in radar.CATEGORY_ORDER:
        by_window: dict[str, list[dict]] = {}
        for item in dated:
            if item["category"] == category:
                by_window.setdefault(item.get("window") or "", []).append(item)
        for items in by_window.values():
            chosen += sorted(items, key=lambda i: -i.get("popularity", 0))[:HIGHLIGHTS_PER_SECTION]
    return _sorted_events((item, "") for item in chosen)


def member_matches(db: Session, user_id: int, pool: list[dict], today: date) -> list[tuple[dict, str]]:
    """(Release Radar item, reason) for releases connected to a member's library."""
    owned = owned_titles(db, user_id, ("movies", "tv-shows", "anime", "video-games"))
    matcher = LibraryMatcher(title for titles in owned.values() for title in titles)
    found = []
    for item in pool:
        if not _in_range(item, today) or not (item.get("title") or "").strip():
            continue
        names = [item["title"]] + ([item["alt_title"]] if item.get("alt_title") else [])
        hit = matcher.find(names)
        if hit is None:
            continue
        reason = "In your library" if normalize_title(hit) == normalize_title(item["title"]) else f"Because you track {hit}"
        found.append((item, reason))
    return found


def member_events(db: Session, user_id: int, pool: list[dict], today: date) -> list[dict]:
    """Releases connected to a member's library: the title itself, a new season or a sequel."""
    return _sorted_events(member_matches(db, user_id, pool, today))[:MEMBER_LIMIT]


def member_feed_events(db: Session, user: models.User, pool: list[dict], today: date,
                       include_episodes: bool) -> list[dict]:
    """The whole private feed: library releases, plus weekly episodes when the member asked for them."""
    matches = member_matches(db, user.id, pool, today)
    events = _sorted_events(matches)[:MEMBER_LIMIT]
    if include_episodes:
        from .episode_calendar import member_episode_events
        premieres = {(normalize_title(item["title"]), item["date"]) for item, _ in matches}
        events += member_episode_events(db, user, today, skip=premieres)
    return events


def pool_for(today: date, client=None) -> list[dict]:
    """Every cached Release Radar item for the current and next period of each section."""
    return radar_pool(today, client)


# ---------------------------------------------------------------- subscribe links

def public_feed_path(feed: str) -> str:
    return "/calendar/release-radar.ics" if feed == "all" else f"/calendar/release-radar/{feed}.ics"


def subscribe_links(path: str, name: str) -> dict:
    """https, webcal, Google Calendar and Outlook addresses for one feed path."""
    https_url = f"{app_url()}{path}"
    webcal_url = "webcal://" + https_url.split("://", 1)[1]
    return {
        "url": https_url,
        "webcal": webcal_url,
        "google": "https://calendar.google.com/calendar/r?cid=" + quote(webcal_url, safe=""),
        "outlook": ("https://outlook.live.com/calendar/0/addfromweb?url=" + quote(https_url, safe="")
                    + "&name=" + quote(name, safe="")),
    }


# ---------------------------------------------------------------- member feeds

def feed_for(db: Session, user_id: int) -> Optional[models.CalendarFeed]:
    return db.query(models.CalendarFeed).filter_by(user_id=user_id).first()


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def set_episodes(db: Session, user_id: int, include: bool) -> models.CalendarFeed:
    feed = enable(db, user_id)
    feed.include_episodes = bool(include)
    db.commit()
    db.refresh(feed)
    return feed


def enable(db: Session, user_id: int) -> models.CalendarFeed:
    feed = feed_for(db, user_id)
    if feed is None:
        feed = models.CalendarFeed(user_id=user_id, token=_new_token())
        db.add(feed)
        db.commit()
        db.refresh(feed)
    return feed


def reset(db: Session, user_id: int) -> models.CalendarFeed:
    feed = feed_for(db, user_id)
    if feed is None:
        return enable(db, user_id)
    feed.token = _new_token()
    feed.last_fetched_at = None
    db.commit()
    db.refresh(feed)
    return feed


def disable(db: Session, user_id: int) -> bool:
    removed = db.query(models.CalendarFeed).filter_by(user_id=user_id).delete()
    db.commit()
    return bool(removed)


def member_feed_path(feed: models.CalendarFeed) -> str:
    # No "/" right before the token: the bot filter scans paths for prefixes such as "/admin".
    return f"/calendar/u/feed-{feed.token}.ics"


def state(db: Session, user_id: int) -> dict:
    feed = feed_for(db, user_id)
    if feed is None:
        return {"enabled": False}
    include = feed.include_episodes is not False
    result = {
        "enabled": True,
        "include_episodes": include,
        "links": subscribe_links(member_feed_path(feed), "OmniTrackr: my releases"),
        "last_fetched_at": feed.last_fetched_at.isoformat() + "Z" if feed.last_fetched_at else None,
    }
    if include:
        from .episode_calendar import upcoming_count
        user = db.get(models.User, user_id)
        result["episodes_soon"] = upcoming_count(db, user, radar.today_utc()) if user else 0
    return result


def member_for_token(db: Session, token: str) -> Optional[models.User]:
    if not token or len(token) > 64 or not all(ch.isalnum() or ch in "-_" for ch in token):
        return None
    feed = db.query(models.CalendarFeed).filter_by(token=token).first()
    if feed is None:
        return None
    user = db.get(models.User, feed.user_id)
    if user is None or not user.is_active:
        return None
    now = datetime.utcnow()
    if feed.last_fetched_at is None or now - feed.last_fetched_at >= FETCH_RECORD_EVERY:
        # Only a coarse "still subscribed" signal for Site stats; calendar apps poll often.
        feed.last_fetched_at = now
        try:
            db.commit()
        except Exception:
            db.rollback()
    return user
