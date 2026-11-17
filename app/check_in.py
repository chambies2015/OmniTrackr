"""Check-ins: "did you finish it?" for members who saved a few titles and then stopped coming.

The member journey on Site stats shows where people stall: most members who save
five titles never come back for a second day. Nothing in the app reaches them
(the Welcome Back Deck and the home cards only help people who open the site),
and the come-back email waits 30 days. This adds a small thing worth answering:

- A check-in page at /check-in/<token>. The link comes from an email and works
  without signing in, for the few titles named in it and nothing else: mark one
  finished, give it a score out of 10, or say you're still going. A link scanner
  opening it changes nothing; every change needs a button press (a POST).
  Answering counts as a visit day, like opening the app does.
- A check-in email, about two weeks after the member's last visit, naming up to
  four titles they saved but haven't finished (or finished without a score),
  plus three picks from the For you tab.
- The come-back email's "Still on your list" rows get the same buttons.

Email rules (all of them, every time):
- Nothing is sent until the site owner presses Start on the Site stats page.
- Verified, active members only; anyone who unsubscribed from product updates
  is skipped, and so are weekly-email subscribers (they already hear from us).
- Only to accounts at least 9 days old (after the welcome emails) whose last
  visit was 9 to 29 days ago; from 30 days the come-back email takes over.
- One per stretch away, at most one every 90 days, and none within 72 hours of
  any other product email. Members with nothing to ask about get none.
- Paused while the "What's new" update is sending, and kept inside the shared
  daily email budget, so sign-up and password-reset emails always have room.

Counters go into site_traffic_daily under kind "checkin" and name no member.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .digest import app_url, mail_configured

STATE_KEY = "check-in"  # the EmailCampaign row holding the owner's on/off switch
SEND_PREFIX = "checkin-"  # each send is an EmailCampaignSend row keyed by month
MIN_ACCOUNT_DAYS = 9
AWAY_MIN_DAYS = 9
AWAY_MAX_DAYS = 29  # from 30 days away the come-back email is the one that goes
EVERY_DAYS = 90
GAP = timedelta(hours=72)
CAME_BACK_WITHIN_DAYS = 7
PER_RUN_LIMIT = 10
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 420
MAX_ITEMS = 4
TOKEN_SALT = "omnitrackr-check-in-v1"
TOKEN_MAX_AGE = 60 * 60 * 24 * 21
TOKEN_MAX_LENGTH = 400
PICK_COUNT = 3
UTM = "utm_source=email&utm_campaign=check-in"

# Where a check-in link came from. Counted per source on Site stats.
SOURCES = {"checkin": "Check-in email", "comeback": "Come-back email"}

# Library category -> (model, finished field, label, "finished" button text)
CATEGORIES = {
    "movies": (models.Movie, "watched", "Movie", "Watched it"),
    "tv-shows": (models.TVShow, "watched", "TV show", "Finished it"),
    "anime": (models.Anime, "watched", "Anime", "Finished it"),
    "video-games": (models.VideoGame, "played", "Game", "Finished it"),
    "music": (models.Music, "listened", "Album", "Listened to it"),
    "books": (models.Book, "read", "Book", "Read it"),
    "manga": (models.Manga, "read", "Manga", "Read it"),
    "podcasts": (models.Podcast, "listened", "Podcast", "Listened to it"),
    "audiobooks": (models.Audiobook, "listened", "Audiobook", "Finished it"),
}
IMAGE_FIELD = {"movies": "poster_url", "tv-shows": "poster_url", "anime": "poster_url"}
# A podcast never really ends, so it is only ever asked about once it's marked finished.
NEVER_ASK_FINISHED = {"podcasts"}
QUESTIONS = {
    "movies": "Did you watch it?", "tv-shows": "Did you finish it?", "anime": "Did you finish it?",
    "video-games": "Did you finish it?", "music": "Did you give it a listen?", "books": "Did you read it?",
    "manga": "Did you read it?", "podcasts": "How was it?", "audiobooks": "Did you finish it?",
}
SUBJECT_VERBS = {
    "movies": "Did you watch", "tv-shows": "Did you finish", "anime": "Did you finish", "video-games": "Did you finish",
    "music": "Did you listen to", "books": "Did you read", "manga": "Did you read", "podcasts": "How was",
    "audiobooks": "Did you finish",
}
COUNTER_KEYS = ("sent", "opened", "finished", "rated", "still", "all_done")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("CHECKIN_DAILY_LIMIT", "20")))
    except ValueError:
        return 20


def enabled_for_process() -> bool:
    setting = os.getenv("CHECKIN_EMAILS", "").strip().lower()
    if setting in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


def send_key(now: datetime) -> str:
    return f"{SEND_PREFIX}{now:%Y-%m}"


def count(key: str) -> bool:
    """Add 1 to a "checkin" counter for today. Never raises."""
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled or len(key) > 60:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "checkin", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- the link

def _serializer() -> URLSafeTimedSerializer:
    from . import auth
    return URLSafeTimedSerializer(auth.SECRET_KEY, salt=TOKEN_SALT)


def make_token(user_id: int, items: list[dict], source: str) -> str:
    """A signed link for one member and the titles named in one email. It expires after 21 days."""
    refs = [[item["category"], int(item["id"])] for item in items[:MAX_ITEMS]]
    return _serializer().dumps({"u": int(user_id), "i": refs, "s": source if source in SOURCES else "checkin"})


def read_token(token: str | None) -> Optional[dict]:
    """{"user_id", "items": [(category, id)], "source"} for a fresh, untampered link, else None."""
    if not token or len(token) > TOKEN_MAX_LENGTH:
        return None
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    user_id, refs, source = data.get("u"), data.get("i"), data.get("s")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        return None
    if not isinstance(refs, list) or not 0 < len(refs) <= MAX_ITEMS or source not in SOURCES:
        return None
    items = []
    for ref in refs:
        if (not isinstance(ref, list) or len(ref) != 2 or ref[0] not in CATEGORIES
                or not isinstance(ref[1], int) or isinstance(ref[1], bool) or not 0 < ref[1] <= 2147483647):
            return None
        items.append((ref[0], ref[1]))
    return {"user_id": user_id, "items": items, "source": source}


def link_for(token: str, index: Optional[int] = None, answer: str = "") -> str:
    """The check-in page, optionally opened on one title with "finished" or "still going" picked."""
    path = f"/check-in/{token}?{UTM}"
    if index is not None:
        path += f"&pick={index}"
        if answer in ("finished", "still"):
            path += f"&a={answer}"
        path += f"#ci-{index}"
    return f"{app_url()}{path}"


# ---------------------------------------------------------------- what to ask about

def _image(category: str, row) -> Optional[str]:
    from .for_you import _safe_image
    value = getattr(row, IMAGE_FIELD.get(category, "cover_art_url"), None)
    image = _safe_image(value)
    return image if image and image.startswith("https://") else None


def _card(category: str, row) -> dict:
    model, done_field, label, finished_label = CATEGORIES[category]
    return {
        "category": category,
        "id": row.id,
        "title": " ".join((row.title or "").split())[:200],
        "label": label,
        "finished_label": finished_label,
        "question": QUESTIONS[category],
        "image": _image(category, row),
        "finished": bool(getattr(row, done_field)),
        "rating": row.rating,
        "added_at": row.added_at,
    }


def candidates(db: Session, user_id: int, limit: int = MAX_ITEMS, unfinished_only: bool = False) -> list[dict]:
    """Up to `limit` titles worth a check-in: unfinished ones first, then finished without a score; newest first.

    `unfinished_only` is for the come-back email, whose list is "Still on your list".
    """
    unfinished: list[dict] = []
    unrated: list[dict] = []
    for category, (model, done_field, _label, _button) in CATEGORIES.items():
        order = (model.added_at.desc().nullslast(), model.id.desc())
        if category not in NEVER_ASK_FINISHED:
            for row in db.query(model).filter(model.user_id == user_id, getattr(model, done_field) != True) \
                    .order_by(*order).limit(limit).all():
                if (row.title or "").strip():
                    unfinished.append(_card(category, row))
        if unfinished_only:
            continue
        for row in db.query(model).filter(model.user_id == user_id, getattr(model, done_field) == True,
                                          model.rating.is_(None)).order_by(*order).limit(limit).all():
            if (row.title or "").strip():
                unrated.append(_card(category, row))
    newest = lambda card: (card["added_at"] or datetime(2000, 1, 1), card["id"])  # noqa: E731
    unfinished.sort(key=newest, reverse=True)
    unrated.sort(key=newest, reverse=True)
    # At most three "did you finish it?" questions, so a finished title without a score gets a turn too.
    chosen = unfinished[:min(3, limit)]
    chosen += unrated[:limit - len(chosen)]
    if len(chosen) < limit:
        chosen += unfinished[len(chosen):limit]
    return chosen[:limit]


def members_with_something_to_ask(db: Session, user_ids: list[int]) -> set[int]:
    """The members among `user_ids` for whom candidates() would find at least one title.

    The same rules as candidates(), one query per library instead of two per library per member.
    """
    from sqlalchemy import and_, or_
    found: set[int] = set()
    for start in range(0, len(user_ids), 400):
        chunk = user_ids[start:start + 400]
        for category, (model, done_field, _label, _button) in CATEGORIES.items():
            done = getattr(model, done_field)
            unrated = and_(done == True, model.rating.is_(None))  # noqa: E712
            ask = unrated if category in NEVER_ASK_FINISHED else or_(done != True, unrated)  # noqa: E712
            rows = db.query(model.user_id).filter(
                model.user_id.in_(chunk), model.title.isnot(None), func.trim(model.title) != "", ask,
            ).distinct().all()
            found.update(user_id for (user_id,) in rows)
    return found


def aligned_items(db: Session, user_id: int, refs: list[tuple[str, int]]) -> list[Optional[dict]]:
    """The titles a link names, as they are now, in the link's order. None for one deleted since."""
    cards: list[Optional[dict]] = []
    for category, item_id in refs:
        model = CATEGORIES[category][0]
        row = db.query(model).filter(model.id == item_id, model.user_id == user_id).first()
        cards.append(_card(category, row) if row is not None else None)
    return cards


def picks(db: Session, user_id: int, limit: int = PICK_COUNT) -> list[dict]:
    """A few For you picks (covers first). Read from members' libraries only; never raises."""
    try:
        from .picked_for_you import picks_for
        found = picks_for(db, user_id)
    except Exception:
        db.rollback()
        return []
    if found.get("state") == "empty":
        return []
    cards = [pick for pick in found.get("picks", []) if pick.get("url") and pick.get("title")]
    with_cover = [pick for pick in cards if isinstance(pick.get("image"), str) and pick["image"].startswith("https://")]
    chosen = (with_cover + [pick for pick in cards if pick not in with_cover])[:limit]
    return [{"title": pick["title"], "label": pick.get("label") or "", "url": pick["url"],
             "image": pick["image"] if pick in with_cover else None, "reason": pick.get("reason") or ""}
            for pick in chosen]


# ---------------------------------------------------------------- answering

def answer(db: Session, user: models.User, category: str, item_id: int, action: str,
           rating: Optional[int] = None) -> Optional[dict]:
    """Apply one answer to one of the member's titles. Returns the title as it is now, or None if it's gone.

    "finished" ticks it off (a journal entry, like ticking it in the library, so goals and
    challenges count it) and saves the score if one was given; "rate" only saves the score;
    "still" changes nothing.
    """
    from .progress import lock_progress_owner
    from .routers.activity import record_completion_activity
    if category not in CATEGORIES or action not in ("finished", "rate", "still"):
        raise ValueError("unknown answer")
    if rating is not None and (isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 10):
        raise ValueError("score must be 1 to 10")
    model, done_field, _label, _button = CATEGORIES[category]
    if action == "still":
        row = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
        return _card(category, row) if row is not None else None
    lock_progress_owner(db, user.id)
    row = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
    if row is None:
        db.rollback()
        return None
    if rating is not None:
        row.rating = float(rating)
    newly_finished = False
    if action == "finished" and not getattr(row, done_field):
        setattr(row, done_field, True)
        newly_finished = True
    if newly_finished:
        logged = db.query(models.ActivityEntry.id).filter(
            models.ActivityEntry.user_id == user.id, models.ActivityEntry.category == category,
            models.ActivityEntry.item_id == row.id, models.ActivityEntry.action == "completed").first()
        if logged is None:
            record_completion_activity(db, user.id, category, row)
    elif rating is not None:
        # A score given after the tick: the automatic "Finished" journal entry carries it too, if it had none.
        entry = db.query(models.ActivityEntry).filter(
            models.ActivityEntry.user_id == user.id, models.ActivityEntry.category == category,
            models.ActivityEntry.item_id == row.id, models.ActivityEntry.action == "completed",
            models.ActivityEntry.source == "automatic", models.ActivityEntry.rating.is_(None),
        ).order_by(models.ActivityEntry.id.desc()).first()
        if entry is not None:
            entry.rating = float(rating)
    db.commit()
    db.refresh(row)
    return _card(category, row)


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

def due_members(db: Session, now: datetime, limit: int | None = None) -> list[models.User]:
    from .comeback import _away_since
    from .editorial_collections import EDITOR_USERNAME
    newest_away = now - timedelta(days=AWAY_MIN_DAYS)
    oldest_away = now - timedelta(days=AWAY_MAX_DAYS + 1)
    opted = db.query(models.EmailOptOut.user_id)
    weekly = db.query(models.EmailDigestSubscription.user_id)
    recent = db.query(models.EmailCampaignSend.user_id).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status != "test",
        models.EmailCampaignSend.sent_at >= now - timedelta(days=EVERY_DAYS))
    candidates_q = db.query(models.User).filter(
        models.User.is_active == True, models.User.is_verified == True,
        models.User.email.isnot(None), models.User.email != "",
        models.User.username != EDITOR_USERNAME,
        models.User.created_at.isnot(None),
        models.User.created_at <= now - timedelta(days=MIN_ACCOUNT_DAYS),
        ~models.User.id.in_(opted), ~models.User.id.in_(weekly), ~models.User.id.in_(recent),
    ).order_by(models.User.id).all()
    if not candidates_q:
        return []
    ids = [user.id for user in candidates_q]
    last_email: dict[int, datetime] = {}
    for user_id, sent_at in db.query(models.EmailCampaignSend.user_id, func.max(models.EmailCampaignSend.sent_at)).filter(
            models.EmailCampaignSend.user_id.in_(ids), models.EmailCampaignSend.status == "sent",
    ).group_by(models.EmailCampaignSend.user_id):
        if sent_at is not None:
            last_email[user_id] = sent_at
    waiting = [user for user in candidates_q
               if oldest_away < _away_since(user) <= newest_away
               and not (user.id in last_email and last_email[user.id] > now - GAP)]
    askable = members_with_something_to_ask(db, [user.id for user in waiting]) if waiting else set()
    due = []
    for user in waiting:
        if user.id not in askable:
            continue
        due.append(user)
        if limit is not None and len(due) >= limit:
            break
    return due


def stats(db: Session, days: int, now: datetime) -> dict:
    """Page opens and answers in the range, by where the link came from."""
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "checkin", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    get = lambda key: int(counts.get(key) or 0)  # noqa: E731
    by_source = [{"source": label, **{key: get(f"{key}_{source}") for key in COUNTER_KEYS}}
                 for source, label in SOURCES.items()]
    return {"by_source": by_source, **{key: sum(row[key] for row in by_source) for key in COUNTER_KEYS}}


def status(db: Session, now: datetime | None = None, days: int = 30) -> dict:
    now = now or datetime.utcnow()
    row = state(db)
    since = now - timedelta(days=30)
    sends = db.query(models.EmailCampaignSend).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status == "sent",
        models.EmailCampaignSend.sent_at >= since,
    ).all()
    users = {user.id: user for user in db.query(models.User).filter(
        models.User.id.in_({send.user_id for send in sends}))} if sends else {}
    came_back = 0
    for send in sends:
        user = users.get(send.user_id)
        if user is None:
            continue
        window_end = send.sent_at + timedelta(days=CAME_BACK_WITHIN_DAYS)
        back = user.last_seen_on and send.sent_at.date() <= user.last_seen_on <= window_end.date()
        logged = user.last_login_at and send.sent_at <= user.last_login_at <= window_end
        if back or logged:
            came_back += 1
    return {
        "status": row.status,
        "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
        "sent_30d": len(sends),
        "sent_all_time": int(db.query(func.count(models.EmailCampaignSend.id)).filter(
            models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
            models.EmailCampaignSend.status == "sent").scalar() or 0),
        "came_back": came_back,
        "came_back_window_days": CAME_BACK_WITHIN_DAYS,
        "due_now": len(due_members(db, now)),
        "waiting_on_whats_new": _whats_new_sending(db),
        "daily_limit": daily_limit(),
        "away_days": [AWAY_MIN_DAYS, AWAY_MAX_DAYS],
        "every_days": EVERY_DAYS,
        "mail_configured": mail_configured(),
        "page": stats(db, days, now),
    }


# ---------------------------------------------------------------- the email

def _link(path: str) -> str:
    joiner = "&" if "?" in path.split("#")[0] else "?"
    if "#" in path:
        head, anchor = path.split("#", 1)
        return f"{app_url()}{head}{joiner}{UTM}#{anchor}"
    return f"{app_url()}{path}{joiner}{UTM}"


def _pill(label: str, url: str, primary: bool) -> str:
    colours = ("background:#7c3aed;color:#fff;border:1px solid #7c3aed" if primary
               else "background:#fff;color:#4c1d95;border:1px solid #d8cdf7")
    return (f'<a href="{escape(url, quote=True)}" style="{colours};display:inline-block;padding:7px 14px;'
            f'border-radius:999px;text-decoration:none;font-weight:700;font-size:13px;margin:6px 6px 0 0">{escape(label)}</a>')


def _cover(image: Optional[str], width: int = 52, height: int = 78) -> str:
    if image:
        return (f'<img src="{escape(image, quote=True)}" width="{width}" height="{height}" alt="" '
                f'style="display:block;width:{width}px;height:{height}px;object-fit:cover;border-radius:6px;background:#e9e5f5">')
    return f'<div style="width:{width}px;height:{height}px;border-radius:6px;background:#e9e5f5"></div>'


def item_rows_html(items: list[dict], token: str) -> str:
    """Email rows for titles with the check-in buttons. Shared with the come-back email."""
    rows = []
    for index, item in enumerate(items):
        if item["finished"]:
            question = "You finished it. How was it?"
            buttons = _pill("Give it a score", link_for(token, index), True)
        else:
            question = item["question"]
            buttons = (_pill(item["finished_label"], link_for(token, index, "finished"), True)
                       + _pill("Still going", link_for(token, index, "still"), False))
        rows.append(
            '<tr><td style="padding:12px 12px 12px 0;border-top:1px solid #e9e5f5;vertical-align:top;width:52px">'
            f'{_cover(item.get("image"))}</td>'
            '<td style="padding:12px 0;border-top:1px solid #e9e5f5;vertical-align:top">'
            f'<div style="color:#1f1640;font-weight:700;font-size:15px">{escape(item["title"])}</div>'
            f'<div style="color:#5b5675;font-size:13px;line-height:1.5">{escape(item["label"])} · {escape(question)}</div>'
            f'<div>{buttons}</div></td></tr>')
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>'


def item_rows_text(items: list[dict], token: str) -> list[str]:
    lines = []
    for index, item in enumerate(items):
        if item["finished"]:
            lines.append(f"- {item['title']} ({item['label']}): give it a score {link_for(token, index)}")
        else:
            lines.append(f"- {item['title']} ({item['label']}): {item['question']} {link_for(token, index, 'finished')}")
    return lines


def build_email(username: str, items: list[dict], suggestions: list[dict], token: str,
                unsubscribe_url: str) -> tuple[str, str, str]:
    """(subject, html, text) for one member."""
    first = items[0]
    if first["finished"]:
        subject = f"How was {first['title']}?"
    else:
        subject = f"{SUBJECT_VERBS[first['category']]} {first['title']}?"
    subject = " ".join(subject.split())[:150]  # library titles are member-typed: one line, bounded
    plural = len(items) != 1
    intro = (f"A little while ago you saved {'these' if plural else 'this'} on OmniTrackr. "
             f"How did {'they' if plural else 'it'} go? One tap answers, and you don't need to sign in.")
    html_picks = ""
    text_picks: list[str] = []
    if suggestions:
        rows = "".join(
            '<tr><td style="padding:10px 12px 10px 0;border-top:1px solid #e9e5f5;vertical-align:top;width:40px">'
            f'{_cover(pick.get("image"), 40, 60)}</td>'
            '<td style="padding:10px 0;border-top:1px solid #e9e5f5;vertical-align:top">'
            f'<a href="{escape(_link(pick["url"]), quote=True)}" style="color:#1f1640;font-weight:700;text-decoration:none;font-size:15px">'
            f'{escape(pick["title"])}</a>'
            f'<div style="color:#5b5675;font-size:13px;line-height:1.5">{escape(" · ".join(part for part in (pick["label"], pick["reason"]) if part))}</div>'
            '</td></tr>' for pick in suggestions)
        html_picks = ('<h2 style="font-size:17px;color:#1f1640;margin:26px 0 4px">Picked for you</h2>'
                      '<p style="color:#5b5675;font-size:13px;margin:0 0 6px">From what members with libraries like yours track. '
                      'Scores you give make these better.</p>'
                      f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{rows}</table>')
        text_picks = ["Picked for you:"] + [f"- {pick['title']} ({pick['label']}): {_link(pick['url'])}" for pick in suggestions] + [""]
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">OmniTrackr check-in</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">How’s it going, {escape(username)}?</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">{escape(intro)}</p>'
        + item_rows_html(items, token) + html_picks +
        f'<p style="margin:26px 0 8px"><a href="{escape(link_for(token), quote=True)}" '
        'style="background:#1a1433;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Answer all at once</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">You’re getting this because you saved '
        'these titles on OmniTrackr and haven’t been back for a couple of weeks. We send one of these per stretch away, '
        'at most every three months. The buttons only work for the titles above and expire in three weeks. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a> with one click.</p>'
        '</div></div></body></html>'
    )
    text = ([f"Hi {username},", "", intro, ""] + item_rows_text(items, token) + [""] + text_picks
            + [f"Answer all at once: {link_for(token)}", "",
               "You're getting this because you saved these titles on OmniTrackr and haven't been back for a couple of weeks. "
               "We send one of these per stretch away, at most every three months.",
               f"Unsubscribe from product updates: {unsubscribe_url}"])
    return subject, html, "\n".join(text)


def email_for(db: Session, user: models.User) -> Optional[tuple[str, str, str, str]]:
    """(subject, html, text, unsubscribe_url), or None when there's nothing to ask about."""
    from .announcements import unsubscribe_token
    items = candidates(db, user.id)
    if not items:
        return None
    token = make_token(user.id, items, "checkin")
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    subject, html, text = build_email(user.username, items, picks(db, user.id), token, unsubscribe_url)
    return subject, html, text, unsubscribe_url


# ---------------------------------------------------------------- sending

async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


def allowance(db: Session, now: datetime) -> int:
    """How many may go out now: inside this email's own limit and the shared daily cap."""
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_checkin = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status != "test",
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_checkin, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


async def send_due(session_factory, now: datetime | None = None, sender=_send) -> dict:
    now = now or datetime.utcnow()
    stats_out = {"sent": 0, "failed": 0, "limited": False}
    if not mail_configured() and sender is _send:
        return stats_out
    db = session_factory()
    try:
        if state(db).status != "sending" or _whats_new_sending(db):
            return stats_out
        budget = allowance(db, now)
        if budget <= 0:
            stats_out["limited"] = True
            return stats_out
        users = due_members(db, now, limit=budget)
        from .email_quota import lock_email_budget
        for user in users:
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                stats_out["limited"] = True
                break
            try:
                built = email_for(db, user)
            except Exception as error:
                print(f"Check-in email for user {user.id} couldn't be built: {error}")
                db.rollback()
                continue
            if built is None:
                db.rollback()
                continue
            # Claim first so an overlapping run can never send twice.
            claim = models.EmailCampaignSend(campaign_key=send_key(now), user_id=user.id, status="sent", sent_at=now)
            db.add(claim)
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            subject, html, _text, unsubscribe_url = built
            try:
                await sender(user.email, subject, html, unsubscribe_url)
                stats_out["sent"] += 1
                count("sent_checkin")
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Check-in email to user {user.id} failed: {error}")
                db.rollback()
                claim.status = "failed"
                db.commit()
                stats_out["failed"] += 1
        return stats_out
    finally:
        db.close()


async def send_test(db: Session, user: models.User, sender=_send) -> bool:
    """Send the email to the owner only (doesn't count as a check-in for them). False if their library has nothing to ask."""
    built = email_for(db, user)
    if built is None:
        return False
    subject, html, _text, unsubscribe_url = built
    await sender(user.email, "[Test] " + subject, html, unsubscribe_url)
    return True


async def check_in_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await send_due(SessionLocal)
            if result["sent"] or result["failed"]:
                print(f"Check-in emails: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Check-in email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
