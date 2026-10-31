"""Following members' public profiles without being friends (Oct 2026).

A follow is one-way and grants nothing: a follower sees exactly what the member's
public profile already shows anyone, built by the same functions the profile page
uses (public_profiles._reviews, _collections and diary.public_entries). So:

- only members with a public profile switched on can be followed, and only while
  they allow followers,
- categories the member made private, reviews that fail the public checks or were
  unlisted by reports, unpublished collections and the diary (unless switched on)
  never reach a follower,
- nothing friends-only is used: not the friends feed, not library adds, not notes.

Removing a follower also stops them following again until the member undoes it.
Turning followers off removes everyone. Deactivated accounts drop out of every
list and feed but keep their rows, so reactivating brings follows back.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import diary, models, public_profiles, title_pages

MAX_FOLLOWING = 500
DAILY_FOLLOWS = 100
FEED_WINDOW = timedelta(days=60)
FEED_LIMIT = 40
# Profiles built per feed request, most recently active first (each one is a few dozen queries).
FEED_SOURCES = 25
SUGGESTIONS_LIMIT = 6
NOTIFY_AGAIN_AFTER = timedelta(days=7)
EMAIL_WINDOW = timedelta(days=7)
EMAIL_SHOWN = 5
SETTINGS_LINK = "/#followers"
NOTIFICATION_TYPE = "new_follower"


class FollowError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


# ---------------------------------------------------------------- settings

def get_setting(db: Session, user_id: int) -> Optional[models.FollowSetting]:
    return db.query(models.FollowSetting).filter(models.FollowSetting.user_id == user_id).first()


def settings_payload(db: Session, user_id: int) -> dict:
    row = get_setting(db, user_id)
    profile = public_profiles.get_settings(db, user_id)
    return {
        "allow_followers": row.allow_followers if row else True,
        "email_following": row.email_following if row else True,
        "profile_enabled": bool(profile and profile.enabled),
        "counts": counts(db, user_id),
    }


def save_settings(db: Session, user_id: int, allow_followers: Optional[bool] = None,
                  email_following: Optional[bool] = None) -> models.FollowSetting:
    row = get_setting(db, user_id)
    if row is None:
        row = models.FollowSetting(user_id=user_id)
        db.add(row)
    if allow_followers is not None:
        row.allow_followers = bool(allow_followers)
        if not allow_followers:
            db.query(models.MemberFollow).filter(models.MemberFollow.followed_id == user_id).delete(
                synchronize_session=False)
    if email_following is not None:
        row.email_following = bool(email_following)
    db.commit()
    db.refresh(row)
    return row


def accepting(db: Session, user_ids) -> set[int]:
    """The members among ``user_ids`` who can be followed right now."""
    ids = {int(i) for i in user_ids if i is not None}
    if not ids:
        return set()
    rows = db.query(models.User.id, models.FollowSetting.allow_followers).join(
        models.PublicProfile, models.PublicProfile.user_id == models.User.id,
    ).outerjoin(models.FollowSetting, models.FollowSetting.user_id == models.User.id).filter(
        models.User.id.in_(ids), models.User.is_active == True, models.PublicProfile.enabled == True,
    ).all()
    return {uid for uid, allow in rows if allow is not False}


def _barred(db: Session, owner_id: int, user_id: int) -> bool:
    return db.query(models.FollowBar.id).filter_by(owner_id=owner_id, barred_id=user_id).first() is not None


# ---------------------------------------------------------------- following

def is_following(db: Session, follower_id: Optional[int], followed_id: int) -> bool:
    if not follower_id:
        return False
    return db.query(models.MemberFollow.id).filter_by(
        follower_id=follower_id, followed_id=followed_id).first() is not None


def follow(db: Session, follower: models.User, target: Optional[models.User]) -> bool:
    """Follow ``target``. Returns False when already following. Raises FollowError otherwise."""
    if target is None or not target.is_active:
        raise FollowError(404, "Profile not found")
    if target.id == follower.id:
        raise FollowError(422, "You can't follow yourself.")
    if public_profiles.visible_profile(db, target) is None:
        raise FollowError(404, "Profile not found")
    if is_following(db, follower.id, target.id):
        return False
    # A removed follower gets the same answer as everyone when followers are off.
    if target.id not in accepting(db, [target.id]) or _barred(db, target.id, follower.id):
        raise FollowError(403, f"{target.username} isn't taking new followers.")
    following = db.query(func.count(models.MemberFollow.id)).filter(
        models.MemberFollow.follower_id == follower.id).scalar() or 0
    if following >= MAX_FOLLOWING:
        raise FollowError(422, f"You can follow up to {MAX_FOLLOWING} people. Unfollow someone first.")
    today = db.query(func.count(models.MemberFollow.id)).filter(
        models.MemberFollow.follower_id == follower.id,
        models.MemberFollow.created_at > datetime.utcnow() - timedelta(days=1)).scalar() or 0
    if today >= DAILY_FOLLOWS:
        raise FollowError(429, "That's a lot of new follows for one day. Try again tomorrow.")
    db.add(models.MemberFollow(follower_id=follower.id, followed_id=target.id))
    _notify(db, follower, target)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def _notify(db: Session, follower: models.User, target: models.User) -> None:
    """One bell notice per follower a week, so following and unfollowing can't flood the bell."""
    message = f"{follower.username} started following your profile."[:250]
    recent = db.query(models.Notification.id).filter(
        models.Notification.user_id == target.id, models.Notification.type == NOTIFICATION_TYPE,
        models.Notification.message == message,
        models.Notification.created_at > datetime.utcnow() - NOTIFY_AGAIN_AFTER).first()
    if recent is None:
        db.add(models.Notification(user_id=target.id, type=NOTIFICATION_TYPE, message=message, link=SETTINGS_LINK))


def unfollow(db: Session, follower_id: int, followed_id: int) -> bool:
    removed = db.query(models.MemberFollow).filter_by(
        follower_id=follower_id, followed_id=followed_id).delete(synchronize_session=False)
    db.commit()
    return bool(removed)


def remove_follower(db: Session, owner_id: int, follower_id: int) -> bool:
    """Take someone off the member's followers and stop them following again."""
    if follower_id == owner_id:
        return False
    removed = db.query(models.MemberFollow).filter_by(
        follower_id=follower_id, followed_id=owner_id).delete(synchronize_session=False)
    if not _barred(db, owner_id, follower_id):
        db.add(models.FollowBar(owner_id=owner_id, barred_id=follower_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return bool(removed)


def allow_again(db: Session, owner_id: int, barred_id: int) -> bool:
    removed = db.query(models.FollowBar).filter_by(owner_id=owner_id, barred_id=barred_id).delete(
        synchronize_session=False)
    db.commit()
    return bool(removed)


# ---------------------------------------------------------------- lists and counts

def _following_ids(db: Session, follower_id: int) -> list[int]:
    rows = db.query(models.MemberFollow.followed_id).filter(
        models.MemberFollow.follower_id == follower_id).order_by(models.MemberFollow.created_at.desc()).all()
    return [uid for uid, in rows]


def counts(db: Session, user_id: int) -> dict:
    """Followers who are still active, and people followed who can still be followed."""
    followers = db.query(func.count(models.MemberFollow.id)).join(
        models.User, models.User.id == models.MemberFollow.follower_id,
    ).filter(models.MemberFollow.followed_id == user_id, models.User.is_active == True).scalar() or 0
    following = len(accepting(db, _following_ids(db, user_id)))
    return {"followers": int(followers), "following": following}


def _person(user: models.User, path: Optional[str], since: datetime) -> dict:
    return {"id": user.id, "username": user.username, "profile_url": path,
            "since": since.date().isoformat() if since else None}


def followers_list(db: Session, owner_id: int) -> list[dict]:
    rows = db.query(models.User, models.MemberFollow.created_at).join(
        models.MemberFollow, models.MemberFollow.follower_id == models.User.id,
    ).filter(models.MemberFollow.followed_id == owner_id, models.User.is_active == True).order_by(
        models.MemberFollow.created_at.desc()).limit(MAX_FOLLOWING).all()
    paths = public_profiles.enabled_profile_paths(db, [user.id for user, _ in rows])
    return [_person(user, paths.get(user.id), since) for user, since in rows]


def following_list(db: Session, follower_id: int) -> list[dict]:
    rows = db.query(models.User, models.MemberFollow.created_at).join(
        models.MemberFollow, models.MemberFollow.followed_id == models.User.id,
    ).filter(models.MemberFollow.follower_id == follower_id).order_by(
        models.MemberFollow.created_at.desc()).limit(MAX_FOLLOWING).all()
    open_ids = accepting(db, [user.id for user, _ in rows])
    return [_person(user, public_profiles.profile_path(user), since) for user, since in rows if user.id in open_ids]


def barred_list(db: Session, owner_id: int) -> list[dict]:
    rows = db.query(models.User, models.FollowBar.created_at).join(
        models.FollowBar, models.FollowBar.barred_id == models.User.id,
    ).filter(models.FollowBar.owner_id == owner_id, models.User.is_active == True).order_by(
        models.FollowBar.created_at.desc()).limit(MAX_FOLLOWING).all()
    return [_person(user, None, since) for user, since in rows]


# ---------------------------------------------------------------- what followers see

def _review_dates(db: Session, user: models.User, reviews: list[dict]) -> dict:
    """{(review category, id): (when, image)}: when the review was written, else when the title was added."""
    by_kind: dict[str, list[int]] = {}
    for review in reviews:
        by_kind.setdefault(title_pages.REVIEW_TO_KIND[review["category"]], []).append(review["id"])
    found = {}
    for kind, ids in by_kind.items():
        model, review_category, library, _, _ = title_pages.KINDS[kind]
        written = dict(db.query(models.FriendFeedEvent.item_id, func.max(models.FriendFeedEvent.created_at)).filter(
            models.FriendFeedEvent.user_id == user.id, models.FriendFeedEvent.category == library,
            models.FriendFeedEvent.kind == "reviewed", models.FriendFeedEvent.item_id.in_(ids),
        ).group_by(models.FriendFeedEvent.item_id).all())
        image_field = title_pages.IMAGE_FIELD[kind]
        for item in db.query(model).filter(model.id.in_(ids), model.user_id == user.id):
            found[(review_category, item.id)] = (written.get(item.id) or item.added_at,
                                                 title_pages._safe_image(getattr(item, image_field, None)))
    return found


def public_items(db: Session, user: models.User, profile: models.PublicProfile, since: datetime) -> list[dict]:
    """What ``user``'s public profile shows that is newer than ``since``, as feed items."""
    path = public_profiles.profile_path(user)
    base = {"user_id": user.id, "username": user.username, "profile_url": path}
    items = []
    if profile.show_reviews:
        reviews = public_profiles._reviews(db, user)
        dates = _review_dates(db, user, reviews)
        for review in reviews:
            when, image = dates.get((review["category"], review["id"]), (None, None))
            if when is None or when < since:
                continue
            spoilers = bool(review.get("spoilers"))
            excerpt = "" if spoilers else " ".join(review["review"].split())
            if len(excerpt) > 240:
                excerpt = excerpt[:240].rsplit(" ", 1)[0] + "…"
            items.append({**base, "kind": "review", "when": when, "title": review["title"], "label": review["label"],
                          "rating": review["rating"], "url": review["url"], "title_url": review["title_url"],
                          "excerpt": excerpt, "spoilers": spoilers, "image": image})
    if profile.show_collections:
        shown = public_profiles._collections(db, user)
        ids = [int(entry["url"].rsplit("/", 1)[1]) for entry in shown]
        published = dict(db.query(models.Collection.id, func.coalesce(
            models.Collection.published_at, models.Collection.created_at)).filter(models.Collection.id.in_(ids)).all()) if ids else {}
        for entry, collection_id in zip(shown, ids):
            when = published.get(collection_id)
            if when is None or when < since:
                continue
            items.append({**base, "kind": "collection", "when": when, "title": entry["name"], "label": "Collection",
                          "url": entry["url"], "excerpt": entry["description"], "count": entry["items"]})
    if profile.show_diary:
        for entry in diary.public_entries(db, user, public_profiles._visible_categories(user)):
            when = datetime.combine(entry["date"], time(12))
            if when < since:
                continue
            items.append({**base, "kind": "diary", "when": when, "title": entry["title"], "label": entry["label"],
                          "rating": entry["rating"], "url": entry["url"], "image": entry["image"],
                          "repeat": entry["repeat"], "visit_label": entry["visit_label"]})
    return items


def _recently_active(db: Session, user_ids: set[int], since: datetime) -> dict[int, datetime]:
    """{user_id: latest public-looking activity} to pick which profiles are worth building."""
    latest: dict[int, datetime] = {}

    def note(rows):
        for uid, when in rows:
            if when is not None and (uid not in latest or when > latest[uid]):
                latest[uid] = when

    note(db.query(models.ActivityEntry.user_id, func.max(models.ActivityEntry.occurred_at)).filter(
        models.ActivityEntry.user_id.in_(user_ids), models.ActivityEntry.action.in_(diary.DIARY_ACTIONS),
        models.ActivityEntry.occurred_at >= since).group_by(models.ActivityEntry.user_id).all())
    note(db.query(models.Collection.user_id, func.max(func.coalesce(
        models.Collection.published_at, models.Collection.created_at))).filter(
        models.Collection.user_id.in_(user_ids), models.Collection.is_public == True,
        func.coalesce(models.Collection.published_at, models.Collection.created_at) >= since,
    ).group_by(models.Collection.user_id).all())
    note(db.query(models.FriendFeedEvent.user_id, func.max(models.FriendFeedEvent.created_at)).filter(
        models.FriendFeedEvent.user_id.in_(user_ids), models.FriendFeedEvent.kind == "reviewed",
        models.FriendFeedEvent.created_at >= since).group_by(models.FriendFeedEvent.user_id).all())
    for model, _, _, _, _ in title_pages.KINDS.values():
        note(db.query(model.user_id, func.max(model.added_at)).filter(
            model.user_id.in_(user_ids), model.review_public == True, model.added_at >= since,
        ).group_by(model.user_id).all())
    return latest


def feed(db: Session, viewer_id: int, now: Optional[datetime] = None, window: timedelta = FEED_WINDOW,
         limit: int = FEED_LIMIT) -> list[dict]:
    """Newest public reviews, collections and diary entries from the people ``viewer_id`` follows."""
    now = now or datetime.utcnow()
    since = now - window
    open_ids = accepting(db, _following_ids(db, viewer_id)) - {viewer_id}
    if not open_ids:
        return []
    active = _recently_active(db, open_ids, since)
    chosen = sorted(active, key=lambda uid: active[uid], reverse=True)[:FEED_SOURCES]
    if not chosen:
        return []
    rows = db.query(models.User, models.PublicProfile).join(
        models.PublicProfile, models.PublicProfile.user_id == models.User.id).filter(models.User.id.in_(chosen)).all()
    items = []
    for user, profile in rows:
        try:
            items.extend(public_items(db, user, profile, since))
        except Exception:
            db.rollback()  # One profile that can't be built never hides the rest.
    items.sort(key=lambda item: item["when"], reverse=True)
    return items[:limit]


def serialize(item: dict) -> dict:
    out = {key: value for key, value in item.items() if key != "when"}
    out["date"] = item["when"].date().isoformat()
    return out


# ---------------------------------------------------------------- suggestions

def suggestions(db: Session, viewer: models.User, visitor_hash: Optional[str]) -> list[dict]:
    """People worth following: writers of reviews this browser marked helpful, and curators of
    collections the member saved. Only members who can be followed and aren't already."""
    reasons: dict[int, str] = {}
    if visitor_hash:
        marks = db.query(models.ReviewReaction.category, models.ReviewReaction.item_id).filter(
            models.ReviewReaction.visitor_hash == visitor_hash).order_by(
            models.ReviewReaction.created_at.desc()).limit(200).all()
        by_kind: dict[str, set[int]] = {}
        for category, item_id in marks:
            kind = title_pages.REVIEW_TO_KIND.get(category)
            if kind:
                by_kind.setdefault(kind, set()).add(item_id)
        for kind, ids in by_kind.items():
            model = title_pages.KINDS[kind][0]
            for uid, in db.query(model.user_id).filter(model.id.in_(ids), model.review_public == True).distinct():
                reasons.setdefault(uid, "You found their review helpful")
    sources = [cid for cid, in db.query(models.CollectionSaveReceipt.source_collection_id).filter(
        models.CollectionSaveReceipt.user_id == viewer.id).limit(200)]
    if sources:
        for uid, in db.query(models.Collection.user_id).filter(
                models.Collection.id.in_(sources), models.Collection.is_public == True).distinct():
            reasons.setdefault(uid, "You saved one of their collections")
    reasons.pop(viewer.id, None)
    if not reasons:
        return []
    already = set(_following_ids(db, viewer.id))
    barred_by = {owner for owner, in db.query(models.FollowBar.owner_id).filter(
        models.FollowBar.barred_id == viewer.id, models.FollowBar.owner_id.in_(list(reasons)))}
    open_ids = accepting(db, [uid for uid in reasons if uid not in already and uid not in barred_by])
    users = db.query(models.User).filter(models.User.id.in_(open_ids)).order_by(func.lower(models.User.username)).all() if open_ids else []
    return [{"id": user.id, "username": user.username, "profile_url": public_profiles.profile_path(user),
             "reason": reasons[user.id]} for user in users[:SUGGESTIONS_LIMIT]]


# ---------------------------------------------------------------- weekly email

def email_items(db: Session, user: models.User, now: datetime) -> list[dict]:
    """The weekly email's "From people you follow" lines, unless the member switched the section off."""
    row = get_setting(db, user.id)
    if row is not None and not row.email_following:
        return []
    return feed(db, user.id, now=now, window=EMAIL_WINDOW, limit=EMAIL_SHOWN)
