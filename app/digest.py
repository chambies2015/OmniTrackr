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
from datetime import date, datetime, timedelta, timezone
from html import escape

from sqlalchemy import or_
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


# Where a member turned the weekly email on or off. Site stats counts each switch by place
# (anonymous daily totals, like the sign-up funnel) so the owner can see which prompt works.
SOURCES = {
    "signup": "the sign-up form",
    "start": "the start page",
    "first_week": "first-week steps",
    "dashboard": "the library home",
    "account": "Account settings",
    "email_link": "a link in an email",
}
OFF_SOURCES = {"account", "dashboard", "email_link"}


def record_switch(on: bool, source: str | None) -> bool:
    """Count one opt-in or opt-out in the daily traffic counters (kind "email"). Never raises."""
    if source not in SOURCES:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "email", f"weekly_{'on' if on else 'off'}_{source}")] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def subscribe(db: Session, user_id: int, source: str | None = None):
    existing = subscription_for(db, user_id)
    if existing:
        return existing
    row = models.EmailDigestSubscription(user_id=user_id, token=secrets.token_urlsafe(32))
    db.add(row)
    db.commit()
    record_switch(True, source)
    return row


def unsubscribe_user(db: Session, user_id: int, source: str | None = None) -> bool:
    removed = db.query(models.EmailDigestSubscription).filter_by(user_id=user_id).delete()
    db.commit()
    if removed:
        record_switch(False, source)
    return bool(removed)


def unsubscribe_token(db: Session, token: str) -> bool:
    if not token or len(token) > 64:
        return False
    removed = db.query(models.EmailDigestSubscription).filter_by(token=token).delete()
    db.commit()
    if removed:
        record_switch(False, "email_link")
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
        f'<div style="color:#6f6a8a;font-size:13px;margin-top:6px">by {escape(review.get("username") or "a member")} · '
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


def challenge_line(db: Session, user_id: int, today: date) -> dict | None:
    """This month's challenge for the weekly email: progress when joined, an invitation otherwise.

    None when there is nothing useful to say: the challenge is already complete, the month
    is nearly over for someone who hasn't joined, or the month has no curated challenge.
    """
    from . import challenges
    month = challenges.month_key(today)
    left = challenges.days_left(month, today)
    entry = challenges.get_entry(db, user_id, month)
    challenge = challenges.challenge_for(month)
    if entry is None:
        if not challenges.is_curated(month) or left < 7:
            return None
        return {"joined": False, "name": challenge["name"], "tagline": challenge["tagline"],
                "month_name": challenges.MONTH_NAMES[today.month - 1], "days_left": left,
                "total_steps": len(challenge["steps"])}
    steps = challenges.progress(db, user_id, month)
    if entry.completed_at is not None or not steps or all(step["done"] for step in steps) or left <= 0:
        return None
    upcoming = next(step for step in steps if not step["done"])
    return {"joined": True, "name": challenge["name"], "days_left": left,
            "done_steps": sum(1 for step in steps if step["done"]), "total_steps": len(steps),
            "next": upcoming["label"], "next_count": upcoming["count"], "next_target": upcoming["target"]}


STEP_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def _challenge_section(challenge: dict | None, base: str) -> tuple[str, list[str]]:
    """'This month's challenge' block; empty when there is none."""
    if not challenge:
        return "", []
    url = f"{base}/#challenge"
    days = f'{challenge["days_left"]} day{"" if challenge["days_left"] == 1 else "s"} left'
    if challenge["joined"]:
        next_step = challenge["next"]
        if challenge["next_target"] > 1:
            next_step += f' ({challenge["next_count"]} of {challenge["next_target"]})'
        summary = f'{challenge["done_steps"]} of {challenge["total_steps"]} steps done, {days}.'
        body = (f'<p style="color:#3b3557;font-size:14px;line-height:1.6;margin:0"><strong>{escape(challenge["name"])}</strong>: '
                f'{escape(summary)}<br>Next up: {escape(next_step)}.</p>')
        link_label = "See your challenge"
        text = [f"This month's challenge, {challenge['name']}: {summary} Next up: {next_step}. {url}", ""]
    else:
        count = challenge["total_steps"]
        steps = f'{STEP_WORDS.get(count, str(count))} small step{"" if count == 1 else "s"}'.capitalize()
        body = (f'<p style="color:#3b3557;font-size:14px;line-height:1.6;margin:0"><strong>{escape(challenge["name"])}</strong>: '
                f'{escape(challenge["tagline"])} {escape(steps)}, {escape(days)}, and anything you finished this month already counts.</p>')
        link_label = f'Take the {challenge["month_name"]} challenge'
        text = [f"This month's challenge, {challenge['name']}: {challenge['tagline']} {days}. {url}", ""]
    html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">This month\'s challenge</h2>' + body +
            f'<p style="margin:8px 0 0"><a href="{escape(url, quote=True)}" style="color:#6d28d9;font-weight:700">{escape(link_label)}</a></p>')
    return html, text


def _badge_section(badge: dict | None, base: str) -> tuple[str, list[str]]:
    """'Closest badge' line: the started badge nearest its next tier; empty when none is close."""
    if not badge:
        return "", []
    url = f"{base}/#badges"
    line = (f'{badge["action"]} to earn {badge["name"]} {badge["tier_name"].lower()} '
            f'({badge["count"]} of {badge["target"]} so far).')
    html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">Your next badge</h2>'
            f'<p style="color:#3b3557;font-size:14px;line-height:1.6;margin:0">{escape(badge["emoji"])} {escape(line)}</p>'
            f'<p style="margin:8px 0 0"><a href="{escape(url, quote=True)}" style="color:#6d28d9;font-weight:700">See your badges</a></p>')
    return html, [f"Your next badge: {line} {url}", ""]


def recap_line(db: Session, user_id: int, today: date) -> dict | None:
    """In December and January, the member's Year in Review when they finished something that year."""
    from . import year_in_review
    year = year_in_review.season_year(today)
    if year is None:
        return None
    finished = sum(year_in_review.finished_counts(db, user_id, year).values())
    return {"year": year, "finished": finished} if finished else None


def _recap_section(recap: dict | None, base: str) -> tuple[str, list[str]]:
    if not recap:
        return "", []
    year, finished = int(recap["year"]), int(recap["finished"])
    url = f"{base}/year-in-review/{year}#story"
    line = (f"You finished {finished} title{'s' if finished != 1 else ''} in {year}. Your recap is ready to play "
            "through, with a story image you can post.")
    html = (f'<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">Your {year} in review</h2>'
            f'<p style="color:#3b3557;font-size:14px;line-height:1.6;margin:0">{escape(line)}</p>'
            f'<p style="margin:8px 0 0"><a href="{escape(url, quote=True)}" style="color:#6d28d9;font-weight:700">Play your year</a></p>')
    return html, [f"Your {year} in review: {line} {url}", ""]


# ---------------------------------------------------------------- episodes and Next Up

EPISODE_SHOWS_SHOWN = 6


def episodes_this_week(db: Session, user, today: date) -> list[dict]:
    """New episodes of the member's unfinished shows in the next seven days, from the cached schedules."""
    from .episode_calendar import week_ahead
    return week_ahead(db, user, today)


def _episode_line(show: dict) -> str:
    episodes = show["episodes"]
    first = episodes[0]
    line = f"{first['code']} on {_day(first['date'])}"
    if first["name"]:
        line = f"{first['code']}, “{first['name']}”, on {_day(first['date'])}"
    if len(episodes) > 1:
        line += f" and {len(episodes) - 1} more this week"
    return line[:1].upper() + line[1:]


def _episodes_section(shows: list | None) -> tuple[str, list[str]]:
    """'New episodes this week' block; empty when none of the member's shows has one."""
    if not shows:
        return "", []
    shown = shows[:EPISODE_SHOWS_SHOWN]
    rows, text = [], ["New episodes this week:"]
    for show in shown:
        line = _episode_line(show)
        rows.append(
            '<tr><td style="padding:10px 0;border-top:1px solid #e9e5f5">'
            f'<a href="{escape(show["url"], quote=True)}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">{escape(show["title"])}</a>'
            f'<div style="color:#5b5675;font-size:13px">{escape(line)}</div></td></tr>'
        )
        text.append(f"- {show['title']}: {line}")
    if len(shows) > len(shown):
        others = len(shows) - len(shown)
        rows.append('<tr><td style="padding:8px 0;border-top:1px solid #e9e5f5;color:#5b5675;font-size:13px">'
                    f'Plus {others} more show{"s" if others != 1 else ""} on your list.</td></tr>')
        text.append(f"Plus {others} more show{'s' if others != 1 else ''} on your list.")
    text.append("")
    html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">New episodes this week</h2>'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>')
    return html, text


NEXT_UP_LABELS = {"movies": "Movie", "tv-shows": "TV show", "anime": "Anime", "video-games": "Game",
                  "music": "Album", "books": "Book", "manga": "Manga", "podcasts": "Podcast", "audiobooks": "Audiobook"}


def next_up_line(db: Session, user_id: int) -> dict | None:
    """The first unfinished title in the member's Next Up queue, with how many wait behind it."""
    from . import title_pages
    entries = db.query(models.NextUpItem.category, models.NextUpItem.item_id).filter(
        models.NextUpItem.user_id == user_id).order_by(models.NextUpItem.position, models.NextUpItem.id).limit(50).all()
    wanted: dict[str, list[int]] = {}
    for category, item_id in entries:
        if category in NEXT_UP_LABELS and category in title_pages.LIBRARY_TO_KIND:
            wanted.setdefault(category, []).append(item_id)
    open_titles = {}
    for category, ids in wanted.items():
        kind = title_pages.LIBRARY_TO_KIND[category]
        model, done = title_pages.KINDS[kind][0], getattr(title_pages.KINDS[kind][0], title_pages.COMPLETE_FIELD[kind])
        for item_id, title in db.query(model.id, model.title).filter(
                model.user_id == user_id, model.id.in_(ids), or_(done == False, done.is_(None))):  # noqa: E712
            if (title or "").strip():
                open_titles[(category, item_id)] = title.strip()
    queue = [(category, item_id) for category, item_id in entries if (category, item_id) in open_titles]
    if not queue:
        return None
    category, item_id = queue[0]
    return {"title": open_titles[queue[0]], "label": NEXT_UP_LABELS[category], "waiting": len(queue) - 1}


def _next_up_section(next_up: dict | None, base: str) -> tuple[str, list[str]]:
    """'Next in your queue' nudge; empty when the queue is empty or all finished."""
    if not next_up:
        return "", []
    url = f"{base}/#next-up"
    waiting = next_up["waiting"]
    after = f" {waiting} more {'title waits' if waiting == 1 else 'titles wait'} behind it." if waiting else ""
    line = f"{next_up['title']} ({next_up['label']}) is at the top.{after}"
    html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">Next in your queue</h2>'
            f'<p style="color:#3b3557;font-size:14px;line-height:1.6;margin:0">{escape(line)}</p>'
            f'<p style="margin:8px 0 0"><a href="{escape(url, quote=True)}" style="color:#6d28d9;font-weight:700">Open Next Up</a></p>')
    return html, [f"Next in your queue: {line} {url}", ""]



def memories_line(db: Session, user, today: date) -> list[dict]:
    from .memories import week_in_past_years
    return week_in_past_years(db, user, today)


def _memories_section(found: list | None) -> tuple[str, list[str]]:
    """'This week in past years': finishes from the same week in earlier years. Never forces a send."""
    if not found:
        return "", []
    lines = []
    for memory in found:
        when = "A year ago" if memory["ago"] == 1 else f"{memory['ago']} years ago"
        line = memory["line"]
        lines.append(f"{when}: {line[0].lower()}{line[1:]}" if line.startswith("You ") else f"{when}: {line}")
    items = "".join(f'<li style="margin:0 0 6px">{escape(line)}</li>' for line in lines)
    html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">This week in past years</h2>'
            f'<ul style="color:#3b3557;font-size:14px;line-height:1.6;margin:0;padding-left:20px">{items}</ul>')
    return html, ["This week in past years:"] + [f"- {line}" for line in lines] + [""]

def following_line(db: Session, user, now: datetime) -> list[dict]:
    from .follows import email_items
    return email_items(db, user, now)


def _following_text(item: dict) -> str:
    rating = f" ({item['rating']:g}/10)" if item.get("rating") is not None else ""
    if item["kind"] == "review":
        return f"{item['username']} reviewed {item['title']}{rating}"
    if item["kind"] == "collection":
        return f"{item['username']} published a collection: {item['title']}"
    verb = "revisited" if item.get("repeat") else "finished"
    return f"{item['username']} {verb} {item['title']}{rating}"


def _following_section(items: list | None, base: str) -> tuple[str, list[str]]:
    """'From people you follow': public reviews, collections and diary entries. Never forces a send."""
    if not items:
        return "", []
    rows, text = [], ["From people you follow:"]
    for item in items:
        line = _following_text(item)
        rest = line[len(item["username"]):]
        link = escape(base + item["url"], quote=True)
        rows.append(f'<li style="margin:0 0 6px"><strong>{escape(item["username"])}</strong>'
                    f'<a href="{link}" style="color:#1f1640;text-decoration:none">{escape(rest)}</a></li>')
        text.append(f"- {line}: {base}{item['url']}")
    html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">From people you follow</h2>'
            f'<ul style="color:#3b3557;font-size:14px;line-height:1.6;margin:0;padding-left:18px">{"".join(rows)}</ul>')
    return html, text + [""]

# ---------------------------------------------------------------- friend activity

FRIEND_WINDOW = timedelta(days=7)
FRIENDS_SHOWN = 4
TITLES_PER_FRIEND = 2
DONE_WORD = {"watched": "watched", "played": "played", "listened": "listened", "read": "read"}


def friend_activity(db: Session, user_id: int, now: datetime) -> list[dict]:
    """What the member's friends added to their libraries in the last week.

    Uses only what friends can already open from the Friends panel: active friends,
    categories they have not made private, and each title's added date, rating and
    finished flag. Completion moments and the Activity Journal stay private.
    """
    from sqlalchemy import func, or_
    from . import title_pages
    pairs = db.query(models.Friendship.user1_id, models.Friendship.user2_id).filter(
        or_(models.Friendship.user1_id == user_id, models.Friendship.user2_id == user_id)).all()
    ids = {a if b == user_id else b for a, b in pairs} - {user_id}
    if not ids:
        return []
    friends = {friend.id: friend for friend in db.query(models.User).filter(
        models.User.id.in_(ids), models.User.is_active.is_(True)).all()}
    since = now - FRIEND_WINDOW
    counts: dict[int, int] = {}
    visible_kinds: dict[int, list[str]] = {}
    for kind, (model, _review, library, _label, _extra) in title_pages.KINDS.items():
        flag = library.replace("-", "_") + "_private"
        visible = [fid for fid, friend in friends.items() if not getattr(friend, flag, False)]
        if not visible:
            continue
        rows = db.query(model.user_id, func.count(model.id)).filter(
            *_recently_added(model, visible, since, now)).group_by(model.user_id).all()
        for fid, count in rows:
            counts[fid] = counts.get(fid, 0) + count
            visible_kinds.setdefault(fid, []).append(kind)
    activity = []
    for fid in sorted(counts, key=lambda fid: (-counts[fid], friends[fid].username.lower())):
        titles = _friend_picks(db, fid, visible_kinds[fid], since, now) if len(activity) < FRIENDS_SHOWN else []
        activity.append({"username": friends[fid].username, "count": counts[fid], "titles": titles})
    return activity


def _recently_added(model, user_ids, since: datetime, now: datetime) -> tuple:
    from sqlalchemy import func
    return (model.user_id.in_(user_ids), model.added_at >= since, model.added_at <= now,
            model.title.isnot(None), func.trim(model.title) != "")


def _friend_picks(db: Session, friend_id: int, kinds: list[str], since: datetime, now: datetime) -> list[dict]:
    """A friend's best few additions this week: rated first, then finished, then newest."""
    from . import title_pages
    picks = []
    for kind in kinds:
        model, _review, _library, label, _extra = title_pages.KINDS[kind]
        done_field = title_pages.COMPLETE_FIELD[kind]
        done = getattr(model, done_field)
        for item in db.query(model).filter(*_recently_added(model, [friend_id], since, now)).order_by(
                model.rating.desc().nullslast(), done.desc(), model.added_at.desc(), model.id.desc()
        ).limit(TITLES_PER_FRIEND).all():
            finished = bool(getattr(item, done_field))
            picks.append((item.rating is not None, item.rating or 0, finished, item.added_at, item.id,
                          kind, item, label, DONE_WORD[done_field] if finished else None))
    titles = []
    for *_order, kind, item, label, done_word in sorted(picks, key=lambda pick: pick[:5], reverse=True)[:TITLES_PER_FRIEND]:
        path = title_pages.path_for_item(kind, item)
        if title_pages.find(db, kind, path.rsplit("/", 1)[1]) is None:
            path = None  # no public title page yet
        titles.append({"title": item.title.strip(), "label": label, "done": done_word,
                       "rating": item.rating, "path": path})
    return titles


def _and_list(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _friend_title(entry: dict) -> str:
    details = [entry["label"]]
    if entry["done"]:
        details.append(entry["done"])
    if entry["rating"] is not None:
        details.append(f'{entry["rating"]:g}/10')
    return f'{entry["title"]} ({", ".join(details)})'


def _friends_section(activity: list | None, base: str) -> tuple[str, list[str]]:
    """'New on your friends' shelves' block; empty when no friend added anything this week."""
    if not activity:
        return "", []
    shown = activity[:FRIENDS_SHOWN]
    rows, text = [], ["New on your friends' shelves:"]
    for friend in shown:
        parts_html, parts_text = [], []
        for entry in friend["titles"]:
            label = _friend_title(entry)
            parts_text.append(label)
            if entry["path"]:
                link = escape(base + entry["path"], quote=True)
                parts_html.append(f'<a href="{link}" style="color:#1f1640;font-weight:700;text-decoration:none">'
                                  f'{escape(entry["title"])}</a>{escape(label[len(entry["title"]):])}')
            else:
                parts_html.append(f'<strong>{escape(entry["title"])}</strong>{escape(label[len(entry["title"]):])}')
        extra = friend["count"] - len(friend["titles"])
        if extra > 0:
            more = f'{extra} more title{"s" if extra != 1 else ""}'
            parts_html.append(escape(more))
            parts_text.append(more)
        rows.append(f'<li style="margin:0 0 6px"><strong>{escape(friend["username"])}</strong> added '
                    + _and_list(parts_html) + '</li>')
        text.append(f'- {friend["username"]} added ' + _and_list(parts_text))
    others = len(activity) - len(shown)
    note = ""
    if others > 0:
        line = f'{others} more friend{"s" if others != 1 else ""} added titles too.'
        note = f'<p style="color:#5b5675;font-size:13px;margin:4px 0 0">{escape(line)}</p>'
        text.append(line)
    html = ('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 8px">New on your friends\' shelves</h2>'
            f'<ul style="color:#3b3557;font-size:14px;line-height:1.6;margin:0;padding-left:18px">{"".join(rows)}</ul>' + note)
    return html, text + [""]


def invite_nudge_due(user_id: int, now: datetime) -> bool:
    """About once a month per member (a different week for each), never every week."""
    return now.isocalendar().week % 4 == user_id % 4


def build_digest(username: str, report: dict, unsubscribe_url: str, spotlight: dict | None = None,
                 ask: dict | None = None, invite: bool = False, goals: list | None = None,
                 goals_year: int | None = None, challenge: dict | None = None,
                 badge: dict | None = None, recap: dict | None = None,
                 friends: list | None = None, episodes: list | None = None,
                 next_up: dict | None = None, past: list | None = None,
                 following: list | None = None) -> tuple[str, str, str] | None:
    """(subject, html, text) or None when there is nothing to send. `spotlight`, `ask`, `invite`, `goals`,
    `challenge`, `badge`, `recap`, `next_up`, `past` and `following` never force a send; friend activity and episodes can."""
    matches, popular = report["matches"], report["popular"]
    if not matches and not popular and not friends and not episodes:
        return None
    base = app_url()
    if matches:
        subject = f"Coming up for you: {matches[0]['title']}" + (f" and {len(matches) - 1} more" if len(matches) > 1 else "")
    elif episodes:
        subject = f"New this week: {episodes[0]['title']} {episodes[0]['episodes'][0]['code']}"
        if len(episodes) > 1:
            subject += f" and {len(episodes) - 1} more show{'s' if len(episodes) > 2 else ''}"
    elif friends:
        subject = f"New on your friends' shelves: {friends[0]['username']} added {friends[0]['titles'][0]['title']}"
    else:
        subject = f"This month on Release Radar: {popular[0]['title']} and more"
    sections = []
    text = [f"Hi {username},", ""]
    recap_html, recap_text = _recap_section(recap, base)
    if recap_html:
        sections.append(recap_html)
        text += recap_text
    if matches:
        sections.append('<h2 style="font-size:17px;color:#1f1640;margin:24px 0 4px">From your library</h2>'
                        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{_rows(matches, base)}</table>')
        text.append("From your library:")
        text += [f"- {c['title']} ({c['label']}, {_day(c.get('date'))}) - {c['reason']}" for c in matches]
        text.append("")
    episodes_html, episodes_text = _episodes_section(episodes)
    if episodes_html:
        sections.append(episodes_html)
        text += episodes_text
    next_up_html, next_up_text = _next_up_section(next_up, base)
    if next_up_html:
        sections.append(next_up_html)
        text += next_up_text
    friends_html, friends_text = _friends_section(friends, base)
    if friends_html:
        sections.append(friends_html)
        text += friends_text
    following_html, following_text = _following_section(following, base)
    if following_html:
        sections.append(following_html)
        text += following_text
    past_html, past_text = _memories_section(past)
    if past_html:
        sections.append(past_html)
        text += past_text
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
    challenge_html, challenge_text = _challenge_section(challenge, base)
    if challenge_html:
        sections.append(challenge_html)
        text += challenge_text
    badge_html, badge_text = _badge_section(badge, base)
    if badge_html:
        sections.append(badge_html)
        text += badge_text
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
    if matches or popular:
        intro = "here is what is on the way."
    elif episodes:
        intro = "here is what airs this week."
    else:
        intro = "here is what your friends added this week."
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">OmniTrackr weekly</div>'
        '<div style="font-size:22px;font-weight:700;margin-top:6px">Coming up for you</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        f'<p style="color:#1f1640;font-size:15px">Hi {escape(username)}, {intro}</p>'
        + "".join(sections) +
        f'<p style="margin:26px 0 8px"><a href="{escape(base, quote=True)}/release-radar" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Open Release Radar</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;margin-top:24px">You get this because you turned on the weekly email in OmniTrackr. '
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

QUIET_WEEK = "quiet-week"  # compose() result when the member would get nothing this week


def compose(db: Session, user, now: datetime, pool=None, spotlight=None, today: date | None = None,
            unsubscribe_url: str = "", client=None, quiet_ok: bool = True):
    """Build this week's email for one member: (subject, html, text), None when there is nothing
    at all to say, or QUIET_WEEK when a round-up went out recently and nothing new came up.
    The member's weekly preview page calls this with quiet_ok=False so it always shows something."""
    subscription = subscription_for(db, user.id)
    if not unsubscribe_url and subscription:
        unsubscribe_url = f"{app_url()}/email/unsubscribe?token={subscription.token}"
    if pool is None:
        from .for_you import radar_pool
        pool = radar_pool(today, client)
    report = coming_up(db, user.id, today=today, pool=pool)
    try:
        friends = friend_activity(db, user.id, now)
    except Exception:
        db.rollback()
        friends = []  # The weekly email never depends on it.
    try:
        episodes = episodes_this_week(db, user, today or radar.today_utc())
    except Exception:
        db.rollback()
        episodes = []  # The weekly email never depends on it.
    if quiet_ok and not report["matches"] and not friends and not episodes:
        last_sent_at = subscription.last_sent_at if subscription else None
        if last_sent_at and last_sent_at > now - ROUNDUP_EVERY:
            return QUIET_WEEK
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
    try:
        challenge = challenge_line(db, user.id, now.date())
    except Exception:
        db.rollback()
        challenge = None  # Optional, like the ask above.
    try:
        from .badges import digest_line
        badge = digest_line(db, user)
    except Exception:
        db.rollback()
        badge = None  # Optional, like the ask above.
    try:
        recap = recap_line(db, user.id, now.date())
    except Exception:
        db.rollback()
        recap = None  # Optional, like the ask above.
    try:
        next_up = next_up_line(db, user.id)
    except Exception:
        db.rollback()
        next_up = None  # Optional, like the ask above.
    try:
        past = memories_line(db, user, today or now.date())
    except Exception:
        db.rollback()
        past = []  # Optional, like the ask above.
    try:
        following = following_line(db, user, now)
    except Exception:
        db.rollback()
        following = []  # Optional, like the ask above.
    return build_digest(user.username, report, unsubscribe_url, spotlight, ask, invite,
                        member_goals, now.year, challenge, badge, recap, friends, episodes, next_up, past,
                        following)


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
        # Both email schedulers draw from the same rolling daily budget.
        from .announcements import shared_cap
        sent_campaign = db.query(models.EmailCampaignSend).filter(
            models.EmailCampaignSend.sent_at >= now - timedelta(hours=24)
        ).count()
        allowance = min(daily_limit() - sent_today, shared_cap() - sent_today - sent_campaign)
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
            # Another process may have loaded this same due list. Claim with
            # a conditional update rather than writing a stale ORM snapshot.
            previous_checked_at = subscription.last_checked_at
            claimed = db.query(models.EmailDigestSubscription).filter(
                models.EmailDigestSubscription.id == subscription.id,
                (models.EmailDigestSubscription.last_checked_at.is_(None))
                | (models.EmailDigestSubscription.last_checked_at <= now - SEND_EVERY),
            ).update({models.EmailDigestSubscription.last_checked_at: now}, synchronize_session=False)
            db.commit()
            if not claimed:
                stats["skipped"] += 1
                continue
            db.refresh(subscription)
            if user is None or not user.is_active or not user.is_verified or not user.email:
                stats["skipped"] += 1
                continue
            if pool is None:  # built once, shared by every member in this run
                from .for_you import radar_pool
                pool = radar_pool(today, client)
            unsubscribe_url = f"{app_url()}/email/unsubscribe?token={subscription.token}"
            built = compose(db, user, now, pool=pool, spotlight=spotlight, today=today,
                            unsubscribe_url=unsubscribe_url, client=client)
            if built is QUIET_WEEK:
                stats["skipped"] += 1  # a quiet week: no news from their library, round-up sent recently
                continue
            if built is None:
                stats["skipped"] += 1
                continue
            subject, html, _text = built
            # Reserve under a cross-process lock before awaiting the provider.
            # Other schedulers count this in-flight send against the shared cap.
            from .email_quota import lock_email_budget
            lock_email_budget(db)
            sent_digest = db.query(models.EmailDigestSubscription).filter(
                models.EmailDigestSubscription.last_sent_at >= now - timedelta(hours=24)
            ).count()
            sent_campaign = db.query(models.EmailCampaignSend).filter(
                models.EmailCampaignSend.sent_at >= now - timedelta(hours=24)
            ).count()
            if sent_digest >= daily_limit() or sent_digest + sent_campaign >= shared_cap():
                subscription.last_checked_at = previous_checked_at
                db.commit()
                stats["limited"] += 1
                continue
            previous_sent_at = subscription.last_sent_at
            subscription.last_sent_at = now
            db.commit()
            try:
                await sender(user.email, subject, html, unsubscribe_url)
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Weekly email to user {user.id} failed: {error}")
                # Preserve the existing failed-send retry semantics without
                # consuming a successful-send allowance.
                subscription.last_sent_at = previous_sent_at
                db.commit()
                stats["failed"] += 1
                continue
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
            try:
                from .for_you import radar_pool
                from .release_alerts import send_due_alerts
                today = radar.today_utc()
                alerts = await asyncio.to_thread(send_due_alerts, SessionLocal, radar_pool(today), today)
                if alerts["members"]:
                    print(f"Release day alerts: {alerts}")
            except Exception as error:  # Never blocks the weekly email.
                print(f"Release day alerts failed: {error}")
            try:
                from .episode_alerts import send_due_alerts as send_due_episode_alerts
                episodes = await asyncio.to_thread(send_due_episode_alerts, SessionLocal)
                if episodes["members"]:
                    print(f"New episode alerts: {episodes}")
            except Exception as error:
                print(f"New episode alerts failed: {error}")
            stats = await send_due_digests(SessionLocal, client)
            if stats["sent"] or stats["failed"]:
                print(f"Weekly emails: {stats}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Weekly email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
