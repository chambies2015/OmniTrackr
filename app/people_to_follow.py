"""Find people: members worth following, for the friends feed tab and its rail (Nov 2026).

Members with friends come back more, and most members have none, so this turns the
follow feature (follows.py) into something you can find people with. Suggestions
come in groups, strongest first:

* Followed you: members who follow you that you don't follow back. Their own
  action toward you, already listed under Settings, so it ignores the opt-out below.
* Similar taste: members whose libraries line up with yours, scored with the same
  taste-neighbour maths as the For you picks (picked_for_you), over the same pool.
* Your signals: writers of reviews this browser marked helpful and curators of
  collections you saved (follows.signal_reasons).
* Reviewed what's on your shelf: public reviews of titles in your library.
* Active this month: public profiles with new reviews, collections or diary entries.

Privacy floors:

* Only members whose public profile is on, who take followers and who haven't
  switched off "Suggest my profile" (FollowSetting.suggest_me) are ever suggested.
  The editors account never is.
* Taste matching reads only the categories a member didn't make private (the For you
  pool already leaves those out). Your own library, private parts included, is only
  used for your own suggestions, as with For you.
* A card only ever names titles the member's profile already shows anyone: pins,
  favorites, public reviews, and the diary or Right now shelf when they switched those
  on. With the compare tastes link on, any shared title can be named, because that
  page already shows signed-in members the overlap. A taste match with no title we
  may name is dropped, so nobody is suggested on hidden overlap alone.
* A taste match needs MIN_SHARED titles in common and a viewer library of MIN_LIBRARY.
* Nobody is told they were suggested, or to whom. "Not for me" is private and only
  hides the card.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import follows, friend_feed, models, picked_for_you, public_profiles, title_pages

MIN_LIBRARY = 5
MIN_SHARED = 3
LOVED = 8.0
PAGE_LIMIT = 12
RAIL_LIMIT = 3
FOLLOW_BACK_LIMIT = 8
TASTE_CANDIDATES = 24      # profiles checked for titles we may name, best scores first
SHELF_CANDIDATES = 8
ACTIVE_CANDIDATES = 8
ACTIVE_WINDOW = timedelta(days=30)
TITLES_SHOWN = 3
BIO_CHARS = 120
DISMISS_LIMIT = 500
CACHE_SECONDS = 600

SOURCES = {"back": "Followed back from Find people", "taste": "Followed from Similar taste",
           "signal": "Followed from reviews they found helpful or lists they saved",
           "shelf": "Followed from Reviewed what's on your shelf", "active": "Followed from Active this month",
           "rail": "Followed from the friends feed rail", "list": "Followed back from Settings → Followers",
           "empty": "Followed from the empty Following tab"}
COUNTERS = {
    "page_shown": "Opened Find people with someone to suggest",
    "page_empty": "Opened Find people with nobody to suggest",
    "rail_shown": "Saw people to follow in the friends feed rail",
    **{f"followed_{key}": label for key, label in SOURCES.items()},
    "friend_back": "Sent a friend request to a follower without a public profile",
    "dismissed": "Pressed Not for me",
    "undismissed": "Undid Not for me",
    "profile_prompt": "Pressed Turn on my public profile",
    "suggest_off": "Switched off Suggest my profile",
    "suggest_on": "Switched Suggest my profile back on",
}
CLIENT_COUNTERS = {"profile_prompt"}

GROUPS = (
    ("taste", "Similar taste", "Members whose libraries line up with yours."),
    ("signal", "From what you liked", "Reviews you found helpful and lists you saved."),
    ("shelf", "Reviewed what's on your shelf", "Public reviews of titles in your library."),
    ("active", "Active this month", "Profiles with new reviews, lists or diary entries."),
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- counters

def count(key: str) -> bool:
    """Add 1 to a "people" counter for today. Never raises, and stores nothing about who."""
    if key not in COUNTERS:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "people", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def count_follow(source: str) -> bool:
    source = (source or "").strip().lower()
    return count(f"followed_{source}") if source in SOURCES else False


# ---------------------------------------------------------------- small caches

_cache_lock = threading.Lock()
_cache: dict = {}


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _cached(key: tuple, build):
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
    value = build()
    with _cache_lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[key] = (time.monotonic(), value)
    return value


# ---------------------------------------------------------------- who can be suggested

def _profile_stamp(user: models.User, profile: models.PublicProfile) -> tuple:
    """Everything that changes what a profile shows, so a cached reading never outlives a switch."""
    flags = tuple(bool(getattr(user, flag, False)) for flag in title_pages.PRIVATE_FLAG.values())
    switches = tuple(bool(getattr(profile, name, False)) for name in public_profiles.SETTINGS_FIELDS)
    return user.id, profile.updated_at, flags, switches


def _open_profiles(db: Session) -> dict[int, tuple[models.User, models.PublicProfile]]:
    """Members who may appear in anyone's suggestions: public, taking followers, not opted out."""
    rows = db.query(models.User, models.PublicProfile, models.FollowSetting.allow_followers,
                    models.FollowSetting.suggest_me).join(
        models.PublicProfile, models.PublicProfile.user_id == models.User.id,
    ).outerjoin(models.FollowSetting, models.FollowSetting.user_id == models.User.id).filter(
        models.User.is_active == True, models.PublicProfile.enabled == True,
        models.User.username != title_pages.EDITOR_USERNAME,
    ).all()
    return {user.id: (user, profile) for user, profile, allow, suggest in rows
            if allow is not False and suggest is not False}


def dismissed_ids(db: Session, viewer_id: int) -> set[int]:
    return {uid for uid, in db.query(models.PeopleSuggestionDismissal.dismissed_id).filter(
        models.PeopleSuggestionDismissal.user_id == viewer_id).limit(DISMISS_LIMIT)}


def _excluded(db: Session, viewer_id: int) -> set[int]:
    """Yourself, people you follow, friends, anyone either of you removed, and your Not for me list."""
    out = {viewer_id}
    out |= {uid for uid, in db.query(models.MemberFollow.followed_id).filter(
        models.MemberFollow.follower_id == viewer_id)}
    out |= friend_feed.friend_ids(db, viewer_id)
    out |= {uid for uid, in db.query(models.FollowBar.owner_id).filter(models.FollowBar.barred_id == viewer_id)}
    out |= {uid for uid, in db.query(models.FollowBar.barred_id).filter(models.FollowBar.owner_id == viewer_id)}
    out |= dismissed_ids(db, viewer_id)
    return out


# ---------------------------------------------------------------- what a profile already shows

def _year_from_path(path: str, title: str) -> tuple[bool, Optional[int]]:
    """(matches, year) for a /titles/<kind>/<slug> path built from ``title``."""
    rest = (path or "").rsplit("/", 1)[-1]
    base = title_pages.slugify(title)
    if rest == base:
        return True, None
    tail = rest[len(base) + 1:] if rest.startswith(base + "-") else ""
    if len(tail) == 4 and tail.isdigit():
        return True, int(tail)
    return False, None


def _kind_from_path(path: str) -> Optional[str]:
    parts = (path or "").split("/")
    return parts[2] if len(parts) >= 4 and parts[1] == "titles" and parts[2] in title_pages.KINDS else None


def _note(shown: dict, kind: Optional[str], title: str, year: Optional[int], *, url: Optional[str],
          image: Optional[str], rated: bool, rating=None, review_url: Optional[str] = None) -> None:
    title = (title or "").strip()
    if not kind or not title:
        return
    key = (kind, title_pages.slugify(title), year)
    entry = shown.setdefault(key, {"title": title, "url": url, "image": image, "rated": False, "rating": None,
                                   "review_url": None})
    entry["image"] = entry["image"] or image
    entry["url"] = entry["url"] or url
    if rated and rating is not None:
        entry["rated"] = True
        entry["rating"] = float(rating)
    if review_url:
        entry["review_url"] = review_url


def _build_shown(db: Session, user: models.User, profile: models.PublicProfile) -> dict:
    """{pool key: title facts} for every title this member's profile shows anyone right now."""
    shown: dict = {}
    for entry in public_profiles.showcase_items(db, user):
        _note(shown, entry["kind"], entry["title"], entry["year"], url=entry["url"], image=entry["image"],
              rated=True, rating=entry["rating"])
    if profile.show_favorites:
        for entry in public_profiles._favorites(db, user):
            _note(shown, entry["kind"], entry["title"], entry["year"], url=entry["url"], image=entry["image"],
                  rated=True, rating=entry["rating"])
    if profile.show_reviews:
        for review in public_profiles._reviews(db, user):
            kind = title_pages.REVIEW_TO_KIND.get(review["category"])
            matches, year = _year_from_path(review["title_url"], review["title"])
            if kind and matches:
                _note(shown, kind, review["title"], year, url=review["title_url"], image=None, rated=True,
                      rating=review["rating"], review_url=review["url"])
    if profile.show_diary:
        from . import diary
        for entry in diary.public_entries(db, user, public_profiles._visible_categories(user)):
            matches, year = _year_from_path(entry["url"], entry["title"])
            if matches:
                _note(shown, _kind_from_path(entry["url"]), entry["title"], year, url=entry["url"],
                      image=entry["image"], rated=True, rating=entry["rating"])
    if getattr(profile, "show_now", False):
        now = public_profiles._now(db, user)
        for entry in [*now.get("current", []), *now.get("queued", [])]:
            _note(shown, entry["kind"], entry["title"], entry["year"], url=entry["url"], image=entry["image"],
                  rated=False)
    return shown


def shown_titles(db: Session, user: models.User, profile: models.PublicProfile) -> dict:
    try:
        return _cached(("shown", *_profile_stamp(user, profile)), lambda: _build_shown(db, user, profile))
    except Exception:
        db.rollback()
        return {}


def _visible_kinds(user: models.User) -> set[str]:
    return {kind for kind, flag in title_pages.PRIVATE_FLAG.items() if not getattr(user, flag, False)}


# ---------------------------------------------------------------- cards

def _avatar(user: models.User) -> Optional[str]:
    url = user.profile_picture_url or None
    return url if isinstance(url, str) and url.startswith("/") and not url.startswith("//") else None


def _bio(profile: models.PublicProfile) -> Optional[str]:
    text = " ".join((profile.bio or "").split())
    if not text:
        return None
    return text if len(text) <= BIO_CHARS else text[:BIO_CHARS - 1].rsplit(" ", 1)[0] + "…"


def _card(user: models.User, profile: Optional[models.PublicProfile], source: str, reason: str,
          titles: list[dict], **extra) -> dict:
    card = {"id": user.id, "username": user.username, "profile_url": public_profiles.profile_path(user),
            "avatar": _avatar(user), "source": source, "reason": reason, "titles": titles[:TITLES_SHOWN],
            "bio": _bio(profile) if profile is not None else None}
    card.update(extra)
    return card


def _names(titles: list[str]) -> str:
    titles = [t for t in titles if t][:2]
    return " and ".join(titles)


def _title_entry(key: tuple, facts: dict, shared_pool) -> dict:
    kind, _, year = key
    pooled = shared_pool.titles.get(key) if shared_pool is not None else None
    title = facts.get("title") or (pooled or {}).get("display") or ""
    image = facts.get("image") or (pooled or {}).get("image")
    url = facts.get("review_url") or facts.get("url") or title_pages.title_path(kind, title, year)
    return {"title": title, "url": url, "image": image, "label": title_pages.KINDS[kind][3]}


# ---------------------------------------------------------------- groups

def follow_back(db: Session, viewer: models.User) -> list[dict]:
    """Followers the viewer doesn't follow back, newest first. Friends are left out (already close)."""
    rows = db.query(models.User, models.MemberFollow.created_at).join(
        models.MemberFollow, models.MemberFollow.follower_id == models.User.id,
    ).filter(models.MemberFollow.followed_id == viewer.id, models.User.is_active == True).order_by(
        models.MemberFollow.created_at.desc()).limit(FOLLOW_BACK_LIMIT * 4).all()
    if not rows:
        return []
    ids = [user.id for user, _ in rows]
    already = {uid for uid, in db.query(models.MemberFollow.followed_id).filter(
        models.MemberFollow.follower_id == viewer.id, models.MemberFollow.followed_id.in_(ids))}
    friends = friend_feed.friend_ids(db, viewer.id)
    barred_by = {uid for uid, in db.query(models.FollowBar.owner_id).filter(
        models.FollowBar.barred_id == viewer.id, models.FollowBar.owner_id.in_(ids))}
    open_ids = follows.accepting(db, ids)
    pending = set()
    for sender, receiver in db.query(models.FriendRequest.sender_id, models.FriendRequest.receiver_id).filter(
            models.FriendRequest.status == "pending", models.FriendRequest.expires_at > _now(),
            or_(models.FriendRequest.sender_id == viewer.id, models.FriendRequest.receiver_id == viewer.id)):
        pending.add(receiver if sender == viewer.id else sender)
    profiles = {row.user_id: row for row in db.query(models.PublicProfile).filter(
        models.PublicProfile.user_id.in_([uid for uid in ids if uid in open_ids]))} if open_ids else {}
    people = []
    for user, since in rows:
        if user.id in already or user.id in friends or user.id == viewer.id:
            continue
        can_follow = user.id in open_ids and user.id not in barred_by
        people.append(_card(user, profiles.get(user.id) if can_follow else None, "back",
                            f"Followed you {_since(since)}", [],
                            profile_url=public_profiles.profile_path(user) if can_follow else None,
                            can_follow=can_follow, can_friend=not can_follow and user.id not in pending,
                            friend_pending=user.id in pending, since=since.date().isoformat() if since else None))
        if len(people) >= FOLLOW_BACK_LIMIT:
            break
    return people


def _since(when: Optional[datetime]) -> str:
    if when is None:
        return "recently"
    days = (_now().date() - when.date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    return f"on {when.strftime('%b')} {when.day}"


def _taste(db: Session, viewer: models.User, candidates: dict, mine: dict) -> list[dict]:
    if len(mine) < MIN_LIBRARY or not candidates:
        return []
    try:
        shared_pool = picked_for_you.pool(db)
    except Exception:
        db.rollback()
        return []
    dot: dict[int, float] = {}
    overlap: dict[int, int] = {}
    for key, entry in mine.items():
        pooled = shared_pool.titles.get(key)
        if pooled is None:
            continue
        for other in pooled["members"]:
            if other not in candidates:
                continue
            like = shared_pool.likes.get(other, {}).get(key)
            if like is None:
                continue
            dot[other] = dot.get(other, 0.0) + entry["like"] * like
            overlap[other] = overlap.get(other, 0) + 1
    my_norm = sum(entry["like"] ** 2 for entry in mine.values()) ** 0.5 or 1.0
    scored = []
    for other, value in dot.items():
        if value <= 0 or overlap[other] < MIN_SHARED:
            continue
        shrink = overlap[other] / (overlap[other] + 2.0)
        scored.append((value / (my_norm * shared_pool.norms.get(other, 1.0)) * shrink, other))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    cards = []
    for score, other in scored[:TASTE_CANDIDATES]:
        user, profile = candidates[other]
        kinds = _visible_kinds(user)
        theirs = shared_pool.likes.get(other, {})
        shared = [key for key in mine if key in theirs and key[0] in kinds]
        if len(shared) < MIN_SHARED:
            continue
        link_on = bool(profile.show_taste_match)
        shown = shown_titles(db, user, profile)
        nameable = shared if link_on else [key for key in shared if key in shown]
        if not nameable:
            continue  # Never suggest someone on overlap their profile doesn't show.

        def their_rating(key):
            facts = shown.get(key)
            if facts and facts["rated"]:
                return facts["rating"]
            return shared_pool.titles.get(key, {}).get("ratings", {}).get(other) if link_on else None

        def strength(key):
            rating = their_rating(key)
            both_loved = (mine[key]["rating"] or 0) >= LOVED and (rating or 0) >= LOVED
            return (not both_loved, -(mine[key]["like"] + theirs.get(key, 0.0)), shared_pool.titles.get(key, {}).get("display", ""))

        nameable.sort(key=strength)
        loved = [key for key in nameable if (mine[key]["rating"] or 0) >= LOVED and (their_rating(key) or 0) >= LOVED]
        titles = [_title_entry(key, shown.get(key, {}), shared_pool) for key in nameable[:TITLES_SHOWN]]
        named = loved[:2] if loved else nameable[:2]
        names = [_title_entry(key, shown.get(key, {}), shared_pool)["title"] for key in named]
        reason = f"You both {'loved' if loved else 'have'} {_names(names)}"
        extra = {}
        if link_on:
            # Their compare tastes link already shows signed-in members how much they share.
            extra["compare_url"] = public_profiles.profile_path(user) + "/match"
            if len(shared) > len(named):
                reason += f", and {len(shared) - len(named)} more in common"
        cards.append(_card(user, profile, "taste", reason, titles, **extra))
    return cards


def _signals(db: Session, viewer: models.User, visitor_hash: Optional[str], candidates: dict) -> list[dict]:
    try:
        reasons = follows.signal_reasons(db, viewer, visitor_hash)
    except Exception:
        db.rollback()
        return []
    cards = []
    for uid in sorted(reasons, key=lambda uid: candidates[uid][0].username.lower() if uid in candidates else ""):
        if uid in candidates:
            user, profile = candidates[uid]
            cards.append(_card(user, profile, "signal", reasons[uid], []))
    return cards


def _shelf(db: Session, candidates: dict, mine: dict) -> list[dict]:
    """Members with a public review of something in the viewer's library."""
    if not candidates or not mine:
        return []
    found: dict[int, int] = {}
    ids = list(candidates)
    for kind, (model, _, _, _, _) in title_pages.KINDS.items():
        year_column = model.release_date if kind == "game" else model.year
        for start in range(0, len(ids), 400):
            for uid, title, year_value in db.query(model.user_id, model.title, year_column).filter(
                    model.user_id.in_(ids[start:start + 400]), model.review_public == True,
                    model.review.isnot(None),
                    func.length(func.trim(model.review)) >= title_pages.REVIEW_MIN_CHARS).limit(2000):
                key = (kind, title_pages.slugify((title or "").strip()), picked_for_you._year(kind, year_value))
                if key in mine:
                    found[uid] = found.get(uid, 0) + 1
    cards = []
    for uid in sorted(found, key=lambda uid: (-found[uid], uid))[:SHELF_CANDIDATES]:
        user, profile = candidates[uid]
        try:
            reviews = public_profiles._reviews(db, user)
        except Exception:
            db.rollback()
            continue
        titles = []
        for review in reviews:
            kind = title_pages.REVIEW_TO_KIND.get(review["category"])
            matches, year = _year_from_path(review["title_url"], review["title"])
            if kind and matches and (kind, title_pages.slugify(review["title"]), year) in mine:
                titles.append({"title": review["title"], "url": review["url"], "image": None,
                               "label": title_pages.KINDS[kind][3]})
        if not titles:
            continue
        names = [t["title"] for t in titles]
        reason = (f"Reviewed {names[0]}, which is in your library" if len(names) == 1
                  else f"Reviewed {_names(names)} from your library")
        cards.append(_card(user, profile, "shelf", reason, titles))
    return cards


def _active(db: Session, candidates: dict, now: datetime) -> list[dict]:
    """Profiles with something new on them this month, read from what the profile shows anyone."""
    if not candidates:
        return []
    since = now - ACTIVE_WINDOW
    try:
        latest = follows._recently_active(db, set(candidates), since)
    except Exception:
        db.rollback()
        return []
    cards = []
    for uid in sorted(latest, key=lambda uid: latest[uid], reverse=True)[:ACTIVE_CANDIDATES]:
        user, profile = candidates[uid]
        try:
            items = _cached(("active", now.date(), *_profile_stamp(user, profile)),
                            lambda: follows.public_items(db, user, profile, since))
        except Exception:
            db.rollback()
            continue
        if not items:
            continue
        items = sorted(items, key=lambda item: item["when"], reverse=True)
        kinds = [item["kind"] for item in items]
        bits = []
        if kinds.count("review"):
            n = kinds.count("review")
            bits.append("a new review" if n == 1 else f"{n} new reviews")
        if kinds.count("collection"):
            n = kinds.count("collection")
            bits.append("a new list" if n == 1 else f"{n} new lists")
        if kinds.count("diary"):
            n = kinds.count("diary")
            bits.append("1 diary entry" if n == 1 else f"{n} diary entries")
        reason = (" and ".join(bits[:2]) if len(bits) <= 2 else f"{bits[0]}, {bits[1]} and {bits[2]}") + " this month"
        reason = reason[0].upper() + reason[1:]
        titles = [{"title": item["title"], "url": item["url"], "image": item.get("image"), "label": item.get("label")}
                  for item in items[:TITLES_SHOWN]]
        cards.append(_card(user, profile, "active", reason, titles))
    return cards


# ---------------------------------------------------------------- all together

def suggestions(db: Session, viewer: models.User, visitor_hash: Optional[str] = None,
                limit: int = PAGE_LIMIT, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    limit = max(1, min(int(limit or PAGE_LIMIT), PAGE_LIMIT))
    excluded = _excluded(db, viewer.id)
    candidates = {uid: pair for uid, pair in _open_profiles(db).items() if uid not in excluded}
    mine = picked_for_you.own_library(db, viewer.id)
    groups, taken = [], set()
    builders = {
        "taste": lambda pool_: _taste(db, viewer, pool_, mine),
        "signal": lambda pool_: _signals(db, viewer, visitor_hash, pool_),
        "shelf": lambda pool_: _shelf(db, pool_, mine),
        "active": lambda pool_: _active(db, pool_, now),
    }
    total = 0
    for key, title, note in GROUPS:
        if total >= limit:
            break
        left = {uid: pair for uid, pair in candidates.items() if uid not in taken}
        try:
            cards = builders[key](left)
        except Exception:
            db.rollback()
            cards = []
        cards = [card for card in cards if card["id"] not in taken][:limit - total]
        if cards:
            taken.update(card["id"] for card in cards)
            total += len(cards)
            groups.append({"key": key, "title": title, "note": note, "people": cards})
    profile = public_profiles.get_settings(db, viewer.id)
    setting = follows.get_setting(db, viewer.id)
    return {
        "follow_back": follow_back(db, viewer),
        "groups": groups,
        "you": {
            "profile_enabled": bool(profile and profile.enabled),
            "allow_followers": setting.allow_followers if setting else True,
            "suggest_me": setting.suggest_me is not False if setting else True,
            "library": len(mine),
            "needs_titles": max(0, MIN_LIBRARY - len(mine)),
            "following": follows.counts(db, viewer.id)["following"],
        },
    }


def rail(db: Session, viewer: models.User, visitor_hash: Optional[str] = None) -> dict:
    """The rail card: follow-backs first, then the best suggestions, RAIL_LIMIT in all."""
    data = suggestions(db, viewer, visitor_hash, limit=RAIL_LIMIT)
    people = [card for card in data["follow_back"] if card["can_follow"]][:RAIL_LIMIT]
    for group in data["groups"]:
        for card in group["people"]:
            if len(people) < RAIL_LIMIT:
                people.append(card)
    more = len(data["follow_back"]) + sum(len(group["people"]) for group in data["groups"]) > len(people)
    return {"people": people, "more": more, "you": data["you"]}


# ---------------------------------------------------------------- Not for me

def dismiss(db: Session, viewer: models.User, target_id: int) -> bool:
    if target_id == viewer.id:
        return False
    table = models.PeopleSuggestionDismissal
    if db.query(table.id).filter_by(user_id=viewer.id, dismissed_id=target_id).first():
        return False
    if db.get(models.User, target_id) is None:
        return False
    total = db.query(func.count(table.id)).filter(table.user_id == viewer.id).scalar() or 0
    if total >= DISMISS_LIMIT:
        oldest = db.query(table).filter(table.user_id == viewer.id).order_by(table.created_at, table.id).first()
        if oldest is not None:
            db.delete(oldest)
    db.add(table(user_id=viewer.id, dismissed_id=target_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def undismiss(db: Session, viewer: models.User, target_id: int) -> bool:
    removed = db.query(models.PeopleSuggestionDismissal).filter_by(
        user_id=viewer.id, dismissed_id=target_id).delete(synchronize_session=False)
    db.commit()
    return bool(removed)


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "people", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    follow = models.MemberFollow
    active_users = db.query(models.User.id).filter(models.User.is_active == True)
    a = db.query(follow.follower_id.label("a"), follow.followed_id.label("b")).subquery()
    mutual = db.query(func.count()).select_from(follow).join(
        a, (a.c.a == follow.followed_id) & (a.c.b == follow.follower_id)).scalar() or 0
    return {
        "counts": {key: int(counts.get(key) or 0) for key in COUNTERS},
        "labels": COUNTERS,
        "follows_now": int(db.query(func.count(follow.id)).filter(follow.follower_id.in_(active_users),
                                                                   follow.followed_id.in_(active_users)).scalar() or 0),
        "new_follows": int(db.query(func.count(follow.id)).filter(follow.created_at >= now - timedelta(days=days)).scalar() or 0),
        "members_following": int(db.query(func.count(func.distinct(follow.follower_id))).scalar() or 0),
        "members_followed": int(db.query(func.count(func.distinct(follow.followed_id))).scalar() or 0),
        "mutual_pairs": int(mutual) // 2,
        "suggest_off": int(db.query(func.count(models.FollowSetting.id)).filter(
            models.FollowSetting.suggest_me == False).scalar() or 0),
        "suggestable": len(_open_profiles(db)),
    }
