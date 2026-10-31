"""Badges: tiered milestones a member earns from their own library and activity (Oct 2026).

Each badge is a track with three tiers (bronze, silver, gold), e.g. Bookworm at
5, 25 and 100 books read. Counts are never stored: they are counted from the
library, friends, goals and challenges on every look, so a badge can't drift
from the library. Only the highest tier reached is stored (``UserBadge``), so
the member hears about each new tier once and never loses one.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

TIERS = ("Bronze", "Silver", "Gold")

# Library category -> (model, finished flag).
LIBRARY = {
    "movies": (models.Movie, "watched"),
    "tv-shows": (models.TVShow, "watched"),
    "anime": (models.Anime, "watched"),
    "video-games": (models.VideoGame, "played"),
    "music": (models.Music, "listened"),
    "books": (models.Book, "read"),
    "manga": (models.Manga, "read"),
    "podcasts": (models.Podcast, "listened"),
    "audiobooks": (models.Audiobook, "listened"),
}

# Each track: key, name, emoji, what is counted, the three tier targets, the "do more"
# wording for the next tier, the dashboard link that helps, and which library shelf it
# reveals on a public profile (None: it shows only aggregate counts).
TRACKS = (
    {"key": "collector", "name": "Collector", "emoji": "🗃️", "metric": "titles", "targets": (5, 50, 250),
     "counts": "titles tracked", "next": "Track {n} more {noun}", "noun": ("title", "titles"), "shelf": None},
    {"key": "cinephile", "name": "Cinephile", "emoji": "🎬", "metric": "movies", "targets": (10, 50, 200),
     "counts": "movies watched", "next": "Watch {n} more {noun}", "noun": ("movie", "movies"), "shelf": "movies"},
    {"key": "binge", "name": "Binge Watcher", "emoji": "📺", "metric": "tv-shows", "targets": (5, 25, 100),
     "counts": "TV shows watched", "next": "Finish {n} more {noun}", "noun": ("show", "shows"), "shelf": "tv-shows"},
    {"key": "anime", "name": "Anime Devotee", "emoji": "🍥", "metric": "anime", "targets": (5, 25, 100),
     "counts": "anime watched", "next": "Finish {n} more {noun}", "noun": ("anime", "anime"), "shelf": "anime"},
    {"key": "player", "name": "Player One", "emoji": "🎮", "metric": "video-games", "targets": (5, 25, 100),
     "counts": "games played", "next": "Play {n} more {noun}", "noun": ("game", "games"), "shelf": "video-games"},
    {"key": "crate", "name": "Crate Digger", "emoji": "🎧", "metric": "music", "targets": (10, 50, 200),
     "counts": "albums listened to", "next": "Listen to {n} more {noun}", "noun": ("album", "albums"), "shelf": "music"},
    {"key": "bookworm", "name": "Bookworm", "emoji": "📖", "metric": "books", "targets": (5, 25, 100),
     "counts": "books read", "next": "Read {n} more {noun}", "noun": ("book", "books"), "shelf": "books"},
    {"key": "mangaka", "name": "Manga Reader", "emoji": "🗯️", "metric": "manga", "targets": (5, 25, 100),
     "counts": "manga series read", "next": "Finish {n} more manga {noun}", "noun": ("series", "series"), "shelf": "manga"},
    {"key": "regular", "name": "Podcast Regular", "emoji": "🎙️", "metric": "podcasts", "targets": (5, 25, 100),
     "counts": "podcasts listened to", "next": "Listen to {n} more {noun}", "noun": ("podcast", "podcasts"), "shelf": "podcasts"},
    {"key": "earful", "name": "All Ears", "emoji": "🔊", "metric": "audiobooks", "targets": (5, 25, 100),
     "counts": "audiobooks finished", "next": "Finish {n} more {noun}", "noun": ("audiobook", "audiobooks"), "shelf": "audiobooks"},
    {"key": "explorer", "name": "Explorer", "emoji": "🧭", "metric": "categories", "targets": (2, 4, 6),
     "counts": "of the nine categories tracked", "next": "Track something in {n} more {noun}",
     "noun": ("category", "categories"), "shelf": None},
    {"key": "rater", "name": "Rater", "emoji": "⭐", "metric": "rated", "targets": (10, 50, 250),
     "counts": "titles rated", "next": "Rate {n} more {noun}", "noun": ("title", "titles"), "shelf": None},
    {"key": "critic", "name": "Critic", "emoji": "✍️", "metric": "reviews", "targets": (1, 10, 50),
     "counts": "reviews written", "one": "review written", "next": "Write {n} more {noun}", "noun": ("review", "reviews"), "shelf": None},
    {"key": "voice", "name": "Public Voice", "emoji": "📣", "metric": "public_reviews", "targets": (1, 5, 25),
     "counts": "public reviews", "one": "public review", "next": "Make {n} more {noun} public", "noun": ("review", "reviews"), "shelf": None},
    {"key": "curator", "name": "Curator", "emoji": "🗂️", "metric": "collections", "targets": (1, 3, 10),
     "counts": "collections made", "one": "collection made", "next": "Make {n} more {noun}", "noun": ("collection", "collections"), "shelf": None},
    {"key": "company", "name": "Good Company", "emoji": "🤝", "metric": "friends", "targets": (1, 5, 15),
     "counts": "friends", "one": "friend", "next": "Add {n} more {noun}", "noun": ("friend", "friends"), "shelf": None},
    {"key": "recruiter", "name": "Recruiter", "emoji": "🎟️", "metric": "invited", "targets": (1, 3, 10),
     "counts": "friends brought to OmniTrackr", "one": "friend brought to OmniTrackr", "next": "Invite {n} more {noun}", "noun": ("friend", "friends"),
     "shelf": None},
    {"key": "regular", "name": "Regular", "emoji": "🔥", "metric": "visit_days", "targets": (7, 30, 100),
     "counts": "days visited", "next": "Visit on {n} more {noun}", "noun": ("day", "days"), "shelf": None},
    {"key": "goals", "name": "Goal Getter", "emoji": "🎯", "metric": "goals", "targets": (1, 3, 6),
     "counts": "yearly goals reached", "one": "yearly goal reached", "next": "Reach {n} more {noun}", "noun": ("goal", "goals"), "shelf": None},
    {"key": "challenger", "name": "Challenger", "emoji": "🏆", "metric": "challenges", "targets": (1, 3, 6),
     "counts": "monthly challenges completed", "one": "monthly challenge completed", "next": "Complete {n} more {noun}",
     "noun": ("challenge", "challenges"), "shelf": None},
)
BY_KEY = {track["key"]: track for track in TRACKS}
TOTAL_LEVELS = len(TRACKS) * len(TIERS)
# Where on the dashboard each badge's next step happens.
LINKS = {
    "goals": "/#goals", "challenger": "/#challenge", "recruiter": "/#invite-friends", "company": "/#invite-friends",
}
NEXT_COUNT = 3


def _has_text(column):
    return func.length(func.trim(func.coalesce(column, ""))) > 0


def counts(db: Session, user: models.User) -> dict:
    """Every metric the tracks count, from the member's own rows."""
    result = {"titles": 0, "categories": 0, "rated": 0, "reviews": 0, "public_reviews": 0}
    for category, (model, flag) in LIBRARY.items():
        total, finished, rated, reviews, public = db.query(
            func.count(model.id),
            func.sum(case((getattr(model, flag).is_(True), 1), else_=0)),
            func.count(model.rating),
            func.sum(case((_has_text(model.review), 1), else_=0)),
            func.sum(case((_has_text(model.review) & model.review_public.is_(True), 1), else_=0)),
        ).filter(model.user_id == user.id).one()
        result[category] = int(finished or 0)
        result["titles"] += int(total or 0)
        result["categories"] += 1 if total else 0
        result["rated"] += int(rated or 0)
        result["reviews"] += int(reviews or 0)
        result["public_reviews"] += int(public or 0)
    result["collections"] = db.query(models.Collection.id).filter(models.Collection.user_id == user.id).count()
    result["friends"] = db.query(models.Friendship.id).filter(
        (models.Friendship.user1_id == user.id) | (models.Friendship.user2_id == user.id)).count()
    from .friend_invites import friends_brought
    result["invited"] = friends_brought(db, user.id)
    result["visit_days"] = int(user.visit_days or 0)
    result["goals"] = db.query(models.GoalAchievement.id).filter(models.GoalAchievement.user_id == user.id).count()
    result["challenges"] = db.query(models.MonthlyChallengeEntry.id).filter(
        models.MonthlyChallengeEntry.user_id == user.id, models.MonthlyChallengeEntry.completed_at.isnot(None)).count()
    return result


def tier_for(track: dict, count: int) -> int:
    """0 (not yet) to 3 (gold)."""
    return sum(1 for target in track["targets"] if count >= target)


def counts_label(track: dict, n: int) -> str:
    """'reviews written', or 'review written' for "0 of 1" and "1+"."""
    return track.get("one", track["counts"]) if n == 1 else track["counts"]


def _noun(track: dict, n: int) -> str:
    singular, plural = track["noun"]
    return singular if n == 1 else plural


def badge_row(track: dict, count: int, stored: Optional[models.UserBadge] = None) -> dict:
    tier = max(tier_for(track, count), stored.tier if stored else 0)
    row = {
        "key": track["key"], "name": track["name"], "emoji": track["emoji"], "count": count,
        "counts": track["counts"], "tier": tier, "tier_name": TIERS[tier - 1] if tier else None,
        "targets": list(track["targets"]), "link": LINKS.get(track["key"]),
        "earned_at": stored.earned_at.isoformat() if stored and stored.earned_at else None,
        "new": bool(stored and stored.seen_at is None),
    }
    if tier < len(TIERS):
        target = track["targets"][tier]
        row["counts"] = counts_label(track, target)
        remaining = max(target - count, 0)
        action = track["next"].format(n=remaining, noun=_noun(track, remaining))
        row.update(next_target=target, next_tier_name=TIERS[tier], remaining=remaining,
                   percent=min(100, int(count * 100 / target)), action=action,
                   hint=f"{action} for {TIERS[tier].lower()}")
    else:
        row.update(next_target=None, next_tier_name=None, remaining=0, percent=100, action=None,
                   hint="Top tier reached")
    return row


def _stored(db: Session, user_id: int) -> dict:
    return {row.badge: row for row in db.query(models.UserBadge).filter_by(user_id=user_id).all()}


def _announce(db: Session, user_id: int, new: list[tuple[dict, int]], first_look: bool) -> None:
    from .crud.friends import create_notification
    if first_look and len(new) > 1:
        message = f"Badges are here: you've already earned {len(new)} of them. Take a look at your trophy case."
    elif len(new) == 1:
        track, tier = new[0]
        message = f"New badge: {track['name']} ({TIERS[tier - 1].lower()}). See what's next in your trophy case."
    else:
        names = [f"{track['name']} ({TIERS[tier - 1].lower()})" for track, tier in new]
        message = f"{len(new)} new badges: {', '.join(names[:-1])} and {names[-1]}."
    # The link must be set before the first flush: that is when the push is queued.
    create_notification(db, user_id, "badge_earned", message, link="/#badges")


def record(db: Session, user: models.User, metric_counts: dict) -> dict:
    """Store tiers reached for the first time and tell the member once. Returns {badge: UserBadge}."""
    stored = _stored(db, user.id)
    first_look = not stored
    new: list[tuple[dict, int]] = []
    now = datetime.utcnow()
    for track in TRACKS:
        tier = tier_for(track, metric_counts.get(track["metric"], 0))
        if not tier:
            continue
        row = stored.get(track["key"])
        if row is None:
            db.add(models.UserBadge(user_id=user.id, badge=track["key"], tier=tier, earned_at=now))
            new.append((track, tier))
        elif row.tier < tier:
            # Claim the new tier atomically so overlapping dashboard loads announce it once.
            claimed = (db.query(models.UserBadge)
                       .filter(models.UserBadge.id == row.id, models.UserBadge.tier < tier)
                       .update({"tier": tier, "earned_at": now, "seen_at": None}, synchronize_session=False))
            if claimed:
                new.append((track, tier))
    if not new:
        return stored
    try:
        db.commit()
    except IntegrityError:
        # Another request recorded the same badge first; it sends the notification.
        db.rollback()
        return _stored(db, user.id)
    _announce(db, user.id, new, first_look)
    return _stored(db, user.id)


def closest(rows: list[dict], limit: int = NEXT_COUNT) -> list[dict]:
    """The badges nearest their next tier: started ones first, by how close they are."""
    open_rows = [row for row in rows if row["next_target"]]
    return sorted(open_rows, key=lambda row: (row["count"] == 0, -row["percent"], row["remaining"]))[:limit]


def payload(db: Session, user: models.User) -> dict:
    metric_counts = counts(db, user)
    stored = record(db, user, metric_counts)
    rows = [badge_row(track, metric_counts.get(track["metric"], 0), stored.get(track["key"])) for track in TRACKS]
    earned = sum(row["tier"] for row in rows)
    return {
        "badges": rows,
        "earned_levels": earned,
        "total_levels": TOTAL_LEVELS,
        "earned_badges": sum(1 for row in rows if row["tier"]),
        "gold": sum(1 for row in rows if row["tier"] == len(TIERS)),
        "next": [row["key"] for row in closest(rows)],
        "celebrate": [row["key"] for row in rows if row["new"]],
    }


def mark_seen(db: Session, user_id: int) -> int:
    changed = (db.query(models.UserBadge)
               .filter(models.UserBadge.user_id == user_id, models.UserBadge.seen_at.is_(None))
               .update({"seen_at": datetime.utcnow()}, synchronize_session=False))
    db.commit()
    return changed


def public_badges(db: Session, user: models.User) -> list[dict]:
    """Earned badges for a public profile: stored tiers only, and none that reveal a private shelf."""
    from .goals import PRIVACY
    rows = []
    stored = _stored(db, user.id)
    for track in TRACKS:
        row = stored.get(track["key"])
        if row is None or not 1 <= row.tier <= len(TIERS):
            continue
        shelf = track["shelf"]
        if shelf and getattr(user, PRIVACY[shelf], False):
            continue
        rows.append({"key": track["key"], "name": track["name"], "emoji": track["emoji"], "tier": row.tier,
                     "tier_name": TIERS[row.tier - 1],
                     "label": f'{track["targets"][row.tier - 1]}+ {counts_label(track, track["targets"][row.tier - 1])}'})
    rows.sort(key=lambda row: -row["tier"])
    return rows


def digest_line(db: Session, user: models.User) -> Optional[dict]:
    """The started badge nearest its next tier, for the weekly email. Read-only."""
    metric_counts = counts(db, user)
    stored = _stored(db, user.id)
    rows = [badge_row(track, metric_counts.get(track["metric"], 0), stored.get(track["key"])) for track in TRACKS]
    for row in closest(rows, limit=1):
        if row["count"] and row["percent"] >= 50:
            return {"name": row["name"], "emoji": row["emoji"], "tier_name": row["next_tier_name"],
                    "action": row["action"], "count": row["count"], "target": row["next_target"],
                    "earned_levels": sum(r["tier"] for r in rows), "total_levels": TOTAL_LEVELS}
    return None
