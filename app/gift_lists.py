"""Holiday gift lists: a member's wishes, shared with family through one link (Nov 2026).

* A member builds the list on /holidays/gifts from three places: their own library
  (titles they haven't started and favourites they'd like to own), the gift guide,
  or a line of text. Items are copies, so the library itself is never changed.
* The list's link (/gifts/<token>) opens without an account. Anyone with it can
  mark a gift as one they're getting, and undo that from the same browser with the
  key they were handed. The owner is never shown which gifts were marked.
* Buy links are Amazon searches built at render time (affiliate.py), so nothing
  here stores a shop URL.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import affiliate, models, title_pages
from .gift_guides import GIFTS

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{16,32}")
CLAIM_KEY_RE = re.compile(r"[A-Za-z0-9_-]{20,64}")
ITEMS_MAX = 40
SUGGESTIONS_MAX = 12
FAVOURITE_MIN_RATING = 8.0
OTHER = "other"
KIND_LABELS = {"movie": "Movie", "tv": "TV show", "anime": "Anime", "game": "Game", "album": "Album", "book": "Book",
               "manga": "Manga", "podcast": "Podcast", "audiobook": "Audiobook", OTHER: "Gift idea"}
# Podcasts are free to listen to, so a podcast is never suggested as a gift.
GIFTABLE_KINDS = [kind for kind in title_pages.KINDS if kind != "podcast"]


class GiftListError(Exception):
    """A request the list can't take, with a message the member can read."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _clean(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _new_token() -> str:
    return secrets.token_urlsafe(16)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- the owner's list

def get(db: Session, user_id: int) -> Optional[models.GiftList]:
    return db.query(models.GiftList).filter(models.GiftList.owner_id == user_id).first()


def get_or_create(db: Session, user) -> tuple[models.GiftList, bool]:
    """The member's list, made on first use. Returns (list, created). Does not commit."""
    existing = get(db, user.id)
    if existing is not None:
        return existing, False
    gift_list = models.GiftList(owner_id=user.id, token=_new_token())
    db.add(gift_list)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        # A second tab made it at the same moment.
        existing = get(db, user.id)
        if existing is None:
            raise
        return existing, False
    return gift_list, True


def share_url(gift_list: models.GiftList) -> str:
    return f"{SITE_URL}/gifts/{gift_list.token}"


def buy_links(item) -> list[dict]:
    """Amazon search links for one wish, or [] when affiliate links are off (or it's a podcast)."""
    if item.search:
        return affiliate.search_links(item.search, item.store or "aps")
    if item.kind == OTHER:
        return affiliate.search_links(item.title)
    if item.kind in GIFTABLE_KINDS:
        return affiliate.links_for(item.kind, item.title, item.creator or "")
    return []


def title_url(item) -> Optional[str]:
    if item.kind in title_pages.KINDS:
        return title_pages.title_path(item.kind, item.title, item.year)
    return None


def item_dict(item, *, claims: bool = False, buy: bool = True) -> dict:
    data = {
        "id": item.id, "kind": item.kind, "label": KIND_LABELS.get(item.kind, "Gift idea"),
        "title": item.title, "year": item.year, "creator": item.creator,
        "image": title_pages._safe_image(item.image), "note": item.note,
    }
    if buy:
        data["buy"] = buy_links(item)
    if claims:
        data["claimed"] = item.claimed_at is not None
    return data


def owner_view(gift_list: Optional[models.GiftList]) -> dict:
    """What the owner sees: the items and the link settings, never the claims."""
    if gift_list is None:
        return {"exists": False, "items": [], "count": 0, "max": ITEMS_MAX, "shared": True, "message": "", "url": None}
    items = [item_dict(item, buy=False) for item in gift_list.items]
    return {
        "exists": True, "items": items, "count": len(items), "max": ITEMS_MAX, "shared": bool(gift_list.shared),
        "message": gift_list.message or "", "url": share_url(gift_list), "path": f"/gifts/{gift_list.token}",
    }


def _keys(gift_list: models.GiftList) -> set[tuple[str, str]]:
    return {(item.kind, item.normalized) for item in gift_list.items}


def _add(db: Session, gift_list: models.GiftList, fields: dict) -> tuple[str, models.GiftListItem]:
    """Add one wish. Returns ("created" | "existing", item). Does not commit."""
    title = _clean(fields["title"], 200)
    if not title:
        raise GiftListError("Give the gift a name first.")
    normalized = title_pages.normalize(title)[:200]
    for item in gift_list.items:
        if item.kind == fields["kind"] and item.normalized == normalized:
            return "existing", item
    if len(gift_list.items) >= ITEMS_MAX:
        raise GiftListError(f"Your list has {ITEMS_MAX} gifts on it, which is the most it can hold. Take one off to add another.")
    item = models.GiftListItem(
        kind=fields["kind"], title=title, normalized=normalized, year=fields.get("year"),
        creator=_clean(fields.get("creator"), 120) or None, image=title_pages._safe_image(fields.get("image")),
        search=_clean(fields.get("search"), 150) or None, store=fields.get("store") or None,
    )
    gift_list.items.append(item)
    gift_list.updated_at = datetime.utcnow()
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        gift_list.items.remove(item)
        raise GiftListError("That one is already on your list.", 409)
    return "created", item


def _library_row(db: Session, user_id: int, kind: str, row_id: int):
    model = title_pages.KINDS[kind][0]
    return db.query(model).filter(model.user_id == user_id, model.id == row_id).first()


def _row_fields(kind: str, row) -> dict:
    creator_field = title_pages.KINDS[kind][4]
    return {
        "kind": kind, "title": row.title or "", "year": title_pages.item_year(kind, row),
        "creator": getattr(row, creator_field, None) if creator_field else None,
        "image": getattr(row, title_pages.IMAGE_FIELD[kind], None),
    }


def add_from_library(db: Session, user, kind: str, row_id: int) -> tuple[str, dict]:
    if kind not in GIFTABLE_KINDS:
        raise GiftListError("That kind of title can't go on a gift list.")
    row = _library_row(db, user.id, kind, row_id)
    if row is None:
        raise GiftListError("That title isn't in your library.", 404)
    gift_list, _ = get_or_create(db, user)
    state, item = _add(db, gift_list, _row_fields(kind, row))
    return state, item_dict(item, buy=False)


def add_from_guide(db: Session, user, gift_id: str) -> tuple[str, dict]:
    gift = GIFTS.get(gift_id)
    if gift is None:
        raise GiftListError("That gift isn't in the guide.", 404)
    gift_list, _ = get_or_create(db, user)
    # Saved under the gift's own name ("The Wire: The Complete Series"), which says which edition to buy.
    fields = {"kind": OTHER, "title": gift["name"], "search": gift["search"], "store": gift["store"]}
    state, item = _add(db, gift_list, fields)
    return state, item_dict(item, buy=False)


def add_text(db: Session, user, text: str) -> tuple[str, dict]:
    text = _clean(text, 120)
    if len(text) < 2:
        raise GiftListError("Type what you'd like, for example \"a book light\" or \"Dune on 4K\".")
    gift_list, _ = get_or_create(db, user)
    state, item = _add(db, gift_list, {"kind": OTHER, "title": text})
    return state, item_dict(item, buy=False)


def _own_item(db: Session, user, item_id: int) -> models.GiftListItem:
    item = (db.query(models.GiftListItem).join(models.GiftList)
            .filter(models.GiftListItem.id == item_id, models.GiftList.owner_id == user.id).first())
    if item is None:
        raise GiftListError("That gift isn't on your list.", 404)
    return item


def remove(db: Session, user, item_id: int) -> None:
    item = _own_item(db, user, item_id)
    item.gift_list.updated_at = datetime.utcnow()
    db.delete(item)


def set_note(db: Session, user, item_id: int, note: str) -> dict:
    item = _own_item(db, user, item_id)
    item.note = _clean(note, 120) or None
    item.gift_list.updated_at = datetime.utcnow()
    return item_dict(item, buy=False)


def update_settings(db: Session, user, *, message=None, shared=None) -> models.GiftList:
    gift_list, _ = get_or_create(db, user)
    if message is not None:
        gift_list.message = _clean(message, 200) or None
    if shared is not None:
        gift_list.shared = bool(shared)
    gift_list.updated_at = datetime.utcnow()
    return gift_list


def reset_link(db: Session, user) -> models.GiftList:
    """Retire the old link and make a new one. Claims stay, since the same people may still be buying."""
    gift_list, _ = get_or_create(db, user)
    gift_list.token = _new_token()
    gift_list.updated_at = datetime.utcnow()
    return gift_list


# ---------------------------------------------------------------- the shared link

def by_token(db: Session, token: str) -> Optional[models.GiftList]:
    """The list behind a share link, if the link is current, switched on and its owner is active."""
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        return None
    gift_list = db.query(models.GiftList).filter(models.GiftList.token == token).first()
    if gift_list is None or not gift_list.shared:
        return None
    owner = db.get(models.User, gift_list.owner_id)
    if owner is None or not owner.is_active:
        return None
    return gift_list


def _shared_item(gift_list: models.GiftList, item_id: int) -> models.GiftListItem:
    item = next((item for item in gift_list.items if item.id == item_id), None)
    if item is None:
        raise GiftListError("That gift isn't on this list anymore.", 404)
    return item


def claim(db: Session, gift_list: models.GiftList, item_id: int) -> str:
    """Mark a gift as taken. Returns the key that undoes it; only its hash is stored."""
    item = _shared_item(gift_list, item_id)
    if item.claimed_at is not None:
        raise GiftListError("Someone else is already getting this one.", 409)
    key = secrets.token_urlsafe(24)
    item.claimed_at = datetime.utcnow()
    item.claim_hash = _hash(key)
    return key


def unclaim(db: Session, gift_list: models.GiftList, item_id: int, key: str) -> None:
    """Undo a claim with its key.

    A wrong key gets the same answer whether or not the gift is marked, so this can't be
    used to check which gifts are taken without marking them.
    """
    item = _shared_item(gift_list, item_id)
    if item.claimed_at is None or not isinstance(key, str) or not CLAIM_KEY_RE.fullmatch(key) \
            or not item.claim_hash or not hmac.compare_digest(item.claim_hash, _hash(key)):
        raise GiftListError("Only the person who marked this gift can undo it, from the same browser.", 403)
    item.claimed_at = None
    item.claim_hash = None


# ---------------------------------------------------------------- ideas from the library

def suggestions(db: Session, user_id: int) -> dict:
    """Titles from the member's own library that would make good gifts.

    "waiting": titles they haven't started, newest first. "favourites": titles they
    finished and rated 8 or more, to own a copy of. Titles already on the list are left out.
    """
    gift_list = get(db, user_id)
    taken = _keys(gift_list) if gift_list else set()
    waiting, favourites = [], []
    for kind in GIFTABLE_KINDS:
        model = title_pages.KINDS[kind][0]
        complete = getattr(model, title_pages.COMPLETE_FIELD[kind])
        base = db.query(model).filter(model.user_id == user_id, model.title.isnot(None))
        open_rows = (base.filter((complete.is_(False)) | (complete.is_(None)))
                     .order_by(model.added_at.desc(), model.id.desc()).limit(SUGGESTIONS_MAX).all())
        loved_rows = (base.filter(complete.is_(True), model.rating >= FAVOURITE_MIN_RATING)
                      .order_by(model.rating.desc(), model.id.desc()).limit(SUGGESTIONS_MAX).all())
        for rows, bucket in ((open_rows, waiting), (loved_rows, favourites)):
            for row in rows:
                title = (row.title or "").strip()
                if not title or (kind, title_pages.normalize(title)[:200]) in taken:
                    continue
                fields = _row_fields(kind, row)
                bucket.append({
                    "kind": kind, "id": row.id, "label": KIND_LABELS[kind], "title": title, "year": fields["year"],
                    "creator": fields["creator"], "image": title_pages._safe_image(fields["image"]),
                    "rating": row.rating, "added": row.added_at,
                })
    waiting.sort(key=lambda entry: (entry["added"] or datetime.min, entry["id"]), reverse=True)
    favourites.sort(key=lambda entry: (entry["rating"] or 0, entry["added"] or datetime.min), reverse=True)
    for bucket in (waiting, favourites):
        for entry in bucket:
            entry.pop("added", None)
    return {"waiting": waiting[:SUGGESTIONS_MAX], "favourites": favourites[:SUGGESTIONS_MAX]}


def library_counts(db: Session, user_id: int) -> dict[str, int]:
    """How many titles of each kind the member tracks, for ordering the guide's sections."""
    from sqlalchemy import func
    counts = {}
    for kind, (model, *_rest) in title_pages.KINDS.items():
        counts[kind] = db.query(func.count(model.id)).filter(model.user_id == user_id).scalar() or 0
    return counts


def owned_gifts(db: Session, user_id: int) -> dict[str, bool]:
    """{gift id: finished?} for guide gifts that are titles already in the member's library."""
    from sqlalchemy import func
    found: dict[str, bool] = {}
    by_kind: dict[str, list[dict]] = {}
    for gift_id, gift in GIFTS.items():
        if gift["kind"] in title_pages.KINDS and gift.get("title"):
            by_kind.setdefault(gift["kind"], []).append(gift)
    for kind, gifts in by_kind.items():
        model = title_pages.KINDS[kind][0]
        complete = getattr(model, title_pages.COMPLETE_FIELD[kind])
        year_column = model.release_date if kind == "game" else model.year
        wanted = sorted({title_pages.normalize(gift["title"]) for gift in gifts})
        rows = (db.query(model.title, year_column, complete)
                .filter(model.user_id == user_id, func.lower(func.trim(model.title)).in_(wanted)).all())
        for title, year, done in rows:
            if kind == "game" and year is not None:
                year = year.year
            for gift in gifts:
                if title_pages.normalize(title) != title_pages.normalize(gift["title"]):
                    continue
                if year is not None and gift.get("year") and abs(int(year) - gift["year"]) > 1:
                    continue
                found[gift["id"]] = found.get(gift["id"], False) or bool(done)
    return found
