"""Shared lists: a list a few members build together, like a couple's watchlist.

* The owner creates a list and brings people in: a friend with one click, or
  anyone through the list's join link (``/lists/join/<token>``). A visitor
  without an account sees a preview and signs up from it.
* Every member can add titles, say "I'm in" on the ones they want, mark a title
  done and copy it into their own library. Each title shows who added it.
* Items are title references (kind, title, year, art), never library rows, so a
  list never reads or changes anyone's library. Only new tables are used.
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, title_pages, title_search
from .crud.friends import are_friends, get_friends

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{16,32}")
OWNED_MAX = 20
JOINED_MAX = 50
MEMBERS_MAX = 12
ITEMS_MAX = 300
PREVIEW_ITEMS = 8
KIND_LABELS = {"movie": "Movie", "tv": "TV show", "anime": "Anime", "game": "Game", "book": "Book", "album": "Album"}


class ListError(Exception):
    """A request the list can't take, with a message the member can read."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def valid_token(token) -> bool:
    return isinstance(token, str) and TOKEN_RE.fullmatch(token) is not None


def join_url(shared: models.SharedList) -> str:
    return f"{SITE_URL}/lists/join/{shared.token}"


def normalized_key(title: str, year: Optional[int]) -> str:
    key = title_pages.normalize(title)[:190]
    return f"{key} ({year})" if year else key


def _now() -> datetime:
    return datetime.utcnow()


def _membership(db: Session, list_id: int, user_id: int) -> Optional[models.SharedListMember]:
    return db.query(models.SharedListMember).filter_by(list_id=list_id, user_id=user_id).first()


def get_for_member(db: Session, list_id: int, user) -> tuple[models.SharedList, models.SharedListMember]:
    """The list and the member's row; a list they aren't in looks the same as one that doesn't exist."""
    shared = db.get(models.SharedList, list_id)
    member = _membership(db, list_id, user.id) if shared is not None else None
    if member is None:
        raise ListError("List not found", 404)
    return shared, member


def by_token(db: Session, token) -> Optional[models.SharedList]:
    if not valid_token(token):
        return None
    return db.query(models.SharedList).filter(models.SharedList.token == token).first()


def _member_rows(db: Session, list_id: int) -> list[tuple[models.SharedListMember, models.User]]:
    return (db.query(models.SharedListMember, models.User)
            .join(models.User, models.User.id == models.SharedListMember.user_id)
            .filter(models.SharedListMember.list_id == list_id, models.User.is_active.is_(True))
            .order_by(models.SharedListMember.joined_at, models.SharedListMember.id).all())


def _notify(db: Session, user_id: int, kind: str, message: str, link: str) -> None:
    db.add(models.Notification(user_id=user_id, type=kind, message=message[:250], link=link))


def create(db: Session, user, name: str, description: Optional[str]) -> models.SharedList:
    owned = db.query(models.SharedList.id).filter(models.SharedList.owner_id == user.id).count()
    if owned >= OWNED_MAX:
        raise ListError(f"You can have up to {OWNED_MAX} shared lists. Delete one you no longer use to start another.")
    shared = models.SharedList(owner_id=user.id, name=name, description=description or None,
                               token=secrets.token_urlsafe(16))
    db.add(shared)
    db.flush()
    db.add(models.SharedListMember(list_id=shared.id, user_id=user.id, seen_at=_now()))
    db.commit()
    db.refresh(shared)
    return shared


def update(db: Session, shared: models.SharedList, user, name: Optional[str], description: Optional[str]) -> None:
    if shared.owner_id != user.id:
        raise ListError("Only the person who made this list can rename it.", 403)
    if name is not None:
        shared.name = name
    if description is not None:
        shared.description = description or None
    shared.updated_at = _now()
    db.commit()


def reset_link(db: Session, shared: models.SharedList, user) -> None:
    if shared.owner_id != user.id:
        raise ListError("Only the person who made this list can change its link.", 403)
    shared.token = secrets.token_urlsafe(16)
    db.commit()


def delete(db: Session, shared: models.SharedList, user) -> None:
    if shared.owner_id != user.id:
        raise ListError("Only the person who made this list can delete it.", 403)
    item_ids = [item_id for item_id, in db.query(models.SharedListItem.id).filter_by(list_id=shared.id)]
    if item_ids:
        db.query(models.SharedListVote).filter(models.SharedListVote.item_id.in_(item_ids)).delete(synchronize_session=False)
    db.delete(shared)
    db.commit()


def _joined_count(db: Session, user_id: int) -> int:
    return db.query(models.SharedListMember.id).filter(models.SharedListMember.user_id == user_id).count()


def _add_member(db: Session, shared: models.SharedList, user) -> bool:
    """Add someone to the list. False when they were already in it. Does not commit."""
    if _membership(db, shared.id, user.id) is not None:
        return False
    if len(_member_rows(db, shared.id)) >= MEMBERS_MAX:
        raise ListError(f"This list already has {MEMBERS_MAX} people, which is as many as a shared list can hold.")
    if _joined_count(db, user.id) >= JOINED_MAX:
        raise ListError(f"You're already in {JOINED_MAX} shared lists. Leave one to join another.")
    db.add(models.SharedListMember(list_id=shared.id, user_id=user.id))
    db.flush()
    return True


def join(db: Session, shared: models.SharedList, user) -> bool:
    """Join through the list's link. Tells the people already in it. False when already a member."""
    try:
        added = _add_member(db, shared, user)
    except IntegrityError:
        db.rollback()  # A double click raced the unique constraint; they're in.
        return False
    if added:
        for member, _ in _member_rows(db, shared.id):
            if member.user_id != user.id:
                _notify(db, member.user_id, "shared_list_joined",
                        f'{user.username} joined your shared list "{shared.name}".', f"/lists/{shared.id}")
        shared.updated_at = _now()
    db.commit()
    return added


def invite_friend(db: Session, shared: models.SharedList, user, friend_id: int) -> models.User:
    """Add one of the member's friends straight to the list."""
    friend = db.get(models.User, friend_id)
    if friend is None or not friend.is_active or friend.id == user.id or not are_friends(db, user.id, friend.id):
        raise ListError("You can add people you're friends with. Anyone else can join with the list's link.", 404)
    try:
        added = _add_member(db, shared, friend)
    except IntegrityError:
        db.rollback()
        return friend
    if added:
        _notify(db, friend.id, "shared_list_added",
                f'{user.username} added you to the shared list "{shared.name}".', f"/lists/{shared.id}")
        shared.updated_at = _now()
    db.commit()
    return friend


def remove_member(db: Session, shared: models.SharedList, user, member_id: int) -> None:
    """The owner removes someone, or a member leaves. The owner can't leave their own list."""
    if member_id == shared.owner_id:
        raise ListError("The person who made a list can't leave it. Delete the list instead.")
    if member_id != user.id and shared.owner_id != user.id:
        raise ListError("Only the person who made this list can remove people.", 403)
    member = _membership(db, shared.id, member_id)
    if member is None:
        raise ListError("They aren't in this list.", 404)
    item_ids = [item_id for item_id, in db.query(models.SharedListItem.id).filter_by(list_id=shared.id)]
    if item_ids:
        # Their "I'm in"s go with them; the titles they added stay, still credited to them.
        db.query(models.SharedListVote).filter(models.SharedListVote.user_id == member_id,
                                               models.SharedListVote.item_id.in_(item_ids)).delete(synchronize_session=False)
    db.delete(member)
    if member_id != user.id:
        # Someone the owner removed still has the join link; a new one keeps them out.
        shared.token = secrets.token_urlsafe(16)
    db.commit()


def invitable_friends(db: Session, shared: models.SharedList, user) -> list[dict]:
    inside = {user_id for user_id, in db.query(models.SharedListMember.user_id).filter_by(list_id=shared.id)}
    friends = [friend for friend in get_friends(db, user.id) if friend.id not in inside]
    friends.sort(key=lambda friend: friend.username.casefold())
    return [{"id": friend.id, "username": friend.username} for friend in friends]


def _clean_year(year) -> Optional[int]:
    return year if isinstance(year, int) and not isinstance(year, bool) and 1800 <= year <= 2100 else None


def _indexed(db: Session, kind: str, slug: str) -> Optional[dict]:
    """The title search entry behind a slug, so art and names come from the site, not the request."""
    for entry in title_search.index(db):
        if entry["kind"] == kind and entry["slug"] == slug:
            return entry
    return None


def add_item(db: Session, shared: models.SharedList, user, kind: str, title: str, year=None,
             slug: Optional[str] = None, note: Optional[str] = None) -> tuple[str, models.SharedListItem]:
    """Add a title. Returns ("created" | "existing", item). A title already on the list is left as it is."""
    if kind not in title_pages.KINDS:
        raise ListError("Pick what kind of title this is.")
    year = _clean_year(year)
    image = None
    entry = _indexed(db, kind, slug) if slug and re.fullmatch(r"[a-z0-9-]{1,130}", slug) else None
    if entry is not None:
        title, year, image = entry["title"], entry["year"], title_pages._safe_image(entry["image"])
        slug = entry["slug"]
    else:
        slug = None
    title = " ".join((title or "").split())[:200]
    if not title:
        raise ListError("Type a title first.")
    key = normalized_key(title, year)
    existing = db.query(models.SharedListItem).filter_by(list_id=shared.id, kind=kind, normalized=key).first()
    if existing is not None:
        return "existing", existing
    if db.query(models.SharedListItem.id).filter_by(list_id=shared.id).count() >= ITEMS_MAX:
        raise ListError(f"A shared list holds up to {ITEMS_MAX} titles. Clear out a few you've finished first.")
    item = models.SharedListItem(list_id=shared.id, added_by_id=user.id, kind=kind, title=title, normalized=key,
                                 year=year, slug=slug, image=image, note=(note or None))
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return "existing", db.query(models.SharedListItem).filter_by(list_id=shared.id, kind=kind, normalized=key).one()
    # Whoever adds a title wants it, so it starts with their "I'm in".
    db.add(models.SharedListVote(item_id=item.id, user_id=user.id))
    shared.updated_at = _now()
    _tell_members_about(db, shared, user, item)
    db.commit()
    db.refresh(item)
    return "created", item


def _tell_members_about(db: Session, shared: models.SharedList, user, item) -> None:
    """One note per member until they open the list again, however many titles go in meanwhile."""
    link = f"/lists/{shared.id}"
    for member, _ in _member_rows(db, shared.id):
        if member.user_id == user.id:
            continue
        waiting = db.query(models.Notification.id).filter(
            models.Notification.user_id == member.user_id, models.Notification.type == "shared_list_item",
            models.Notification.link == link, models.Notification.read_at.is_(None)).first()
        if waiting is None:
            _notify(db, member.user_id, "shared_list_item",
                    f'{user.username} added {item.title} to "{shared.name}".', link)


def get_item(db: Session, shared: models.SharedList, item_id: int) -> models.SharedListItem:
    item = db.query(models.SharedListItem).filter_by(id=item_id, list_id=shared.id).first()
    if item is None:
        raise ListError("That title isn't on this list anymore.", 404)
    return item


def update_item(db: Session, shared: models.SharedList, user, item, done: Optional[bool], note: Optional[str]) -> None:
    if done is not None:
        if done and item.done_at is None:
            item.done_at, item.done_by_id = _now(), user.id
        elif not done:
            item.done_at, item.done_by_id = None, None
    if note is not None:
        if item.added_by_id != user.id and shared.owner_id != user.id:
            raise ListError("Only whoever added a title can change its note.", 403)
        item.note = note or None
    db.commit()


def remove_item(db: Session, shared: models.SharedList, user, item) -> None:
    if item.added_by_id != user.id and shared.owner_id != user.id:
        raise ListError("Only whoever added a title, or the list's owner, can take it off.", 403)
    db.delete(item)
    db.commit()


def vote(db: Session, item, user, wanted: bool) -> None:
    current = db.query(models.SharedListVote).filter_by(item_id=item.id, user_id=user.id).first()
    if wanted and current is None:
        db.add(models.SharedListVote(item_id=item.id, user_id=user.id))
    elif not wanted and current is not None:
        db.delete(current)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # The same "I'm in" twice at once.


def add_to_library(db: Session, user, item) -> tuple[str, object]:
    """Copy a list title into the member's own library (title, year and art only). Does not commit."""
    from . import pick
    from .routers.titles import add_group_to_library
    group = title_pages.find(db, item.kind, item.slug) if item.slug else None
    if group is not None:
        return add_group_to_library(db, user, group)
    return pick.add_to_library(db, user, {"kind": item.kind, "title": item.title, "year": item.year, "creator": None},
                               image=item.image)


def _library_keys(db: Session, user, kinds: set[str]) -> set[tuple[str, str]]:
    """(kind, normalized title) for the titles the member already tracks, for the kinds on the list."""
    keys = set()
    for kind in kinds:
        model = title_pages.KINDS[kind][0]
        for title, in db.query(model.title).filter(model.user_id == user.id):
            keys.add((kind, title_pages.normalize(title or "")))
    return keys


def _initials(name: str) -> str:
    letters = [part[0] for part in re.split(r"[^A-Za-z0-9]+", name or "") if part]
    return ("".join(letters[:2]) or (name or "?")[:1]).upper()


def _person(user: Optional[models.User], viewer) -> Optional[dict]:
    if user is None or not user.is_active:
        return None
    return {"id": user.id, "username": user.username, "initials": _initials(user.username), "you": user.id == viewer.id}


def detail(db: Session, shared: models.SharedList, member: models.SharedListMember, viewer) -> dict:
    """Everything the list page shows. Opening it marks every title as seen for this member."""
    rows = _member_rows(db, shared.id)
    people = {user.id: user for _, user in rows}
    items = db.query(models.SharedListItem).filter_by(list_id=shared.id).all()
    extra_ids = {i.added_by_id for i in items} | {i.done_by_id for i in items}
    extra_ids -= set(people) | {None}
    if extra_ids:
        # People who added or finished a title and have since left the list keep the credit.
        people.update({user.id: user for user in db.query(models.User).filter(models.User.id.in_(extra_ids))})
    votes: dict[int, list[int]] = {}
    if items:
        for item_id, user_id, in db.query(models.SharedListVote.item_id, models.SharedListVote.user_id).filter(
                models.SharedListVote.item_id.in_([i.id for i in items])).order_by(models.SharedListVote.created_at):
            votes.setdefault(item_id, []).append(user_id)
    inside = {m.user_id for m, _ in rows}
    owned = _library_keys(db, viewer, {i.kind for i in items})
    seen = member.seen_at
    is_owner = shared.owner_id == viewer.id

    def serialize(item):
        voters = [people[uid] for uid in votes.get(item.id, []) if uid in inside and uid in people]
        return {
            "id": item.id, "kind": item.kind, "label": KIND_LABELS[item.kind], "title": item.title, "year": item.year,
            "url": f"/titles/{item.kind}/{item.slug}" if item.slug else None, "image": item.image, "note": item.note,
            "added_by": _person(people.get(item.added_by_id), viewer), "added_at": item.created_at.isoformat() + "Z",
            "new": bool(seen and item.created_at > seen and item.added_by_id != viewer.id),
            "votes": [_person(u, viewer) for u in voters], "voted": viewer.id in {u.id for u in voters},
            "done_at": item.done_at.isoformat() + "Z" if item.done_at else None,
            "done_by": _person(people.get(item.done_by_id), viewer),
            "in_library": (item.kind, title_pages.normalize(item.title)) in owned,
            "can_remove": is_owner or item.added_by_id == viewer.id,
            "can_edit_note": is_owner or item.added_by_id == viewer.id,
        }

    open_items = sorted((i for i in items if i.done_at is None),
                        key=lambda i: (-len([u for u in votes.get(i.id, []) if u in inside]), i.created_at, i.id))
    done_items = sorted((i for i in items if i.done_at is not None), key=lambda i: (i.done_at, i.id), reverse=True)
    result = {
        "id": shared.id, "name": shared.name, "description": shared.description or "", "is_owner": is_owner,
        "owner": _person(people.get(shared.owner_id), viewer),
        "members": [dict(_person(user, viewer), owner=user.id == shared.owner_id) for _, user in rows],
        "members_max": MEMBERS_MAX, "items_max": ITEMS_MAX,
        "join_url": join_url(shared),
        "open": [serialize(i) for i in open_items], "done": [serialize(i) for i in done_items],
    }
    member.seen_at = _now()
    db.query(models.Notification).filter(
        models.Notification.user_id == viewer.id, models.Notification.link == f"/lists/{shared.id}",
        models.Notification.type.in_(("shared_list_item", "shared_list_joined", "shared_list_added")),
        models.Notification.read_at.is_(None)).update({"read_at": _now()}, synchronize_session=False)
    db.commit()
    return result


def overview(db: Session, user) -> list[dict]:
    """The member's lists, most recently active first, with a few covers and what's new since their last visit."""
    memberships = (db.query(models.SharedListMember, models.SharedList)
                   .join(models.SharedList, models.SharedList.id == models.SharedListMember.list_id)
                   .filter(models.SharedListMember.user_id == user.id)
                   .order_by(models.SharedList.updated_at.desc(), models.SharedList.id.desc()).all())
    results = []
    for member, shared in memberships:
        rows = _member_rows(db, shared.id)
        items = (db.query(models.SharedListItem).filter_by(list_id=shared.id)
                 .order_by(models.SharedListItem.created_at.desc()).all())
        open_items = [i for i in items if i.done_at is None]
        new = sum(1 for i in items if member.seen_at and i.created_at > member.seen_at and i.added_by_id != user.id)
        results.append({
            "id": shared.id, "name": shared.name, "description": shared.description or "",
            "is_owner": shared.owner_id == user.id,
            "members": [_person(u, user) for _, u in rows],
            "open_count": len(open_items), "done_count": len(items) - len(open_items), "new_count": new,
            "covers": [{"title": i.title, "image": i.image} for i in open_items[:4]],
        })
    return results


def preview(db: Session, shared: models.SharedList) -> dict:
    """What a join link shows before someone joins: names and titles, never anyone's library."""
    rows = _member_rows(db, shared.id)
    owner = next((user for member, user in rows if user.id == shared.owner_id), None)
    items = (db.query(models.SharedListItem).filter_by(list_id=shared.id)
             .filter(models.SharedListItem.done_at.is_(None))
             .order_by(models.SharedListItem.created_at.desc()).all())
    return {
        "name": shared.name, "description": shared.description or "",
        "owner": owner.username if owner else None,
        "members": [user.username for _, user in rows],
        "count": len(items),
        "items": [{"title": i.title, "year": i.year, "label": KIND_LABELS[i.kind], "image": i.image}
                  for i in items[:PREVIEW_ITEMS]],
        "full": len(rows) >= MEMBERS_MAX,
    }
